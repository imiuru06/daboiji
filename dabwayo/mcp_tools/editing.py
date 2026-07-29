"""Clip editing tools: inspect, retime, patch, move and remove existing clips."""
from __future__ import annotations

from typing import Optional

from .app import mcp, _proj, _commit

__all__ = ["list_clips", "update_clip", "remove_clip", "move_clip"]


def _deep_merge(base: dict, patch: dict) -> dict:
    """Recursively merge ``patch`` into ``base`` (lists are replaced)."""
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
    return {"index": idx, "name": clip.get("name", ""), "type": el.get("type"),
            "start": clip.get("start"), "duration": clip.get("duration"),
            "preview": str(preview)[:48]}


@mcp.tool()
def list_clips(project_id: str) -> dict:
    """List every clip (with its track, index, type, timing and a content
    preview) so you can target one for editing. This is how you find the
    ``track`` + ``clip_index`` the edit tools take."""
    spec = _proj(project_id)
    out = []
    for tr in spec["tracks"]:
        clips = [_clip_summary(c, i) if tr.get("kind", "video") == "video"
                 else {"index": i, "type": "audio", "start": c.get("start"),
                       "preview": c.get("path", "")[:48]}
                 for i, c in enumerate(tr.get("clips", []))]
        out.append({"track": tr.get("name"), "kind": tr.get("kind", "video"),
                    "clips": clips})
    return {"tracks": out}


@mcp.tool()
def update_clip(project_id: str, track: str, clip_index: int, patch: dict) -> dict:
    """Edit ONE clip in place by deep-merging ``patch`` into it — change only
    what you pass, everything else is preserved. Examples:
      patch={"start": 4.0, "duration": 3.0}                  # retime
      patch={"transform": {"position": [800, 300]}}          # move
      patch={"element": {"text": "new text", "color": "#f00"}}  # edit content
      patch={"effects": [{"type": "glow", "intensity": 0.5}]} # replace effects
    Lists (e.g. effects) are replaced; nested dicts are merged. Pass a key with
    null to delete it."""
    spec = _proj(project_id)
    tr = _find_track(spec, track)
    clips = tr.get("clips", [])
    if not -len(clips) <= clip_index < len(clips):
        raise ValueError(f"clip_index {clip_index} out of range (0..{len(clips)-1})")
    _deep_merge(clips[clip_index], patch)
    _commit(project_id, spec)
    return {"ok": True, "clip": clips[clip_index]}


@mcp.tool()
def remove_clip(project_id: str, track: str, clip_index: int) -> dict:
    """Delete one clip from a track. Other clips are untouched."""
    spec = _proj(project_id)
    tr = _find_track(spec, track)
    removed = tr["clips"].pop(clip_index)
    _commit(project_id, spec)
    return {"ok": True, "removed": _clip_summary(removed, clip_index),
            "remaining": len(tr["clips"])}


@mcp.tool()
def move_clip(project_id: str, track: str, clip_index: int,
              start: Optional[float] = None, duration: Optional[float] = None,
              to_track: Optional[str] = None) -> dict:
    """Retime a clip (set start/duration) and/or move it to another video
    track, without altering its content."""
    spec = _proj(project_id)
    tr = _find_track(spec, track)
    clip = tr["clips"][clip_index]
    if start is not None:
        clip["start"] = start
    if duration is not None:
        clip["duration"] = duration
    if to_track is not None and to_track != track:
        tr["clips"].pop(clip_index)
        _find_track(spec, to_track)["clips"].append(clip)
    _commit(project_id, spec)
    return {"ok": True, "clip": _clip_summary(clip, clip_index)}
