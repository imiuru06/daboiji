"""Natural-language editing — provider-agnostic.

A chat turn ("말로 지시") is turned into engine edits: an LLM receives the
user's instruction plus a set of editing tools, calls them in an agentic
loop, and each tool runs the *same* function the MCP server exposes — so the
edits land on the shared project store and show up live in the UI and to any
MCP client on the same store.

The LLM backend is pluggable so this works beyond Claude Code:

* ``anthropic``        — the official Anthropic SDK (``claude-opus-4-8``).
* ``openai`` / compatible — the ``openai`` SDK against any OpenAI-compatible
  endpoint (OpenAI, Azure, OpenRouter, Groq, Ollama, LM Studio, opencode
  gateways, GitHub Models, …) via ``OPENAI_BASE_URL`` + ``VIDEOFORGE_LLM_MODEL``.

Selection: ``VIDEOFORGE_LLM_PROVIDER`` (``anthropic``|``openai``), else
auto-detected from whichever API key is present. Both SDKs are optional deps
(``[ai]``), imported lazily, so the Studio runs without them.

Note: the MCP server (``videoforge.mcp_server``) is itself provider-neutral —
Claude Code, GitHub Copilot, opencode, Cline, Continue, Cursor, etc. connect
to it directly (see ``examples/mcp-clients/``). This module is only the
*in-app* chat convenience.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

from .. import capabilities as engine_capabilities
from .. import mcp_server as M

ANTHROPIC_MODEL = "claude-opus-4-8"

# Per-project conversation state: pid -> {"provider": str, "messages": [...]}
_STATE: Dict[str, dict] = {}


# --- tools (Anthropic schema; converted to OpenAI form on demand) ----------
TOOLS = [
    {"name": "list_clips", "description": "List every clip with its track, index, "
     "type, timing and a content preview. Call this to see the current timeline "
     "before editing.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "add_background", "description": "Add a full-frame background — a "
     "gradient (from/to colors) or a solid color.", "input_schema": {"type": "object",
     "properties": {"gradient_from": {"type": "string"}, "gradient_to": {"type": "string"},
                    "kind": {"type": "string", "enum": ["linear", "radial"]},
                    "color": {"type": "string"}, "start": {"type": "number"},
                    "duration": {"type": "number"}}}},
    {"name": "add_text", "description": "Add a text clip. Korean text needs font "
     "'kr-bold' or 'kr'. position is [x,y]; omit to center.", "input_schema": {"type": "object",
     "properties": {"text": {"type": "string"}, "size": {"type": "integer"},
                    "color": {"type": "string"}, "font": {"type": "string"},
                    "start": {"type": "number"}, "duration": {"type": "number"},
                    "position": {"type": "array", "items": {"type": "number"}},
                    "transition_in": {"type": "string", "enum": ["fade", "zoom", "slide", "blur_in", ""]}},
     "required": ["text"]}},
    {"name": "add_callout", "description": "Add a speech-bubble callout that points "
     "at a feature. position [x,y] is the bubble center; tail_side points the tail.",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string"},
                    "position": {"type": "array", "items": {"type": "number"}},
                    "tail_side": {"type": "string", "enum": ["bottom", "top", "left", "right"]},
                    "start": {"type": "number"}, "duration": {"type": "number"}},
     "required": ["text", "position"]}},
    {"name": "add_effect", "description": "Attach an effect. Omit track/clip_index "
     "for a master effect on the whole frame.", "input_schema": {"type": "object",
     "properties": {"type": {"type": "string"}, "params": {"type": "object"},
                    "track": {"type": "string"}, "clip_index": {"type": "integer"}},
     "required": ["type"]}},
    {"name": "set_camera", "description": "Set a keyframeable camera (pan [x,y] px, "
     "zoom, rotation deg).", "input_schema": {"type": "object", "properties": {
                    "pan": {"type": "array", "items": {"type": "number"}},
                    "zoom": {"type": "number"}, "rotation": {"type": "number"}}}},
    {"name": "update_clip", "description": "Edit ONE clip in place by deep-merging a "
     "patch (only the keys you pass change). e.g. {'element':{'text':'new'}} or "
     "{'start':2.0}.", "input_schema": {"type": "object", "properties": {
                    "track": {"type": "string"}, "clip_index": {"type": "integer"},
                    "patch": {"type": "object"}}, "required": ["track", "clip_index", "patch"]}},
    {"name": "remove_clip", "description": "Delete one clip from a track.",
     "input_schema": {"type": "object", "properties": {"track": {"type": "string"},
                    "clip_index": {"type": "integer"}}, "required": ["track", "clip_index"]}},
]


def _openai_tools():
    return [{"type": "function", "function": {
        "name": t["name"], "description": t["description"],
        "parameters": t["input_schema"]}} for t in TOOLS]


def _dispatch(pid: str, name: str, inp: dict) -> str:
    """Execute one tool call against the shared store; return a JSON string."""
    try:
        if name == "list_clips":
            return json.dumps(M.list_clips(pid), ensure_ascii=False)
        if name == "add_background":
            grad = None
            if inp.get("gradient_from"):
                grad = {"stops": [[0, inp["gradient_from"]], [1, inp.get("gradient_to", "#0b0e16")]],
                        "kind": inp.get("kind", "radial")}
            return json.dumps(M.add_background(pid, color=inp.get("color", "#0b0e16"),
                              start=inp.get("start", 0.0), duration=inp.get("duration", 6.0),
                              gradient=grad))
        if name == "add_text":
            return json.dumps(M.add_text(pid, text=inp["text"], size=inp.get("size", 90),
                              font=inp.get("font", "kr-bold"), color=inp.get("color", "#ffffff"),
                              start=inp.get("start", 0.0), duration=inp.get("duration", 4.0),
                              position=inp.get("position"),
                              transition_in=({"type": inp["transition_in"], "duration": 0.5}
                                             if inp.get("transition_in") else None)))
        if name == "add_callout":
            return json.dumps(M.add_callout(pid, text=inp["text"], position=inp["position"],
                              tail_side=inp.get("tail_side", "bottom"),
                              start=inp.get("start", 0.0), duration=inp.get("duration", 4.0)))
        if name == "add_effect":
            eff = {"type": inp["type"], **(inp.get("params") or {})}
            return json.dumps(M.add_effect(pid, effect=eff, track=inp.get("track"),
                              clip_index=inp.get("clip_index")))
        if name == "set_camera":
            return json.dumps(M.set_camera(pid, pan=inp.get("pan"), zoom=inp.get("zoom"),
                              rotation=inp.get("rotation")))
        if name == "update_clip":
            return json.dumps(M.update_clip(pid, inp["track"], inp["clip_index"], inp["patch"]),
                              ensure_ascii=False)
        if name == "remove_clip":
            return json.dumps(M.remove_clip(pid, inp["track"], inp["clip_index"]), ensure_ascii=False)
        return json.dumps({"error": f"unknown tool {name}"})
    except Exception as e:  # noqa: BLE001 — report to the model, don't crash the loop
        return json.dumps({"error": str(e)})


def _system(pid: str) -> str:
    caps = engine_capabilities()
    spec = M.get_project(pid)
    return (
        "You are VideoForge's in-app editing assistant. You edit the user's video "
        "project by calling the provided tools — each one runs the real engine and "
        "the result appears in the preview immediately.\n"
        f"Project: {spec.get('width')}x{spec.get('height')} @ {spec.get('fps')}fps, "
        f"duration {spec.get('duration', 'auto')}s. Coordinates are pixels, origin "
        "top-left.\n"
        f"Available effects: {', '.join(caps['effects'])}.\n"
        "Fonts (names/aliases): sans, sans-bold, display, serif, mono, kr, kr-bold "
        "(use kr-bold for Korean).\n"
        "Guidelines: make exactly the change requested, nothing more. Prefer "
        "update_clip for tweaks to an existing clip (call list_clips first to find "
        "its track+index). Keep replies to one or two short sentences describing what "
        "you did. Reply in the user's language."
    )


# --------------------------------------------------------------------------
# Provider selection
# --------------------------------------------------------------------------
def _provider() -> str:
    p = os.environ.get("VIDEOFORGE_LLM_PROVIDER", "").lower()
    if p in ("anthropic", "openai"):
        return p
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return ""


def _model(provider: str) -> str:
    if provider == "anthropic":
        return os.environ.get("VIDEOFORGE_LLM_MODEL", ANTHROPIC_MODEL)
    return os.environ.get("VIDEOFORGE_LLM_MODEL", "gpt-4o")


def status() -> dict:
    provider = _provider()
    if not provider:
        return {"available": False, "provider": None,
                "hint": "Set ANTHROPIC_API_KEY (Claude) or OPENAI_API_KEY + "
                        "OPENAI_BASE_URL/VIDEOFORGE_LLM_MODEL (OpenAI-compatible)."}
    try:
        __import__("anthropic" if provider == "anthropic" else "openai")
    except ImportError:
        pkg = "anthropic" if provider == "anthropic" else "openai"
        return {"available": False, "provider": provider,
                "hint": f"pip install {pkg}"}
    return {"available": True, "provider": provider, "model": _model(provider)}


def available() -> bool:
    return status().get("available", False)


def _history(pid: str, provider: str) -> list:
    st = _STATE.get(pid)
    if st is None or st["provider"] != provider:
        st = _STATE[pid] = {"provider": provider, "messages": []}
    return st["messages"]


# --------------------------------------------------------------------------
# Agentic loops
# --------------------------------------------------------------------------
def _run_anthropic(pid: str, message: str, model: str, max_turns: int) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    msgs = _history(pid, "anthropic")
    msgs.append({"role": "user", "content": message})
    actions, resp = [], None
    for _ in range(max_turns):
        resp = client.messages.create(
            model=model, max_tokens=8192, thinking={"type": "adaptive"},
            system=_system(pid), tools=TOOLS, messages=msgs)
        msgs.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})
        if resp.stop_reason != "tool_use":
            break
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                actions.append({"name": b.name, "input": b.input})
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": _dispatch(pid, b.name, b.input)})
        msgs.append({"role": "user", "content": results})
    reply = " ".join(b.text for b in (resp.content if resp else []) if b.type == "text").strip()
    return {"reply": reply, "actions": actions}


def _run_openai(pid: str, message: str, model: str, max_turns: int) -> dict:
    from openai import OpenAI
    client = OpenAI(base_url=os.environ.get("OPENAI_BASE_URL") or None)
    msgs = _history(pid, "openai")
    msgs.append({"role": "user", "content": message})
    tools = _openai_tools()
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
                         "content": _dispatch(pid, tc.function.name, args)})
    return {"reply": reply.strip(), "actions": actions}


def run_chat(pid: str, message: str, max_turns: int = 8) -> dict:
    """Run one chat turn with the configured provider."""
    provider = _provider()
    model = _model(provider)
    if provider == "openai":
        out = _run_openai(pid, message, model, max_turns)
    else:
        out = _run_anthropic(pid, message, model, max_turns)
    out["reply"] = out["reply"] or "(완료)"
    out["provider"] = provider
    out["model"] = model
    return out


def reset(pid: str) -> None:
    _STATE.pop(pid, None)
