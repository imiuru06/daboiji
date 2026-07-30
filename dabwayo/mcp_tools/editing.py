"""Clip editing tools: inspect, retime, patch, move and remove existing clips.

Every clip carries a stable ``id`` (assigned by the authoring tools). The edit
tools accept that ``clip_id`` (preferred — it survives reordering/deletion of
other clips) or the legacy ``(track, clip_index)`` pair, kept for backward
compatibility with the Studio REST layer and older callers."""
from __future__ import annotations

import copy
from typing import Optional

from .app import (mcp, _proj, _commit, _deep_merge, _find_track,
                  _clip_summary, _resolve_clip, _new_clip_id)

__all__ = ["list_clips", "update_clip", "remove_clip", "move_clip",
           "split_clip", "trim_clip", "duplicate_clip", "ripple_delete"]


def _ripple_shift(track: dict, threshold: float, delta: float,
                  exclude_id: Optional[str] = None) -> int:
    """Shift every clip on ``track`` that starts at/after ``threshold`` by
    ``delta`` seconds (clamped at 0). Used to open/close gaps so downstream
    clips stay adjacent. Ordering is by time, not list position, so it is
    robust to unsorted clip lists. Returns how many clips moved."""
    if not delta:
        return 0
    n = 0
    for c in track.get("clips", []):
        if exclude_id and c.get("id") == exclude_id:
            continue
        if float(c.get("start", 0.0)) >= threshold - 1e-9:
            c["start"] = max(0.0, float(c.get("start", 0.0)) + delta)
            n += 1
    return n


def _shift_source_inpoint(clip: dict, delta_timeline: float) -> None:
    """Advance a clip's *source* in-point so the same media frames stay aligned
    when its head moves by ``delta_timeline`` seconds on the timeline. Video
    consumes source at ``speed``; audio 1:1. Images/solids have no source time."""
    el = clip.get("element")
    if el is not None:
        if el.get("type") == "video":
            el["start"] = max(0.0, el.get("start", 0.0) + delta_timeline * el.get("speed", 1.0))
    elif "in_point" in clip:            # audio clip
        clip["in_point"] = max(0.0, clip.get("in_point", 0.0) + delta_timeline)


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


@mcp.tool()
def trim_clip(project_id: str, clip_id: Optional[str] = None,
              track: Optional[str] = None, clip_index: Optional[int] = None,
              new_start: Optional[float] = None,
              new_end: Optional[float] = None, ripple: bool = False) -> dict:
    """Trim a clip's edges on the timeline (like dragging its left/right handle).

    Target it with ``clip_id`` (preferred) or ``track`` + ``clip_index``.
    ``new_start`` / ``new_end`` are absolute timeline seconds; pass either or
    both (the one you omit is left where it is). By default this only changes
    this clip (leaving any gap); set ``ripple`` to also slide every later clip
    on the same track by the change in this clip's END, so they stay adjacent.

    Media stays in sync: moving the head (new_start) advances the clip's *source*
    in-point by the same amount (times its speed for video), so the surviving
    frames are the same ones — you cut media off the front, you don't shift it.
    Moving only the tail (new_end) just changes duration. (Video/audio source is
    frame-accurate; a per-clip *keyframed* transform is evaluated at local clip
    time, so a head trim shifts that animation.)"""
    spec = _proj(project_id)
    tr, idx = _resolve_clip(spec, track, clip_index, clip_id)
    clip = tr["clips"][idx]
    old_start = float(clip.get("start", 0.0))
    old_end = old_start + float(clip.get("duration", 0.0))
    ns = old_start if new_start is None else float(new_start)
    ne = old_end if new_end is None else float(new_end)
    if ns < 0:
        raise ValueError("new_start must be >= 0")
    if ne <= ns:
        raise ValueError(f"new_end ({ne}) must be greater than new_start ({ns})")
    head_delta = ns - old_start
    if head_delta:
        _shift_source_inpoint(clip, head_delta)
    clip["start"] = ns
    clip["duration"] = ne - ns
    rippled = _ripple_shift(tr, old_end, ne - old_end, exclude_id=clip.get("id")) if ripple else 0
    _commit(project_id, spec)
    return {"ok": True, "clip": _clip_summary(clip, idx), "rippled": rippled}


