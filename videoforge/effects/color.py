"""Color-grading effects: exposure/contrast/saturation, lift-gamma-gain, tint."""
from __future__ import annotations

import numpy as np

from ..core.types import Color
from .base import Effect, register

_LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


@register("color_grade")
class ColorGrade(Effect):
    """Primary color correction.

    Params (all optional, animatable):
      brightness (0..n, 1=neutral), exposure (stops), contrast (1=neutral),
      saturation (1=neutral), gamma (1=neutral), temperature (-1..1 warm),
      tint (-1..1 magenta/green), hue (degrees).
    """

    def apply(self, img, ctx, t):
        rgb = img[..., :3].copy()
        exposure = self.p("exposure", t, 0.0)
        if exposure:
            rgb *= 2.0 ** float(exposure)
        brightness = self.p("brightness", t, 1.0)
        if brightness != 1.0:
            rgb *= float(brightness)
        temp = self.p("temperature", t, 0.0)
        tint = self.p("tint", t, 0.0)
        if temp or tint:
            rgb[..., 0] *= 1.0 + 0.25 * float(temp)
            rgb[..., 2] *= 1.0 - 0.25 * float(temp)
            rgb[..., 1] *= 1.0 + 0.15 * float(tint)
        contrast = self.p("contrast", t, 1.0)
        if contrast != 1.0:
            rgb = (rgb - 0.5) * float(contrast) + 0.5
        sat = self.p("saturation", t, 1.0)
        if sat != 1.0:
            luma = (rgb * _LUMA).sum(axis=2, keepdims=True)
            rgb = luma + (rgb - luma) * float(sat)
        gamma = self.p("gamma", t, 1.0)
        if gamma != 1.0:
            rgb = np.clip(rgb, 0, None) ** (1.0 / float(gamma))
        img = img.copy()
        img[..., :3] = np.clip(rgb, 0.0, 1.0)
        return img


@register("lift_gamma_gain")
class LiftGammaGain(Effect):
    """Three-way color corrector. lift/gamma/gain each an RGB color triplet."""

    def apply(self, img, ctx, t):
        rgb = img[..., :3].copy()
        lift = np.array(Color.parse(self.p("lift", t, "#000000")).rgb, np.float32)
        gamma = np.array(Color.parse(self.p("gamma", t, "#808080")).rgb, np.float32) * 2.0
        gain = np.array(Color.parse(self.p("gain", t, "#808080")).rgb, np.float32) * 2.0
        rgb = rgb * gain + lift * (1.0 - rgb)
        gamma = np.where(gamma <= 0, 1.0, gamma)
        rgb = np.clip(rgb, 0, None) ** (1.0 / gamma)
        img = img.copy()
        img[..., :3] = np.clip(rgb, 0.0, 1.0)
        return img
