"""Place a transformed element layer onto the timeline canvas.

Work is kept proportional to the *layer* size, not the canvas size: the
source layer is scaled and rotated while small, then returned together with
its top-left offset on the canvas (the compositor blits only the overlap).
Anchor-centered rotation (the common case) is exact; non-centered rotation
uses the analytic offset.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image

from ..core.transform import anchor_offset
from ..core.types import Anchor


def place_layer(layer: np.ndarray, canvas_w: int, canvas_h: int,
                position, scale, rotation_deg, anchor: Anchor,
                extra_offset=(0.0, 0.0), extra_scale=1.0):
    """Return ``(arr, x, y)``: the placed RGBA float layer and its top-left
    offset on the canvas."""
    lh, lw = layer.shape[:2]
    sx = max(scale[0] * extra_scale, 1e-4)
    sy = max(scale[1] * extra_scale, 1e-4)
    px = position[0] + extra_offset[0]
    py = position[1] + extra_offset[1]
    ax0, ay0 = anchor_offset(anchor, lw, lh)

    # Fast path: full-canvas, centered, no scale/rotation -> no resampling.
    if (lw == canvas_w and lh == canvas_h and abs(rotation_deg) < 1e-6
            and abs(sx - 1.0) < 1e-6 and abs(sy - 1.0) < 1e-6
            and abs(px - canvas_w / 2.0) < 0.5 and abs(py - canvas_h / 2.0) < 0.5
            and anchor == Anchor.CENTER):
        return layer, 0, 0

    sw = max(1, int(round(lw * sx)))
    sh = max(1, int(round(lh * sy)))
    ax_s, ay_s = ax0 * sx, ay0 * sy

    src = Image.fromarray((np.clip(layer, 0, 1) * 255).astype(np.uint8), "RGBA")
    if (sw, sh) != (lw, lh):
        src = src.resize((sw, sh), Image.LANCZOS)

    if abs(rotation_deg) > 1e-6:
        rsrc = src.rotate(rotation_deg, expand=True, resample=Image.BICUBIC)
        rw, rh = rsrc.size
        vx, vy = ax_s - sw / 2.0, ay_s - sh / 2.0
        th = math.radians(rotation_deg)
        cos, sin = math.cos(th), math.sin(th)
        rvx = cos * vx + sin * vy
        rvy = -sin * vx + cos * vy
        arr = np.asarray(rsrc, np.float32) / 255.0
        return arr, int(round(px - (rw / 2.0 + rvx))), int(round(py - (rh / 2.0 + rvy)))

    arr = np.asarray(src, np.float32) / 255.0
    return arr, int(round(px - ax_s)), int(round(py - ay_s))
