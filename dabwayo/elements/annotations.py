"""Annotation elements: speech-bubble callouts for explainer/product videos."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from ..core.types import Color
from ..render.context import RenderContext
from .base import Element, register
from .text import _wrap

_SS = 2  # supersample for smooth edges


@register("callout")
class Callout(Element):
    """A rounded speech bubble with a pointer tail — for explainer overlays.

    The element renders the bubble sized to its text plus a triangular tail on
    one side. Position the clip so the tail tip lands on the feature you are
    pointing at (anchor defaults to the tail tip via ``tail_side``).

    Params: text, font, font_size, color (text), fill (bubble), stroke,
    stroke_width, radius, padding, max_width, tail_side
    (bottom/top/left/right), tail_size, tail_pos (0..1 along the side),
    align, line_spacing.
    """

    def __init__(self, text="", font="sans", font_size=34, color="#0b0e16",
                 fill="#ffffff", stroke=None, stroke_width=0, radius=18,
                 padding=22, max_width=520, tail_side="bottom", tail_size=28,
                 tail_pos=0.5, align="left", line_spacing=1.2):
        self.text = text
        self.font = font
        self.font_size = int(font_size)
        self.color = Color.parse(color)
        self.fill = Color.parse(fill)
        self.stroke = Color.parse(stroke) if stroke else None
        self.stroke_width = int(stroke_width)
        self.radius = int(radius)
        self.padding = int(padding)
        self.max_width = max_width
        self.tail_side = tail_side
        self.tail_size = int(tail_size)
        self.tail_pos = float(tail_pos)
        self.align = align
        self.line_spacing = line_spacing

    def _layout(self, ctx):
        font = ctx.load_font(self.font, self.font_size)
        probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        inner_w = (self.max_width - 2 * self.padding) if self.max_width else None
        lines = _wrap(probe, self.text, font, inner_w)
        asc, desc = font.getmetrics()
        line_h = int((asc + desc) * self.line_spacing)
        widths = [probe.textlength(ln, font=font) for ln in lines]
        text_w = int(max(widths) if widths else 1)
        text_h = int(line_h * len(lines))
        return font, lines, widths, line_h, text_w, text_h

    def natural_size(self, ctx):
        _, _, _, _, tw, th = self._layout(ctx)
        bw = tw + 2 * self.padding
        bh = th + 2 * self.padding
        if self.tail_side in ("bottom", "top"):
            return (bw, bh + self.tail_size)
        return (bw + self.tail_size, bh)

    def render(self, ctx: RenderContext, t: float) -> np.ndarray:
        font, lines, widths, line_h, tw, th = self._layout(ctx)
        bw = tw + 2 * self.padding
        bh = th + 2 * self.padding
        W, H = self.natural_size(ctx)
        S = _SS
        img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # bubble origin within the layer (leave room for the tail)
        ox = self.tail_size if self.tail_side == "left" else 0
        oy = self.tail_size if self.tail_side == "top" else 0
        box = [ox * S, oy * S, (ox + bw) * S, (oy + bh) * S]
        fill = self.fill.to_uint8()
        stroke = self.stroke.to_uint8() if self.stroke else None
        d.rounded_rectangle(box, radius=self.radius * S, fill=fill,
                            outline=stroke, width=self.stroke_width * S)

        # tail triangle
        ts = self.tail_size * S
        if self.tail_side in ("bottom", "top"):
            tx = (ox + self.tail_pos * bw) * S
            if self.tail_side == "bottom":
                base_y = (oy + bh) * S
                d.polygon([(tx - ts * 0.5, base_y - 2), (tx + ts * 0.5, base_y - 2),
                           (tx, base_y + ts)], fill=fill)
            else:
                base_y = oy * S
                d.polygon([(tx - ts * 0.5, base_y + 2), (tx + ts * 0.5, base_y + 2),
                           (tx, base_y - ts)], fill=fill)
        else:
            ty = (oy + self.tail_pos * bh) * S
            if self.tail_side == "right":
                base_x = (ox + bw) * S
                d.polygon([(base_x - 2, ty - ts * 0.5), (base_x - 2, ty + ts * 0.5),
                           (base_x + ts, ty)], fill=fill)
            else:
                base_x = ox * S
                d.polygon([(base_x + 2, ty - ts * 0.5), (base_x + 2, ty + ts * 0.5),
                           (base_x - ts, ty)], fill=fill)

        # text
        col = self.color.to_uint8()
        for i, ln in enumerate(lines):
            if self.align == "center":
                x = (ox + (bw - widths[i]) / 2) * S
            elif self.align == "right":
                x = (ox + bw - self.padding - widths[i]) * S
            else:
                x = (ox + self.padding) * S
            y = (oy + self.padding) * S + i * line_h * S
            d.text((x, y), ln, font=ctx.load_font(self.font, self.font_size * S), fill=col)

        img = img.resize((W, H), Image.LANCZOS)
        return np.asarray(img, np.float32) / 255.0

    @classmethod
    def from_spec(cls, spec):
        return cls(
            text=spec.get("text", ""), font=spec.get("font", "sans"),
            font_size=spec.get("font_size", 34), color=spec.get("color", "#0b0e16"),
            fill=spec.get("fill", "#ffffff"), stroke=spec.get("stroke"),
            stroke_width=spec.get("stroke_width", 0), radius=spec.get("radius", 18),
            padding=spec.get("padding", 22), max_width=spec.get("max_width", 520),
            tail_side=spec.get("tail_side", "bottom"), tail_size=spec.get("tail_size", 28),
            tail_pos=spec.get("tail_pos", 0.5), align=spec.get("align", "left"),
            line_spacing=spec.get("line_spacing", 1.2),
        )
