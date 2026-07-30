"""Rendering tools: whole project, a time window, or a stateless spec."""
from __future__ import annotations

import os
import time
import uuid
from typing import Optional

from ..core.timeline import Timeline
from ..render.engine import render
from .app import mcp, _proj, _OUTPUT_DIR

__all__ = ["render_project", "render_range", "render_from_spec"]


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
def render_range(project_id: str, start: float, end: float,
                 out_path: Optional[str] = None, crf: int = 20,
                 preset: str = "veryfast") -> dict:
    """Render ONLY the time window [start, end] seconds — a fast preview of a
    section you just edited, so you don't re-render the whole video. (Video
    only; use render_project for the final with audio.)"""
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out_path = out_path or os.path.join(
        _OUTPUT_DIR, f"{project_id}_{int(start*1000)}-{int(end*1000)}.mp4")
    tl = Timeline.from_spec(_proj(project_id))
    t0 = time.time()
    res = render(tl, out_path, crf=crf, preset=preset, t_start=start, t_end=end)
    return {"ok": True, "path": res.path, "frames": res.frames,
            "window": [start, end], "render_seconds": round(time.time() - t0, 2),
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
