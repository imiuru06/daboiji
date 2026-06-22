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
    """Bloom: extract bright areas, blur, add back.

    For large frames the blur is computed at reduced resolution (downscale ->
    blur -> upscale), which is visually identical for soft bloom but far
    cheaper than a full-resolution Gaussian.
    """

    def apply(self, img, ctx, t):
        threshold = float(self.p("threshold", t, 0.6))
        intensity = float(self.p("intensity", t, 0.7))
        radius = float(self.p("radius", t, 18.0))
        rgb = img[..., :3]
        luma = rgb.mean(axis=2, keepdims=True)
        mask = np.clip((luma - threshold) / max(1e-4, 1 - threshold), 0, 1)
        bright = (rgb * mask).astype(np.float32)
        h, w = bright.shape[:2]
        ds = 0.4 if max(w, h) > 720 else 1.0
        pil = Image.fromarray((np.clip(bright, 0, 1) * 255).astype(np.uint8), "RGB")
        if ds < 1.0:
            sw, sh = max(1, int(w * ds)), max(1, int(h * ds))
            pil = pil.resize((sw, sh), Image.BILINEAR)
            pil = pil.filter(ImageFilter.GaussianBlur(max(1.0, radius * ds)))
            pil = pil.resize((w, h), Image.BILINEAR)
        else:
            pil = pil.filter(ImageFilter.GaussianBlur(radius))
        blurred = np.asarray(pil, np.float32) / 255.0
        out = img.copy()
        out[..., :3] = np.clip(rgb + blurred * intensity, 0, 1)
        return out


@register("vignette")
class Vignette(Effect):
    def __init__(self, **params):
        super().__init__(**params)
        self._cache = None

    def apply(self, img, ctx, t):
        amount = float(self.p("amount", t, 0.5))
        softness = float(self.p("softness", t, 0.6))
        h, w = img.shape[:2]
        key = (w, h, round(amount, 4), round(softness, 4))
        animated = any(p.is_animated for p in self._params.values())
        if not animated and self._cache and self._cache[0] == key:
            mask = self._cache[1]
        else:
            from ..render.grids import mesh
            yy, xx = mesh(w, h)
            cx, cy = w / 2, h / 2
            d = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2) / np.sqrt(2)
            mask = (1.0 - amount * np.clip((d - (1 - softness)) / max(softness, 1e-4), 0, 1) ** 2)[..., None]
            if not animated:
                self._cache = (key, mask)
        out = img.copy()
        out[..., :3] *= mask
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
