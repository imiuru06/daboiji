"""Remote generative-video providers.

* ``RemoteHTTPProvider`` — the one used with **Google Colab**. Point it at any
  HTTP server that speaks the simple contract below (the bundled Colab notebook
  ``colab/videoforge_gpu_server.ipynb`` implements it with LTX-Video on a free
  T4 GPU). It is also the bring-your-own-endpoint adapter for a local GPU box.

      GET  /health            -> {"ok": true, "model": "...", "modes": [...]}
      POST /generate (JSON)   -> raw ``video/mp4`` bytes (or JSON with
                                 "video_b64" or "url").
        body: {prompt, mode, num_frames, fps, width, height, seed, steps,
               guidance, image_b64?}

* ``ReplicateProvider`` / ``HuggingFaceProvider`` / ``FalProvider`` — adapters
  for the hosted APIs, each activated by its own API-key env var. They follow
  each service's native request/poll flow and download the resulting MP4.

All of them just need ``requests``; none import heavy ML deps.
"""
from __future__ import annotations

import base64
import os
import time
from typing import Optional

from .base import GenRequest, GenResult, VideoGenProvider


def _require_requests():
    try:
        import requests  # noqa: F401
        return requests
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("the 'requests' package is required for remote "
                           "video generation (pip install requests)") from e


