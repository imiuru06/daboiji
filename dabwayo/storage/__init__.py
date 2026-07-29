"""Pluggable storage backends for asset bytes (index stays in the registry)."""
from .base import StorageError, StorageProvider  # noqa: F401
from .registry import (asset_url, get_backend, list_backends,  # noqa: F401
                       localize_asset, put_asset)
