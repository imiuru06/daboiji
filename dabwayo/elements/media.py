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


@register("image")
class ImageElement(Element):
    def __init__(self, path, fit="contain", size=None):
        self.path = path
        self.fit = FitMode(fit)
        self.size = size
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
        img = self._load()
        if self.size:
            return _fit(img, self.size[0], self.size[1], self.fit)
        return img

    @classmethod
    def from_spec(cls, spec):
        return cls(path=spec["path"], fit=spec.get("fit", "contain"), size=spec.get("size"))


@register("video")
class VideoElement(Element):
    """A clip sourced from an existing video file (decoded via imageio)."""

    def __init__(self, path, fit="cover", size=None, speed=1.0, loop=False, start=0.0):
        self.path = path
        self.fit = FitMode(fit)
        self.size = size
        self.speed = float(speed)
        self.loop = loop
        self.start = float(start)
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
        w, h = self.size or ctx.size
        return _fit(arr, w, h, self.fit)

    @classmethod
    def from_spec(cls, spec):
        return cls(
            path=spec["path"], fit=spec.get("fit", "cover"),
            size=spec.get("size"), speed=spec.get("speed", 1.0),
            loop=spec.get("loop", False), start=spec.get("start", 0.0),
        )
