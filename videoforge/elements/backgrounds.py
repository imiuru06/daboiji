"""Solid and gradient background/fill elements."""
from __future__ import annotations

import numpy as np

from ..core.keyframe import AnimatedProperty
from ..core.types import Color
from ..render.compositor import new_canvas
from ..render.context import RenderContext
from .base import Element, register


@register("solid")
class Solid(Element):
    def __init__(self, color="#000000", size=None):
        self.color = AnimatedProperty.coerce(color)
        self.size = size  # (w, h) or None -> canvas

    def natural_size(self, ctx):
        return tuple(self.size) if self.size else ctx.size

    def render(self, ctx: RenderContext, t: float) -> np.ndarray:
        w, h = self.natural_size(ctx)
        col = Color.parse(self.color.at(t))
        return new_canvas(w, h, col.rgba)

    @classmethod
    def from_spec(cls, spec):
        return cls(color=spec.get("color", "#000000"), size=spec.get("size"))


@register("gradient")
class Gradient(Element):
    """Linear or radial gradient between an ordered list of color stops."""

    def __init__(self, stops, kind="linear", angle=90.0, size=None, center=(0.5, 0.5), radius=0.75):
        # stops: list of (offset[0..1], color)
        self.stops = [(float(o), Color.parse(c)) for o, c in stops]
        self.stops.sort(key=lambda s: s[0])
        self.kind = kind
        self.angle = AnimatedProperty.coerce(angle)
        self.size = size
        self.center = center
        self.radius = radius

    def natural_size(self, ctx):
        return tuple(self.size) if self.size else ctx.size

    def _ramp(self, tcoord: np.ndarray) -> np.ndarray:
        offs = np.array([s[0] for s in self.stops])
        cols = np.array([s[1].rgba for s in self.stops], dtype=np.float32)
        out = np.empty(tcoord.shape + (4,), dtype=np.float32)
        for ch in range(4):
            out[..., ch] = np.interp(tcoord, offs, cols[:, ch])
        return out

    def render(self, ctx: RenderContext, t: float) -> np.ndarray:
        w, h = self.natural_size(ctx)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        nx, ny = xx / max(w - 1, 1), yy / max(h - 1, 1)
        if self.kind == "radial":
            cx, cy = self.center
            d = np.sqrt(((nx - cx) * (w / max(h, 1))) ** 2 + (ny - cy) ** 2)
            tcoord = np.clip(d / max(self.radius, 1e-4), 0.0, 1.0)
        else:
            ang = np.deg2rad(float(self.angle.at(t)))
            proj = np.cos(ang) * nx + np.sin(ang) * ny
            lo, hi = proj.min(), proj.max()
            tcoord = (proj - lo) / max(hi - lo, 1e-6)
        return self._ramp(tcoord)

    @classmethod
    def from_spec(cls, spec):
        return cls(
            stops=spec["stops"],
            kind=spec.get("kind", "linear"),
            angle=spec.get("angle", 90.0),
            size=spec.get("size"),
            center=tuple(spec.get("center", (0.5, 0.5))),
            radius=spec.get("radius", 0.75),
        )
