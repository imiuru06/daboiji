"""Cached coordinate grids.

Per-frame effects (gradients, vignette, lighting) need pixel coordinate
grids. Recomputing them every frame is a major cost, so they are cached by
size — they are read-only and shared across frames.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np


@lru_cache(maxsize=16)
def mesh(w: int, h: int):
    """Return (yy, xx) float32 pixel-index grids of shape (h, w)."""
    yy, xx = np.mgrid[0:h, 0:w]
    return yy.astype(np.float32), xx.astype(np.float32)


@lru_cache(maxsize=16)
def norm_mesh(w: int, h: int):
    """Return (ny, nx) grids normalized to [0, 1]."""
    yy, xx = mesh(w, h)
    return yy / max(h - 1, 1), xx / max(w - 1, 1)
