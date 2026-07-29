"""Shared FastMCP instance, cross-cutting helpers, and the server entrypoint.

The tool *definitions* live in the sibling category modules (discovery,
projects, clips, editing, generation, watermark, music, assets, dashboard,
inspection, render). Importing the package (``dabwayo.mcp_tools``) imports
each of them, which registers every ``@mcp.tool()`` onto the single ``mcp``
instance created here.

This split replaces the former monolithic ``dabwayo/mcp_server.py``; that
module is kept as a thin backward-compatible shim (same import path, entry
point and function names).
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ..service import OUTPUT_DIR as _OUTPUT_DIR, STORE as _PROJECTS

mcp = FastMCP("dabwayo")

# Where fetch_music saves downloads (see mcp_tools/music.py).
_MUSIC_DIR = os.environ.get("DABWAYO_MUSIC_DIR", "assets/audio")


# --------------------------------------------------------------------------
# Shared spec helpers (used across project/clip/edit/inspection tools)
# --------------------------------------------------------------------------
def _proj(project_id: str) -> dict:
    if project_id not in _PROJECTS:
        raise ValueError(f"Unknown project_id {project_id!r}. Call create_project first.")
    return _PROJECTS[project_id]


def _commit(project_id: str, spec: dict) -> None:
    """Persist a mutated spec back to the shared store."""
    _PROJECTS[project_id] = spec


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
# Clip identity + addressing
#
# Every clip gets a stable ``id`` at creation. Edit tools accept EITHER that
# id (preferred — survives reordering/deletion of other clips) OR the legacy
# (track, clip_index) pair, so older callers and the Studio REST layer keep
# working unchanged.
# --------------------------------------------------------------------------
def _new_clip_id() -> str:
    return "clip_" + uuid.uuid4().hex[:8]


def _deep_merge(base: dict, patch: dict) -> dict:
    """Recursively merge ``patch`` into ``base`` (lists are replaced; a key set
    to null is deleted)."""
    for k, v in patch.items():
        if v is None:
            base.pop(k, None)
        elif isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _find_track(spec: dict, track: Optional[str], kind: str = "video") -> dict:
    for tr in spec["tracks"]:
        if tr.get("kind", "video") == kind and (track is None or tr.get("name") == track):
            return tr
    raise ValueError(f"Track {track!r} not found")


def _clip_summary(clip: dict, idx: int) -> dict:
    el = clip.get("element", {})
    preview = el.get("text") or el.get("path") or el.get("color") or el.get("type", "")
    return {"index": idx, "id": clip.get("id", ""), "name": clip.get("name", ""),
            "type": el.get("type"), "start": clip.get("start"),
            "duration": clip.get("duration"), "preview": str(preview)[:48]}


def _resolve_clip(spec: dict, track: Optional[str] = None,
                  clip_index: Optional[int] = None,
                  clip_id: Optional[str] = None):
    """Locate a clip by stable ``clip_id`` (searched across all tracks) or by
    the legacy ``(track, clip_index)``. Returns ``(track_dict, index)``."""
    if clip_id:
        for tr in spec["tracks"]:
            for i, c in enumerate(tr.get("clips", [])):
                if c.get("id") == clip_id:
                    return tr, i
        raise ValueError(f"clip_id {clip_id!r} not found")
    if clip_index is None:
        raise ValueError("provide clip_id, or track + clip_index")
    tr = _find_track(spec, track)
    clips = tr.get("clips", [])
    if not clips or not -len(clips) <= clip_index < len(clips):
        raise ValueError(f"clip_index {clip_index} out of range (0..{len(clips)-1})")
    return tr, clip_index % len(clips)


def _log_activity_safe(action, summary, inputs=None, outputs=None, notes=""):
    """Append to the activity log without ever breaking the caller."""
    try:
        from ..studio.guide import append_activity
        append_activity({"action": action, "summary": summary,
                         "inputs": inputs or [], "outputs": outputs or [],
                         "notes": notes})
    except Exception:  # noqa: BLE001
        pass


_HELP = """Dabwayo authoring guide
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
    """Run the MCP server.

    Default transport is stdio (local clients spawn this via .mcp.json).
    Set DABWAYO_MCP_TRANSPORT=http to expose it over Streamable HTTP so a
    *remote* client (e.g. a cloud session) can reach this host's open internet
    — bind/port come from FASTMCP_HOST / FASTMCP_PORT (default 127.0.0.1:8000;
    use 0.0.0.0 to listen on all interfaces). 'sse' is also accepted.
    """
    transport = os.environ.get("DABWAYO_MCP_TRANSPORT", "stdio").lower()
    if transport in ("http", "streamable-http", "streamable_http"):
        mcp.run(transport="streamable-http")
    elif transport == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run()
