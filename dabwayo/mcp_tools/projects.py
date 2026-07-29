"""Project lifecycle tools: create a project, add tracks."""
from __future__ import annotations

import uuid
from typing import Optional

from ..builder import Project
from .app import mcp, _proj, _commit, _PROJECTS

__all__ = ["create_project", "add_track"]


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
    _commit(project_id, spec)
    return {"ok": True, "tracks": [t.get("name") for t in spec["tracks"]]}
