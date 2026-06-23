"""Generative-video providers for VideoForge.

Turn a prompt (text-to-video) or a still image (image-to-video) into a short
MP4 that composites into a timeline like any other ``video`` clip.

    from videoforge import generate_video
    res = generate_video("a slow drone shot over a misty forest at dawn",
                         duration=4, out_path="output/shot.mp4")

Backends are pluggable: ``local`` (procedural, always available), ``remote``
(a Google Colab / GPU server over HTTP), or hosted APIs (replicate/fal/
huggingface). See ``registry.get_provider`` for selection rules.
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from .base import GenRequest, GenResult, VideoGenProvider
from .registry import get_provider, list_providers

__all__ = ["GenRequest", "GenResult", "VideoGenProvider", "get_provider",
           "list_providers", "generate_video"]


def generate_video(prompt: str, out_path: Optional[str] = None, *,
                   mode: str = "t2v", image: Optional[str] = None,
                   duration: float = 4.0, fps: float = 24.0,
                   width: int = 768, height: int = 432,
                   seed: Optional[int] = None, steps: int = 30,
                   guidance: float = 3.0, provider: Optional[str] = None,
                   **extra) -> GenResult:
    """Generate a video clip from ``prompt`` (or ``image`` when ``mode='i2v'``).

    Returns a :class:`GenResult` with the output path. Picks the backend per
    :func:`registry.get_provider` unless ``provider`` is given.
    """
    prov = get_provider(provider)
    ok, why = prov.available()
    if not ok:
        raise RuntimeError(f"provider {prov.name!r} not ready: {why}")
    if out_path is None:
        out_dir = os.environ.get("VIDEOFORGE_OUTPUT", os.path.abspath("output"))
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"gen_{uuid.uuid4().hex[:8]}.mp4")
    req = GenRequest.from_kwargs(
        prompt, duration=duration, fps=fps, mode=mode, image=image,
        width=width, height=height, seed=seed, steps=steps, guidance=guidance,
        extra=extra)
    return prov.generate(req, out_path)
