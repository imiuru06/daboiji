"""Shared rendering context passed down the pipeline."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from PIL import ImageFont

_FONT_DIRS = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "fonts"),
]

_FONT_ALIASES = {
    "sans": "Outfit-Regular",
    "sans-bold": "Outfit-Bold",
    "outfit": "Outfit-Regular",
    "outfit-bold": "Outfit-Bold",
    "work": "WorkSans-Regular",
    "work-bold": "WorkSans-Bold",
    "display": "BricolageGrotesque-Bold",
    "mono": "GeistMono-Regular",
    "serif": "YoungSerif-Regular",
    "serif-plex": "IBMPlexSerif-Regular",
    # CJK / Korean
    "kr": "NanumBarunGothic-Regular",
    "kr-bold": "NanumBarunGothic-Bold",
    "cjk": "NanumBarunGothic-Regular",
    "cjk-bold": "NanumBarunGothic-Bold",
    "nanum": "NanumBarunGothic-Regular",
    "nanum-bold": "NanumBarunGothic-Bold",
}


@dataclass
class RenderContext:
    width: int
    height: int
    fps: float
    frame_index: int = 0
    time: float = 0.0
    extra_font_dirs: list = field(default_factory=list)

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)

    def font_dirs(self) -> list:
        return list(self.extra_font_dirs) + _FONT_DIRS

    def resolve_font_path(self, name: str) -> Optional[str]:
        key = (name or "sans").lower()
        base = _FONT_ALIASES.get(key, name)
        for d in self.font_dirs():
            for cand in (base, f"{base}-Regular", base.replace(" ", "")):
                p = os.path.join(d, cand if cand.endswith((".ttf", ".otf")) else f"{cand}.ttf")
                if os.path.isfile(p):
                    return p
        # Allow absolute/relative path passed directly.
        if os.path.isfile(name):
            return name
        return None

    def load_font(self, name: str, size: int) -> ImageFont.FreeTypeFont:
        return _load_font_cached(self.resolve_font_path(name) or "", int(size))


@lru_cache(maxsize=128)
def _load_font_cached(path: str, size: int):
    if path and os.path.isfile(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)
