"""Music-fetch client for the dabwayo pipeline.

Pulls royalty-free / Creative-Commons music straight from provider APIs so a
clip can be scored without leaving the toolchain. Like ``dewatermark`` and the
remote video provider, this is a thin, dependency-light client (only
``requests``) — it is meant to run wherever the MCP server runs *and has open
internet* (e.g. your VM), not inside a locked-down egress sandbox.

Providers
---------
* **Jamendo** (primary) — full downloadable tracks, mood/genre/tag search,
  per-track licence info. Needs ``JAMENDO_CLIENT_ID`` (free, instant).
* **Freesound** (ambience / SFX layers) — needs ``FREESOUND_API_KEY``. The
  public token can fetch HQ *previews* (mp3); the original-file ``/download``
  endpoint needs OAuth2, so we use previews, which are fine as texture beds.

Licensing is surfaced, never assumed: every result carries its licence URL and
a ready-to-use attribution string. Respect each track's terms before
publishing (some CC tracks need attribution and/or are non-commercial).
"""
from __future__ import annotations

import os
from typing import List, Optional

JAMENDO_BASE = "https://api.jamendo.com/v3.0"
FREESOUND_BASE = "https://freesound.org/apiv2"

ENV_JAMENDO = "JAMENDO_CLIENT_ID"
ENV_FREESOUND = "FREESOUND_API_KEY"


class MusicError(RuntimeError):
    """Raised on missing keys or provider/transport failures."""


def _requests():
    try:
        import requests  # noqa: F401
        return requests
    except ImportError as e:  # pragma: no cover
        raise MusicError("the 'requests' package is required (pip install requests)") from e


def _key(env: str, explicit: Optional[str]) -> str:
    val = (explicit or os.environ.get(env, "")).strip()
    if not val:
        raise MusicError(
            f"set {env} (free key). Jamendo: https://devportal.jamendo.com  "
            f"Freesound: https://freesound.org/apiv2/apply")
    return val


# --------------------------------------------------------------------------- #
#  Search                                                                      #
# --------------------------------------------------------------------------- #
def search_jamendo(query: str, *, limit: int = 6, instrumental: bool = True,
                   min_duration: int = 0, max_duration: int = 0,
                   tags: str = "", order: str = "popularity_total",
                   client_id: Optional[str] = None) -> List[dict]:
    """Search Jamendo tracks. ``query`` matches name/artist/tags loosely;
    ``tags`` is an extra comma-list (e.g. 'piano,calm,cinematic')."""
    rq = _requests()
    cid = _key(ENV_JAMENDO, client_id)
    params = {
        "client_id": cid, "format": "json", "limit": max(1, min(limit, 50)),
        "search": query, "audioformat": "mp32",
        "include": "musicinfo licenses", "order": order,
        "imagesize": 200,
    }
    if instrumental:
        params["vocalinstrumental"] = "instrumental"
    if tags:
        params["fuzzytags"] = tags
    if min_duration or max_duration:
        lo = min_duration or 0
        hi = max_duration or 600
        params["durationbetween"] = f"{lo}_{hi}"
    try:
        r = rq.get(f"{JAMENDO_BASE}/tracks/", params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        raise MusicError(f"Jamendo request failed: {e}") from e
    out = []
    for t in data.get("results", []):
        lic = t.get("license_ccurl", "")
        out.append({
            "source": "jamendo",
            "id": str(t.get("id")),
            "title": t.get("name", ""),
            "artist": t.get("artist_name", ""),
            "duration": t.get("duration", 0),
            "license_url": lic,
            "download_url": t.get("audiodownload") if t.get("audiodownload_allowed") else t.get("audio"),
            "stream_url": t.get("audio", ""),
            "tags": ((t.get("musicinfo") or {}).get("tags") or {}),
            "attribution": f'"{t.get("name","")}" by {t.get("artist_name","")} (Jamendo) — {lic or "see licence"}',
        })
    return out


def search_freesound(query: str, *, limit: int = 6, min_duration: int = 0,
                     max_duration: int = 0, api_key: Optional[str] = None) -> List[dict]:
    """Search Freesound (texture / ambience / SFX). Uses HQ mp3 previews."""
    rq = _requests()
    key = _key(ENV_FREESOUND, api_key)
    flt = []
    if min_duration or max_duration:
        flt.append(f"duration:[{min_duration or 0} TO {max_duration or 600}]")
    params = {
        "query": query, "token": key,
        "page_size": max(1, min(limit, 50)),
        "fields": "id,name,duration,license,previews,username,tags",
    }
    if flt:
        params["filter"] = " ".join(flt)
    try:
        r = rq.get(f"{FREESOUND_BASE}/search/text/", params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        raise MusicError(f"Freesound request failed: {e}") from e
    out = []
    for s in data.get("results", []):
        prev = (s.get("previews") or {})
        url = prev.get("preview-hq-mp3") or prev.get("preview-lq-mp3", "")
        out.append({
            "source": "freesound",
            "id": str(s.get("id")),
            "title": s.get("name", ""),
            "artist": s.get("username", ""),
            "duration": round(s.get("duration", 0), 1),
            "license_url": s.get("license", ""),
            "download_url": url,           # HQ preview (token-accessible)
            "stream_url": url,
            "tags": s.get("tags", []),
            "attribution": f'"{s.get("name","")}" by {s.get("username","")} (Freesound) — {s.get("license","")}',
        })
    return out


def search(query: str, *, source: str = "jamendo", **kw) -> List[dict]:
    if source == "jamendo":
        return search_jamendo(query, **kw)
    if source == "freesound":
        kw.pop("instrumental", None); kw.pop("tags", None); kw.pop("order", None)
        return search_freesound(query, **kw)
    raise MusicError(f"unknown source '{source}' (use 'jamendo' or 'freesound')")


# --------------------------------------------------------------------------- #
#  Download                                                                    #
# --------------------------------------------------------------------------- #
def download(item: dict, out_path: str, *, api_key: Optional[str] = None) -> str:
    """Download a search-result ``item`` to ``out_path``. Freesound previews
    need the token as a query param; Jamendo download URLs are open."""
    rq = _requests()
    url = item.get("download_url") or item.get("stream_url")
    if not url:
        raise MusicError("item has no download/stream url")
    params = {}
    if item.get("source") == "freesound":
        params["token"] = _key(ENV_FREESOUND, api_key)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    try:
        with rq.get(url, params=params, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
    except Exception as e:  # noqa: BLE001
        raise MusicError(f"download failed: {e}") from e
    if os.path.getsize(out_path) < 1024:
        raise MusicError("downloaded file is suspiciously small (auth/url issue?)")
    return out_path
