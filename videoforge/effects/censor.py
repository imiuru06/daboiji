"""Censoring / restoration: mosaic (pixelate) and inpaint (object removal).

* ``mosaic`` pixelates the whole frame or a targeted region — face/plate
  redaction, stylization.
* ``inpaint`` removes content inside a region using classical content-aware
  inpainting (OpenCV Telea / Navier-Stokes). This is a practical, no-GPU
  watermark/logo remover. It works best for small watermarks over fairly
  flat or low-frequency backgrounds; busy textures or large areas need an
  ML inpainter (e.g. LaMa) — wire one in via the same region interface.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from ._regions import build_mask
from .base import Effect, register


@register("mosaic")
class Mosaic(Effect):
    """Pixelate. Params: block (cell size px, animatable), region (optional
    region spec to limit the effect; whole frame if omitted)."""

    def apply(self, img, ctx, t):
        h, w = img.shape[:2]
        block = max(2, int(self.p("block", t, 24)))
        small_w, small_h = max(1, w // block), max(1, h // block)
        rgb = (np.clip(img[..., :3], 0, 1) * 255).astype(np.uint8)
        pil = Image.fromarray(rgb, "RGB")
        pix = pil.resize((small_w, small_h), Image.BILINEAR).resize((w, h), Image.NEAREST)
        pix = np.asarray(pix, np.float32) / 255.0

        out = img.copy()
        region = self._params.get("region")
        if region is not None:
            m = build_mask(w, h, region.at(t) if hasattr(region, "at") else region)[..., None]
            out[..., :3] = pix * m + out[..., :3] * (1 - m)
        else:
            out[..., :3] = pix
        return out


@register("inpaint")
class Inpaint(Effect):
    """Remove content inside a region (watermark/logo/object removal).

    Params: region (region spec, required — the area to remove), radius
    (inpaint neighbourhood px, default 4), method ("telea"|"ns"),
    grow (px to dilate the mask so edges are fully covered)."""

    def apply(self, img, ctx, t):
        import cv2
        h, w = img.shape[:2]
        region = self._params.get("region")
        if region is None:
            return img
        spec = region.at(t) if hasattr(region, "at") else region
        mask = build_mask(w, h, spec)
        grow = int(self.p("grow", t, 2))
        m8 = (mask > 0.05).astype(np.uint8) * 255
        if grow > 0:
            k = np.ones((grow * 2 + 1, grow * 2 + 1), np.uint8)
            m8 = cv2.dilate(m8, k)
        radius = int(self.p("radius", t, 4))
        flag = cv2.INPAINT_NS if self.p("method", t, "telea") == "ns" else cv2.INPAINT_TELEA

        rgb = (np.clip(img[..., :3], 0, 1) * 255).astype(np.uint8)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        fixed = cv2.inpaint(bgr, m8, radius, flag)
        fixed = cv2.cvtColor(fixed, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0

        out = img.copy()
        out[..., :3] = fixed
        return out
