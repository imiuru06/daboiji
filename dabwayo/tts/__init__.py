"""Pluggable, optional text-to-speech (voiceover)."""
from .base import TTSError, VoiceProvider  # noqa: F401
from .registry import get_provider, list_providers, synth  # noqa: F401
