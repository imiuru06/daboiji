"""Client for the remote LaMa watermark-removal server.

The heavy ML inpainter (LaMa) needs ``torch`` and a GPU, so it runs *off-box*
on a Colab server (``colab/dabwayo_lama_server.ipynb``) exactly like the
generative-video ``remote`` provider. This module is the thin, dependency-light
client that uploads a clip, asks the server to erase a watermark region, and
saves the cleaned MP4 (with the original audio preserved server-side).

Contract (the Colab notebook implements it):

    GET  /health        -> {"ok": true, "model": "lama", "gpu": "...", ...}
    POST /dewatermark    (multipart/form-data)
        file=<video>, regions="[[x,y,w,h], ...]",
        pad=48, feather=4, dilate=9
      -> raw ``video/mp4`` bytes (watermark inpainted, audio kept)

Only ``requests`` is required; nothing ML is imported here.
"""
from __future__ import annotations

import json
import os
from typing import Optional, Sequence, Union

ENV_URL = "DABWAYO_LAMA_URL"
ENV_KEY = "DABWAYO_LAMA_KEY"

Region = Sequence[int]                       # [x, y, w, h]
Regions = Union[Region, Sequence[Region]]


class DewatermarkError(RuntimeError):
    """Raised when the LaMa server is misconfigured or returns an error."""


def _require_requests():
    try:
        import requests  # noqa: F401
        return requests
    except ImportError as e:  # pragma: no cover
        raise DewatermarkError(
            "the 'requests' package is required (pip install requests)") from e


def _base_url(base_url: Optional[str]) -> str:
    url = (base_url or os.environ.get(ENV_URL, "")).strip().rstrip("/")
    if not url:
        raise DewatermarkError(
            f"set {ENV_URL} to your Colab LaMa server URL "
            f"(see colab/dabwayo_lama_server.ipynb)")
    return url


def _headers(api_key: Optional[str]) -> dict:
    key = api_key or os.environ.get(ENV_KEY, "")
    return {"Authorization": f"Bearer {key}"} if key else {}


def _normalize_regions(regions: Regions) -> list[list[int]]:
    """Accept a single ``[x,y,w,h]`` or a list of them; return a list."""
    regs = list(regions)
    if regs and all(isinstance(v, (int, float)) for v in regs):
        regs = [regs]                        # a single box was passed
    out = []
    for r in regs:
        if len(r) != 4:
            raise DewatermarkError(f"each region must be [x, y, w, h]; got {r!r}")
        out.append([int(v) for v in r])
    return out


def health(base_url: Optional[str] = None, *, api_key: Optional[str] = None,
           timeout: float = 30.0) -> dict:
    """Probe the LaMa server's ``/health`` endpoint."""
    requests = _require_requests()
    url = _base_url(base_url) + "/health"
    try:
        r = requests.get(url, headers=_headers(api_key), timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:  # noqa: BLE001
        raise DewatermarkError(f"LaMa server unreachable at {url}: {e}") from e


def remove_watermark(
    input_path: str,
    out_path: str,
    regions: Regions,
    *,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    pad: int = 48,
    feather: int = 4,
    dilate: int = 9,
    timeout: float = 900.0,
) -> str:
    """Upload ``input_path`` to the LaMa server, erase ``regions``, save to
    ``out_path``. Returns ``out_path``.

    ``regions`` is ``[x, y, w, h]`` (pixels, source resolution) or a list of
    such boxes. The server inpaints each frame over a padded ROI and muxes the
    original audio back, so ``out_path`` keeps sound.
    """
    requests = _require_requests()
    if not os.path.isfile(input_path):
        raise DewatermarkError(f"input video not found: {input_path}")
    url = _base_url(base_url) + "/dewatermark"
    regs = _normalize_regions(regions)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)

    data = {"regions": json.dumps(regs), "pad": str(int(pad)),
            "feather": str(int(feather)), "dilate": str(int(dilate))}
    with open(input_path, "rb") as fh:
        files = {"file": (os.path.basename(input_path), fh, "video/mp4")}
        try:
            r = requests.post(url, data=data, files=files,
                              headers=_headers(api_key), timeout=timeout)
        except Exception as e:  # noqa: BLE001
            raise DewatermarkError(f"request to {url} failed: {e}") from e
    if r.status_code != 200:
        detail = r.text[:500]
        raise DewatermarkError(f"server returned HTTP {r.status_code}: {detail}")
    ctype = r.headers.get("Content-Type", "")
    if "video" not in ctype and "octet-stream" not in ctype:
        raise DewatermarkError(f"expected video bytes, got {ctype!r}: {r.text[:300]}")
    with open(out_path, "wb") as out:
        out.write(r.content)
    return out_path
