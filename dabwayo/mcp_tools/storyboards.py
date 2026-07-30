"""First-class storyboard tools (ADR-0002): a reusable storyboard library,
decoupled from render projects.

A storyboard is a named entity in the store with scenes → shots; each shot binds
a cast (multiple characters), an environment and props. resolve_storyboard_shot
composes a shot's generation request from those bindings; assemble_storyboard
materialises the whole plan into a render project. The plan is reusable across
projects — the render project is the *output*, not the home of the plan.
"""
from __future__ import annotations

from typing import Optional

from .app import mcp, _PROJECTS

__all__ = ["create_storyboard", "list_storyboards", "get_storyboard",
           "update_storyboard", "remove_storyboard", "add_scene", "move_scene",
           "add_storyboard_shot", "update_storyboard_shot", "remove_storyboard_shot",
           "move_storyboard_shot", "storyboard_cast",
           "resolve_storyboard_shot", "assemble_storyboard_project"]


@mcp.tool()
def create_storyboard(name: str, description: str = "", width: int = 1080,
                      height: int = 1920, fps: float = 24.0) -> dict:
    """Create a reusable storyboard (the plan) in the library. It holds scenes
    and shots and can be assembled into any number of render projects. Returns
    the record with its id."""
    from .. import storyboards as _sb
    return {"ok": True, "storyboard": _sb.create(name, description, width, height, fps)}


@mcp.tool()
def list_storyboards() -> dict:
    """List storyboards (id, name, #scenes, #shots)."""
    from .. import storyboards as _sb
    out = []
    for r in _sb.list_all():
        shots = sum(len(s.get("shots", [])) for s in r.get("scenes", []))
        out.append({"id": r["id"], "name": r.get("name"),
                    "scenes": len(r.get("scenes", [])), "shots": shots})
    return {"ok": True, "count": len(out), "storyboards": out}


@mcp.tool()
def get_storyboard(storyboard_id: str) -> dict:
    """Return a storyboard's full record (scenes → shots with their bindings)."""
    from .. import storyboards as _sb
    return {"ok": True, "storyboard": _sb.get(storyboard_id)}


@mcp.tool()
def update_storyboard(storyboard_id: str, patch: dict) -> dict:
    """Edit a storyboard's top-level fields (name/description/width/height/fps).
    Scenes/shots have their own tools."""
    from .. import storyboards as _sb
    return {"ok": True, "storyboard": _sb.update(storyboard_id, patch)}


@mcp.tool()
def remove_storyboard(storyboard_id: str) -> dict:
    """Delete a storyboard from the library."""
    from .. import storyboards as _sb
    return {"ok": _sb.remove(storyboard_id)}


@mcp.tool()
def add_scene(storyboard_id: str, name: str = "") -> dict:
    """Add a scene (a group of shots) to a storyboard. Returns the scene id."""
    from .. import storyboards as _sb
    return {"ok": True, "scene": _sb.add_scene(storyboard_id, name)}


@mcp.tool()
def move_scene(storyboard_id: str, scene_id: str, to_index: int) -> dict:
    """Reorder a scene within the storyboard (0-based ``to_index``)."""
    from .. import storyboards as _sb
    _sb.move_scene(storyboard_id, scene_id, to_index)
    return {"ok": True}


@mcp.tool()
def add_storyboard_shot(storyboard_id: str, scene_id: str, prompt: str = "",
                        duration: float = 4.0, mode: str = "t2v", caption: str = "",
                        cast: Optional[list] = None, environment: Optional[dict] = None,
                        props: Optional[list] = None, camera: Optional[dict] = None) -> dict:
    """Add a shot to a scene. A shot binds a ``cast`` (a list of
    {character_id, variant:[...]} — MULTIPLE characters per shot), an
    ``environment`` ({id, variant}), ``props`` ([{prop_id, variant}]) and a
    ``camera`` dict, plus its ``prompt`` (action), ``duration``, ``mode`` and
    ``caption``. Returns the shot id."""
    from .. import storyboards as _sb
    shot = _sb.add_shot(storyboard_id, scene_id, prompt=prompt, duration=duration,
                        mode=mode, caption=caption, cast=cast, environment=environment,
                        props=props, camera=camera)
    return {"ok": True, "shot_id": shot["id"], "shot": shot}


