"""Storyboard tools: a structured shot list on a project, plus deterministic
assembly into a timeline.

Scope note — dabwayo is the *tool* layer other agents drive over MCP, not an
agent itself. So there is no LLM planner here: the calling agent decides the
shots (prompt, timing, caption per shot) by calling ``add_shot``; dabwayo just
holds that plan as structured state and turns it into a timeline with
``assemble_storyboard`` (placing attached/generated media, chaining transitions,
laying captions). Generation, when requested, goes through the existing
pluggable video providers — dabwayo wraps external models, it doesn't embed one.
"""
from __future__ import annotations

import uuid
from typing import Optional

from .app import mcp, _proj, _commit

__all__ = ["add_shot", "list_shots", "update_shot", "remove_shot",
           "assemble_storyboard"]


def _shots(spec: dict) -> list:
    return spec.setdefault("storyboard", [])


def _new_shot_id() -> str:
    return "shot_" + uuid.uuid4().hex[:8]


@mcp.tool()
def add_shot(project_id: str, prompt: str = "", duration: float = 4.0,
             mode: str = "t2v", image: Optional[str] = None, caption: str = "",
             media: Optional[str] = None, transition: str = "fade") -> dict:
    """Append a shot to the project's storyboard (the calling agent's plan).

    A shot is intent, not footage yet: ``prompt`` (what to generate), ``mode``
    (t2v|i2v), ``image`` (reference for i2v), ``duration``, an optional
    ``caption`` to burn over it, and ``transition`` into it. If you already have
    a clip, pass ``media`` (a file path) and assembly will use it directly
    instead of generating. Returns the new ``shot_id``."""
    spec = _proj(project_id)
    shot = {"id": _new_shot_id(), "prompt": prompt, "duration": float(duration),
            "mode": mode, "image": image, "caption": caption,
            "media": media, "transition": transition}
    _shots(spec).append(shot)
    _commit(project_id, spec)
    return {"ok": True, "shot_id": shot["id"], "shots": len(_shots(spec))}


@mcp.tool()
def list_shots(project_id: str) -> dict:
    """List the storyboard shots in order (id, prompt, duration, whether media
    is attached, caption)."""
    spec = _proj(project_id)
    out = [{"index": i, "id": s.get("id"), "prompt": s.get("prompt", ""),
            "duration": s.get("duration"), "mode": s.get("mode"),
            "has_media": bool(s.get("media")), "caption": s.get("caption", "")}
           for i, s in enumerate(_shots(spec))]
    return {"shots": out, "count": len(out)}


def _find_shot(spec: dict, shot_id: str):
    for i, s in enumerate(_shots(spec)):
        if s.get("id") == shot_id:
            return i, s
    raise ValueError(f"shot_id {shot_id!r} not found")


@mcp.tool()
def update_shot(project_id: str, shot_id: str, patch: dict) -> dict:
    """Edit one shot's fields (prompt, duration, caption, media, …) by shallow
    merge. The shot ``id`` is immutable."""
    spec = _proj(project_id)
    _, shot = _find_shot(spec, shot_id)
    for k, v in (patch or {}).items():
        if k == "id":
            continue
        if v is None:
            shot.pop(k, None)
        else:
            shot[k] = v
    _commit(project_id, spec)
    return {"ok": True, "shot": shot}


@mcp.tool()
def remove_shot(project_id: str, shot_id: str) -> dict:
    """Remove a shot from the storyboard."""
    spec = _proj(project_id)
    i, _ = _find_shot(spec, shot_id)
    _shots(spec).pop(i)
    _commit(project_id, spec)
    return {"ok": True, "shots": len(_shots(spec))}


@mcp.tool()
def assemble_storyboard(project_id: str, generate: bool = False,
                        transition_duration: float = 0.4, captions: bool = True,
                        track: str = "video", caption_track: str = "captions") -> dict:
    """Turn the storyboard into a timeline: lay each shot back-to-back in order,
    chaining transitions and (optionally) burning each shot's caption over it.

    For each shot: if it has ``media`` (a clip path) it is placed directly; else
    if ``generate`` is true and it has a ``prompt``, a clip is generated via the
    active video provider and cached back onto the shot; otherwise a text
    placeholder card (the prompt) is laid down so the storyboard is viewable
    before any generation. Deterministic — the creative choices already live in
    the shots. Returns the placed clip ids and total duration."""
    spec = _proj(project_id)
    shots = _shots(spec)
    if not shots:
        raise ValueError("no shots — add_shot first")
    from .clips import add_media, add_clip
    w = int(spec.get("width", 1920))
    h = int(spec.get("height", 1080))

    t = 0.0
    placed, generated = [], 0
    for i, shot in enumerate(shots):
        dur = float(shot.get("duration", 4.0))
        tin = {"type": shot.get("transition", "fade"), "duration": transition_duration} if i > 0 else None
        tout = {"type": "fade", "duration": transition_duration}
        media = shot.get("media")
        if not media and generate and shot.get("prompt"):
            from .generation import generate_video as _gv
            res = _gv(project_id, shot["prompt"], mode=shot.get("mode", "t2v"),
                      image=shot.get("image"), duration=dur, add_to_timeline=False)
            media = res.get("path")
            shot["media"] = media
            generated += 1
        if media:
            clip = add_media(project_id, media, "video", t, dur, "cover", None,
                             track, None, None, tin, tout)
        else:
            el = {"type": "text", "text": shot.get("prompt") or f"Shot {i + 1}",
                  "size": max(28, round(h * 0.05)), "font": "sans", "color": "#ffffff",
                  "align": "center", "max_width": round(w * 0.8),
                  "shadow": {"color": "#000000cc", "offset": [0, 3], "blur": 8}}
            clip = add_clip(project_id, el, t, dur, track,
                            {"position": [round(w / 2), round(h / 2)], "anchor": "center"},
                            None, "normal", tin, tout)
        placed.append(clip["clip_id"])
        if captions and shot.get("caption"):
            cap = {"type": "text", "text": shot["caption"], "size": max(20, round(h * 0.05)),
                   "font": "sans-bold", "color": "#ffffff", "align": "center",
                   "max_width": round(w * 0.86), "stroke": "#000000", "stroke_width": 3,
                   "shadow": {"color": "#000000cc", "offset": [0, 3], "blur": 8}}
            add_clip(project_id, cap, t, dur, caption_track,
                     {"position": [round(w / 2), h - round(h * 0.08)], "anchor": "bottom"})
        t += dur

    spec = _proj(project_id)
    _commit(project_id, spec)
    return {"ok": True, "shots": len(shots), "clips": placed,
            "generated": generated, "duration": round(t, 3)}
