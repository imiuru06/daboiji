"""Music-fetch tools (royalty-free / CC providers). Client: dabwayo/music.py."""
from __future__ import annotations

import os
import time
from typing import Optional

from .app import mcp, _MUSIC_DIR, _log_activity_safe

__all__ = ["list_music_sources", "search_music", "fetch_music"]


@mcp.tool()
def list_music_sources() -> dict:
    """List the available music providers and which API key each needs.

    Run the MCP server somewhere with open internet (e.g. your VM); these call
    provider APIs directly. Keys: JAMENDO_CLIENT_ID, FREESOUND_API_KEY."""
    return {
        "sources": [
            {"name": "jamendo", "needs": "JAMENDO_CLIENT_ID",
             "set": bool(os.environ.get("JAMENDO_CLIENT_ID")),
             "good_for": "full background-music tracks, mood/genre/tag search",
             "signup": "https://devportal.jamendo.com"},
            {"name": "freesound", "needs": "FREESOUND_API_KEY",
             "set": bool(os.environ.get("FREESOUND_API_KEY")),
             "good_for": "ambience / SFX / texture layers (HQ previews)",
             "signup": "https://freesound.org/apiv2/apply"},
        ],
        "note": "licences vary per track; every result returns license_url + "
                "an attribution string. Verify terms before publishing.",
    }


@mcp.tool()
def search_music(query: str, source: str = "jamendo", limit: int = 6,
                 instrumental: bool = True, min_duration: int = 0,
                 max_duration: int = 0, tags: str = "") -> dict:
    """Search a music provider and return candidates WITHOUT downloading.

    ``query`` is a mood/keyword (e.g. 'hopeful emotional piano'); ``tags`` adds
    a comma-list of Jamendo fuzzy tags (e.g. 'piano,calm,cinematic'). Each
    result has title/artist/duration/license_url/attribution/download_url so a
    caller can pick before calling ``fetch_music``."""
    from .. import music as _music
    items = _music.search(query, source=source, limit=limit,
                          instrumental=instrumental, min_duration=min_duration,
                          max_duration=max_duration, tags=tags)
    return {"ok": True, "source": source, "count": len(items), "results": items}


@mcp.tool()
def fetch_music(query: str, source: str = "jamendo", pick: int = 0,
                limit: int = 6, instrumental: bool = True,
                min_duration: int = 0, max_duration: int = 0, tags: str = "",
                out_path: Optional[str] = None) -> dict:
    """Search, download one track, and register it as a tracked audio asset.

    Searches ``source`` for ``query``, downloads result index ``pick`` (0 =
    top) into DABWAYO_MUSIC_DIR (default assets/audio), and registers it with
    provenance (so it flows into compose/render/publish). Returns the local
    path, asset id, the chosen track's metadata (incl. licence + attribution),
    and the full candidate list. Requires the provider's API key and open
    internet on the host running this server."""
    from .. import music as _music
    from .. import assets as _assets
    t0 = time.time()
    items = _music.search(query, source=source, limit=limit,
                          instrumental=instrumental, min_duration=min_duration,
                          max_duration=max_duration, tags=tags)
    if not items:
        return {"ok": False, "error": "no results", "source": source, "query": query}
    if pick < 0 or pick >= len(items):
        return {"ok": False, "error": f"pick {pick} out of range (0..{len(items)-1})",
                "results": items}
    chosen = items[pick]
    os.makedirs(_MUSIC_DIR, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in chosen.get("title", "track"))[:40] or "track"
    out_path = out_path or os.path.join(_MUSIC_DIR, f"{source}_{chosen['id']}_{safe}.mp3")
    _music.download(chosen, out_path)
    ast = _assets.register(out_path, kind="audio", role="music",
                           source={"action": "fetch_music", "provider": source,
                                   "params": {"query": query, "track_id": chosen["id"],
                                              "license_url": chosen.get("license_url"),
                                              "attribution": chosen.get("attribution")}})
    _log_activity_safe("fetch_music", f"음원 다운로드({source}): {chosen.get('title','')}",
                       [query], [ast["id"]])
    return {"ok": True, "path": out_path, "asset_id": ast["id"],
            "chosen": chosen, "candidates": items,
            "seconds": round(time.time() - t0, 2)}
