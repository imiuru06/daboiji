"""Visual element base class and registry.

An Element produces an RGBA layer (numpy float32, shape (H, W, 4)) for a
given render context and local clip time. Elements render at their own
natural size; the owning clip's Transform places them on the canvas.
"""
from __future__ import annotations

from typing import Callable, Dict, Type

import numpy as np

from ..render.context import RenderContext

_REGISTRY: Dict[str, Type["Element"]] = {}


def register(type_name: str):
    def deco(cls):
        cls.type_name = type_name
        _REGISTRY[type_name] = cls
        return cls
    return deco


def from_spec(spec: dict) -> "Element":
    t = spec.get("type")
    if t not in _REGISTRY:
        raise ValueError(
            f"Unknown element type {t!r}. Available: {', '.join(sorted(_REGISTRY))}"
        )
    return _REGISTRY[t].from_spec(spec)


def available_types() -> list:
    return sorted(_REGISTRY)


class Element:
    """Base class for all renderable content."""

    type_name: str = "base"

    def natural_size(self, ctx: RenderContext) -> tuple[int, int]:
        """Default natural size: full canvas."""
        return ctx.size

    def render(self, ctx: RenderContext, t: float) -> np.ndarray:
        raise NotImplementedError

    @classmethod
    def from_spec(cls, spec: dict) -> "Element":
        raise NotImplementedError
