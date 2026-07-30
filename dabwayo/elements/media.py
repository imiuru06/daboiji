"""Image and video source elements."""
from __future__ import annotations

import os

import numpy as np
from PIL import Image

from ..core.types import FitMode
from ..render.context import RenderContext
from .base import Element, register


def _fit(img: np.ndarray, target_w: int, target_h: int, mode: FitMode) -> np.ndarray:
    h, w = img.shape[:2]
    if mode == FitMode.NONE:
        return img
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGBA")
    if mode == FitMode.STRETCH:
        pil = pil.resize((target_w, target_h), Image.LANCZOS)
        return np.asarray(pil, np.float32) / 255.0
    scale = (max(target_w / w, target_h / h) if mode == FitMode.COVER
             else min(target_w / w, target_h / h))
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    pil = pil.resize((nw, nh), Image.LANCZOS)
    arr = np.asarray(pil, np.float32) / 255.0
    if mode == FitMode.COVER:
        x0 = (nw - target_w) // 2
        y0 = (nh - target_h) // 2
        return arr[y0:y0 + target_h, x0:x0 + target_w]
    canvas = np.zeros((target_h, target_w, 4), np.float32)
    x0 = (target_w - nw) // 2
    y0 = (target_h - nh) // 2
    canvas[y0:y0 + nh, x0:x0 + nw] = arr
    return canvas


def _crop(img: np.ndarray, crop) -> np.ndarray:
    """Crop to ``crop`` = [x, y, w, h] given as fractions (0..1) of the source
    frame. Returns ``img`` unchanged when ``crop`` is falsy."""
    if not crop:
        return img
    h, w = img.shape[:2]
    cx, cy, cw, ch = crop
    x0 = max(0, min(w - 1, int(round(cx * w))))
    y0 = max(0, min(h - 1, int(round(cy * h))))
    x1 = max(x0 + 1, min(w, int(round((cx + cw) * w))))
    y1 = max(y0 + 1, min(h, int(round((cy + ch) * h))))
    return img[y0:y1, x0:x1]


@register("image")
class ImageElement(Element):
    def __init__(self, path, fit="contain", size=None, crop=None):
        self.path = path
        self.fit = FitMode(fit)
        self.size = size
        self.crop = crop
        self._cache = None

    def _load(self):
        if self._cache is None:
            if not os.path.isfile(self.path):
                raise FileNotFoundError(f"Image not found: {self.path}")
            pil = Image.open(self.path).convert("RGBA")
            self._cache = np.asarray(pil, np.float32) / 255.0
        return self._cache

    def natural_size(self, ctx):
        if self.size:
            return tuple(self.size)
        img = self._load()
        return (img.shape[1], img.shape[0])

    def render(self, ctx: RenderContext, t: float) -> np.ndarray:
        img = _crop(self._load(), self.crop)
        if self.size:
            return _fit(img, self.size[0], self.size[1], self.fit)
        return img

    @classmethod
    def from_spec(cls, spec):
        return cls(path=spec["path"], fit=spec.get("fit", "contain"),
                   size=spec.get("size"), crop=spec.get("crop"))


@register("video")
class VideoElement(Element):
    """A clip sourced from an existing video file (decoded via imageio)."""

    def __init__(self, path, fit="cover", size=None, speed=1.0, loop=False,
                 start=0.0, crop=None):
        self.path = path
        self.fit = FitMode(fit)
        self.size = size
        self.speed = float(speed)
        self.loop = loop
        self.start = float(start)
        self.crop = crop
        self._reader = None
        self._meta = None

    def _open(self):
        if self._reader is None:
            import imageio.v2 as imageio
            self._reader = imageio.get_reader(self.path)
            self._meta = self._reader.get_meta_data()
        return self._reader

    def natural_size(self, ctx):
        if self.size:
            return tuple(self.size)
        self._open()
        sz = self._meta.get("size")
        return (int(sz[0]), int(sz[1])) if sz else ctx.size

    def render(self, ctx: RenderContext, t: float) -> np.ndarray:
        reader = self._open()
        fps = self._meta.get("fps", ctx.fps)
        nframes = self._meta.get("nframes", None)
        src_t = self.start + t * self.speed
        idx = int(src_t * fps)
        if nframes and isinstance(nframes, int) and nframes > 0:
            idx = idx % nframes if self.loop else min(idx, nframes - 1)
        idx = max(0, idx)
        try:
            frame = reader.get_data(idx)
        except (IndexError, RuntimeError):
            frame = reader.get_data(0)
        arr = np.asarray(frame, np.float32) / 255.0
        if arr.shape[2] == 3:
            arr = np.dstack([arr, np.ones(arr.shape[:2], np.float32)])
        arr = _crop(arr, self.crop)
        w, h = self.size or ctx.size
        return _fit(arr, w, h, self.fit)

    @classmethod
    def from_spec(cls, spec):
        return cls(
            path=spec["path"], fit=spec.get("fit", "cover"),
            size=spec.get("size"), speed=spec.get("speed", 1.0),
            loop=spec.get("loop", False), start=spec.get("start", 0.0),
            crop=spec.get("crop"),
        )
