"""Pluggable, optional ASR (speech-to-text with word timestamps)."""
from .base import ASRError, ASRProvider, Transcript, Word  # noqa: F401
from .registry import get_provider, list_providers, transcribe  # noqa: F401
