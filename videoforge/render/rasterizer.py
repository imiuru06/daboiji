"""Place a transformed element layer onto the timeline canvas.

A single inverse-affine map (anchor -> scale -> rotate -> translate) is fed
to Pillow's high-quality resampler so scale, rotation and positioning are
handled in one pass. Returns a full canvas-sized RGBA layer plus the
effective opacity, ready for the compositor.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image

from ..core.transform import anchor_offset
from ..core.types import Anchor


def place_layer(layer: np.ndarray, canvas_w: int, canvas_h: int,
                position, scale, rotation_deg, anchor: Anchor,
                extra_offset=(0.0, 0.0), extra_scale=1.0) -> np.ndarray:
    """Return a (canvas_h, canvas_w, 4) float layer with ``layer`` placed."""
    lh, lw = layer.shape[:2]
    sx = max(scale[0] * extra_scale, 1e-4)
    sy = max(scale[1] * extra_scale, 1e-4)
    px = position[0] + extra_offset[0]
    py = position[1] + extra_offset[1]
    ax0, ay0 = anchor_offset(anchor, lw, lh)

    theta = math.radians(rotation_deg)
    cos, sin = math.cos(theta), math.sin(theta)

    a = cos / sx
    b = sin / sx
    c = -(cos * px + sin * py) / sx + ax0
    d = -sin / sy
    e = cos / sy
    f = (sin * px - cos * py) / sy + ay0

    src = Image.fromarray((np.clip(layer, 0, 1) * 255).astype(np.uint8), "RGBA")
    out = src.transform(
        (canvas_w, canvas_h), Image.AFFINE, (a, b, c, d, e, f),
        resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0),
    )
    return np.asarray(out, np.float32) / 255.0
