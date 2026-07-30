"""A 2.5D virtual camera over the composition.

The camera defines a viewing transform — pan (px), zoom and rotation — that
is applied to every clip as it is placed. Each clip has a ``depth`` in
[0, 1]: depth 1 reacts fully to the camera (foreground), depth 0 is locked
(a painted backdrop), and values between give parallax. This yields real
camera moves — push-ins, pans, dolly, whip-pans, dutch tilts — and layered
parallax, all keyframeable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .keyframe import AnimatedProperty


@dataclass
class Camera:
    pan: AnimatedProperty = field(default_factory=lambda: AnimatedProperty([0.0, 0.0]))
    zoom: AnimatedProperty = field(default_factory=lambda: AnimatedProperty(1.0))
    rotation: AnimatedProperty = field(default_factory=lambda: AnimatedProperty(0.0))
    focus: Optional[list] = None        # [x, y] focal point; None -> canvas center

    @staticmethod
    def from_spec(spec: Optional[dict]) -> Optional["Camera"]:
        if not spec:
            return None
        cam = Camera()
        if "pan" in spec:
            cam.pan = AnimatedProperty.coerce(spec["pan"])
        if "zoom" in spec:
            cam.zoom = AnimatedProperty.coerce(spec["zoom"])
        if "rotation" in spec:
            cam.rotation = AnimatedProperty.coerce(spec["rotation"])
        cam.focus = spec.get("focus")
        return cam

    def sample(self, t: float, canvas_w: int, canvas_h: int) -> dict:
        pan = self.pan.at(t)
        focus = self.focus or [canvas_w / 2.0, canvas_h / 2.0]
        return {
            "pan": (float(pan[0]), float(pan[1])),
            "zoom": float(self.zoom.at(t)),
            "rotation": float(self.rotation.at(t)),
            "focus": (float(focus[0]), float(focus[1])),
        }


def apply_camera(samp: dict, cam: dict, depth: float) -> dict:
    """Remap a clip's sampled transform through the camera at the given depth.

    depth 1 -> full camera reaction; depth 0 -> locked (parallax in between).
    """
    import math

    fx, fy = cam["focus"]
    z = 1.0 + (cam["zoom"] - 1.0) * depth
    rot = cam["rotation"] * depth
    panx, pany = cam["pan"][0] * depth, cam["pan"][1] * depth

    px, py = samp["position"]
    # translate into focus space, apply pan, zoom and rotation, translate back
    dx, dy = px - fx - panx, py - fy - pany
    if rot:
        th = math.radians(rot)
        cos, sin = math.cos(th), math.sin(th)
        dx, dy = cos * dx - sin * dy, sin * dx + cos * dy
    out = dict(samp)
    out["position"] = (fx + dx * z, fy + dy * z)
    out["scale"] = (samp["scale"][0] * z, samp["scale"][1] * z)
    out["rotation"] = samp["rotation"] + rot
    out["explicit_position"] = True
    return out