def _write_bytes(out_path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(data)


def _probe_mp4(path: str) -> tuple[int, int, int, float]:
    """Read back (frames, w, h, fps) from a finished mp4."""
    import imageio.v2 as imageio
    r = imageio.get_reader(path)
    m = r.get_meta_data()
    fps = float(m.get("fps", 24.0))
    sz = m.get("size", (0, 0))
    try:
        n = r.count_frames()
    except Exception:
        n = int(m.get("nframes", 0) or 0)
    r.close()
    return int(n), int(sz[0]), int(sz[1]), fps


class RemoteHTTPProvider(VideoGenProvider):
    """Generic HTTP backend — Google Colab tunnel, local GPU server, or any
    endpoint implementing the /generate contract."""

    name = "remote"

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None,
                 timeout: float = 900.0):
        self.base_url = (base_url or os.environ.get("VIDEOFORGE_VIDEOGEN_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("VIDEOFORGE_VIDEOGEN_KEY", "")
        self.timeout = timeout

    def available(self) -> tuple[bool, str]:
        if not self.base_url:
            return False, ("set VIDEOFORGE_VIDEOGEN_URL to your Colab/GPU server "
                           "URL (see colab/videoforge_gpu_server.ipynb)")
        return True, f"remote endpoint {self.base_url}"

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def health(self) -> dict:
        requests = _require_requests()
        r = requests.get(self.base_url + "/health", timeout=30,
                         headers=self._headers())
        r.raise_for_status()
        return r.json()

    def generate(self, req: GenRequest, out_path: str) -> GenResult:
        requests = _require_requests()
        ok, why = self.available()
        if not ok:
            raise RuntimeError(why)
        body = {
            "prompt": req.prompt, "mode": req.mode,
            "num_frames": req.num_frames, "fps": req.fps,
            "width": req.width, "height": req.height,
            "seed": req.seed, "steps": req.steps, "guidance": req.guidance,
            **req.extra,
        }
        if req.mode == "i2v" and req.image:
            with open(req.image, "rb") as f:
                body["image_b64"] = base64.b64encode(f.read()).decode("ascii")
        r = requests.post(self.base_url + "/generate", json=body,
                          headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        ctype = r.headers.get("Content-Type", "")
        if "application/json" in ctype:
            j = r.json()
            if j.get("video_b64"):
                _write_bytes(out_path, base64.b64decode(j["video_b64"]))
            elif j.get("url"):
                dl = requests.get(j["url"], timeout=self.timeout)
                dl.raise_for_status()
                _write_bytes(out_path, dl.content)
            else:
                raise RuntimeError(f"server JSON had no video payload: {list(j)}")
        else:
            _write_bytes(out_path, r.content)
        n, w, h, fps = _probe_mp4(out_path)
        return GenResult(path=out_path, provider=self.name, frames=n or req.num_frames,
                         fps=fps or req.fps, width=w or req.width, height=h or req.height,
                         meta={"mode": req.mode, "endpoint": self.base_url})


class ReplicateProvider(VideoGenProvider):
    """Replicate hosted models (REPLICATE_API_TOKEN). Default model is an
    open video model; override with VIDEOFORGE_VIDEOGEN_MODEL='owner/model'."""

    name = "replicate"
    DEFAULT_MODEL = "lightricks/ltx-video"

    def __init__(self, token: Optional[str] = None, model: Optional[str] = None):
        self.token = token or os.environ.get("REPLICATE_API_TOKEN", "")
        self.model = model or os.environ.get("VIDEOFORGE_VIDEOGEN_MODEL", self.DEFAULT_MODEL)

    def available(self) -> tuple[bool, str]:
        if not self.token:
            return False, "set REPLICATE_API_TOKEN (https://replicate.com/account)"
        return True, f"replicate:{self.model}"

    def generate(self, req: GenRequest, out_path: str) -> GenResult:
        requests = _require_requests()
        ok, why = self.available()
        if not ok:
            raise RuntimeError(why)
        headers = {"Authorization": f"Bearer {self.token}",
                   "Content-Type": "application/json"}
        payload = {"prompt": req.prompt, "num_frames": req.num_frames,
                   "fps": int(req.fps), "width": req.width, "height": req.height}
        if req.seed is not None:
            payload["seed"] = int(req.seed)
        if req.mode == "i2v" and req.image:
            with open(req.image, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            payload["image"] = f"data:application/octet-stream;base64,{b64}"
        # create prediction (official models endpoint)
        url = f"https://api.replicate.com/v1/models/{self.model}/predictions"
        r = requests.post(url, json={"input": payload}, headers=headers, timeout=60)
        r.raise_for_status()
        pred = r.json()
        get_url = pred["urls"]["get"]
        # poll
        deadline = time.time() + 900
        while pred["status"] not in ("succeeded", "failed", "canceled"):
            if time.time() > deadline:
                raise TimeoutError("replicate prediction timed out")
            time.sleep(2.5)
            pred = requests.get(get_url, headers=headers, timeout=60).json()
        if pred["status"] != "succeeded":
            raise RuntimeError(f"replicate failed: {pred.get('error')}")
        out = pred["output"]
        video_url = out[-1] if isinstance(out, list) else out
        dl = requests.get(video_url, timeout=300)
        dl.raise_for_status()
        _write_bytes(out_path, dl.content)
        n, w, h, fps = _probe_mp4(out_path)
        return GenResult(path=out_path, provider=self.name, frames=n, fps=fps,
                         width=w, height=h, meta={"model": self.model, "mode": req.mode})


class HuggingFaceProvider(VideoGenProvider):
    """Hugging Face Inference (HF_TOKEN — free tier). Text-to-video models such
    as 'ali-vilab/text-to-video-ms-1.7b'. Quality is modest but it is free."""

    name = "huggingface"
    DEFAULT_MODEL = "ali-vilab/text-to-video-ms-1.7b"

    def __init__(self, token: Optional[str] = None, model: Optional[str] = None):
        self.token = token or os.environ.get("HF_TOKEN", "") or os.environ.get(
            "HUGGINGFACEHUB_API_TOKEN", "")
        self.model = model or os.environ.get("VIDEOFORGE_VIDEOGEN_MODEL", self.DEFAULT_MODEL)

    def available(self) -> tuple[bool, str]:
        if not self.token:
            return False, "set HF_TOKEN (free at https://huggingface.co/settings/tokens)"
        return True, f"huggingface:{self.model} (free tier; t2v only, modest quality)"

    def generate(self, req: GenRequest, out_path: str) -> GenResult:
        requests = _require_requests()
        ok, why = self.available()
        if not ok:
            raise RuntimeError(why)
        url = f"https://api-inference.huggingface.co/models/{self.model}"
        headers = {"Authorization": f"Bearer {self.token}"}
        r = requests.post(url, headers=headers, json={"inputs": req.prompt},
                          timeout=self.__dict__.get("timeout", 600))
        r.raise_for_status()
        _write_bytes(out_path, r.content)
        n, w, h, fps = _probe_mp4(out_path)
        return GenResult(path=out_path, provider=self.name, frames=n or req.num_frames,
                         fps=fps or req.fps, width=w or req.width, height=h or req.height,
                         meta={"model": self.model, "mode": "t2v"})


class FalProvider(VideoGenProvider):
    """fal.ai hosted models (FAL_KEY). Set VIDEOFORGE_VIDEOGEN_MODEL to a fal
    model id, e.g. 'fal-ai/ltx-video'."""

    name = "fal"
    DEFAULT_MODEL = "fal-ai/ltx-video"

    def __init__(self, key: Optional[str] = None, model: Optional[str] = None):
        self.key = key or os.environ.get("FAL_KEY", "")
        self.model = model or os.environ.get("VIDEOFORGE_VIDEOGEN_MODEL", self.DEFAULT_MODEL)

    def available(self) -> tuple[bool, str]:
        if not self.key:
            return False, "set FAL_KEY (https://fal.ai/dashboard/keys)"
        return True, f"fal:{self.model}"

    def generate(self, req: GenRequest, out_path: str) -> GenResult:
        requests = _require_requests()
        ok, why = self.available()
        if not ok:
            raise RuntimeError(why)
        headers = {"Authorization": f"Key {self.key}", "Content-Type": "application/json"}
        payload = {"prompt": req.prompt, "num_frames": req.num_frames}
        if req.seed is not None:
            payload["seed"] = int(req.seed)
        if req.mode == "i2v" and req.image:
            with open(req.image, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            payload["image_url"] = f"data:image/png;base64,{b64}"
        r = requests.post(f"https://fal.run/{self.model}", json=payload,
                          headers=headers, timeout=900)
        r.raise_for_status()
        j = r.json()
        video_url = (j.get("video") or {}).get("url") if isinstance(j.get("video"), dict) \
            else j.get("video_url") or j.get("url")
        if not video_url:
            raise RuntimeError(f"fal response had no video url: {list(j)}")
        dl = requests.get(video_url, timeout=300)
        dl.raise_for_status()
        _write_bytes(out_path, dl.content)
        n, w, h, fps = _probe_mp4(out_path)
        return GenResult(path=out_path, provider=self.name, frames=n, fps=fps,
                         width=w, height=h, meta={"model": self.model, "mode": req.mode})
