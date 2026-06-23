"""Configuration for the DABWAYO video-gen client.

All settings come from environment variables so the same code works in local
development, CI and the Claude Code web environment. The two variables that
the service is wired up with are:

    export DABWAYO_VIDEOGEN_URL='https://<host>.trycloudflare.com'
    export DABWAYO_VIDEOGEN_PROVIDER=remote
"""

from __future__ import annotations

import os
from dataclasses import dataclass

#: Environment variable names (kept in one place so they are easy to grep).
ENV_URL = "DABWAYO_VIDEOGEN_URL"
ENV_PROVIDER = "DABWAYO_VIDEOGEN_PROVIDER"
ENV_API_KEY = "DABWAYO_VIDEOGEN_API_KEY"
ENV_TIMEOUT = "DABWAYO_VIDEOGEN_TIMEOUT"

DEFAULT_PROVIDER = "remote"
DEFAULT_TIMEOUT = 60.0


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    """Resolved configuration for talking to the video-gen service."""

    base_url: str
    provider: str = DEFAULT_PROVIDER
    api_key: str | None = None
    timeout: float = DEFAULT_TIMEOUT

    def url(self, path: str) -> str:
        """Join ``path`` onto :attr:`base_url`, tolerating stray slashes."""
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"


def load_config(env: dict[str, str] | None = None) -> Config:
    """Build a :class:`Config` from the environment.

    Parameters
    ----------
    env:
        Mapping to read from. Defaults to :data:`os.environ`. Passing an
        explicit mapping makes this trivial to unit-test.

    Raises
    ------
    ConfigError
        If ``DABWAYO_VIDEOGEN_URL`` is not set, or ``DABWAYO_VIDEOGEN_TIMEOUT``
        is not a number.
    """
    env = os.environ if env is None else env

    base_url = (env.get(ENV_URL) or "").strip()
    if not base_url:
        raise ConfigError(
            f"{ENV_URL} is not set. Point it at the video-gen service, e.g.\n"
            f"    export {ENV_URL}='https://<host>.trycloudflare.com'"
        )

    provider = (env.get(ENV_PROVIDER) or DEFAULT_PROVIDER).strip().lower()
    api_key = (env.get(ENV_API_KEY) or "").strip() or None

    raw_timeout = (env.get(ENV_TIMEOUT) or "").strip()
    if raw_timeout:
        try:
            timeout = float(raw_timeout)
        except ValueError as exc:
            raise ConfigError(f"{ENV_TIMEOUT} must be a number, got {raw_timeout!r}") from exc
        if timeout <= 0:
            raise ConfigError(f"{ENV_TIMEOUT} must be positive, got {timeout}")
    else:
        timeout = DEFAULT_TIMEOUT

    return Config(base_url=base_url, provider=provider, api_key=api_key, timeout=timeout)
