# daboiji

A small, **dependency-free** Python client and CLI for the **DABWAYO**
video-generation service. Standard library only — nothing to `pip install` to
run it.

## Configuration

The client is driven entirely by environment variables:

| Variable                     | Required | Default  | Meaning                                  |
| ---------------------------- | -------- | -------- | ---------------------------------------- |
| `DABWAYO_VIDEOGEN_URL`       | yes      | —        | Base URL of the video-gen service        |
| `DABWAYO_VIDEOGEN_PROVIDER`  | no       | `remote` | Provider mode sent with each request     |
| `DABWAYO_VIDEOGEN_API_KEY`   | no       | —        | Bearer token, if the service requires it |
| `DABWAYO_VIDEOGEN_TIMEOUT`   | no       | `60`     | Per-request timeout in seconds           |

```bash
export DABWAYO_VIDEOGEN_URL='https://<host>.trycloudflare.com'
export DABWAYO_VIDEOGEN_PROVIDER=remote
```

> **Network note (Claude Code on the web):** outbound access is governed by the
> environment's network egress allowlist. To let this client reach the service,
> add the service host (e.g. `*.trycloudflare.com`) to the environment's egress
> settings. **Allowlist changes apply to *new* sessions only** — a running
> container keeps the network policy it started with, so start a fresh session
> after editing the allowlist. See
> <https://code.claude.com/docs/en/claude-code-on-the-web>.

## Install

```bash
pip install -e .          # exposes the `dabwayo` command
# or just run from source (no install needed):
PYTHONPATH=src python -m dabwayo.cli --help
```

## CLI usage

```bash
dabwayo config                                  # show resolved config
dabwayo ping                                    # check the service is reachable
dabwayo generate "a cat surfing a wave" -o cat.mp4
dabwayo generate "city at night" --duration 6 --seed 42 --param fps=24
dabwayo status <job_id>                          # poll a specific job
```

`generate` submits the prompt, waits for the job to finish (printing progress to
stderr), then downloads the result to `-o/--output` (default `output.mp4`).

## Library usage

```python
from dabwayo import VideoGenClient

client = VideoGenClient()                        # reads env vars
path = client.generate_to_file("a cat surfing", "cat.mp4", duration=5)
print("saved", path)
```

Or step by step:

```python
job = client.generate("a cat surfing", duration=5)
job = client.wait(job, on_progress=lambda j: print(j.status, j.progress))
client.download(job, "cat.mp4")
```

## Verified service contract

Probed live against the deployed DABWAYO service (a FastAPI app — see `/docs`):

| Endpoint        | Method | Notes                                                              |
| --------------- | ------ | ----------------------------------------------------------------- |
| `/health`       | GET    | `{"ok":true,"backend":"modelscope-1.7b","modes":["t2v"],"gpu":"Tesla T4"}` |
| `/generate`     | POST   | **Synchronous** — returns the encoded video directly (no job id)  |

There is **no status/polling endpoint**: generation is synchronous, so the
client saves the bytes returned by `POST /generate` straight to disk. The
async `wait`/`status` flow below is kept as a fallback for deployments that
*do* hand back a job id.

## How it adapts to the service

The exact REST paths can differ between deployments, so the client tries a set
of conventional candidates and remembers the one that works:

- **generate:** `POST /generate` (confirmed), `/api/generate`, `/v1/generate`, …
- **status:** `GET /status/{id}`, `/jobs/{id}`, `/result/{id}`, … (fallback only)
- a synchronous (binary) `/generate` response is written straight to the output
  file; a JSON response is matched loosely (`job_id`/`id`/`task_id`,
  `video_url`/`url`/`output`, `status`/`state`, …).

If you already know the endpoints, pass them explicitly:

```python
VideoGenClient(generate_path="/api/generate", status_path_template="/jobs/{job_id}")
```

Run `dabwayo ping` once the host is allowlisted to confirm reachability; the
real API shape can then be locked in via those overrides if needed.

## Development

```bash
pip install -e ".[dev]"
pytest
```
