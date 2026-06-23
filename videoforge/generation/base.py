"""Generative-video provider abstraction.

A *provider* turns a prompt (and optionally a source image / first frame) into
a short MP4 clip on disk. The rest of VideoForge then treats that clip like any
other ``video`` element, so a generated shot composites with text, effects,
camera moves and audio exactly like hand-authored content.

Providers are deliberately uniform so the *same* ``generate_video`` MCP tool /
Python call works whether the frames come from a local procedural synthesiser
(no GPU, no network — always available) or a real diffusion model running on a
GPU somewhere (Google Colab, fal, Replicate, Hugging Face, ...).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable, Optional

import numpy as np

from ..render.encoder import FrameEncoder


@dataclass
class GenRequest:
    """A single text/image -> video generation request."""

    prompt: str
    mode: str = "t2v"                 # "t2v" (text->video) or "i2v" (image->video)
    image: Optional[str] = None       # path to the source image/first frame (i2v)
    num_frames: int = 96
    fps: float = 24.0
    width: int = 768
    height: int = 432
    seed: Optional[int] = None
    steps: int = 30                   # diffusion steps (cloud providers)
    guidance: float = 3.0             # guidance / cfg scale (cloud providers)
    extra: dict = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return self.num_frames / float(self.fps)

    @classmethod
    def from_kwargs(cls, prompt: str, *, duration: Optional[float] = None,
                    num_frames: Optional[int] = None, fps: float = 24.0,
                    **kw) -> "GenRequest":
        if num_frames is None:
            num_frames = int(round((duration if duration is not None else 4.0) * fps))
        num_frames = max(1, int(num_frames))
        return cls(prompt=prompt, num_frames=num_frames, fps=fps, **kw)


@dataclass
class GenResult:
    path: str
    provider: str
    frames: int
    fps: float
    width: int
    height: int
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "path": self.path, "provider": self.provider, "frames": self.frames,
            "fps": self.fps, "width": self.width, "height": self.height,
            "duration": round(self.frames / float(self.fps), 3), "meta": self.meta,
        }


class VideoGenProvider:
    """Base class. Subclasses implement :meth:`generate`."""

    name = "base"

    def available(self) -> tuple[bool, str]:
        """Return ``(ok, reason)``. ``reason`` explains *why* when not ok
        (missing key/URL/dependency) so callers can guide the user."""
        return True, "ready"

    def generate(self, req: GenRequest, out_path: str) -> GenResult:  # pragma: no cover
        raise NotImplementedError


def write_mp4(frames: Iterable[np.ndarray], out_path: str, fps: float,
              crf: int = 18, preset: str = "medium") -> tuple[int, int, int]:
    """Encode an iterable of uint8 RGB (H,W,3) frames to H.264. Returns
    ``(num_frames, width, height)``."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    enc = None
    n = w = h = 0
    try:
        for fr in frames:
            fr = np.ascontiguousarray(np.clip(fr, 0, 255).astype(np.uint8))
            if fr.ndim == 2:
                fr = np.repeat(fr[:, :, None], 3, axis=2)
            if fr.shape[2] == 4:
                fr = fr[:, :, :3]
            if enc is None:
                h, w = fr.shape[:2]
                enc = FrameEncoder(out_path, w, h, fps, crf=crf, preset=preset)
            enc.write(fr)
            n += 1
    finally:
        if enc is not None:
            enc.close()
    if n == 0:
        raise RuntimeError("generator produced no frames")
    return n, w, h
