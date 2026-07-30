"""In-app editing chat — implemented as an MCP client.

The integration model is MCP-first: the chat does not call engine functions
directly, it connects to the Dabwayo **MCP server** as a client (the same
way GitHub Copilot, opencode, Cline or Claude Code would), discovers the tools
via ``list_tools``, and executes them via ``call_tool``. The LLM is only the
"brain" that decides which MCP tools to call; the single source of truth for
the tools is the MCP server, so anything exposed there is automatically
available here.

The LLM brain is pluggable (the official Anthropic SDK, or any OpenAI-
compatible endpoint) — both are optional ``[ai]`` deps imported lazily. The
MCP client (``mcp``) is a base dependency.

Architecture::

    user message ─▶ LLM (picks tools) ─▶ MCP client.call_tool ─▶ MCP server
                                                                    │
                              shared project store ◀────────────────┘
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from typing import Dict, List, Optional

from .. import capabilities as engine_capabilities

ANTHROPIC_MODEL = "claude-opus-4-8"

# Per-project conversation state: pid -> {"provider": str, "messages": [...]}
_STATE: Dict[str, dict] = {}


# --------------------------------------------------------------------------
# MCP client host — one persistent stdio connection to the Dabwayo server,
# driven from a background asyncio loop so the sync HTTP server can use it.
# --------------------------------------------------------------------------
class MCPHost:
    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._session = None
        self._ready = threading.Event()
        self._error: Optional[str] = None
        self._shutdown: Optional[asyncio.Event] = None
        self.tools: list = []                 # raw MCP Tool objects
        self.pid_tools: set = set()           # tool names that take project_id
        self._started = False

    def ensure(self) -> bool:
        if self._started:
            return self._ready.is_set() and self._error is None
        self._started = True
        threading.Thread(target=self._run, daemon=True).start()
        self._ready.wait(timeout=20)
        return self._error is None and self._session is not None

    def _run(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._serve())
        except Exception as e:  # noqa: BLE001
            self._error = str(e)
            self._ready.set()

    async def _serve(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=sys.executable, args=["-m", "dabwayo.mcp_server"],
            env=dict(os.environ),    # inherits DABWAYO_STORE/_OUTPUT -> shared store
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                self.tools = listed.tools
                self.pid_tools = {
                    t.name for t in listed.tools
                    if "project_id" in (t.inputSchema or {}).get("properties", {})
                }
                self._session = session
                self._shutdown = asyncio.Event()
                self._ready.set()
                await self._shutdown.wait()

    def call(self, name: str, arguments: dict, pid: Optional[str] = None) -> str:
        if self._session is None:
            raise RuntimeError(self._error or "MCP server not connected")
        if name in self.pid_tools and pid:
            arguments = {**arguments, "project_id": pid}
        fut = asyncio.run_coroutine_threadsafe(
            self._session.call_tool(name, arguments=arguments), self._loop)
        res = fut.result(timeout=180)
        return "".join(getattr(c, "text", "") for c in res.content) or "{}"

    def shutdown(self):
        if self._loop and self._shutdown and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._shutdown.set)

    # Editing tool set for the chat: project-bound MCP tools (project_id
    # injected automatically and hidden from the model), plus discovery.
    _INCLUDE_NO_PID = {"get_capabilities"}
    _EXCLUDE = {"update_project", "render_from_spec", "get_help", "estimate"}

    def chat_tools(self) -> list:
        out = []
        for t in self.tools:
            if t.name in self._EXCLUDE:
                continue
            if t.name in self.pid_tools or t.name in self._INCLUDE_NO_PID:
                schema = json.loads(json.dumps(t.inputSchema or {"type": "object", "properties": {}}))
                props = schema.get("properties", {})
                props.pop("project_id", None)
                if "required" in schema:
                    schema["required"] = [r for r in schema["required"] if r != "project_id"]
                out.append({"name": t.name, "description": (t.description or "").strip(),
                            "input_schema": schema})
        return out


_HOST = MCPHost()

import atexit
atexit.register(_HOST.shutdown)


# --------------------------------------------------------------------------
# Provider selection (the LLM "brain")
# --------------------------------------------------------------------------
def _provider() -> str:
    p = os.environ.get("DABWAYO_LLM_PROVIDER", "").lower()
    if p in ("anthropic", "openai"):
        return p
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return ""


def _model(provider: str) -> str:
    if provider == "anthropic":
        return os.environ.get("DABWAYO_LLM_MODEL", ANTHROPIC_MODEL)
    return os.environ.get("DABWAYO_LLM_MODEL", "gpt-4o")


def status() -> dict:
    provider = _provider()
    mcp_ok = _HOST.ensure()
    mcp_tools = len(_HOST.chat_tools()) if mcp_ok else 0
    base = {"mcp_connected": mcp_ok, "mcp_tools": mcp_tools,
            "mcp_error": _HOST._error}
    if not provider:
        return {**base, "available": False, "provider": None,
                "hint": "Set ANTHROPIC_API_KEY (Claude) or OPENAI_API_KEY + "
                        "OPENAI_BASE_URL/DABWAYO_LLM_MODEL (OpenAI-compatible)."}
    try:
        __import__("anthropic" if provider == "anthropic" else "openai")
    except ImportError:
        pkg = "anthropic" if provider == "anthropic" else "openai"
        return {**base, "available": False, "provider": provider, "hint": f"pip install {pkg}"}
    return {**base, "available": mcp_ok, "provider": provider, "model": _model(provider),
            "hint": None if mcp_ok else "MCP server failed to start"}


def available() -> bool:
    return status().get("available", False)


def _system(pid: str) -> str:
    caps = engine_capabilities()
    spec = json.loads(_HOST.call("get_project", {}, pid))
    return (
        "You are Dabwayo's in-app editing assistant. You edit the user's video "
        "project by calling MCP tools — each runs the real engine and the result "
        "appears in the preview immediately. The project_id is supplied for you; "
        "never ask for it.\n"
        f"Project: {spec.get('width')}x{spec.get('height')} @ {spec.get('fps')}fps, "
        f"duration {spec.get('duration', 'auto')}s. Coordinates are pixels, origin "
        "top-left.\n"
        f"Available effects: {', '.join(caps['effects'])}.\n"
        "Fonts (names/aliases): sans, sans-bold, display, serif, mono, kr, kr-bold "
        "(use kr-bold for Korean).\n"
        "Guidelines: make exactly the change requested, nothing more. Use list_clips "
        "first to find a clip's track+index, then update_clip for tweaks. Keep replies "
        "to one or two short sentences. Reply in the user's language."
    )


def _history(pid: str, provider: str) -> list:
    st = _STATE.get(pid)
    if st is None or st["provider"] != provider:
        st = _STATE[pid] = {"provider": provider, "messages": []}
    return st["messages"]


# --------------------------------------------------------------------------
# LLM loops — tools come from MCP, execution goes through the MCP client
# --------------------------------------------------------------------------
def _run_anthropic(pid: str, message: str, model: str, max_turns: int) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    tools = [{"name": t["name"], "description": t["description"],
              "input_schema": t["input_schema"]} for t in _HOST.chat_tools()]
    msgs = _history(pid, "anthropic")
    msgs.append({"role": "user", "content": message})
    actions, resp = [], None
    for _ in range(max_turns):
        resp = client.messages.create(
            model=model, max_tokens=8192, thinking={"type": "adaptive"},
            system=_system(pid), tools=tools, messages=msgs)
        msgs.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})
        if resp.stop_reason != "tool_use":
            break
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                actions.append({"name": b.name, "input": b.input})
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": _HOST.call(b.name, dict(b.input), pid)})
        msgs.append({"role": "user", "content": results})
    reply = " ".join(b.text for b in (resp.content if resp else []) if b.type == "text").strip()
    return {"reply": reply, "actions": actions}


def _run_openai(pid: str, message: str, model: str, max_turns: int) -> dict:
    from openai import OpenAI
    client = OpenAI(base_url=os.environ.get("OPENAI_BASE_URL") or None)
    tools = [{"type": "function", "function": {"name": t["name"],
              "description": t["description"], "parameters": t["input_schema"]}}
             for t in _HOST.chat_tools()]
    msgs = _history(pid, "openai")
    msgs.append({"role": "user", "content": message})
    actions, reply = [], ""
    for _ in range(max_turns):
        resp = client.chat.completions.create(
            model=model, tools=tools, tool_choice="auto",
            messages=[{"role": "system", "content": _system(pid)}] + msgs)
        msg = resp.choices[0].message
        msgs.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            reply = msg.content or ""
            break
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            actions.append({"name": tc.function.name, "input": args})
            msgs.append({"role": "tool", "tool_call_id": tc.id,
                         "content": _HOST.call(tc.function.name, args, pid)})
    return {"reply": reply.strip(), "actions": actions}


def run_chat(pid: str, message: str, max_turns: int = 8) -> dict:
    if not _HOST.ensure():
        return {"reply": f"MCP 서버 연결 실패: {_HOST._error}", "actions": [], "available": False}
    provider = _provider()
    model = _model(provider)
    out = (_run_openai if provider == "openai" else _run_anthropic)(pid, message, model, max_turns)
    out["reply"] = out["reply"] or "(완료)"
    out["provider"], out["model"] = provider, model
    return out


def reset(pid: str) -> None:
    _STATE.pop(pid, None)
