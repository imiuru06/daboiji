"""Video encoding via the bundled static ffmpeg (imageio-ffmpeg).

The encoder streams raw RGB frames to ffmpeg over a pipe and muxes a mixed
audio track if one is provided. H.264 + yuv420p for broad compatibility.
"""
from __future__ import annotations

import subprocess
import tempfile
from typing import Optional

import imageio_ffmpeg
import numpy as np


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


class FrameEncoder:
    def __init__(self, path: str, width: int, height: int, fps: float,
                 crf: int = 18, preset: str = "medium",
                 pix_fmt: str = "yuv420p", audio_path: Optional[str] = None):
        self.path = path
        self.width = width
        self.height = height
        self.fps = fps
        cmd = [
            ffmpeg_exe(), "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{width}x{height}", "-r", f"{fps}",
            "-i", "pipe:0",
        ]
        if audio_path:
            cmd += ["-i", audio_path]
        cmd += [
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-pix_fmt", pix_fmt, "-movflags", "+faststart",
        ]
        if audio_path:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
        cmd += [path]
        self.cmd = cmd
        # ffmpeg logs to stderr continuously; draining it via a PIPE we never
        # read would deadlock long renders once the OS buffer fills. Route it
        # to a temp file we only read if encoding fails.
        self._log = tempfile.TemporaryFile()
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=self._log,
        )

    def write(self, rgb_uint8: np.ndarray):
        self.proc.stdin.write(rgb_uint8.tobytes())

    def close(self):
        if self.proc.stdin:
            self.proc.stdin.close()
        ret = self.proc.wait()
        if ret != 0:
            self._log.seek(0)
            err = self._log.read().decode("utf-8", "replace")[-2000:]
            self._log.close()
            raise RuntimeError(f"ffmpeg failed (code {ret}):\n{err}")
        self._log.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if any(exc):
            self.proc.kill()
        else:
            self.close()
