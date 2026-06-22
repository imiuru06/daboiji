"""Annotate an existing video with a scenario/product-intro overlay.

Takes the (de-watermarked) car clip and layers a styled explainer on top:
lower-third title, timed speech-bubble callouts pointing at features, a
spotlight that follows the action, spec chips and an outro CTA — themed to
an accent colour sampled from the footage so the overlay matches its style.

Run: PYTHONPATH=. python examples/demo_annotate.py
"""
from __future__ import annotations

import os

import numpy as np
from PIL import Image

import videoforge as vf
from videoforge import keyframes as K

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "output", "dewatermarked_lama.mp4")
OUT = os.path.join(ROOT, "output", "product_intro.mp4")
INK = "#0a0c12"


def sample_accent(path: str, times=(2.0, 5.0, 8.0)) -> str:
    """Derive a vivid UI accent from the footage's dominant saturated hue.

    Collects highly-saturated pixels across a few frames, takes their median
    colour and normalises it to a bright, punchy accent (keeps the hue, lifts
    saturation/value) so overlays read clearly while matching the scene.
    """
    import colorsys

    import imageio.v2 as imageio
    rdr = imageio.get_reader(path)
    fps = rdr.get_meta_data().get("fps", 24)
    sel = []
    for t in times:
        try:
            arr = np.asarray(rdr.get_data(int(t * fps)), np.float32) / 255.0
        except (IndexError, RuntimeError):
            continue
        mx = arr.max(2); mn = arr.min(2)
        sat = (mx - mn) / (mx + 1e-6)
        mask = (sat > 0.5) & (mx > 0.4)
        if mask.sum() > 50:
            sel.append(arr[mask])
    if not sel:
        return "#e5394a"
    r, g, b = np.median(np.concatenate(sel), axis=0)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    r, g, b = colorsys.hsv_to_rgb(h, min(1.0, s * 1.25 + 0.15), 0.92)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def build() -> vf.Project:
    accent = sample_accent(SRC)
    print("sampled accent:", accent)
    W, H = 1280, 720

    p = vf.Project(W, H, fps=24, duration=10.0, background=INK, name="product_intro")

    # base footage
    p.track("video", "footage").add(
        vf.Project.video(SRC, fit="cover", size=[W, H]), 0, 10.0)

    # cinematic focus that matches the moody tunnel footage
    p.master_effect("spotlight",
                    region={"shape": "ellipse", "rect": [240, 90, 800, 560], "feather": 120},
                    darken=K((0, 0.0), (1.0, 0.42), (8.5, 0.42), (9.6, 0.0)))

    overlay = p.track("video", "overlay")
    calls = p.track("video", "callouts")

    def callout(text, pos, side, start, dur, fontsize=30, mw=460):
        (calls.add(vf.Project.callout(
            text, font="kr-bold", font_size=fontsize, fill="#ffffff",
            color="#0b0e16", stroke=accent, stroke_width=3, tail_side=side,
            max_width=mw, padding=20, radius=16), start, dur)
            .position(pos)
            .effect("glow", intensity=0.18, radius=8)
            .transition_in("zoom", 0.4, **{"from": 0.7})
            .transition_out("fade", 0.3))

    # ---- lower-third brand intro (0.3 - 3.2s) ----
    (overlay.add(vf.Project.shape("rect", size=[10, 96], fill=accent), 0.3, 2.9)
        .position([92, 600]).anchor("left")
        .transition_in("slide", 0.5, direction="up", distance=30)
        .transition_out("fade", 0.4))
    (overlay.add(vf.Project.text("AURORA GT", size=70, font="display", color="#ffffff",
                                 align="left"), 0.4, 2.8)
        .position([120, 578]).anchor("left")
        .transition_in("slide", 0.5, direction="left", distance=60)
        .transition_out("fade", 0.4).effect("glow", intensity=0.25, radius=10))
    (overlay.add(vf.Project.text("일렉트릭 하이퍼카  ·  제품 소개", size=26, font="kr",
                                 color=accent, align="left"), 0.7, 2.5)
        .position([122, 636]).anchor("left")
        .transition_in("fade", 0.6).transition_out("fade", 0.4))

    # ---- timed feature callouts ----
    callout("전동 리트랙터블 리어윙\n고속 주행 시 자동 전개", [640, 330], "top", 0.8, 2.6, 30, 440)
    callout("20인치 단조 카본 휠\n세라믹 브레이크", [560, 470], "left", 3.2, 2.6, 30, 380)
    callout("LED 매트릭스 헤드램프\n적응형 하이빔", [900, 470], "top", 5.9, 2.4, 30, 400)

    # ---- spec chips lower-third (7.4 - 9.6s) ----
    chips = [("0 → 100 km/h", "2.9s"), ("최고출력", "1,020 PS"), ("최고속도", "350 km/h")]
    cw, gap = 300, 24
    x0 = W / 2 - (len(chips) * cw + (len(chips) - 1) * gap) / 2
    for i, (label, value) in enumerate(chips):
        cx = x0 + i * (cw + gap) + cw / 2
        st = 7.4 + i * 0.18
        (overlay.add(vf.Project.shape("rounded_rect", size=[cw, 96], fill="#0e1320",
                                      stroke=accent, stroke_width=2, radius=14), st, 9.7 - st)
            .position([cx, 632])
            .transition_in("slide", 0.5, direction="up", distance=50)
            .transition_out("fade", 0.3).effect("glow", intensity=0.15, radius=6))
        (overlay.add(vf.Project.text(label, size=22, font="kr", color="#9fb0cf"), st + 0.05, 9.7 - st)
            .position([cx, 612]).transition_in("fade", 0.4).transition_out("fade", 0.3))
        (overlay.add(vf.Project.text(value, size=34, font="display", color="#ffffff"), st + 0.05, 9.7 - st)
            .position([cx, 648]).transition_in("fade", 0.4).transition_out("fade", 0.3))

    # ---- outro CTA ----
    (overlay.add(vf.Project.text("AURORA GT", size=120, font="display", color="#ffffff"), 9.0, 1.0)
        .position([W / 2, H / 2 - 30])
        .transition_in("zoom", 0.5, **{"from": 0.85}).effect("glow", intensity=0.4, radius=16))
    (overlay.add(vf.Project.text("2026 · 사전 예약 시작", size=34, font="kr", color=accent), 9.2, 0.8)
        .position([W / 2, H / 2 + 60]).transition_in("fade", 0.5))

    # master polish to blend overlay with footage grade
    p.master_effect("vignette", amount=0.3, softness=0.7)
    p.master_effect("grain", amount=0.02)

    # keep the original footage audio
    p.audio(SRC, start=0.0)
    return p


def main():
    p = build()
    p.save(os.path.join(ROOT, "examples", "product_intro_spec.json"))

    def prog(i, n):
        print(f"\r  rendering {i}/{n}", end="", flush=True)

    p.render(OUT, crf=19, preset="medium", progress=prog)
    print("\nDONE", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
