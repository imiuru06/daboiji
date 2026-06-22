"""Effect registry — importing this package registers all built-in effects."""
from . import color, lighting, stylize  # noqa: F401
from .base import Effect, available, from_spec, register  # noqa: F401