@mcp.tool()
def update_storyboard_shot(storyboard_id: str, shot_id: str, patch: dict) -> dict:
    """Edit a shot in place (any field, including its cast/environment/props/
    camera bindings). E.g. patch={"cast":[{"character_id":"char_..","variant":["v_.."]}]}."""
    from .. import storyboards as _sb
    return {"ok": True, "shot": _sb.update_shot(storyboard_id, shot_id, patch)}


@mcp.tool()
def remove_storyboard_shot(storyboard_id: str, shot_id: str) -> dict:
    """Remove a shot from its scene."""
    from .. import storyboards as _sb
    _sb.remove_shot(storyboard_id, shot_id)
    return {"ok": True}


@mcp.tool()
def move_storyboard_shot(storyboard_id: str, shot_id: str,
                         to_scene_id: Optional[str] = None,
                         to_index: Optional[int] = None) -> dict:
    """Reorder a shot within its scene, or move it into another scene
    (``to_scene_id``), optionally at ``to_index`` (default: append). The shot
    keeps its id and bindings."""
    from .. import storyboards as _sb
    _sb.move_shot(storyboard_id, shot_id, to_scene_id=to_scene_id, to_index=to_index)
    return {"ok": True}


@mcp.tool()
def storyboard_cast(storyboard_id: str) -> dict:
    """The cast list for a storyboard — the distinct characters, environments and
    props it references across all shots, with names and how many shots use each.
    (Like a production's cast/locations/props breakdown.)"""
    from .. import storyboards as _sb, reference as _ref
    rec = _sb.get(storyboard_id)
    tally = {"character": {}, "environment": {}, "prop": {}}
    for _, shot in _sb.iter_shots(rec):
        for m in (shot.get("cast") or []):
            if m.get("character_id"):
                tally["character"][m["character_id"]] = tally["character"].get(m["character_id"], 0) + 1
        eb = shot.get("environment") or {}
        if eb.get("id"):
            tally["environment"][eb["id"]] = tally["environment"].get(eb["id"], 0) + 1
        for pb in (shot.get("props") or []):
            if pb.get("prop_id"):
                tally["prop"][pb["prop_id"]] = tally["prop"].get(pb["prop_id"], 0) + 1

    def rows(kind):
        out = []
        for rid, n in tally[kind].items():
            name = rid
            try:
                name = _ref.get(kind, rid).get("name", rid)
            except Exception:  # noqa: BLE001
                pass
            out.append({"id": rid, "name": name, "shots": n})
        return sorted(out, key=lambda x: -x["shots"])
    return {"ok": True, "storyboard_id": storyboard_id,
            "characters": rows("character"), "environments": rows("environment"),
            "props": rows("prop")}


def _compose_shot(shot: dict):
    """Deterministically compose a shot's generation request from its bindings —
    multiple cast members, environment and props. No ML. Returns (prompt, refs)."""
    from .. import reference as _ref
    parts, refs = [], []
    for member in (shot.get("cast") or []):
        cid = member.get("character_id")
        if not cid:
            continue
        try:
            c = _ref.get("character", cid)
        except Exception:  # noqa: BLE001
            continue
        if c.get("description"):
            parts.append(c["description"])
        refs += list(c.get("base_refs", []))
        vids = member.get("variant") or []
        vids = vids if isinstance(vids, list) else [vids]
        for v in c.get("variants", []):
            if v.get("id") in vids:
                if v.get("prompt_fragment"):
                    parts.append(v["prompt_fragment"])
                refs += list(v.get("refs", []))
    eb = shot.get("environment")
    if eb and eb.get("id"):
        try:
            e = _ref.get("environment", eb["id"])
            if e.get("description"):
                parts.append(e["description"])
            refs += list(e.get("base_refs", []))
            for v in e.get("variants", []):
                if v.get("id") == eb.get("variant"):
                    bits = [v.get("prompt_fragment")] + [
                        f"{k}: {v[k]}" for k in ("time_of_day", "lighting", "mood", "focus") if v.get(k)]
                    parts += [b for b in bits if b]
                    refs += list(v.get("refs", []))
        except Exception:  # noqa: BLE001
            pass
    for pb in (shot.get("props") or []):
        try:
            p = _ref.get("prop", pb.get("prop_id"))
            if p.get("description"):
                parts.append(p["description"])
            refs += list(p.get("base_refs", []))
        except Exception:  # noqa: BLE001
            pass
    cam = shot.get("camera") or {}
    if cam:
        parts.append(", ".join(f"{k} {v}" for k, v in cam.items()))
    if shot.get("prompt"):
        parts.append(shot["prompt"])
    return ", ".join(p for p in parts if p), refs


