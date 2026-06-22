"""Stylize effects: blur, sharpen, glow/bloom, vignette, grain, chromatic."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from ..core.types import Color
from .base import Effect, register


def _pil(img):
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGBA")


def _np(pil):
    return np.asarray(pil, np.float32) / 255.0


@register("blur")
class Blur(Effect):
    def apply(self, img, ctx, t):
        radius = float(self.p("radius", t, 8.0))
        if radius <= 0:
            return img
        return _np(_pil(img).filter(ImageFilter.GaussianBlur(radius)))


@register("sharpen")
class Sharpen(Effect):
    def apply(self, img, ctx, t):
        amount = float(self.p("amount", t, 1.0))
        blurred = _np(_pil(img).filter(ImageFilter.GaussianBlur(2.0)))
        out = img.copy()
        out[..., :3] = np.clip(img[..., :3] + (img[..., :3] - blurred[..., :3]) * amount, 0, 1)
        return out


@register("glow")
class Glow(Effect):
    """Bloom: extract bright areas, blur, add back."""

    def apply(self, img, ctx, t):
        threshold = float(self.p("threshold", t, 0.6))
        intensity = float(self.p("intensity", t, 0.7))
        radius = float(self.p("radius", t, 18.0))
        rgb = img[..., :3]
        luma = rgb.mean(axis=2, keepdims=True)
        mask = np.clip((luma - threshold) / max(1e-4, 1 - threshold), 0, 1)
        bright = rgb * mask
        ba = np.dstack([bright, np.ones(bright.shape[:2], np.float32)])
        blurred = _np(_pil(ba).filter(ImageFilter.GaussianBlur(radius)))[..., :3]
        out = img.copy()
        out[..., :3] = np.clip(rgb + blurred * intensity, 0, 1)
        return out


@register("vignette")
class Vignette(Effect):
    def apply(self, img, ctx, t):
        amount = float(self.p("amount", t, 0.5))
        softness = float(self.p("softness", t, 0.6))
        h, w = img.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = w / 2, h / 2
        d = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2) / np.sqrt(2)
        mask = 1.0 - amount * np.clip((d - (1 - softness)) / max(softness, 1e-4), 0, 1) ** 2
        out = img.copy()
        out[..., :3] *= mask[..., None]
        return out


@register("grain")
class Grain(Effect):
    def apply(self, img, ctx, t):
        amount = float(self.p("amount", t, 0.06))
        if amount <= 0:
            return img
        rng = np.random.default_rng(int(ctx.frame_index) * 2654435761 % (2**32))
        noise = rng.standard_normal(img.shape[:2]).astype(np.float32) * amount
        out = img.copy()
        out[..., :3] = np.clip(out[..., :3] + noise[..., None], 0, 1)
        return out


@register("chromatic_aberration")
class Chromatic(Effect):
    def apply(self, img, ctx, t):
        shift = int(self.p("shift", t, 3))
        if shift == 0:
            return img
        out = img.copy()
        out[..., 0] = np.roll(img[..., 0], shift, axis=1)
        out[..., 2] = np.roll(img[..., 2], -shift, axis=1)
        return out
