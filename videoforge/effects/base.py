"""Effect base class and registry.

An Effect transforms an RGBA float image (H, W, 4) given a render context
and local time. Effects may be applied per-clip (on the element layer) or
per-timeline (on the flattened composite). Parameters may be animated.
"""
from __future__ import annotations

from typing import Dict, Type

import numpy as np

from ..core.keyframe import AnimatedProperty
from ..render.context import RenderContext

_REGISTRY: Dict[str, Type["Effect"]] = {}


def register(name: str):
    def deco(cls):
        cls.effect_name = name
        _REGISTRY[name] = cls
        return cls
    return deco


def from_spec(spec: dict) -> "Effect":
    name = spec.get("type")
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown effect {name!r}. Available: {', '.join(sorted(_REGISTRY))}"
        )
    return _REGISTRY[name].from_spec(spec)


def available() -> list:
    return sorted(_REGISTRY)


class Effect:
    effect_name = "base"

    def __init__(self, **params):
        self._params = {k: AnimatedProperty.coerce(v) for k, v in params.items()}

    def p(self, name, t, default=None):
        prop = self._params.get(name)
        return prop.at(t) if prop is not None else default

    def apply(self, img: np.ndarray, ctx: RenderContext, t: float) -> np.ndarray:
        raise NotImplementedError

    @classmethod
    def from_spec(cls, spec: dict) -> "Effect":
        params = {k: v for k, v in spec.items() if k != "type"}
        return cls(**params)
