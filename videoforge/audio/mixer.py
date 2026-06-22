"""Audio mixing via ffmpeg filter graphs.

Takes a list of AudioClip placements and produces a single mixed wav/aac
track aligned to the timeline, applying per-clip delay, trim, gain and
fades. Returns the path to the rendered audio, or None if no audio.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from typing import List, Optional

from ..render.encoder import ffmpeg_exe


def mix_audio(audio_clips: List, total_duration: float,
              out_dir: Optional[str] = None) -> Optional[str]:
    if not audio_clips:
        return None
    out_dir = out_dir or tempfile.gettempdir()
    out_path = os.path.join(out_dir, f"vf_audio_{os.getpid()}.m4a")

    cmd = [ffmpeg_exe(), "-y"]
    for c in audio_clips:
        cmd += ["-i", c.path]

    filters = []
    labels = []
    for i, c in enumerate(audio_clips):
        dur = c.duration if c.duration else max(0.1, total_duration - c.start)
        chain = f"[{i}:a]atrim=start={c.in_point}:duration={dur},asetpts=PTS-STARTPTS"
        gain = 10 ** (c.gain_db / 20.0)
        chain += f",volume={gain:.4f}"
        if c.fade_in > 0:
            chain += f",afade=t=in:st=0:d={c.fade_in}"
        if c.fade_out > 0:
            chain += f",afade=t=out:st={max(0.0, dur - c.fade_out):.3f}:d={c.fade_out}"
        delay_ms = int(c.start * 1000)
        chain += f",adelay={delay_ms}|{delay_ms}"
        lab = f"a{i}"
        filters.append(f"{chain}[{lab}]")
        labels.append(f"[{lab}]")

    n = len(labels)
    mix = "".join(labels) + f"amix=inputs={n}:duration=longest:normalize=0[out]"
    filter_complex = ";".join(filters + [mix])

    cmd += [
        "-filter_complex", filter_complex, "-map", "[out]",
        "-t", f"{total_duration}", "-c:a", "aac", "-b:a", "192k", out_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"audio mix failed:\n{proc.stderr[-1500:]}")
    return out_path
