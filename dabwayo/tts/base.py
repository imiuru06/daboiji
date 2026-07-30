"""Text-to-speech (voiceover) provider interface.

Symmetric with the ASR and video-gen providers: a thin abstraction with
pluggable backends selected by env/arg. dabwayo wraps external synthesis and
places/registers the result — it does not embed a voice model. TTS is optional:
you can always ``add_audio`` your own narration file instead.
"""
from __future__ import annotations

from typing import Optional


class TTSError(RuntimeError):
    """Raised when no provider is available or a backend fails."""


class VoiceProvider:
    name = "base"

    def available(self) -> tuple[bool, str]:
        return (False, "not implemented")

    def synth(self, text: str, out_path: str, voice: Optional[str] = None) -> dict:  # pragma: no cover
        """Write spoken ``text`` to ``out_path`` and return
        ``{path, provider, voice, format}``."""
        raise NotImplementedError
