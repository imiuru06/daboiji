"""Clip editing tools: inspect, retime, patch, move and remove existing clips.

Every clip carries a stable ``id`` (assigned by the authoring tools). The edit
tools accept that ``clip_id`` (preferred — it survives reordering/deletion of
other clips) or the legacy ``(track, clip_index)`` pair, kept for backward
compatibility with the Studio REST layer and older callers."""
from __future__ import annotations

from typing import Optional

from .app import (mcp, _proj, _commit, _deep_merge, _find_track,
                  _clip_summary, _resolve_clip)

__all__ = ["list_clips", "update_clip", "remove_clip", "move_clip"]


@mcp.tool()
def list_clips(project_id: str) -> dict:
    """List every clip (with its track, stable ``id``, index, type, timing and a
    content preview) so you can target one for editing. Prefer the ``id`` for
    edits — it does not shift when other clips are added or removed."""
    spec = _proj(project_id)
    out = []
    for tr in spec["tracks"]:
        clips = [_clip_summary(c, i) if tr.get("kind", "video") == "video"
                 else {"index": i, "id": c.get("id", ""), "type": "audio",
                       "start": c.get("start"), "preview": c.get("path", "")[:48]}
                 for i, c in enumerate(tr.get("clips", []))]
        out.append({"track": tr.get("name"), "kind": tr.get("kind", "video"),
                    "clips": clips})
    return {"tracks": out}


@mcp.tool()
def update_clip(project_id: str, track: Optional[str] = None,
                clip_index: Optional[int] = None, patch: Optional[dict] = None,
                clip_id: Optional[str] = None) -> dict:
    """Edit ONE clip in place by deep-merging ``patch`` into it — change only
    what you pass, everything else is preserved. Target it with ``clip_id``
    (preferred, stable) or the legacy ``track`` + ``clip_index``. Examples:
      patch={"start": 4.0, "duration": 3.0}                  # retime
      patch={"transform": {"position": [800, 300]}}          # move
      patch={"element": {"text": "new text", "color": "#f00"}}  # edit content
      patch={"effects": [{"type": "glow", "intensity": 0.5}]} # replace effects
    Lists (e.g. effects) are replaced; nested dicts are merged. Pass a key with
    null to delete it. (The clip's ``id`` cannot be changed.)"""
    if patch is None:
        raise ValueError("update_clip: patch is required")
    spec = _proj(project_id)
    tr, idx = _resolve_clip(spec, track, clip_index, clip_id)
    clip = tr["clips"][idx]
    patch = {k: v for k, v in patch.items() if k != "id"}  # id is immutable
    _deep_merge(clip, patch)
    _commit(project_id, spec)
    return {"ok": True, "clip": clip}


@mcp.tool()
def remove_clip(project_id: str, track: Optional[str] = None,
                clip_index: Optional[int] = None,
                clip_id: Optional[str] = None) -> dict:
    """Delete one clip from a track (by ``clip_id`` or ``track`` + ``clip_index``).
    Other clips are untouched."""
    spec = _proj(project_id)
    tr, idx = _resolve_clip(spec, track, clip_index, clip_id)
    removed = tr["clips"].pop(idx)
    _commit(project_id, spec)
    return {"ok": True, "removed": _clip_summary(removed, idx),
            "remaining": len(tr["clips"])}


@mcp.tool()
def move_clip(project_id: str, track: Optional[str] = None,
              clip_index: Optional[int] = None,
              start: Optional[float] = None, duration: Optional[float] = None,
              to_track: Optional[str] = None,
              clip_id: Optional[str] = None) -> dict:
    """Retime a clip (set start/duration) and/or move it to another video
    track, without altering its content. Target it with ``clip_id`` or
    ``track`` + ``clip_index``. The clip keeps its id across the move."""
    spec = _proj(project_id)
    tr, idx = _resolve_clip(spec, track, clip_index, clip_id)
    clip = tr["clips"][idx]
    if start is not None:
        clip["start"] = start
    if duration is not None:
        clip["duration"] = duration
    if to_track is not None and to_track != tr.get("name"):
        tr["clips"].pop(idx)
        _find_track(spec, to_track)["clips"].append(clip)
    _commit(project_id, spec)
    return {"ok": True, "clip": _clip_summary(clip, idx)}
