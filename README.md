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
> add the service host (e.g. `oldest-hypothesis-have-oven.trycloudflare.com`)
> to the environment's egress settings. Until then, `ping`/`generate` will
> report the host as unreachable. See
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

## How it adapts to the service

The exact REST paths can differ between deployments, so the client tries a set
of conventional candidates and remembers the one that works:

- **generate:** `POST /generate`, `/api/generate`, `/v1/generate`, `/videos`, …
- **status:** `GET /status/{id}`, `/jobs/{id}`, `/result/{id}`, …
- response fields are matched loosely (`job_id`/`id`/`task_id`,
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
