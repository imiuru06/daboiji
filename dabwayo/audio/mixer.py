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


def _duck_expr(base_gain: float, clip_start: float, duck: dict) -> str:
    """Build an ffmpeg ``volume`` expression that dips the base gain during
    ducking windows, with attack/release ramps.

    ``duck`` = {windows:[[a,b]...] absolute s, amount_db, attack, release}.
    The ``volume`` filter runs on the PTS-reset stream (t starts at 0 at the
    clip's own start), so absolute windows are shifted by ``clip_start``. The
    overall factor is the minimum envelope across all windows (deepest dip
    wins), times the static base gain."""
    d = 10 ** (float(duck.get("amount_db", -12.0)) / 20.0)
    atk = max(1e-3, float(duck.get("attack", 0.25)))
    rel = max(1e-3, float(duck.get("release", 0.6)))
    envs = []
    for a, b in duck.get("windows", []):
        la, lb = float(a) - clip_start, float(b) - clip_start
        if lb <= 0:
            continue
        la = max(0.0, la)
        # 1 before la; ramp 1->d over [la,la+atk]; hold d to lb; ramp d->1 over [lb,lb+rel]
        env = (
            f"if(lt(t,{la:.4f}),1,"
            f"if(lt(t,{la + atk:.4f}),1+({d:.5f}-1)*(t-{la:.4f})/{atk:.4f},"
            f"if(lt(t,{lb:.4f}),{d:.5f},"
            f"if(lt(t,{lb + rel:.4f}),{d:.5f}+(1-{d:.5f})*(t-{lb:.4f})/{rel:.4f},1))))"
        )
        envs.append(env)
    if not envs:
        return f"{base_gain:.4f}"
    factor = envs[0]
    for e in envs[1:]:
        factor = f"min({factor},{e})"
    return f"{base_gain:.5f}*{factor}"


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
        duck = getattr(c, "duck", None)
        if duck and duck.get("windows"):
            expr = _duck_expr(gain, c.start, duck)
            chain += f",volume=eval=frame:volume='{expr}'"
        else:
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
