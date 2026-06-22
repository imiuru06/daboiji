"""Element registry — importing this package registers all built-in elements."""
from . import backgrounds, media, shapes, text  # noqa: F401
from .base import Element, available_types, from_spec, register  # noqa: F401
