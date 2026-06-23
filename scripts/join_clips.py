#!/usr/bin/env python3
"""Join video clips into one, auto-matching their look by default.

AI-generated clips drift in white balance / saturation even when the seam
frame matches, so two clips placed back to back look like different cameras.
This tool makes *colour conform* the default step of joining: it measures each
clip, conforms every clip to a reference (the first clip by default, at 80%
strength) so the whole thing reads as one look, then joins them — choosing a
hard cut where the seam frames already match and a short crossfade where they
don't.

    python3 scripts/join_clips.py a.mp4 b.mp4 [c.mp4 ...] -o joined.mp4

Defaults (no flags): conform ON, anchor = first clip, strength 0.8, seam auto.
    --no-conform        join without colour matching
    --strength 0..1     how strongly to conform (default 0.8)
    --anchor N          index of the reference clip (default 0)
    --crossfade S       force an S-second crossfade at every seam
    --cut               force hard cuts at every seam
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import warnings

warnings.filterwarnings("ignore")

import imageio.v2 as iio
import imageio_ffmpeg
import numpy as np

try:
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None

FF = imageio_ffmpeg.get_ffmpeg_exe()


def profile(path: str, n: int = 16) -> dict:
    """Sample n frames -> mean R/G/B, luminance, saturation and sharpness."""
    r = iio.get_reader(path)
    tot = r.count_frames()
    idx = np.linspace(0, tot - 1, n).astype(int)
    px, sharp = [], []
    for i in idx:
        try:
            f = r.get_data(int(i))
        except Exception:  # noqa: BLE001
            continue
        px.append((f.astype(np.float32) / 255.0).reshape(-1, 3))
        if cv2 is not None:
            g = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY).astype(np.float32)
            sharp.append(float(cv2.Laplacian(g, cv2.CV_32F).var()))
    r.close()
    flat = np.concatenate(px)
    mx, mn = flat.max(1), flat.min(1)
    sat = np.where(mx > 1e-6, (mx - mn) / (mx + 1e-6), 0.0)
    m = flat.mean(0)
    lum = float((flat @ np.array([0.2126, 0.7152, 0.0722], np.float32)).mean())
    return {"R": float(m[0]), "G": float(m[1]), "B": float(m[2]),
            "L": lum, "sat": float(sat.mean()),
            "sharp": float(np.mean(sharp)) if sharp else 0.0}


def duration(path: str) -> float:
    r = iio.get_reader(path)
    meta = r.get_meta_data()
    n = r.count_frames()
    r.close()
    return n / float(meta.get("fps", 24) or 24)


def has_audio(path: str) -> bool:
    out = subprocess.run([FF, "-i", path], capture_output=True, text=True).stderr
    return "Audio:" in out


def edge_frames(path: str):
    r = iio.get_reader(path)
    n = r.count_frames()
    first = r.get_data(0).astype(np.float32)
    last = r.get_data(n - 1).astype(np.float32)
    r.close()
    return first, last


def conform_filter(prof: dict, ref: dict, strength: float) -> str:
    """Conform prof -> ref. White balance (per-channel gain) is the reliable,
    perceptible cue and gets the full strength; saturation is noisy and tends
    to drift *within* a clip, so it is nudged gently and clamped tight."""
    def g(ch):
        v = 1.0 + (ref[ch] / max(prof[ch], 1e-6) - 1.0) * strength
        return float(np.clip(v, 0.6, 1.7))
    gr, gg, gb = g("R"), g("G"), g("B")
    sat = float(np.clip(1.0 + (ref["sat"] / max(prof["sat"], 1e-6) - 1.0) * strength * 0.5,
                        0.9, 1.12))
    f = (f"colorchannelmixer=rr={gr:.4f}:gg={gg:.4f}:bb={gb:.4f},"
         f"eq=saturation={sat:.4f}")
    # sharpness match: gently sharpen a softer clip toward the reference
    if prof.get("sharp") and ref.get("sharp"):
        ratio = ref["sharp"] / max(prof["sharp"], 1e-6)
        if ratio > 1.05:
            # deliberately under-correct: closes most of the gap, never crunchy
            amt = float(np.clip((ratio - 1.0) * strength, 0.0, 0.8))
            if amt > 0.05:
                f += f",unsharp=5:5:{amt:.3f}:5:5:0.0"
    return f


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips", nargs="+", help="input clips, in order (>=2)")
    ap.add_argument("-o", "--out", default="joined.mp4")
    ap.add_argument("--no-conform", action="store_true")
    ap.add_argument("--strength", type=float, default=0.7)
    ap.add_argument("--anchor", type=int, default=0)
    ap.add_argument("--crossfade", type=float, default=None)
    ap.add_argument("--cut", action="store_true")
    a = ap.parse_args()
    clips = a.clips
    if len(clips) < 2:
        print("need at least 2 clips"); return 2
    for c in clips:
        if not os.path.isfile(c):
            print("missing:", c); return 2

    profs = [profile(c) for c in clips]
    ref = profs[a.anchor]
    durs = [duration(c) for c in clips]
    audio = all(has_audio(c) for c in clips)

    # per-clip colour conform filter (identity for the anchor)
    vf = []
    print("colour conform (anchor = clip %d, strength %.2f):" % (a.anchor, a.strength))
    for i, p in enumerate(profs):
        if a.no_conform or i == a.anchor:
            vf.append("null")
            print(f"  clip{i}: reference / unchanged" if i == a.anchor else f"  clip{i}: off")
        else:
            f = conform_filter(p, ref, a.strength)
            vf.append(f)
            warm_s = (p["R"] / p["B"]); warm_r = (ref["R"] / ref["B"])
            print(f"  clip{i}: warm {warm_s:.2f}->{warm_r:.2f}, sat {p['sat']:.3f}->{ref['sat']:.3f}, "
                  f"sharp {p.get('sharp',0):.1f}->{ref.get('sharp',0):.1f}\n         [{f}]")

    # seam decision per boundary
    seams = []
    for k in range(len(clips) - 1):
        if a.cut:
            seams.append(0.06)
        elif a.crossfade is not None:
            seams.append(max(0.06, a.crossfade))
        else:
            _, last = edge_frames(clips[k])
            first, _ = edge_frames(clips[k + 1])
            h = min(last.shape[0], first.shape[0]); w = min(last.shape[1], first.shape[1])
            diff = float(np.abs(last[:h, :w] - first[:h, :w]).mean())
            xf = 0.08 if diff < 18 else 0.40
            seams.append(xf)
            print(f"  seam {k}->{k+1}: boundary diff {diff:.1f} -> "
                  f"{'cut' if xf < 0.1 else f'{xf}s crossfade'}")

    # build filter graph
    parts = [f"[{i}:v]{vf[i]},format=yuv420p,settb=AVTB[v{i}]" for i in range(len(clips))]
    cur = "v0"; run = durs[0]
    for k in range(len(clips) - 1):
        d = seams[k]; off = max(0.0, run - d)
        out = f"vx{k}"
        parts.append(f"[{cur}][v{k+1}]xfade=transition=fade:duration={d}:offset={off:.3f}[{out}]")
        cur = out; run = run + durs[k + 1] - d
    fg = ";".join(parts)
    maps = ["-map", f"[{cur}]"]
    if audio:
        acur = "0:a"
        ap_parts = []
        arun_built = False
        for k in range(len(clips) - 1):
            out = f"ax{k}"
            ap_parts.append(f"[{acur}][{k+1}:a]acrossfade=d={seams[k]}[{out}]")
            acur = out
        fg = fg + ";" + ";".join(ap_parts)
        maps += ["-map", f"[{acur}]"]

    cmd = [FF, "-y"]
    for c in clips:
        cmd += ["-i", c]
    cmd += ["-filter_complex", fg] + maps + [
        "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p"]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "160k"]
    cmd += [a.out]
    print("\nrendering ->", a.out)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:]); return 1
    print("done:", a.out, f"({os.path.getsize(a.out)//1024} KB, ~{run:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
