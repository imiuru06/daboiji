"""Remove a static watermark from a video via per-frame inpainting.

Decodes the source through VideoForge's `video` element, applies the
`inpaint` effect over the given region(s) every frame, renders, and muxes
the original audio back losslessly.

Usage:
    PYTHONPATH=. python examples/remove_watermark.py INPUT OUTPUT \
        --region X Y W H [--region X Y W H ...] [--radius 6] [--grow 4]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile

import imageio.v2 as imageio
import imageio_ffmpeg

import videoforge as vf


def remove_watermark(src: str, out: str, regions, radius=6, grow=4,
                     feather=3, method="telea", crf=18):
    meta = imageio.get_reader(src).get_meta_data()
    fps = float(meta.get("fps", 24))
    w, h = meta.get("size", (1280, 720))
    nframes = meta.get("nframes")
    duration = meta.get("duration") or (nframes / fps if nframes else None)

    region_specs = [
        {"shape": "rect", "rect": list(r), "feather": feather} for r in regions
    ]

    p = vf.Project(int(w), int(h), fps=fps, duration=duration, name="dewatermark")
    p.track("video").add(
        vf.Project.video(src, fit="stretch", size=[int(w), int(h)]),
        0, duration,
    )
    p.master_effect("inpaint", region=region_specs, radius=radius,
                    grow=grow, method=method)

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name

    def prog(i, n):
        print(f"\r  inpainting {i}/{n}", end="", flush=True)

    p.render(tmp, crf=crf, preset="medium", progress=prog)
    print()

    # mux original audio (lossless copy) if present
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    has_audio = subprocess.run(
        [ff, "-i", src], capture_output=True, text=True
    ).stderr.find("Audio:") != -1
    if has_audio:
        cmd = [ff, "-y", "-v", "error", "-i", tmp, "-i", src,
               "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy",
               "-shortest", out]
    else:
        cmd = [ff, "-y", "-v", "error", "-i", tmp, "-c", "copy", out]
    subprocess.run(cmd, check=True)
    os.remove(tmp)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--region", action="append", nargs=4, type=int,
                    metavar=("X", "Y", "W", "H"), required=True)
    ap.add_argument("--radius", type=int, default=6)
    ap.add_argument("--grow", type=int, default=4)
    ap.add_argument("--feather", type=int, default=3)
    ap.add_argument("--method", choices=["telea", "ns"], default="telea")
    ap.add_argument("--crf", type=int, default=18)
    args = ap.parse_args()
    out = remove_watermark(args.input, args.output, args.region, args.radius,
                           args.grow, args.feather, args.method, args.crf)
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