@mcp.tool()
def resolve_storyboard_shot(storyboard_id: str, shot_id: str) -> dict:
    """Compose a shot's generation request from ALL its bindings (multi-cast +
    environment + props + camera + action) — deterministic, no ML. Returns the
    composed ``prompt`` and ordered ``reference_images`` for the provider."""
    from .. import storyboards as _sb
    rec = _sb.get(storyboard_id)
    _, _, shot = _sb._find_shot(rec, shot_id)
    prompt, refs = _compose_shot(shot)
    return {"ok": True, "shot_id": shot_id, "prompt": prompt,
            "reference_images": refs, "mode": shot.get("mode", "t2v"),
            "duration": shot.get("duration")}


@mcp.tool()
def assemble_storyboard_project(storyboard_id: str, project_id: Optional[str] = None,
                        transition_duration: float = 0.4, captions: bool = True,
                        track: str = "video", caption_track: str = "captions") -> dict:
    """Materialise a storyboard (the plan) into a render project (the output) —
    flatten its scenes → shots in order and lay each on the timeline (its
    ``media`` if present, else a prompt placeholder card), chaining transitions
    and burning captions. The storyboard stays reusable; this produces one
    render project from it. Creates a project (from the storyboard's format) or
    fills ``project_id``. Returns the project id, placed clips and duration."""
    from .. import storyboards as _sb
    from .clips import add_media, add_clip
    from .projects import create_project
    rec = _sb.get(storyboard_id)
    shots = [sh for _, sh in _sb.iter_shots(rec)]
    if not shots:
        raise ValueError("storyboard has no shots")
    if project_id is None:
        project_id = create_project(rec.get("width", 1080), rec.get("height", 1920),
                                    fps=rec.get("fps", 24.0),
                                    name=rec.get("name", "storyboard"))["project_id"]
    spec = _PROJECTS[project_id]
    w, h = int(spec.get("width", 1080)), int(spec.get("height", 1920))
    t, placed = 0.0, []
    for i, shot in enumerate(shots):
        dur = float(shot.get("duration", 4.0))
        tin = {"type": shot.get("transition", "fade"), "duration": transition_duration} if i > 0 else None
        tout = {"type": "fade", "duration": transition_duration}
        if shot.get("media"):
            clip = add_media(project_id, shot["media"], "video", t, dur, "cover",
                             None, track, None, None, tin, tout)
        else:
            el = {"type": "text", "text": shot.get("prompt") or f"Shot {i+1}",
                  "size": max(28, round(h * 0.05)), "font": "sans", "color": "#ffffff",
                  "align": "center", "max_width": round(w * 0.8),
                  "shadow": {"color": "#000000cc", "offset": [0, 3], "blur": 8}}
            clip = add_clip(project_id, el, t, dur, track,
                            {"position": [round(w/2), round(h/2)], "anchor": "center"},
                            None, "normal", tin, tout)
        placed.append(clip["clip_id"])
        if captions and shot.get("caption"):
            cap = {"type": "text", "text": shot["caption"], "size": max(20, round(h*0.05)),
                   "font": "sans-bold", "color": "#ffffff", "align": "center",
                   "max_width": round(w*0.86), "stroke": "#000000", "stroke_width": 3,
                   "shadow": {"color": "#000000cc", "offset": [0, 3], "blur": 8}}
            add_clip(project_id, cap, t, dur, caption_track,
                     {"position": [round(w/2), h - round(h*0.08)], "anchor": "bottom"})
        t += dur
    return {"ok": True, "storyboard_id": storyboard_id, "project_id": project_id,
            "shots": len(shots), "clips": placed, "duration": round(t, 3)}
