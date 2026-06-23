"""Command-line interface for the DABWAYO video-gen client.

Examples
--------
    dabwayo config                       # show resolved configuration
    dabwayo ping                         # check the service is reachable
    dabwayo generate "a cat surfing" -o cat.mp4
    dabwayo status <job_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from . import __version__
from .config import ConfigError, load_config
from .client import VideoGenClient, VideoGenError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dabwayo", description="DABWAYO video-gen client")
    parser.add_argument("--version", action="version", version=f"dabwayo {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("config", help="print resolved configuration")
    sub.add_parser("ping", help="probe the service health endpoints")

    g = sub.add_parser("generate", help="generate a video from a prompt")
    g.add_argument("prompt", help="text prompt")
    g.add_argument("-o", "--output", default="output.mp4", help="output file (default: output.mp4)")
    # Parameters understood by the DABWAYO modelscope-1.7b server.
    g.add_argument("--num-frames", type=int, help="number of frames (server default 16)")
    g.add_argument("--fps", type=int, help="frames per second (server default 12)")
    g.add_argument("--steps", type=int, help="inference steps (server default 20)")
    g.add_argument("--duration", type=float, help="clip duration in seconds (advisory)")
    g.add_argument("--seed", type=int, help="random seed")
    g.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="extra request parameter (repeatable)",
    )
    g.add_argument("--poll-interval", type=float, default=2.0, help="status poll interval (s)")
    g.add_argument("--max-wait", type=float, default=600.0, help="give up after this many seconds")

    s = sub.add_parser("status", help="fetch the status of a job")
    s.add_argument("job_id")

    return parser


def _parse_params(items: Sequence[str]) -> dict[str, object]:
    out: dict[str, object] = {}
    for item in items:
        if "=" not in item:
            raise ConfigError(f"--param must look like KEY=VALUE, got {item!r}")
        key, _, value = item.partition("=")
        # Best-effort typing: int, float, bool, else string.
        out[key.strip()] = _coerce(value.strip())
    return out


def _coerce(value: str) -> object:
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    for cast in (int, float):
        try:
            return cast(value)
        except ValueError:
            pass
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.command == "config":
        print(
            json.dumps(
                {
                    "base_url": config.base_url,
                    "provider": config.provider,
                    "api_key_set": bool(config.api_key),
                    "timeout": config.timeout,
                },
                indent=2,
            )
        )
        return 0

    client = VideoGenClient(config)

    try:
        if args.command == "ping":
            info = client.ping()
            print(json.dumps(info, indent=2))
            return 0

        if args.command == "status":
            job = client.get_status(args.job_id)
            print(json.dumps(job.raw or {"status": job.status}, indent=2))
            return 0

        if args.command == "generate":
            params = _parse_params(args.param)
            if args.num_frames is not None:
                params["num_frames"] = args.num_frames
            if args.fps is not None:
                params["fps"] = args.fps
            if args.steps is not None:
                params["steps"] = args.steps
            if args.duration is not None:
                params["duration"] = args.duration
            if args.seed is not None:
                params["seed"] = args.seed

            job = client.generate(args.prompt, **params)
            print(f"submitted job: {job.job_id or '(synchronous)'} [{job.status}]", file=sys.stderr)

            if not job.done:
                def _report(j) -> None:
                    pct = f" {j.progress:.0%}" if j.progress is not None else ""
                    print(f"  status: {j.status}{pct}", file=sys.stderr)

                job = client.wait(
                    job,
                    poll_interval=args.poll_interval,
                    max_wait=args.max_wait,
                    on_progress=_report,
                )

            dest = client.download(job, args.output)
            print(dest)
            return 0
    except (VideoGenError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error("unknown command")  # pragma: no cover
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
