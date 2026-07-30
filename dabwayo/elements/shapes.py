"""Vector shape elements (rect, rounded-rect, ellipse, line) via Pillow."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from ..core.types import Color
from ..render.context import RenderContext
from .base import Element, register

_SS = 2  # supersampling factor for anti-aliased edges


def _to_rgba_float(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("RGBA"), dtype=np.float32) / 255.0


@register("shape")
class Shape(Element):
    def __init__(self, shape="rect", size=(200, 200), fill="#ffffff",
                 stroke=None, stroke_width=0, radius=0):
        self.shape = shape
        self.size = tuple(size)
        self.fill = Color.parse(fill) if fill is not None else None
        self.stroke = Color.parse(stroke) if stroke else None
        self.stroke_width = int(stroke_width)
        self.radius = int(radius)

    def natural_size(self, ctx):
        return self.size

    def render(self, ctx: RenderContext, t: float) -> np.ndarray:
        w, h = self.size
        W, H = w * _SS, h * _SS
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        fill = self.fill.to_uint8() if self.fill else None
        stroke = self.stroke.to_uint8() if self.stroke else None
        sw = self.stroke_width * _SS
        pad = sw // 2 + 1
        box = [pad, pad, W - pad, H - pad]
        if self.shape in ("rect", "rounded_rect"):
            r = self.radius * _SS
            if r > 0:
                d.rounded_rectangle(box, radius=r, fill=fill, outline=stroke, width=sw)
            else:
                d.rectangle(box, fill=fill, outline=stroke, width=sw)
        elif self.shape in ("ellipse", "circle"):
            d.ellipse(box, fill=fill, outline=stroke, width=sw)
        elif self.shape == "line":
            d.line([pad, H // 2, W - pad, H // 2], fill=fill or stroke, width=max(sw, _SS))
        else:
            d.rectangle(box, fill=fill, outline=stroke, width=sw)
        img = img.resize((w, h), Image.LANCZOS)
        return _to_rgba_float(img)

    @classmethod
    def from_spec(cls, spec):
        return cls(
            shape=spec.get("shape", "rect"),
            size=tuple(spec.get("size", (200, 200))),
            fill=spec.get("fill", "#ffffff"),
            stroke=spec.get("stroke"),
            stroke_width=spec.get("stroke_width", 0),
            radius=spec.get("radius", 0),
        )
