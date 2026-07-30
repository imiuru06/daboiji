"""Speech-to-text tools: list ASR providers, transcribe, and auto-caption.

ASR is pluggable (local Whisper / remote HTTP / OpenAI) and optional — if you
have no provider, author captions with add_word_captions and your own word
list. auto_captions closes the loop: transcribe media, then lay word-timed
pop-on captions in one call."""
from __future__ import annotations

from typing import Optional

from .app import mcp, _proj, _log_activity_safe
from .captions import add_word_captions

__all__ = ["list_asr_providers", "transcribe", "auto_captions"]


@mcp.tool()
def list_asr_providers() -> dict:
    """List speech-to-text backends and whether each is ready (which key/URL or
    package it needs), plus the active one. ASR is optional — captions can also
    be authored from a manual word list via add_word_captions."""
    from ..transcription import list_providers
    return {"ok": True, **list_providers()}


@mcp.tool()
def transcribe(audio_path: str, provider: Optional[str] = None,
               language: str = "") -> dict:
    """Transcribe an audio/video file to text WITH word timestamps.

    ``provider`` picks a backend (local|remote|openai); omit to auto-select
    (remote URL → OpenAI key → local Whisper). ``language`` is an optional hint
    (e.g. 'ko','en'); leave blank to auto-detect. Returns the text, detected
    language, and a ``words`` list ({word,start,end}) you can feed straight into
    add_word_captions. Requires a configured provider (see list_asr_providers)."""
    from ..transcription import transcribe as _tx
    t = _tx(audio_path, provider=provider, language=language or None)
    d = t.as_dict()
    d["ok"] = True
    d["word_count"] = len(t.words)
    return d


@mcp.tool()
def auto_captions(project_id: str, audio_path: str, provider: Optional[str] = None,
                  language: str = "", group_size: int = 3, track: str = "captions",
                  offset: float = 0.0, font: str = "sans-bold",
                  size: Optional[int] = None, color: str = "#ffffff") -> dict:
    """Transcribe ``audio_path`` and lay word-timed pop-on captions onto the
    project in one step.

    Combines ASR (see transcribe) with add_word_captions: it transcribes the
    media, groups words (``group_size`` at a time) and adds them as styled
    caption clips on ``track``, offset by ``offset`` seconds (to line captions
    up with where the clip sits on the timeline). Needs a configured ASR
    provider; for manual timing without ASR, call add_word_captions directly.
    Returns the transcript summary and the created caption clip ids."""
    from ..transcription import transcribe as _tx
    _proj(project_id)                       # validate project exists early
    t = _tx(audio_path, provider=provider, language=language or None)
    words = [w.as_dict() for w in t.words]
    if not words:
        return {"ok": False, "error": "no words in transcript", "text": t.text,
                "provider": t.provider}
    cap = add_word_captions(project_id, words=words, track=track,
                            group_size=group_size, font=font, size=size,
                            color=color, offset=offset)
    _log_activity_safe("auto_captions", f"자동 자막({t.provider}): {len(words)}단어",
                       [audio_path], [f"project:{project_id}"])
    return {"ok": True, "provider": t.provider, "language": t.language,
            "text": t.text, "word_count": len(words),
            "captions": cap.get("count"), "clip_ids": cap.get("clip_ids", []),
            "track": track}
