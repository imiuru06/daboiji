"""Clip authoring tools: place content (clips), effects, camera and audio."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .app import mcp, _proj, _commit, _video_track, _new_clip_id, _resolve_clip

__all__ = ["add_clip", "add_text", "add_callout", "add_background", "add_media",
           "add_effect", "set_camera", "add_audio"]


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
    clip: Dict[str, Any] = {"id": _new_clip_id(), "element": element,
                            "start": start, "duration": duration}
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
    _commit(project_id, spec)
    return {"ok": True, "track": tr.get("name"), "clip_index": len(tr["clips"]) - 1,
            "clip_id": clip["id"]}


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
                color: str = "#0b0e16", font: str = "kr-bold", font_size: int = 34,
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
              transition_out: Optional[dict] = None,
              speed: float = 1.0, loop: bool = False, source_start: float = 0.0,
              crop: Optional[List[float]] = None) -> dict:
    """Add an image or video file clip. kind='image' or 'video'. fit controls
    scaling to ``size`` (or canvas): contain|cover|stretch|none.

    Video editing controls (video clips): ``speed`` retimes playback
    (0.5 = half-speed/slow-mo, 2 = double-speed); ``loop`` repeats the source
    if the clip outlasts it; ``source_start`` trims in from this many seconds
    into the source. ``crop`` = [x, y, w, h] as fractions (0..1) of the source
    frame, applied before fit (works for image and video)."""
    element: Dict[str, Any] = {"type": kind, "path": path, "fit": fit}
    if size:
        element["size"] = size
    if crop:
        element["crop"] = crop
    if kind == "video":
        if speed != 1.0:
            element["speed"] = speed
        if loop:
            element["loop"] = True
        if source_start:
            element["start"] = source_start
    return add_clip(project_id, element, start, duration, track, transform,
                    effects, "normal", transition_in, transition_out)


@mcp.tool()
def add_effect(project_id: str, effect: dict, track: Optional[str] = None,
               clip_index: Optional[int] = None, clip_id: Optional[str] = None) -> dict:
    """Attach an effect to a clip, or (if no clip is targeted) to the timeline
    master chain (applied to the final frame).

    Target a clip with ``clip_id`` (preferred — stable across edits) or the
    legacy ``track`` + ``clip_index``; if ``track`` is given without an index,
    the track's last clip is used. With none of clip_id/track/clip_index, the
    effect is added to the master chain. ``effect`` e.g.
    {"type":"glow","intensity":0.6} or {"type":"color_grade","contrast":1.1}."""
    spec = _proj(project_id)
    if clip_id is None and clip_index is None and track is None:
        spec["effects"].append(effect)
        _commit(project_id, spec)
        return {"ok": True, "scope": "master", "count": len(spec["effects"])}
    if clip_id is None and clip_index is None:
        tr = _video_track(spec, track)
        idx = len(tr["clips"]) - 1
    else:
        tr, idx = _resolve_clip(spec, track, clip_index, clip_id)
    clip = tr["clips"][idx]
    clip.setdefault("effects", []).append(effect)
    _commit(project_id, spec)
    return {"ok": True, "scope": "clip", "track": tr.get("name"),
            "clip_index": idx, "clip_id": clip.get("id", "")}


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
    _commit(project_id, spec)
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
    clip = {"id": _new_clip_id(), "path": path, "start": start,
            "duration": duration, "gain_db": gain_db, "fade_in": fade_in,
            "fade_out": fade_out, "in_point": in_point}
    track["clips"].append(clip)
    _commit(project_id, spec)
    return {"ok": True, "audio_clips": len(track["clips"]), "clip_id": clip["id"]}
