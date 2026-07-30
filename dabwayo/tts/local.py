"""Offline local TTS via pyttsx3 (if installed). No network/key needed."""
from __future__ import annotations

import os
from typing import Optional

from .base import VoiceProvider, TTSError


class Pyttsx3Provider(VoiceProvider):
    name = "local"

    def available(self) -> tuple[bool, str]:
        try:
            import pyttsx3  # noqa: F401
            return (True, "pyttsx3 installed")
        except Exception:  # noqa: BLE001  (pyttsx3 can raise at import on headless)
            return (False, "pip install pyttsx3 (offline TTS)")

    def synth(self, text: str, out_path: str, voice: Optional[str] = None) -> dict:
        if not text.strip():
            raise TTSError("empty text")
        try:
            import pyttsx3
            engine = pyttsx3.init()
            if voice:
                engine.setProperty("voice", voice)
            os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
            engine.save_to_file(text, out_path)
            engine.runAndWait()
        except Exception as e:  # noqa: BLE001
            raise TTSError(f"pyttsx3 synthesis failed: {e}") from e
        if not os.path.exists(out_path) or os.path.getsize(out_path) < 128:
            raise TTSError("pyttsx3 produced no audio")
        return {"path": out_path, "provider": "local", "voice": voice or "default",
                "format": os.path.splitext(out_path)[1].lstrip(".") or "wav"}
