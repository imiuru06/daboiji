"""Local Whisper ASR — uses faster-whisper (preferred) or openai-whisper if
installed. Needs no network; model name via DABWAYO_ASR_MODEL (default 'base').
"""
from __future__ import annotations

import os
from typing import Optional

from .base import ASRProvider, Transcript, Word, ASRError


class LocalWhisperProvider(ASRProvider):
    name = "local"

    def _backend(self) -> Optional[str]:
        try:
            import faster_whisper  # noqa: F401
            return "faster_whisper"
        except ImportError:
            pass
        try:
            import whisper  # noqa: F401
            return "whisper"
        except ImportError:
            return None

    def available(self) -> tuple[bool, str]:
        b = self._backend()
        if not b:
            return (False, "pip install faster-whisper (recommended) or openai-whisper")
        return (True, f"{b} installed")

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> Transcript:
        if not os.path.exists(audio_path):
            raise ASRError(f"audio not found: {audio_path}")
        backend = self._backend()
        model_name = os.environ.get("DABWAYO_ASR_MODEL", "base")
        if backend == "faster_whisper":
            from faster_whisper import WhisperModel
            model = WhisperModel(model_name)
            segments, info = model.transcribe(audio_path, language=language,
                                              word_timestamps=True)
            words, text = [], []
            for seg in segments:
                text.append(seg.text)
                for w in (seg.words or []):
                    words.append(Word(w.word.strip(), float(w.start), float(w.end)))
            return Transcript(" ".join(t.strip() for t in text).strip(), words,
                              getattr(info, "language", "") or (language or ""), "local")
        elif backend == "whisper":
            import whisper
            model = whisper.load_model(model_name)
            r = model.transcribe(audio_path, language=language, word_timestamps=True)
            words = []
            for seg in r.get("segments", []):
                for w in seg.get("words", []):
                    words.append(Word(str(w["word"]).strip(), float(w["start"]), float(w["end"])))
            return Transcript(r.get("text", "").strip(), words,
                              r.get("language", "") or (language or ""), "local")
        raise ASRError("no local Whisper backend installed")
