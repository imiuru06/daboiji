"""Intent-level camera & focus tools.

These sit one altitude above the raw keyframe math of ``set_camera`` /
``add_effect``: the calling agent names a *creative* move ("push in", "rack
focus to the subject") and dabwayo compiles it deterministically into the
existing primitives — camera pan/zoom/rotation keyframes and per-clip blur.
No ML, no new engine feature: just a well-named wrapper over what the engine
already does.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.presets import CAMERA_PRESETS as _CAMERA_PRESETS
from .app import mcp, _proj, _commit, _resolve_clip

__all__ = ["camera_move", "set_focus"]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _timeline_end(spec: dict) -> float:
    """Best estimate of the composition's end time (seconds)."""
    end = 0.0
    for tr in spec.get("tracks", []):
        if tr.get("kind", "video") != "video":
            continue
        for c in tr.get("clips", []):
            end = max(end, float(c.get("start", 0.0)) + float(c.get("duration", 0.0)))
    if end <= 0.0:
        end = float(spec.get("duration") or 5.0)
    return end


def _kf(t0: float, v0, t1: float, v1, easing: str) -> dict:
    """A two-keyframe animated property (hold v0 until t0, ease to v1 by t1).

    The first keyframe's easing is irrelevant (value is held before it), so it
    is linear; ``easing`` shapes the approach to the second keyframe."""
    return {"keyframes": [
        {"time": round(t0, 4), "value": v0, "easing": "linear"},
        {"time": round(t1, 4), "value": v1, "easing": easing},
    ]}


@mcp.tool()
def camera_move(project_id: str, preset: str, amount: Optional[float] = None,
                duration: Optional[float] = None, start: float = 0.0,
                easing: Optional[str] = None,
                direction: Optional[str] = None) -> dict:
    """Apply a NAMED camera move, compiled to keyframes on the virtual camera.

    This is the agent-friendly way to move the camera: say *what* the shot
    does and dabwayo writes the pan/zoom/rotation keyframes for you (the raw
    escape hatch is still ``set_camera``). Moves COMPOSE — call it twice
    (e.g. push_in then pan_right) and both channels animate together.

    presets:
      push_in / pull_out  — dolly/zoom on the frame (``amount`` = zoom delta,
                            default 0.12).
      pan_left/right/up/down — glide the frame (``amount`` = px, default 8%
                            of the canvas along that axis).
      tilt / dutch        — rotate the horizon (``amount`` = degrees, default 5).
      whip_pan            — fast directional pan (needs ``direction``); snappy
                            easing, short default ``duration`` (0.4s).
      ken_burns           — slow zoom + drift for stills/i2v (``direction``
                            sets the drift; default up-left).
      hold                — clear any camera move (lock off).

    ``duration`` defaults to the whole timeline from ``start``. ``easing``
    defaults to a natural ease_in_out (whip_pan uses ease_in_out_expo).
    Give clips a ``depth`` (add_clip) for parallax during the move."""
    spec = _proj(project_id)
    w = int(spec.get("width", 1920))
    h = int(spec.get("height", 1080))
    end = _timeline_end(spec)
    if duration is None:
        duration = max(0.1, end - start)
    t0, t1 = start, start + duration
    ez = easing or "ease_in_out"
    dir_ = (direction or "").lower()

    cam: Dict[str, Any] = dict(spec.get("camera") or {})

    if preset == "hold":
        spec["camera"] = {}
        _commit(project_id, spec)
        return {"ok": True, "preset": preset, "camera": {}}

    if preset in ("push_in", "pull_out"):
        amt = 0.12 if amount is None else float(amount)
        z0, z1 = (1.0, 1.0 + amt) if preset == "push_in" else (1.0 + amt, 1.0)
        cam["zoom"] = _kf(t0, z0, t1, z1, ez)

    elif preset in ("pan_left", "pan_right", "pan_up", "pan_down"):
        horiz = preset in ("pan_left", "pan_right")
        amt = (0.08 * (w if horiz else h)) if amount is None else float(amount)
        sign = {"pan_right": 1, "pan_left": -1, "pan_down": 1, "pan_up": -1}[preset]
        if horiz:
            cam["pan"] = _kf(t0, [0.0, 0.0], t1, [sign * amt, 0.0], ez)
        else:
            cam["pan"] = _kf(t0, [0.0, 0.0], t1, [0.0, sign * amt], ez)

    elif preset in ("tilt", "dutch"):
        amt = 5.0 if amount is None else float(amount)
        cam["rotation"] = _kf(t0, 0.0, t1, amt, ez)

    elif preset == "whip_pan":
        if duration == max(0.1, end - start):   # user didn't set one -> snappy
            duration = 0.4
            t1 = start + duration
        d = dir_ or "right"
        amt = (0.5 * (w if d in ("left", "right") else h)) if amount is None else float(amount)
        ez = easing or "ease_in_out_expo"
        vec = {"right": [amt, 0.0], "left": [-amt, 0.0],
               "down": [0.0, amt], "up": [0.0, -amt]}.get(d, [amt, 0.0])
        cam["pan"] = _kf(t0, [0.0, 0.0], t1, vec, ez)

    elif preset == "ken_burns":
        amt = 0.12 if amount is None else float(amount)
        cam["zoom"] = _kf(t0, 1.0, t1, 1.0 + amt, easing or "ease_in_out")
        d = dir_ or "up_left"
        dx = 0.06 * w
        dy = 0.06 * h
        drift = {
            "up_left": [-dx, -dy], "up_right": [dx, -dy],
            "down_left": [-dx, dy], "down_right": [dx, dy],
            "left": [-dx, 0.0], "right": [dx, 0.0],
            "up": [0.0, -dy], "down": [0.0, dy],
        }.get(d, [-dx, -dy])
        cam["pan"] = _kf(t0, [0.0, 0.0], t1, drift, easing or "ease_in_out")

    else:
        raise ValueError(
            f"Unknown preset {preset!r}. Available: {', '.join(_CAMERA_PRESETS)}")

    spec["camera"] = cam
    _commit(project_id, spec)
    return {"ok": True, "preset": preset, "start": t0, "duration": duration,
            "camera": cam}


