"""HTTP client for the DABWAYO video-generation service.

This client is written against a *conventional* asynchronous video-gen REST
API — the common "submit a job, poll for status, download the result" shape:

    POST  {base}/generate         -> {"job_id": "...", "status": "queued"}
    GET   {base}/status/{job_id}  -> {"status": "...", "progress": 0.5,
                                      "video_url": "..."}
    GET   {video_url}             -> binary video bytes

Because the exact paths can vary between deployments, the endpoints are
parameterised and the client can :meth:`discover` them against a live service.
Only the Python standard library is used, so there is nothing to install.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .config import Config, load_config


class VideoGenError(RuntimeError):
    """Raised when the service returns an error or behaves unexpectedly."""


# Candidate paths tried by :meth:`VideoGenClient.discover`. Ordered most- to
# least-likely so the first hit wins.
HEALTH_PATHS: tuple[str, ...] = ("/health", "/healthz", "/ping", "/status", "/")
GENERATE_PATHS: tuple[str, ...] = (
    "/generate",
    "/api/generate",
    "/v1/generate",
    "/videos",
    "/api/videos",
    "/txt2video",
)
STATUS_PATH_TEMPLATES: tuple[str, ...] = (
    "/status/{job_id}",
    "/jobs/{job_id}",
    "/api/status/{job_id}",
    "/v1/status/{job_id}",
    "/result/{job_id}",
)

# Keys the client will look at when pulling a job id / video url out of a
# response body, so it adapts to small naming differences.
_JOB_ID_KEYS = ("job_id", "id", "task_id", "request_id", "uuid")
_VIDEO_URL_KEYS = ("video_url", "url", "output", "output_url", "result_url", "video")
_STATUS_KEYS = ("status", "state")
_PROGRESS_KEYS = ("progress", "percent", "percentage")

_DONE_STATES = {"succeeded", "success", "completed", "complete", "done", "finished", "ready"}
_FAILED_STATES = {"failed", "error", "errored", "cancelled", "canceled"}


@dataclass
class Job:
    """A handle to an in-flight or finished generation job."""

    job_id: str | None
    status: str = "unknown"
    progress: float | None = None
    video_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def done(self) -> bool:
        return self.status.lower() in _DONE_STATES or bool(self.video_url)

    @property
    def failed(self) -> bool:
        return self.status.lower() in _FAILED_STATES


def _first(d: dict[str, Any], keys: Iterable[str]) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _job_from_payload(payload: Any) -> Job:
    """Build a :class:`Job` from a decoded JSON response, tolerating shapes."""
    if not isinstance(payload, dict):
        raise VideoGenError(f"Expected a JSON object from the service, got {type(payload).__name__}")

    progress_raw = _first(payload, _PROGRESS_KEYS)
    progress = None
    if progress_raw is not None:
        try:
            progress = float(progress_raw)
        except (TypeError, ValueError):
            progress = None

    return Job(
        job_id=_first(payload, _JOB_ID_KEYS),
        status=str(_first(payload, _STATUS_KEYS) or "unknown"),
        progress=progress,
        video_url=_first(payload, _VIDEO_URL_KEYS),
        raw=payload,
    )


class VideoGenClient:
    """A thin, dependency-free client for the video-gen service.

    Parameters
    ----------
    config:
        A :class:`~dabwayo.config.Config`. Defaults to one built from the
        environment via :func:`~dabwayo.config.load_config`.
    generate_path / status_path_template:
        Override the endpoints if they are already known (skips discovery).
    """

    def __init__(
        self,
        config: Config | None = None,
        *,
        generate_path: str | None = None,
        status_path_template: str | None = None,
    ) -> None:
        self.config = config or load_config()
        self.generate_path = generate_path
        self.status_path_template = status_path_template

    # -- low level ---------------------------------------------------------

    def _headers(self, json_body: bool) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "dabwayo/0.1"}
        if json_body:
            headers["Content-Type"] = "application/json"
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: dict[str, Any] | None = None,
        raw: bool = False,
        timeout: float | None = None,
    ) -> Any:
        """Perform an HTTP request.

        Returns decoded JSON, or raw ``bytes`` when ``raw=True``.
        """
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(
            url, data=data, method=method, headers=self._headers(body is not None)
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.config.timeout) as resp:
                payload = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise VideoGenError(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise VideoGenError(f"{method} {url} failed: {exc.reason}") from exc

        if raw:
            return payload
        if not payload:
            return {}
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise VideoGenError(f"{method} {url} returned non-JSON body") from exc

    # -- discovery ---------------------------------------------------------

    def ping(self) -> dict[str, Any]:
        """Probe known health endpoints; return ``{path, status, body}``.

        Raises :class:`VideoGenError` if none respond.
        """
        last: VideoGenError | None = None
        for path in HEALTH_PATHS:
            url = self.config.url(path)
            try:
                req = urllib.request.Request(url, method="GET", headers=self._headers(False))
                with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                    body = resp.read().decode("utf-8", "replace")[:2000]
                    return {"path": path, "status": resp.status, "body": body}
            except urllib.error.HTTPError as exc:
                # A 4xx still means the host is up and reachable.
                return {"path": path, "status": exc.code, "body": exc.read().decode("utf-8", "replace")[:2000]}
            except urllib.error.URLError as exc:
                last = VideoGenError(f"{url} unreachable: {exc.reason}")
        raise last or VideoGenError("no health endpoint responded")

    # -- high level --------------------------------------------------------

    def generate(self, prompt: str, **params: Any) -> Job:
        """Submit a generation request and return a :class:`Job`.

        Extra keyword arguments (e.g. ``duration``, ``seed``, ``width``) are
        passed straight through in the request body.
        """
        body: dict[str, Any] = {"prompt": prompt, **params}
        if self.config.provider:
            body.setdefault("provider", self.config.provider)

        paths = [self.generate_path] if self.generate_path else list(GENERATE_PATHS)
        last: VideoGenError | None = None
        for path in paths:
            url = self.config.url(path)
            try:
                payload = self._request("POST", url, body=body)
            except VideoGenError as exc:
                last = exc
                continue
            # Remember the working path for subsequent calls.
            self.generate_path = path
            return _job_from_payload(payload)
        raise last or VideoGenError("could not submit generation request")

    def get_status(self, job_id: str) -> Job:
        """Fetch the current status of ``job_id``."""
        templates = (
            [self.status_path_template] if self.status_path_template else list(STATUS_PATH_TEMPLATES)
        )
        last: VideoGenError | None = None
        for tpl in templates:
            url = self.config.url(tpl.format(job_id=job_id))
            try:
                payload = self._request("GET", url)
            except VideoGenError as exc:
                last = exc
                continue
            self.status_path_template = tpl
            return _job_from_payload(payload)
        raise last or VideoGenError(f"could not fetch status for job {job_id}")

    def wait(
        self,
        job: Job | str,
        *,
        poll_interval: float = 2.0,
        max_wait: float = 600.0,
        on_progress: Callable[[Job], None] | None = None,
        _sleep: Callable[[float], None] = time.sleep,
        _now: Callable[[], float] = time.monotonic,
    ) -> Job:
        """Poll until the job is done or failed.

        ``on_progress`` is invoked with the latest :class:`Job` after each poll.
        Raises :class:`VideoGenError` on failure or timeout.
        """
        job_id = job.job_id if isinstance(job, Job) else job
        if not job_id:
            # Synchronous service that returned the video straight away.
            if isinstance(job, Job) and job.done:
                return job
            raise VideoGenError("job has no id to poll")

        deadline = _now() + max_wait
        while True:
            current = self.get_status(job_id)
            if on_progress:
                on_progress(current)
            if current.failed:
                raise VideoGenError(f"job {job_id} failed: {current.raw}")
            if current.done:
                return current
            if _now() >= deadline:
                raise VideoGenError(f"job {job_id} did not finish within {max_wait}s")
            _sleep(poll_interval)

    def download(self, job: Job | str, dest: str) -> str:
        """Download the finished video to ``dest``; returns ``dest``."""
        video_url = job.video_url if isinstance(job, Job) else job
        if not video_url:
            raise VideoGenError("job has no video_url to download")
        # Allow relative URLs returned by the service.
        if video_url.startswith("/"):
            video_url = self.config.url(video_url)
        data = self._request("GET", video_url, raw=True)
        with open(dest, "wb") as fh:
            fh.write(data)
        return dest

    def generate_to_file(self, prompt: str, dest: str, **params: Any) -> str:
        """Convenience: submit, wait, and download in one call."""
        job = self.generate(prompt, **params)
        if not job.done:
            job = self.wait(job)
        return self.download(job, dest)
