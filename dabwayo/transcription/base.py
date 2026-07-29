"""ASR (speech-to-text) provider interface + result types.

Mirrors the generative-video provider pattern: a thin abstraction with
pluggable backends (local Whisper, a remote HTTP server, OpenAI), selected by
env/arg. ASR is *optional* — if no provider is configured you can still author
word-timed captions by passing your own word list to ``add_word_captions``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


class ASRError(RuntimeError):
    """Raised when no provider is available or a backend fails."""


@dataclass
class Word:
    word: str
    start: float
    end: float

    def as_dict(self) -> dict:
        return {"word": self.word, "start": round(self.start, 3), "end": round(self.end, 3)}


@dataclass
class Transcript:
    text: str
    words: List[Word] = field(default_factory=list)
    language: str = ""
    provider: str = ""

    def as_dict(self) -> dict:
        return {"text": self.text, "language": self.language,
                "provider": self.provider,
                "words": [w.as_dict() for w in self.words]}


class ASRProvider:
    """Base class. Subclasses set ``name`` and implement availability/transcribe."""
    name = "base"

    def available(self) -> tuple[bool, str]:
        return (False, "not implemented")

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> Transcript:  # pragma: no cover
        raise NotImplementedError
