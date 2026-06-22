"""Built-in transition library."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from ..core import easing
from ..core.types import Color, Direction
from .base import Transition, TransitionResult, register


def _ease(name, p):
    return easing.get(name)(max(0.0, min(1.0, p)))


@register("fade")
class Fade(Transition):
    def apply(self, layer, p, entering, ctx):
        e = _ease(self.params.get("easing", "ease_in_out"), p)
        return TransitionResult(layer, opacity=e)


@register("fade_color")
class FadeColor(Transition):
    """Fade through a solid color (e.g. dip to black)."""

    def apply(self, layer, p, entering, ctx):
        e = _ease(self.params.get("easing", "ease_in_out"), p)
        col = Color.parse(self.params.get("color", "#000000"))
        out = layer.copy()
        out[..., :3] = out[..., :3] * e + np.array(col.rgb, np.float32) * (1 - e)
        return TransitionResult(out, opacity=1.0)


@register("slide")
class Slide(Transition):
    def apply(self, layer, p, entering, ctx):
        e = _ease(self.params.get("easing", "ease_out_cubic"), p)
        direction = Direction(self.params.get("direction", "left"))
        dist = float(self.params.get("distance", ctx.width * 0.5))
        amt = (1 - e) * dist
        dx = {"left": amt, "right": -amt, "up": 0, "down": 0}[direction.value]
        dy = {"up": amt, "down": -amt, "left": 0, "right": 0}[direction.value]
        return TransitionResult(layer, opacity=1.0, offset=(dx, dy))


@register("zoom")
class Zoom(Transition):
    def apply(self, layer, p, entering, ctx):
        e = _ease(self.params.get("easing", "ease_out_cubic"), p)
        frm = float(self.params.get("from", 0.6))
        scale = frm + (1.0 - frm) * e
        return TransitionResult(layer, opacity=e, scale=scale)


@register("blur_in")
class BlurIn(Transition):
    def apply(self, layer, p, entering, ctx):
        e = _ease(self.params.get("easing", "ease_out_cubic"), p)
        radius = float(self.params.get("radius", 30)) * (1 - e)
        out = layer
        if radius > 0.5:
            pil = Image.fromarray((np.clip(layer, 0, 1) * 255).astype(np.uint8), "RGBA")
            out = np.asarray(pil.filter(ImageFilter.GaussianBlur(radius)), np.float32) / 255.0
        return TransitionResult(out, opacity=e)


@register("wipe")
class Wipe(Transition):
    def apply(self, layer, p, entering, ctx):
        e = _ease(self.params.get("easing", "ease_in_out"), p)
        direction = Direction(self.params.get("direction", "left"))
        soft = float(self.params.get("softness", 0.08))
        h, w = layer.shape[:2]
        if direction in (Direction.LEFT, Direction.RIGHT):
            grad = np.linspace(0, 1, w, dtype=np.float32)[None, :]
            if direction == Direction.RIGHT:
                grad = grad[:, ::-1]
        else:
            grad = np.linspace(0, 1, h, dtype=np.float32)[:, None]
            if direction == Direction.DOWN:
                grad = grad[::-1, :]
        grad = np.broadcast_to(grad, (h, w))
        mask = np.clip((e - grad) / max(soft, 1e-3) + 0.5, 0, 1)
        out = layer.copy()
        out[..., 3] *= mask
        return TransitionResult(out, opacity=1.0)