def _dof_radius(clip_depth: float, focus_depth: float, aperture: float,
                max_blur: float) -> float:
    """Blur radius for a clip given its depth vs the focus plane.

    Clips at the focus depth are sharp; distance from the focus plane (in
    depth units, 0..1) scales the blur by ``aperture`` up to ``max_blur``."""
    dist = abs(float(clip_depth) - float(focus_depth))
    return round(min(max_blur, aperture * max_blur * dist), 3)


@mcp.tool()
def set_focus(project_id: str, subject: Optional[object] = None,
              focus_depth: Optional[float] = None, aperture: float = 0.6,
              max_blur: float = 14.0, pull_to: Optional[object] = None,
              duration: float = 1.0, start: float = 0.0,
              track: Optional[str] = None) -> dict:
    """Set focus / depth-of-field across the composition (creative unit).

    Instead of hand-blurring each layer, name the focus plane and dabwayo
    computes a depth-of-field: clips at the focus depth stay sharp, and layers
    fall off into blur by how far their ``depth`` is from that plane. This is
    what makes a subject "pop" against a soft background.

    subject: the thing in focus — a clip_id (its ``depth`` becomes the focus
      plane and its position the camera focus point) or a ``[x,y]`` point, or
      omit and pass ``focus_depth`` directly.
    focus_depth: focus plane in depth units (1=foreground, 0=backdrop);
      inferred from ``subject`` when that is a clip.
    aperture: 0..1 shallow→deep DOF strength. max_blur: px cap for the
      farthest layer.
    pull_to: RACK FOCUS — a second clip_id / depth to shift focus TO over
      ``duration`` seconds from ``start`` (blur is keyframed per clip).

    Reuses the ``blur`` effect and the per-clip ``depth`` you already set; give
    foreground/background clips distinct depths for DOF to have anything to do.
    Call again to re-pull; ``subject=None, aperture=0`` clears it."""
    spec = _proj(project_id)

    def _resolve_plane(ref):
        """Return (focus_depth, focus_point_or_None) for a clip_id / point / depth."""
        if ref is None:
            return None, None
        if isinstance(ref, (list, tuple)) and len(ref) == 2:
            return None, [float(ref[0]), float(ref[1])]
        if isinstance(ref, (int, float)):
            return float(ref), None
        # treat as clip_id
        tr, idx = _resolve_clip(spec, None, None, str(ref))
        clip = tr["clips"][idx]
        d = float(clip.get("depth", 1.0))
        pos = (clip.get("transform") or {}).get("position")
        pt = pos if (isinstance(pos, (list, tuple)) and len(pos) == 2) else None
        return d, ([float(pt[0]), float(pt[1])] if pt else None)

    fd_from, point = _resolve_plane(subject)
    if focus_depth is not None:
        fd_from = float(focus_depth)
    if fd_from is None:
        fd_from = 1.0

    fd_to, _ = _resolve_plane(pull_to)
    rack = pull_to is not None and fd_to is not None

    # camera focus point (parallax pivot) if we could resolve one
    if point is not None:
        cam = dict(spec.get("camera") or {})
        cam["focus"] = point
        spec["camera"] = cam

    touched = 0
    for tr in spec.get("tracks", []):
        if tr.get("kind", "video") != "video":
            continue
        if track and tr.get("name") != track:
            continue
        for clip in tr.get("clips", []):
            depth = float(clip.get("depth", 1.0))
            r_from = _dof_radius(depth, fd_from, aperture, max_blur)
            fx_list = clip.setdefault("effects", [])
            # drop any DOF blur we injected before (idempotent re-focus)
            fx_list[:] = [f for f in fx_list if not f.get("_dof")]
            if rack:
                r_to = _dof_radius(depth, fd_to, aperture, max_blur)
                cs = float(clip.get("start", 0.0))
                lt0 = max(0.0, start - cs)
                lt1 = max(lt0 + 0.01, start + duration - cs)
                radius: Any = {"keyframes": [
                    {"time": round(lt0, 4), "value": r_from, "easing": "linear"},
                    {"time": round(lt1, 4), "value": r_to, "easing": "ease_in_out"},
                ]}
            else:
                radius = r_from
            if (not rack) and r_from <= 0.0:
                continue          # sharp layer, nothing to add
            fx_list.append({"type": "blur", "radius": radius, "_dof": True})
            touched += 1

    _commit(project_id, spec)
    return {"ok": True, "focus_depth": fd_from,
            "rack_to": fd_to if rack else None, "aperture": aperture,
            "clips_affected": touched}
