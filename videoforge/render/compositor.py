"""Layer compositing: blend modes and alpha-over.

Images are numpy float32 arrays of shape (H, W, 4), channels RGBA in
[0, 1], straight (non-premultiplied) alpha. ``composite`` places a source
layer over a destination using a blend mode and a global opacity.
"""
from __future__ import annotations

import numpy as np

from ..core.types import BlendMode


def new_canvas(width: int, height: int, color=(0.0, 0.0, 0.0, 0.0)) -> np.ndarray:
    canvas = np.empty((height, width, 4), dtype=np.float32)
    canvas[:] = color
    return canvas


def _blend_rgb(dst: np.ndarray, src: np.ndarray, mode: BlendMode) -> np.ndarray:
    """Blend two RGB arrays (in [0,1]) according to ``mode``."""
    if mode == BlendMode.NORMAL:
        return src
    if mode == BlendMode.ADD:
        return np.clip(dst + src, 0.0, 1.0)
    if mode == BlendMode.SCREEN:
        return 1.0 - (1.0 - dst) * (1.0 - src)
    if mode == BlendMode.MULTIPLY:
        return dst * src
    if mode == BlendMode.LIGHTEN:
        return np.maximum(dst, src)
    if mode == BlendMode.DARKEN:
        return np.minimum(dst, src)
    if mode == BlendMode.DIFFERENCE:
        return np.abs(dst - src)
    if mode == BlendMode.OVERLAY:
        return np.where(dst < 0.5, 2 * dst * src, 1 - 2 * (1 - dst) * (1 - src))
    if mode == BlendMode.SOFT_LIGHT:
        return np.where(
            src < 0.5,
            dst - (1 - 2 * src) * dst * (1 - dst),
            dst + (2 * src - 1) * (np.sqrt(np.clip(dst, 0, 1)) - dst),
        )
    return src


def composite(
    dst: np.ndarray,
    src: np.ndarray,
    x: int = 0,
    y: int = 0,
    opacity: float = 1.0,
    mode: BlendMode = BlendMode.NORMAL,
) -> np.ndarray:
    """Composite ``src`` over ``dst`` at top-left ``(x, y)``, in place.

    Only the overlapping region is touched, so cost scales with the source
    layer, not the canvas. Uses standard source-over alpha compositing,
    optionally routing colors through a blend function for non-normal modes.
    """
    if opacity <= 0.0:
        return dst
    ch, cw = dst.shape[:2]
    sh, sw = src.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(cw, x + sw), min(ch, y + sh)
    if x1 <= x0 or y1 <= y0:
        return dst
    sub_src = src[y0 - y:y1 - y, x0 - x:x1 - x]
    sub_dst = dst[y0:y1, x0:x1]

    src_rgb = sub_src[..., :3]
    src_a = sub_src[..., 3:4] * float(opacity)
    dst_rgb = sub_dst[..., :3]
    dst_a = sub_dst[..., 3:4]

    if mode != BlendMode.NORMAL:
        blended = _blend_rgb(dst_rgb, src_rgb, mode)
        src_rgb = dst_a * blended + (1.0 - dst_a) * src_rgb

    out_a = src_a + dst_a * (1.0 - src_a)
    safe_a = np.where(out_a > 1e-6, out_a, 1.0)
    out_rgb = (src_rgb * src_a + dst_rgb * dst_a * (1.0 - src_a)) / safe_a

    sub_dst[..., :3] = out_rgb
    sub_dst[..., 3:4] = out_a
    return dst


def flatten(img: np.ndarray, background=(0.0, 0.0, 0.0)) -> np.ndarray:
    """Composite an RGBA image over an opaque background -> RGB float array."""
    a = img[..., 3:4]
    bg = np.array(background, dtype=np.float32)
    return img[..., :3] * a + bg * (1.0 - a)


def to_uint8(rgb: np.ndarray) -> np.ndarray:
    return (np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
