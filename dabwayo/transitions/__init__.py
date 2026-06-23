"""Transition registry — importing this package registers all transitions."""
from . import library  # noqa: F401
from .base import Transition, TransitionResult, available, from_spec, register  # noqa: F401
