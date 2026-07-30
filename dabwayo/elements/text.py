"""Rich text element with wrapping, alignment, shadow and stroke."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from ..core.types import Color
from ..render.context import RenderContext
from .base import Element, register


def _wrap(draw, text, font, max_width):
    if not max_width:
        return text.split("\n")
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        cur = ""
        for word in words:
            trial = word if not cur else cur + " " + word
            if draw.textlength(trial, font=font) <= max_width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


@register("text")
class Text(Element):
    def __init__(self, text="", font="sans", size=64, color="#ffffff",
                 align="center", line_spacing=1.15, max_width=None,
                 shadow=None, stroke=None, stroke_width=0, padding=8,
                 letter_spacing=0.0):
        self.text = text
        self.font = font
        self.size = int(size)
        self.color = Color.parse(color)
        self.align = align
        self.line_spacing = line_spacing
        self.max_width = max_width
        self.shadow = shadow  # {"color","offset":[x,y],"blur":r}
        self.stroke = Color.parse(stroke) if stroke else None
        self.stroke_width = int(stroke_width)
        self.padding = int(padding)
        self.letter_spacing = float(letter_spacing)

    def _layout(self, ctx):
        font = ctx.load_font(self.font, self.size)
        probe = Image.new("RGBA", (8, 8))
        d = ImageDraw.Draw(probe)
        lines = _wrap(d, self.text, font, self.max_width)
        ascent, descent = font.getmetrics()
        line_h = int((ascent + descent) * self.line_spacing)
        widths = []
        for ln in lines:
            w = d.textlength(ln, font=font)
            if self.letter_spacing and len(ln) > 1:
                w += self.letter_spacing * (len(ln) - 1)
            widths.append(w)
        text_w = int(max(widths) if widths else 1)
        text_h = int(line_h * len(lines))
        return font, lines, widths, line_h, ascent, text_w, text_h

    def natural_size(self, ctx):
        _, _, _, _, _, tw, th = self._layout(ctx)
        pad = self.padding + self.stroke_width
        margin = 0
        if self.shadow:
            ox, oy = self.shadow.get("offset", [0, 0])
            margin = int(abs(ox) + abs(oy) + self.shadow.get("blur", 0) * 2)
        return (tw + 2 * pad + 2 * margin, th + 2 * pad + 2 * margin)

    def _draw_text(self, size, font, lines, widths, line_h, ascent, ox, oy, color, stroke=None, sw=0):
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        col = color.to_uint8()
        scol = stroke.to_uint8() if stroke else None
        for i, ln in enumerate(lines):
            lw = widths[i]
            if self.align == "center":
                x = (size[0] - lw) / 2
            elif self.align == "right":
                x = size[0] - lw - ox
            else:
                x = ox
            y = oy + i * line_h
            if self.letter_spacing and len(ln) > 1:
                cx = x
                for ch in ln:
                    d.text((cx, y), ch, font=font, fill=col,
                           stroke_width=sw, stroke_fill=scol)
                    cx += d.textlength(ch, font=font) + self.letter_spacing
            else:
                d.text((x, y), ln, font=font, fill=col,
                       stroke_width=sw, stroke_fill=scol)
        return img

    def render(self, ctx: RenderContext, t: float) -> np.ndarray:
        font, lines, widths, line_h, ascent, tw, th = self._layout(ctx)
        W, H = self.natural_size(ctx)
        pad = self.padding + self.stroke_width
        margin_x = (W - tw) // 2
        margin_y = (H - th) // 2
        base = Image.new("RGBA", (W, H), (0, 0, 0, 0))

        if self.shadow:
            from PIL import ImageFilter
            scol = Color.parse(self.shadow.get("color", "#000000cc"))
            sx, sy = self.shadow.get("offset", [0, 6])
            blur = self.shadow.get("blur", 8)
            sh = self._draw_text((W, H), font, lines, widths, line_h, ascent,
                                 margin_x + sx, margin_y + sy, scol)
            if blur > 0:
                sh = sh.filter(ImageFilter.GaussianBlur(blur))
            base = Image.alpha_composite(base, sh)

        fg = self._draw_text((W, H), font, lines, widths, line_h, ascent,
                             margin_x, margin_y, self.color,
                             stroke=self.stroke, sw=self.stroke_width)
        base = Image.alpha_composite(base, fg)
        return np.asarray(base, dtype=np.float32) / 255.0

    @classmethod
    def from_spec(cls, spec):
        return cls(
            text=spec.get("text", ""),
            font=spec.get("font", "sans"),
            size=spec.get("size", 64),
            color=spec.get("color", "#ffffff"),
            align=spec.get("align", "center"),
            line_spacing=spec.get("line_spacing", 1.15),
            max_width=spec.get("max_width"),
            shadow=spec.get("shadow"),
            stroke=spec.get("stroke"),
            stroke_width=spec.get("stroke_width", 0),
            padding=spec.get("padding", 8),
            letter_spacing=spec.get("letter_spacing", 0.0),
        )
