"""dabwayo — a small client for the DABWAYO video-generation service.

The service location is configured via environment variables:

* ``DABWAYO_VIDEOGEN_URL``      — base URL of the video-gen service.
* ``DABWAYO_VIDEOGEN_PROVIDER`` — provider mode (``remote`` or ``local``).

See :mod:`dabwayo.config`, :mod:`dabwayo.client` and :mod:`dabwayo.cli`.
"""

from .config import Config, load_config
from .client import VideoGenClient, VideoGenError, Job

__all__ = [
    "Config",
    "load_config",
    "VideoGenClient",
    "VideoGenError",
    "Job",
    "__version__",
]

__version__ = "0.1.0"
