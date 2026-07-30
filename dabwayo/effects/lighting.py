"""Lighting effects: point/radial lights, ambient, light leaks.

These approximate cinematic lighting in 2D compositing space. Lights are
additive/screen-blended radial sources with color, intensity and falloff.
Positions are normalized [0,1] across the frame and may be animated.
"""
from __future__ import annotations

import numpy as np

from ..core.keyframe import AnimatedProperty
from ..core.types import Color
from ..render.grids import mesh
from .base import Effect, register


def _radial_mask(w, h, cx, cy, radius, falloff):
    yy, xx = mesh(w, h)
    aspect = w / max(h, 1)
    d = np.sqrt(((xx / w - cx) * aspect) ** 2 + (yy / h - cy) ** 2)
    r = max(radius, 1e-4)
    m = np.clip(1.0 - d / r, 0.0, 1.0)
    return m ** max(falloff, 1e-3)


@register("light")
class Light(Effect):
    """A single radial light source.

    Params: position [x,y] in 0..1 (animatable), color, intensity,
    radius (0..1.5), falloff (1=linear,>1 tighter), mode (add|screen).
    """

    def __init__(self, **params):
        self.position = AnimatedProperty.coerce(params.pop("position", [0.5, 0.3]))
        super().__init__(**params)

    def apply(self, img, ctx, t):
        h, w = img.shape[:2]
        pos = self.position.at(t)
        col = np.array(Color.parse(self.p("color", t, "#ffffff")).rgb, np.float32)
        intensity = float(self.p("intensity", t, 0.8))
        radius = float(self.p("radius", t, 0.6))
        falloff = float(self.p("falloff", t, 2.0))
        mode = self.p("mode", t, "screen")
        m = _radial_mask(w, h, float(pos[0]), float(pos[1]), radius, falloff)[..., None]
        light = m * col[None, None, :] * intensity
        out = img.copy()
        if mode == "add":
            out[..., :3] = np.clip(out[..., :3] + light, 0, 1)
        else:  # screen
            out[..., :3] = 1.0 - (1.0 - out[..., :3]) * (1.0 - np.clip(light, 0, 1))
        return out


@register("ambient")
class Ambient(Effect):
    """Uniform ambient tint/fill light."""

    def apply(self, img, ctx, t):
        col = np.array(Color.parse(self.p("color", t, "#1a2240")).rgb, np.float32)
        intensity = float(self.p("intensity", t, 0.15))
        out = img.copy()
        out[..., :3] = np.clip(out[..., :3] + col[None, None, :] * intensity, 0, 1)
        return out


@register("light_leak")
class LightLeak(Effect):
    """Animated diagonal light leak sweeping across the frame."""

    def apply(self, img, ctx, t):
        h, w = img.shape[:2]
        col = np.array(Color.parse(self.p("color", t, "#ff9a3c")).rgb, np.float32)
        intensity = float(self.p("intensity", t, 0.4))
        pos = float(self.p("position", t, 0.5))   # 0..1 sweep position
        width = float(self.p("width", t, 0.3))
        yy, xx = mesh(w, h)
        diag = (xx / w + yy / h) / 2.0
        m = np.exp(-((diag - pos) ** 2) / (2 * max(width, 1e-3) ** 2))[..., None]
        light = m * col[None, None, :] * intensity
        out = img.copy()
        out[..., :3] = 1.0 - (1.0 - out[..., :3]) * (1.0 - np.clip(light, 0, 1))
        return out
