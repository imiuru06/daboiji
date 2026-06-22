"""VideoForge MCP server.

Exposes the rendering engine as MCP tools so other agents can author and
render video declaratively. Two complementary styles are supported:

* Stateful authoring — ``create_project`` then ``add_*`` tools mutate a
  server-held project, finishing with ``render_project``.
* Stateless — ``render_from_spec`` renders a complete JSON project in one
  call (ideal when an agent assembles the whole spec itself).

Run:  python -m videoforge.mcp_server         (stdio transport)
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from . import capabilities as engine_capabilities
from .builder import Project
from .render.engine import render, render_thumbnail
from .core.timeline import Timeline

mcp = FastMCP("videoforge")

# In-memory project store: project_id -> spec dict
_PROJECTS: Dict[str, dict] = {}
_OUTPUT_DIR = os.environ.get("VIDEOFORGE_OUTPUT", os.path.abspath("output"))


def _proj(project_id: str) -> dict:
    if project_id not in _PROJECTS:
        raise ValueError(f"Unknown project_id {project_id!r}. Call create_project first.")
    return _PROJECTS[project_id]


def _video_track(spec: dict, track_name: Optional[str]) -> dict:
    tracks = spec["tracks"]
    if track_name:
        for tr in tracks:
            if tr.get("name") == track_name and tr.get("kind", "video") == "video":
                return tr
        tr = {"kind": "video", "name": track_name, "clips": []}
        tracks.append(tr)
        return tr
    for tr in tracks:
        if tr.get("kind", "video") == "video":
            return tr
    tr = {"kind": "video", "name": "video", "clips": []}
    tracks.append(tr)
    return tr


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------
@mcp.tool()
def get_capabilities() -> dict:
    """List everything the engine supports: element types, effects,
    transitions, blend modes, easings and anchors. Call this first to learn
    which values are valid for the other tools."""
    return engine_capabilities()


@mcp.tool()
def get_help() -> str:
    """Return a concise authoring guide: coordinate system, the spec model,
    how keyframes/transitions/effects work, and a minimal example."""
    return _HELP


# --------------------------------------------------------------------------
# Project lifecycle
# --------------------------------------------------------------------------
@mcp.tool()
def create_project(width: int = 1920, height: int = 1080, fps: float = 30.0,
                   background: str = "#0b0e16", name: str = "untitled",
                   duration: Optional[float] = None) -> dict:
    """Create a new video project and return its ``project_id``.

    width/height: output resolution in pixels (e.g. 1920x1080, 1080x1920 for
    vertical, 1080x1080 for square). background: hex/named color shown behind
    all tracks. duration: optional fixed length in seconds; if omitted it is
    derived from the latest clip end."""
    pid = uuid.uuid4().hex[:12]
    p = Project(width, height, fps, background, duration, name)
    _PROJECTS[pid] = p.spec
    return {"project_id": pid, "spec": p.spec}


@mcp.tool()
def add_track(project_id: str, name: str, kind: str = "video") -> dict:
    """Add a named track. kind='video' tracks composite bottom-to-top in the
    order created; kind='audio' tracks are mixed into the soundtrack. Use the
    track ``name`` when adding clips to target a specific layer."""
    spec = _proj(project_id)
    spec["tracks"].append({"kind": kind, "name": name, "clips": []})
    return {"ok": True, "tracks": [t.get("name") for t in spec["tracks"]]}


# --------------------------------------------------------------------------
# Clip authoring
# --------------------------------------------------------------------------
@mcp.tool()
def add_clip(project_id: str, element: dict, start: float = 0.0,
             duration: float = 5.0, track: Optional[str] = None,
             transform: Optional[dict] = None, effects: Optional[List[dict]] = None,
             blend_mode: str = "normal", transition_in: Optional[dict] = None,
             transition_out: Optional[dict] = None, depth: float = 1.0,
             name: str = "") -> dict:
    """Add a clip to a video track. ``element`` is an element spec dict (see
    get_capabilities / add_text/add_background helpers). ``transform`` may set
    position [x,y], scale (number or [sx,sy]), rotation (deg), opacity (0..1),
    anchor; any of these may be a keyframed property
    ({"keyframes":[{"time":t,"value":v,"easing":e}]}). Returns the clip index."""
    spec = _proj(project_id)
    tr = _video_track(spec, track)
    clip: Dict[str, Any] = {"element": element, "start": start, "duration": duration}
    if transform:
        clip["transform"] = transform
    if effects:
        clip["effects"] = effects
    if blend_mode != "normal":
        clip["blend_mode"] = blend_mode
    if transition_in:
        clip["transition_in"] = transition_in
    if transition_out:
        clip["transition_out"] = transition_out
    if depth != 1.0:
        clip["depth"] = depth
    if name:
        clip["name"] = name
    tr["clips"].append(clip)
    return {"ok": True, "track": tr.get("name"), "clip_index": len(tr["clips"]) - 1}


@mcp.tool()
def add_text(project_id: str, text: str, start: float = 0.0, duration: float = 5.0,
             size: int = 96, font: str = "sans", color: str = "#ffffff",
             align: str = "center", position: Optional[List[float]] = None,
             track: Optional[str] = None, shadow: Optional[dict] = None,
             stroke: Optional[str] = None, stroke_width: int = 0,
             max_width: Optional[int] = None, transition_in: Optional[dict] = None,
             transition_out: Optional[dict] = None,
             effects: Optional[List[dict]] = None) -> dict:
    """Convenience: add a text clip. ``font`` accepts aliases
    (sans, sans-bold, display, serif, mono) or a bundled font name. ``shadow``
    e.g. {"color":"#000000aa","offset":[0,6],"blur":10}. ``position`` defaults
    to canvas center when omitted."""
    element = {"type": "text", "text": text, "size": size, "font": font,
               "color": color, "align": align}
    if max_width:
        element["max_width"] = max_width
    if shadow:
        element["shadow"] = shadow
    if stroke:
        element["stroke"] = stroke
        element["stroke_width"] = stroke_width
    transform = {"position": position} if position else None
    return add_clip(project_id, element, start, duration, track, transform,
                    effects, "normal", transition_in, transition_out)


@mcp.tool()
def add_callout(project_id: str, text: str, position: List[float], start: float = 0.0,
                duration: float = 4.0, tail_side: str = "bottom", fill: str = "#ffffff",
                color: str = "#0b0e16", font: str = "sans", font_size: int = 34,
                max_width: int = 520, stroke: Optional[str] = None,
                track: Optional[str] = None, transition_in: Optional[dict] = None,
                transition_out: Optional[dict] = None) -> dict:
    """Add a speech-bubble callout for explainer/product overlays. ``position``
    [x,y] places the bubble; ``tail_side`` (bottom/top/left/right) points the
    pointer toward the feature you are annotating. Pair with a `pop`/`slide`
    transition_in for a lively reveal."""
    element = {"type": "callout", "text": text, "tail_side": tail_side,
               "fill": fill, "color": color, "font": font, "font_size": font_size,
               "max_width": max_width}
    if stroke:
        element["stroke"] = stroke
        element["stroke_width"] = 2
    transform = {"position": position, "anchor": "center"}
    return add_clip(project_id, element, start, duration, track, transform,
                    None, "normal", transition_in, transition_out)


@mcp.tool()
def add_background(project_id: str, color: str = "#0b0e16", start: float = 0.0,
                   duration: float = 5.0, gradient: Optional[dict] = None,
                   track: Optional[str] = None) -> dict:
    """Add a full-frame solid or gradient background clip. For a gradient pass
    e.g. {"stops":[[0,"#12203a"],[1,"#0b0e16"]], "kind":"radial", "angle":90}."""
    if gradient:
        element = {"type": "gradient", **gradient}
    else:
        element = {"type": "solid", "color": color}
    return add_clip(project_id, element, start, duration, track)


@mcp.tool()
def add_media(project_id: str, path: str, kind: str = "image", start: float = 0.0,
              duration: float = 5.0, fit: str = "cover", size: Optional[List[int]] = None,
              track: Optional[str] = None, transform: Optional[dict] = None,
              effects: Optional[List[dict]] = None,
              transition_in: Optional[dict] = None,
              transition_out: Optional[dict] = None) -> dict:
    """Add an image or video file clip. kind='image' or 'video'. fit controls
    scaling to ``size`` (or canvas): contain|cover|stretch|none."""
    element: Dict[str, Any] = {"type": kind, "path": path, "fit": fit}
    if size:
        element["size"] = size
    return add_clip(project_id, element, start, duration, track, transform,
                    effects, "normal", transition_in, transition_out)


@mcp.tool()
def add_effect(project_id: str, effect: dict, track: Optional[str] = None,
               clip_index: Optional[int] = None) -> dict:
    """Attach an effect to a specific clip (track+clip_index) or, if both are
    omitted, to the timeline master chain (applied to the final frame).
    ``effect`` e.g. {"type":"glow","intensity":0.6} or
    {"type":"color_grade","contrast":1.1,"saturation":1.2}."""
    spec = _proj(project_id)
    if clip_index is None and track is None:
        spec["effects"].append(effect)
        return {"ok": True, "scope": "master", "count": len(spec["effects"])}
    tr = _video_track(spec, track)
    if clip_index is None:
        clip_index = len(tr["clips"]) - 1
    tr["clips"][clip_index].setdefault("effects", []).append(effect)
    return {"ok": True, "scope": "clip", "track": tr.get("name"), "clip_index": clip_index}


@mcp.tool()
def set_camera(project_id: str, pan: Optional[List] = None,
               zoom: Optional[object] = None, rotation: Optional[object] = None,
               focus: Optional[List[float]] = None) -> dict:
    """Set a keyframeable virtual camera over the whole composition.

    pan: [x,y] px offset (or a keyframed property). zoom: scale (1=neutral).
    rotation: degrees. focus: [x,y] focal point (default canvas center).
    Give clips a ``depth`` (1=foreground, 0=locked backdrop) for parallax.
    Enables push-ins, pans, dolly, whip-pans and dutch tilts."""
    spec = _proj(project_id)
    cam: Dict[str, Any] = {}
    if pan is not None:
        cam["pan"] = pan
    if zoom is not None:
        cam["zoom"] = zoom
    if rotation is not None:
        cam["rotation"] = rotation
    if focus is not None:
        cam["focus"] = focus
    spec["camera"] = cam
    return {"ok": True, "camera": cam}


@mcp.tool()
def add_audio(project_id: str, path: str, start: float = 0.0,
              duration: Optional[float] = None, gain_db: float = 0.0,
              fade_in: float = 0.0, fade_out: float = 0.0,
              in_point: float = 0.0) -> dict:
    """Add an audio clip to the soundtrack (music, VO, SFX). Multiple audio
    clips are mixed. gain_db adjusts level; fade_in/out in seconds."""
    spec = _proj(project_id)
    track = None
    for tr in spec["tracks"]:
        if tr.get("kind") == "audio":
            track = tr
            break
    if track is None:
        track = {"kind": "audio", "name": "audio", "clips": []}
        spec["tracks"].append(track)
    track["clips"].append({"path": path, "start": start, "duration": duration,
                           "gain_db": gain_db, "fade_in": fade_in,
                           "fade_out": fade_out, "in_point": in_point})
    return {"ok": True, "audio_clips": len(track["clips"])}


# --------------------------------------------------------------------------
# Inspection / serialization
# --------------------------------------------------------------------------
@mcp.tool()
def get_project(project_id: str) -> dict:
    """Return the full project spec (JSON-able) for inspection or editing."""
    return _proj(project_id)


@mcp.tool()
def update_project(project_id: str, spec: dict) -> dict:
    """Replace the stored spec for a project (e.g. after external editing)."""
    _PROJECTS[project_id] = spec
    return {"ok": True}


@mcp.tool()
def estimate(project_id: str) -> dict:
    """Report computed duration and frame count without rendering."""
    tl = Timeline.from_spec(_proj(project_id))
    return {"duration": tl.computed_duration(), "frames": tl.total_frames,
            "fps": tl.fps, "resolution": [tl.width, tl.height]}


@mcp.tool()
def preview_frame(project_id: str, time: float = 0.0,
                  out_path: Optional[str] = None) -> dict:
    """Render a single PNG frame at ``time`` seconds for quick visual review."""
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out_path = out_path or os.path.join(_OUTPUT_DIR, f"preview_{project_id}_{int(time*1000)}.png")
    tl = Timeline.from_spec(_proj(project_id))
    render_thumbnail(tl, out_path, time)
    return {"ok": True, "path": out_path}


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
@mcp.tool()
def render_project(project_id: str, out_path: Optional[str] = None,
                   crf: int = 18, preset: str = "medium") -> dict:
    """Render the project to an MP4 (H.264). Lower crf = higher quality/larger
    (18 is visually lossless-ish). preset trades speed for size
    (ultrafast..veryslow). Returns the output path and metadata."""
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out_path = out_path or os.path.join(_OUTPUT_DIR, f"{project_id}.mp4")
    tl = Timeline.from_spec(_proj(project_id))
    t0 = time.time()
    res = render(tl, out_path, crf=crf, preset=preset)
    return {"ok": True, "path": res.path, "frames": res.frames,
            "duration": res.duration, "resolution": [res.width, res.height],
            "fps": res.fps, "render_seconds": round(time.time() - t0, 2),
            "bytes": os.path.getsize(out_path)}


@mcp.tool()
def render_from_spec(spec: dict, out_path: Optional[str] = None,
                     crf: int = 18, preset: str = "medium") -> dict:
    """Render a complete project spec in one stateless call. ``spec`` is the
    same JSON structure returned by get_project. Best when the calling agent
    assembles the entire timeline itself."""
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out_path = out_path or os.path.join(_OUTPUT_DIR, f"spec_{uuid.uuid4().hex[:8]}.mp4")
    tl = Timeline.from_spec(spec)
    res = render(tl, out_path, crf=crf, preset=preset)
    return {"ok": True, "path": res.path, "frames": res.frames,
            "duration": res.duration, "resolution": [res.width, res.height],
            "bytes": os.path.getsize(out_path)}


_HELP = """VideoForge authoring guide
==========================
Coordinate system: pixels, origin top-left, +x right, +y down.
A project = tracks (composited bottom->top) of clips placed at absolute
times. Each clip has an element (the content), a transform, effects, and
optional in/out transitions.

Transform fields (any may be a keyframed property):
  position [x,y]  scale (n or [sx,sy])  rotation (deg)  opacity (0..1)
  anchor (center/top_left/.../bottom_right)
Keyframed property:
  {"keyframes":[{"time":0,"value":[0,540],"easing":"ease_out_cubic"},
                {"time":1.0,"value":[960,540]}]}

Typical flow:
  1. create_project(1920,1080,fps=30)
  2. add_background(..., gradient={...})
  3. add_text(..., transition_in={"type":"zoom","duration":0.6})
  4. add_effect(..., effect={"type":"glow"})  # clip or master
  5. add_audio(...) optional
  6. render_project(...)

Use get_capabilities() for the full list of element/effect/transition names.
"""


def main():
    mcp.run()


if __name__ == "__main__":
    main()
