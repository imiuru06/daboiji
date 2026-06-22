"""Showcase render: a ~15s cinematic motion-graphics piece.

Demonstrates: animated gradients, Ken-Burns on imagery, keyframed kinetic
typography, lighting (ambient/point/leak), glow & color-grade effects,
staggered transitions, blend modes, and a synthesized audio bed.

Run:  python examples/generate_assets.py && python examples/demo_showcase.py
"""
from __future__ import annotations

import os

import videoforge as vf
from videoforge import keyframes as K

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GEN = os.path.join(ROOT, "assets", "generated")
OUT = os.path.join(ROOT, "output", "showcase.mp4")

W, H = 1920, 1080
CX, CY = W / 2, H / 2

# palette
INK = "#070912"
ACCENT = "#5cc8ff"
ACCENT2 = "#9a7bff"
PAPER = "#eaf2ff"


def build() -> vf.Project:
    p = vf.Project(W, H, fps=30, background=INK, name="VideoForge Showcase")

    bg = p.track("video", "bg")
    mid = p.track("video", "mid")
    fg = p.track("video", "fg")
    light = p.track("video", "light")

    # =================== SCENE A — cold open (0.0–5.0) ===================
    bg.add(vf.Project.gradient(
        [[0, "#13224a"], [0.55, "#0b1430"], [1, INK]],
        kind="radial", center=[0.5, 0.42], radius=0.95), 0, 5.2)

    # nebula texture, screen-blended, slow Ken Burns push-in
    (mid.add(vf.Project.image(os.path.join(GEN, "texture.png"), fit="cover",
                              size=[W, H]), 0, 5.2)
        .blend("screen")
        .opacity(K((0, 0.0), (0.8, 0.55), (4.4, 0.55), (5.2, 0.0)))
        .scale(K((0, 1.06), (5.2, 1.22), default=1.06)))

    # logo: zoom + settle, with glow
    (fg.add(vf.Project.image(os.path.join(GEN, "logo.png"), size=[360, 360]), 0.3, 4.7)
        .position([CX, CY - 150])
        .scale(K((0.3, 0.4), (1.2, 1.0, "ease_out_back"), default=0.4))
        .opacity(K((0.3, 0), (1.0, 1.0)))
        .rotation(K((0.3, -12), (1.4, 0, "ease_out_cubic")))
        .effect("glow", intensity=0.55, threshold=0.5, radius=22)
        .transition_out("fade", 0.5))

    # title — kinetic, scales down into place
    (fg.add(vf.Project.text("VIDEOFORGE", size=150, font="display", color=PAPER,
                            letter_spacing=8), 1.0, 4.2)
        .position([CX, CY + 130])
        .scale(K((1.0, 1.18), (1.9, 1.0, "ease_out_cubic"), default=1.18))
        .opacity(K((1.0, 0), (1.6, 1.0)))
        .effect("glow", intensity=0.35, radius=14)
        .transition_out("fade", 0.5))

    (fg.add(vf.Project.text("a modular video engine · MCP-ready", size=40,
                            font="sans", color=ACCENT, letter_spacing=4), 1.8, 3.4)
        .position([CX, CY + 250])
        .transition_in("slide", 0.7, direction="up", distance=40)
        .transition_out("fade", 0.4))

    # lighting for scene A
    (light.add(vf.Project.solid("#000000", size=[W, H]), 0, 5.2)
        .blend("screen")
        .fx({"type": "ambient", "color": "#16294f", "intensity": 0.25})
        .effect("light", position=[0.5, 0.18], color="#7db8ff",
                intensity=0.8, radius=0.8, falloff=2.2)
        .effect("light_leak",
                color="#ff8a4c",
                intensity=K((0, 0.0), (2.5, 0.0), (3.6, 0.45), (5.0, 0.0)),
                position=K((2.5, 0.1), (5.0, 1.0)), width=0.22))

    # =================== SCENE B — feature cards (5.2–10.2) =============
    bg.add(vf.Project.gradient([[0, "#0e1838"], [1, INK]],
                               kind="linear",
                               angle=K((5.2, 60), (10.2, 110))), 5.2, 5.0)

    (fg.add(vf.Project.text("BUILT FOR MOTION", size=58, font="sans-bold",
                            color=PAPER, letter_spacing=6), 5.5, 4.7)
        .position([CX, 230])
        .transition_in("blur_in", 0.6, radius=26)
        .transition_out("fade", 0.4))

    cards = [
        ("KEYFRAMES", "easing · animation curves", ACCENT),
        ("LIGHTING", "point · ambient · leaks", ACCENT2),
        ("EFFECTS", "glow · grade · grain", "#54e0b0"),
    ]
    gap = 560
    x0 = CX - gap
    for i, (title, sub, col) in enumerate(cards):
        cx = x0 + i * gap
        st = 5.9 + i * 0.22
        (mid.add(vf.Project.shape("rounded_rect", size=[460, 360], fill="#101b3a",
                                  stroke=col, stroke_width=3, radius=28), st, 10.2 - st)
            .position([cx, CY + 60])
            .transition_in("slide", 0.6, direction="up", distance=120)
            .transition_out("fade", 0.4)
            .effect("glow", intensity=0.2, radius=10))
        (fg.add(vf.Project.text(title, size=52, font="display", color=col), st + 0.1, 10.2 - st - 0.1)
            .position([cx, CY - 10])
            .transition_in("fade", 0.5)
            .transition_out("fade", 0.4))
        (fg.add(vf.Project.text(sub, size=28, font="sans", color="#b9c6e6",
                                max_width=380), st + 0.2, 10.2 - st - 0.2)
            .position([cx, CY + 90])
            .transition_in("fade", 0.6)
            .transition_out("fade", 0.4))

    (light.add(vf.Project.solid("#000000", size=[W, H]), 5.2, 5.0)
        .blend("screen")
        .effect("light",
                position=K((5.2, [0.15, 0.3]), (10.2, [0.85, 0.3]), default=[0.15, 0.3]),
                color="#6fa8ff", intensity=0.5, radius=0.9, falloff=1.8))

    # =================== SCENE C — outro (10.2–15.2) ====================
    bg.add(vf.Project.gradient([[0, "#1a2c5e"], [0.6, "#0b1430"], [1, INK]],
                               kind="radial", center=[0.5, 0.55], radius=1.0), 10.2, 5.0)

    (fg.add(vf.Project.text("Render anything.", size=120, font="display", color=PAPER), 10.5, 4.7)
        .position([CX, CY - 40])
        .scale(K((10.5, 1.1), (11.6, 1.0, "ease_out_cubic"), default=1.1))
        .transition_in("fade", 0.6)
        .effect("glow", intensity=0.4, radius=18)
        .transition_out("fade", 0.6))

    (fg.add(vf.Project.text("from agents, in plain JSON.", size=44, font="serif",
                            color=ACCENT), 11.4, 3.8)
        .position([CX, CY + 90])
        .transition_in("slide", 0.7, direction="up", distance=40)
        .transition_out("fade", 0.6))

    (light.add(vf.Project.solid("#000000", size=[W, H]), 10.2, 5.0)
        .blend("screen")
        .effect("light", position=[0.5, 0.45], color="#8fc0ff",
                intensity=K((10.2, 0.2), (11.5, 0.7), (15.2, 0.5)),
                radius=0.95, falloff=2.0))

    # =================== master grade + audio ==========================
    p.master_effect("color_grade", contrast=1.06, saturation=1.12, temperature=0.05)
    p.master_effect("vignette", amount=0.45, softness=0.7)
    p.master_effect("grain", amount=0.03)

    p.audio(os.path.join(GEN, "ambient.wav"), start=0.0, gain_db=-3.0,
            fade_in=1.0, fade_out=2.0)
    return p


def main():
    p = build()
    p.save(os.path.join(ROOT, "examples", "showcase_spec.json"))
    print("frames:", p.timeline().total_frames, "duration:", p.timeline().computed_duration())

    def prog(i, n):
        print(f"\r  rendering {i}/{n}", end="", flush=True)

    res = p.render(OUT, crf=18, preset="medium", progress=prog)
    print("\nDONE", res.path, os.path.getsize(res.path), "bytes")


if __name__ == "__main__":
    main()
