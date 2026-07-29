"""Inspection / serialization tools: read a spec, estimate, preview a frame."""
from __future__ import annotations

import os
from typing import Optional

from ..core.timeline import Timeline
from ..render.engine import render_thumbnail
from .app import mcp, _proj, _OUTPUT_DIR, _PROJECTS

__all__ = ["get_project", "update_project", "estimate", "preview_frame"]


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
