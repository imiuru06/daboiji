"""Audio mixing intent tools: automatic music ducking under narration.

``add_audio`` gives per-clip gain and head/tail fades — enough to place a
track, not enough to *mix* one. The recurring creative need is "drop the music
while the voice-over is talking, bring it back after". ``duck_audio`` computes
that envelope deterministically from where the VO clips actually sit on the
timeline and stores it on the music clip; the mixer applies it at render time.
No sidechain graph to wire, no ML.
"""
from __future__ import annotations

import os
import re
import subprocess
from typing import List, Optional

from .app import mcp, _proj, _commit

__all__ = ["duck_audio", "clear_ducking"]

_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def _audio_tracks(spec: dict):
    return [tr for tr in spec.get("tracks", []) if tr.get("kind") == "audio"]


def _all_audio_clips(spec: dict):
    return [c for tr in _audio_tracks(spec) for c in tr.get("clips", [])]


def _probe_duration(path: str) -> Optional[float]:
    """Best-effort media duration (seconds) via ffmpeg; None if unknown."""
    try:
        from ..render.encoder import ffmpeg_exe
        out = subprocess.run([ffmpeg_exe(), "-i", path], capture_output=True,
                             text=True).stderr
        m = _DUR_RE.search(out)
        if m:
            h, mm, s = m.groups()
            return int(h) * 3600 + int(mm) * 60 + float(s)
    except Exception:  # noqa: BLE001
        pass
    return None


def _span(clip) -> Optional[List[float]]:
    """[start, end] for an audio clip, probing the file when duration is None."""
    start = float(clip.get("start", 0.0))
    dur = clip.get("duration")
    if dur is None:
        path = clip.get("path")
        probed = _probe_duration(path) if path and os.path.exists(path) else None
        if probed is None:
            return None
        dur = max(0.0, probed - float(clip.get("in_point", 0.0)))
    return [start, start + float(dur)]


def _merge(windows: List[List[float]], gap: float = 0.3) -> List[List[float]]:
    """Sort and merge windows that overlap or sit within ``gap`` seconds."""
    if not windows:
        return []
    windows = sorted(windows)
    out = [list(windows[0])]
    for a, b in windows[1:]:
        if a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


@mcp.tool()
def duck_audio(project_id: str, music_clip_id: Optional[str] = None,
               under: Optional[List[str]] = None, amount_db: float = -12.0,
               attack: float = 0.25, release: float = 0.6) -> dict:
    """Auto-duck a music track beneath voice-over / SFX (creative mix unit).

    Computes where the ``under`` clips play and writes a ducking envelope onto
    the music clip: full level, dipping by ``amount_db`` (negative = quieter)
    whenever a VO clip is speaking, with ``attack``/``release`` ramps in and
    out. Windows are read from the clips' real timeline spans (durations are
    probed from the files when not set), so it stays in sync with the edit.

    music_clip_id: the music/bed to duck. Default = the longest audio clip.
    under: audio clip_ids to duck beneath. Default = every OTHER audio clip
      (treated as narration/SFX).
    Re-run after moving VO to recompute; ``clear_ducking`` removes it."""
    spec = _proj(project_id)
    clips = _all_audio_clips(spec)
    if not clips:
        raise ValueError("project has no audio clips; add music + voiceover first")

    by_id = {c.get("id"): c for c in clips if c.get("id")}

    # resolve the music clip
    if music_clip_id:
        music = by_id.get(music_clip_id)
        if music is None:
            raise ValueError(f"music_clip_id {music_clip_id!r} not found")
    else:
        spans = [(c, _span(c)) for c in clips]
        rated = [(sp[1] - sp[0], c) for c, sp in spans if sp]
        if not rated:
            raise ValueError("could not determine any audio clip duration")
        music = max(rated, key=lambda r: r[0])[1]

    # resolve the under (key) clips
    if under:
        key_clips = [by_id[i] for i in under if i in by_id]
    else:
        key_clips = [c for c in clips if c is not music]
    if not key_clips:
        raise ValueError("no VO/SFX clips to duck under")

    windows, skipped = [], 0
    for c in key_clips:
        sp = _span(c)
        if sp is None:
            skipped += 1
            continue
        windows.append(sp)
    windows = _merge(windows)
    if not windows:
        raise ValueError(
            "could not resolve any VO timing (durations unknown); "
            "set duration on the VO clips or render after synthesis")

    music["duck"] = {"windows": windows, "amount_db": amount_db,
                     "attack": attack, "release": release}
    _commit(project_id, spec)
    return {"ok": True, "music_clip_id": music.get("id"),
            "windows": windows, "amount_db": amount_db,
            "attack": attack, "release": release, "skipped": skipped}


@mcp.tool()
def clear_ducking(project_id: str, music_clip_id: Optional[str] = None) -> dict:
    """Remove ducking envelopes (restore flat music level).

    Clears the ``duck`` envelope from ``music_clip_id``, or from every audio
    clip when omitted."""
    spec = _proj(project_id)
    cleared = 0
    for c in _all_audio_clips(spec):
        if music_clip_id and c.get("id") != music_clip_id:
            continue
        if c.pop("duck", None) is not None:
            cleared += 1
    _commit(project_id, spec)
    return {"ok": True, "cleared": cleared}
