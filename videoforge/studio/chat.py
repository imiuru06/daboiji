"""Natural-language editing: Claude drives the same MCP operations via tool use.

This wires a chat turn ("말로 지시") to the engine: Claude (claude-opus-4-8)
receives the user's instruction plus a set of editing tools, calls them in an
agentic loop, and each tool runs the *same* function the MCP server exposes —
so the edits land on the shared project store and show up live in the UI and
to any Claude Code session on the same store.

Requires ``ANTHROPIC_API_KEY`` in the environment. The official ``anthropic``
SDK is an optional dependency, imported lazily so the Studio still runs
without it (the chat endpoint just reports it's unavailable).
"""
from __future__ import annotations

import json
from typing import Dict, List

from .. import capabilities as engine_capabilities
from .. import mcp_server as M

MODEL = "claude-opus-4-8"

# Per-project conversation history (content blocks), kept for the session.
_HISTORY: Dict[str, list] = {}


# --- tools exposed to Claude: each maps to an MCP server function ----------
TOOLS = [
    {"name": "list_clips", "description": "List every clip with its track, index, "
     "type, timing and a content preview. Call this to see the current timeline "
     "before editing.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "add_background", "description": "Add a full-frame background. Use a "
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
     "for a master effect on the whole frame. See capabilities for effect names.",
     "input_schema": {"type": "object", "properties": {"type": {"type": "string"},
                    "params": {"type": "object"}, "track": {"type": "string"},
                    "clip_index": {"type": "integer"}}, "required": ["type"]}},
    {"name": "set_camera", "description": "Set a keyframeable camera (pan [x,y] px, "
     "zoom, rotation deg). Give clips depth 0..1 for parallax.", "input_schema": {"type": "object",
     "properties": {"pan": {"type": "array", "items": {"type": "number"}},
                    "zoom": {"type": "number"}, "rotation": {"type": "number"}}}},
    {"name": "update_clip", "description": "Edit ONE clip in place by deep-merging a "
     "patch (only the keys you pass change). e.g. patch={'element':{'text':'new'}} or "
     "{'start':2.0}.", "input_schema": {"type": "object", "properties": {"track": {"type": "string"},
                    "clip_index": {"type": "integer"}, "patch": {"type": "object"}},
     "required": ["track", "clip_index", "patch"]}},
    {"name": "remove_clip", "description": "Delete one clip from a track.",
     "input_schema": {"type": "object", "properties": {"track": {"type": "string"},
                    "clip_index": {"type": "integer"}}, "required": ["track", "clip_index"]}},
]


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
        f"Available fonts (font names/aliases): sans, sans-bold, display, serif, mono, "
        f"kr, kr-bold (use kr-bold for Korean).\n"
        "Guidelines: make exactly the change requested, nothing more. Prefer "
        "update_clip for tweaks to an existing clip (call list_clips first to find "
        "its track+index). Keep replies to one or two short sentences describing what "
        "you did. Reply in the user's language."
    )


def available() -> bool:
    import os
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def run_chat(pid: str, message: str, max_turns: int = 8) -> dict:
    """Run one chat turn: Claude plans and calls editing tools in a loop."""
    import anthropic

    client = anthropic.Anthropic()
    history = _HISTORY.setdefault(pid, [])
    history.append({"role": "user", "content": message})

    actions: List[dict] = []
    resp = None
    for _ in range(max_turns):
        resp = client.messages.create(
            model=MODEL, max_tokens=8192,
            thinking={"type": "adaptive"},
            system=_system(pid), tools=TOOLS, messages=history,
        )
        # Preserve full content (incl. thinking blocks) for correct replay.
        history.append({"role": "assistant",
                        "content": [b.model_dump() for b in resp.content]})
        if resp.stop_reason != "tool_use":
            break
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                out = _dispatch(pid, b.name, b.input)
                actions.append({"name": b.name, "input": b.input})
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
        history.append({"role": "user", "content": results})

    reply = " ".join(b.text for b in (resp.content if resp else []) if b.type == "text").strip()
    return {"reply": reply or "(완료)", "actions": actions}


def reset(pid: str) -> None:
    _HISTORY.pop(pid, None)
