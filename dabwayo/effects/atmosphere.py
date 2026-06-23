"""Atmospheric effects: fog / haze / mist.

Fog is layered value-noise modulated by a vertical depth gradient and
screen-blended over the frame. The noise scrolls over time for a living,
drifting feel. Cheap, deterministic, and fully keyframeable.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from ..core.types import Color
from ..render.grids import norm_mesh
from .base import Effect, register


def _value_noise(w: int, h: int, seed: int, octaves=4) -> np.ndarray:
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w), np.float32)
    amp = 1.0
    total = 0.0
    cells = 4
    for _ in range(octaves):
        small = rng.random((cells, cells)).astype(np.float32)
        up = np.asarray(
            Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC),
            np.float32,
        ) / 255.0
        acc += up * amp
        total += amp
        amp *= 0.5
        cells *= 2
    return acc / total


# cache the static noise field per size/seed
_NOISE_CACHE: dict = {}


def _noise(w, h, seed):
    key = (w, h, seed)
    if key not in _NOISE_CACHE:
        if len(_NOISE_CACHE) > 8:
            _NOISE_CACHE.clear()
        _NOISE_CACHE[key] = _value_noise(w, h, seed)
    return _NOISE_CACHE[key]


@register("fog")
class Fog(Effect):
    """Drifting fog/haze.

    Params (animatable): color (default soft blue-grey), density (0..1),
    height (0..1 fraction of frame the fog rises to from the bottom),
    speed (px/s drift), seed.
    """

    def apply(self, img, ctx, t):
        h, w = img.shape[:2]
        col = np.array(Color.parse(self.p("color", t, "#c8d2e0")).rgb, np.float32)
        density = float(self.p("density", t, 0.5))
        height = float(self.p("height", t, 0.6))
        speed = float(self.p("speed", t, 40.0))
        seed = int(self.p("seed", t, 1))

        noise = _noise(w, h, seed)
        shift = int((t * speed) % w)
        noise = np.roll(noise, shift, axis=1)

        ny, _ = norm_mesh(w, h)
        # depth gradient: fog densest at the bottom, fades by `height`
        depth = np.clip((ny - (1.0 - height)) / max(height, 1e-3), 0, 1)
        amount = (noise * 0.6 + 0.4) * depth * density
        amount = amount[..., None]

        fog = col[None, None, :] * amount
        out = img.copy()
        out[..., :3] = 1.0 - (1.0 - out[..., :3]) * (1.0 - np.clip(fog, 0, 1))
        return out