@mcp.tool()
def duplicate_clip(project_id: str, clip_id: Optional[str] = None,
                   track: Optional[str] = None, clip_index: Optional[int] = None,
                   start: Optional[float] = None, ripple: bool = False) -> dict:
    """Duplicate a clip (content, transform, effects and source in-point are
    copied exactly) and drop the copy on the same track with a NEW id.

    Target the source with ``clip_id`` (preferred) or ``track`` + ``clip_index``.
    The copy is placed at ``start`` (absolute seconds) or, by default, right
    after the original. Set ``ripple`` to push every later clip on the track
    right by the copy's duration first, so the copy is inserted into the flow
    instead of overlapping what follows. Returns the new clip's id."""
    spec = _proj(project_id)
    tr, idx = _resolve_clip(spec, track, clip_index, clip_id)
    orig = tr["clips"][idx]
    dup = copy.deepcopy(orig)
    dup["id"] = _new_clip_id()
    dur = float(orig.get("duration", 0.0))
    dup["start"] = (float(orig.get("start", 0.0)) + dur) if start is None else float(start)
    rippled = _ripple_shift(tr, dup["start"], dur, exclude_id=orig.get("id")) if ripple else 0
    tr["clips"].insert(idx + 1, dup)
    _commit(project_id, spec)
    return {"ok": True, "source_id": orig.get("id", ""), "clip_id": dup["id"],
            "track": tr.get("name"), "start": dup["start"], "rippled": rippled}


@mcp.tool()
def ripple_delete(project_id: str, clip_id: Optional[str] = None,
                  track: Optional[str] = None, clip_index: Optional[int] = None) -> dict:
    """Delete a clip AND close the gap: every later clip on the same track slides
    left by the removed clip's duration, so the timeline stays gapless.

    Target it with ``clip_id`` (preferred) or ``track`` + ``clip_index``. (Use
    ``remove_clip`` instead if you want to leave the gap in place.)"""
    spec = _proj(project_id)
    tr, idx = _resolve_clip(spec, track, clip_index, clip_id)
    removed = tr["clips"].pop(idx)
    gap = float(removed.get("duration", 0.0))
    removed_end = float(removed.get("start", 0.0)) + gap
    rippled = _ripple_shift(tr, removed_end, -gap)
    _commit(project_id, spec)
    return {"ok": True, "removed": _clip_summary(removed, idx),
            "remaining": len(tr["clips"]), "rippled": rippled}


@mcp.tool()
def split_clip(project_id: str, at: float, clip_id: Optional[str] = None,
               track: Optional[str] = None, clip_index: Optional[int] = None) -> dict:
    """Split one clip into two at ``at`` (absolute timeline seconds), which must
    fall strictly inside the clip. Target it with ``clip_id`` (preferred) or
    ``track`` + ``clip_index``.

    The left piece keeps the original id and its ``transition_in``; the right
    piece gets a NEW id, keeps the original ``transition_out``, and is inserted
    right after. For video/audio the right piece's *source* in-point is advanced
    so playback continues seamlessly across the cut (no repeated/skipped frames).
    Effects and transform are copied to both pieces; a per-clip *keyframed*
    transform restarts on the right piece (it is evaluated at local clip time).
    Returns both clip ids."""
    spec = _proj(project_id)
    tr, idx = _resolve_clip(spec, track, clip_index, clip_id)
    left = tr["clips"][idx]
    start = float(left.get("start", 0.0))
    dur = float(left.get("duration", 0.0))
    end = start + dur
    if not (start < at < end):
        raise ValueError(f"split time {at} must be strictly inside the clip "
                         f"[{start}, {end}]")
    left_dur = at - start
    right = copy.deepcopy(left)
    right["id"] = _new_clip_id()
    # retime the two halves
    left["duration"] = left_dur
    right["start"] = at
    right["duration"] = end - at
    # keep the right piece's media in sync from the cut point
    _shift_source_inpoint(right, left_dur)
    # transitions belong to the outer edges only; the seam is a hard cut
    left.pop("transition_out", None)
    right.pop("transition_in", None)
    tr["clips"].insert(idx + 1, right)
    _commit(project_id, spec)
    return {"ok": True, "at": at, "track": tr.get("name"),
            "left_id": left["id"], "right_id": right["id"],
            "left": _clip_summary(left, idx),
            "right": _clip_summary(right, idx + 1)}
