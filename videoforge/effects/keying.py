"""Keying & matting: chroma key (green/blue screen) and alpha masks.

* ``chroma_key`` makes pixels near a key color transparent, with tolerance
  and edge softness, plus optional spill suppression — the core of
  green-screen compositing.
* ``mask`` multiplies the layer's alpha by a region mask (or external image
  matte), with feather and invert — for reveals, cut-outs and vignette
  shapes. Apply it as a clip effect to cut the element into a shape.
"""
from __future__ import annotations

import numpy as np

from ..core.types import Color
from ._regions import build_mask
from .base import Effect, register


@register("chroma_key")
class ChromaKey(Effect):
    """Key out a color. Params: key (color, default green), tolerance
    (0..1 color distance kept opaque), softness (0..1 falloff), spill
    (0..1 suppress key-color tint on edges)."""

    def apply(self, img, ctx, t):
        key = np.array(Color.parse(self.p("key", t, "#00ff00")).rgb, np.float32)
        tol = float(self.p("tolerance", t, 0.25))
        soft = float(self.p("softness", t, 0.12))
        spill = float(self.p("spill", t, 0.5))

        rgb = img[..., :3]
        dist = np.sqrt(((rgb - key[None, None, :]) ** 2).sum(axis=2))
        # alpha: 0 inside tolerance, ramps to 1 over softness
        alpha = np.clip((dist - tol) / max(soft, 1e-4), 0, 1)

        out = img.copy()
        out[..., 3] = out[..., 3] * alpha
        if spill > 0:
            # suppress green/key spill: pull key channel toward the avg of others
            g = rgb[..., 1]
            rb_avg = (rgb[..., 0] + rgb[..., 2]) * 0.5
            over = np.clip(g - rb_avg, 0, 1)
            out[..., 1] = g - over * spill
        return out


@register("mask")
class Mask(Effect):
    """Multiply alpha by a region mask. Params: region (region spec) or
    image (path to a grayscale matte), invert, feather (px)."""

    def apply(self, img, ctx, t):
        h, w = img.shape[:2]
        region = self._params.get("region")
        if region is not None:
            spec = region.at(t) if hasattr(region, "at") else region
            m = build_mask(w, h, spec)
        elif self._params.get("image") is not None:
            from PIL import Image
            path = self.p("image", t, None)
            mi = Image.open(path).convert("L").resize((w, h))
            m = np.asarray(mi, np.float32) / 255.0
            if self.p("invert", t, False):
                m = 1.0 - m
        else:
            return img
        out = img.copy()
        out[..., 3] = out[..., 3] * m
        return out
