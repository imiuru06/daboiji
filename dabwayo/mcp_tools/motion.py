"""Per-clip motion presets — the clip-level twin of ``camera_move``.

``camera_move`` names moves for the *whole* composition; a single clip still
had only raw ``transform`` keyframes. ``animate_clip`` closes that asymmetry:
name an idle/emphasis motion (a logo that gently floats, a badge that pulses,
an impact shake) and dabwayo compiles it to keyframes on that clip's own
transform — oscillating around whatever position/scale/rotation it already
has. Pure keyframe math over the existing transform; no new engine feature,
no ML.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from ..core.presets import MOTION_PRESETS as _MOTION_PRESETS
from .app import mcp, _proj, _commit, _resolve_clip

__all__ = ["animate_clip"]


def _base_position(clip: dict, w: float, h: float) -> List[float]:
    p = (clip.get("transform") or {}).get("position")
    if isinstance(p, dict) and p.get("keyframes"):
        p = p["keyframes"][0]["value"]          # oscillate around the first key
    if isinstance(p, (list, tuple)) and len(p) == 2:
        return [float(p[0]), float(p[1])]
    return [w / 2.0, h / 2.0]


def _base_scalar(clip: dict, field: str, default: float) -> float:
    v = (clip.get("transform") or {}).get(field)
    if isinstance(v, dict) and v.get("keyframes"):
        v = v["keyframes"][0]["value"]
    if isinstance(v, (list, tuple)):
        v = v[0]
    return float(v) if isinstance(v, (int, float)) else default


def _osc_vec(base: List[float], ax: float, ay: float, cycles: float,
             duration: float, phase_y: float = 0.0) -> dict:
    """Keyframed [x,y] oscillating sinusoidally around ``base`` (8 keys/cycle)."""
    steps = max(4, int(round(cycles * 8)))
    seg = duration / steps
    kfs = []
    for k in range(steps + 1):
        ang = 2 * math.pi * cycles * (k / steps)
        x = base[0] + ax * math.sin(ang)
        y = base[1] + ay * math.sin(ang + phase_y)
        kfs.append({"time": round(k * seg, 4), "value": [round(x, 2), round(y, 2)],
                    "easing": "linear" if k == 0 else "ease_in_out_sine"})
    return {"keyframes": kfs}


def _osc_scalar(base: float, delta: float, cycles: float, duration: float) -> dict:
    """Keyframed scalar oscillating around ``base`` by ±``delta``."""
    steps = max(4, int(round(cycles * 8)))
    seg = duration / steps
    kfs = []
    for k in range(steps + 1):
        ang = 2 * math.pi * cycles * (k / steps)
        kfs.append({"time": round(k * seg, 4),
                    "value": round(base + delta * math.sin(ang), 4),
                    "easing": "linear" if k == 0 else "ease_in_out_sine"})
    return {"keyframes": kfs}


@mcp.tool()
def animate_clip(project_id: str, preset: str, clip_id: Optional[str] = None,
                 clip_index: Optional[int] = None, track: Optional[str] = None,
                 amount: Optional[float] = None, cycles: Optional[float] = None,
                 duration: Optional[float] = None, loops: float = 1.0) -> dict:
    """Apply a NAMED motion preset to one clip, compiled to transform keyframes.

    The clip-level counterpart to ``camera_move``: say what the clip *does* and
    dabwayo animates its own transform, oscillating around the position/scale/
    rotation it already has (the raw escape hatch is ``update_clip`` transform
    keyframes).

    presets:
      float   — gentle vertical bob (idle life on a still). ``amount`` px (14).
      drift   — slow circular drift (organic idle for i2v stills). ``amount`` px.
      sway    — rock back and forth. ``amount`` degrees (3).
      pulse   — scale throb for emphasis. ``amount`` scale delta (0.06).
      breathe — very slow, subtle scale swell. ``amount`` (0.02).
      spin    — continuous rotation; ``loops`` full turns over the clip.
      pop     — one-shot entrance: scale overshoot in (ease-out-back).
      shake   — one-shot impact jitter that decays. ``amount`` px (12).

    ``cycles`` sets how many oscillations over ``duration`` (defaults per
    preset). ``duration`` defaults to the whole clip. Target with ``clip_id``
    (preferred) or ``track`` + ``clip_index``."""
    spec = _proj(project_id)
    w = float(spec.get("width", 1920))
    h = float(spec.get("height", 1080))
    tr, idx = _resolve_clip(spec, track, clip_index, clip_id)
    clip = tr["clips"][idx]
    dur = float(duration if duration is not None else clip.get("duration", 5.0))
    t = clip.setdefault("transform", {})

    if preset == "float":
        A = 14.0 if amount is None else float(amount)
        n = cycles if cycles is not None else max(1.0, dur / 2.0)
        t["position"] = _osc_vec(_base_position(clip, w, h), 0.0, A, n, dur)

    elif preset == "drift":
        A = 10.0 if amount is None else float(amount)
        n = cycles if cycles is not None else max(1.0, dur / 4.0)
        t["position"] = _osc_vec(_base_position(clip, w, h), A, A, n, dur,
                                 phase_y=math.pi / 2)   # circular idle

    elif preset == "sway":
        A = 3.0 if amount is None else float(amount)
        n = cycles if cycles is not None else max(1.0, dur / 2.5)
        t["rotation"] = _osc_scalar(_base_scalar(clip, "rotation", 0.0), A, n, dur)

    elif preset == "pulse":
        A = 0.06 if amount is None else float(amount)
        n = cycles if cycles is not None else max(1.0, dur / 0.9)
        t["scale"] = _osc_scalar(_base_scalar(clip, "scale", 1.0), A, n, dur)

    elif preset == "breathe":
        A = 0.02 if amount is None else float(amount)
        n = cycles if cycles is not None else max(1.0, dur / 3.5)
        t["scale"] = _osc_scalar(_base_scalar(clip, "scale", 1.0), A, n, dur)

    elif preset == "spin":
        base = _base_scalar(clip, "rotation", 0.0)
        t["rotation"] = {"keyframes": [
            {"time": 0.0, "value": round(base, 4), "easing": "linear"},
            {"time": round(dur, 4), "value": round(base + 360.0 * loops, 4),
             "easing": "linear"}]}

    elif preset == "pop":
        base = _base_scalar(clip, "scale", 1.0)
        d = min(dur, 0.5 if duration is None else dur)
        t["scale"] = {"keyframes": [
            {"time": 0.0, "value": round(base * 0.6, 4), "easing": "linear"},
            {"time": round(d * 0.7, 4), "value": round(base * 1.08, 4),
             "easing": "ease_out_back"},
            {"time": round(d, 4), "value": round(base, 4), "easing": "ease_out_cubic"}]}

    elif preset == "shake":
        A = 12.0 if amount is None else float(amount)
        base = _base_position(clip, w, h)
        d = min(dur, 0.5 if duration is None else dur)
        # fixed decaying jitter pattern -> deterministic + reproducible
        pat = [(1, -1), (-1, 1), (1, 1), (-1, -1), (1, 0), (0, 1), (-1, 0), (0, -1)]
        steps = len(pat)
        seg = d / steps
        kfs = [{"time": 0.0, "value": [round(base[0], 2), round(base[1], 2)],
                "easing": "linear"}]
        for k, (sx, sy) in enumerate(pat, 1):
            decay = 1.0 - (k / (steps + 1))
            kfs.append({"time": round(k * seg, 4),
                        "value": [round(base[0] + sx * A * decay, 2),
                                  round(base[1] + sy * A * decay, 2)],
                        "easing": "ease_out_quad"})
        t["position"] = {"keyframes": kfs}

    else:
        raise ValueError(
            f"Unknown preset {preset!r}. Available: {', '.join(_MOTION_PRESETS)}")

    _commit(project_id, spec)
    return {"ok": True, "preset": preset, "clip_id": clip.get("id", ""),
            "duration": dur}
