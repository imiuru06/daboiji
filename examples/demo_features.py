"""Demonstrate the advanced features: inpaint (watermark removal), chroma
key, mosaic censoring, fog, and a parallax camera move.

Produces before/after stills and a short motion clip under output/.
Run:  python examples/generate_assets.py && PYTHONPATH=. python examples/demo_features.py
"""
from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageDraw

import videoforge as vf
from videoforge import keyframes as K

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GEN = os.path.join(ROOT, "assets", "generated")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

W, H = 1280, 720


def _side_by_side(before_path, after_path, out_path, labels=("BEFORE", "AFTER")):
    a = Image.open(before_path).convert("RGB")
    b = Image.open(after_path).convert("RGB")
    gap = 12
    canvas = Image.new("RGB", (a.width + b.width + gap, a.height), (8, 10, 18))
    canvas.paste(a, (0, 0))
    canvas.paste(b, (a.width + gap, 0))
    d = ImageDraw.Draw(canvas)
    from videoforge.render.context import RenderContext
    font = RenderContext(W, H, 30).load_font("sans-bold", 34)
    d.text((24, 20), labels[0], font=font, fill=(255, 90, 90))
    d.text((a.width + gap + 24, 20), labels[1], font=font, fill=(90, 230, 140))
    canvas.save(out_path)


# --------------------------------------------------------------------------
# 1. Watermark removal (inpaint)
# --------------------------------------------------------------------------
def inpaint_demo():
    base = Image.open(os.path.join(GEN, "texture.png")).convert("RGB").resize((W, H))
    wm = base.copy()
    d = ImageDraw.Draw(wm, "RGBA")
    from videoforge.render.context import RenderContext
    ctx = RenderContext(W, H, 30)
    f1 = ctx.load_font("sans-bold", 40)
    f2 = ctx.load_font("sans", 26)
    # a corner logo box + copyright line — typical small watermarks
    d.rectangle([40, 40, 250, 110], fill=(255, 255, 255, 70))
    d.text((60, 55), "LOGO ©", font=f1, fill=(255, 255, 255, 220))
    d.text((W - 360, H - 60), "© SAMPLE STUDIO 2026", font=f2, fill=(255, 255, 255, 210))
    before = os.path.join(OUT, "feat_inpaint_before.png")
    wm.convert("RGB").save(before)

    regions = [
        {"shape": "rect", "rect": [36, 36, 220, 80], "feather": 2},
        {"shape": "rect", "rect": [W - 366, H - 66, 340, 50], "feather": 2},
    ]
    p = vf.Project(W, H)
    p.track("video").add(vf.Project.image(before, fit="cover", size=[W, H]), 0, 1)
    p.master_effect("inpaint", region=regions, radius=6, grow=3)
    after = os.path.join(OUT, "feat_inpaint_after.png")
    p.thumbnail(after, 0.0)
    _side_by_side(before, after, os.path.join(OUT, "feat_inpaint.png"),
                  ("WATERMARKED", "INPAINTED (removed)"))
    print("inpaint:", os.path.join(OUT, "feat_inpaint.png"))


# --------------------------------------------------------------------------
# 2. Chroma key (green screen)
# --------------------------------------------------------------------------
def chroma_demo():
    # synthesize a green-screen "subject": a colored figure on pure green
    subj = Image.new("RGB", (W, H), (0, 255, 0))
    d = ImageDraw.Draw(subj)
    d.ellipse([W // 2 - 110, 120, W // 2 + 110, 340], fill=(40, 90, 200))      # head
    d.rounded_rectangle([W // 2 - 160, 320, W // 2 + 160, 680], radius=80, fill=(40, 90, 200))
    d.ellipse([W // 2 - 60, 180, W // 2 + 60, 300], fill=(235, 200, 170))       # face
    subj_path = os.path.join(OUT, "feat_greenscreen.png")
    subj.convert("RGB").save(subj_path)

    # before: subject on green over nebula (no key)
    pb = vf.Project(W, H, background="#0b0e16")
    pb.track("video", "bg").add(vf.Project.image(os.path.join(GEN, "texture.png"),
                                                 fit="cover", size=[W, H]), 0, 1).depth(0)
    pb.track("video", "subj").add(vf.Project.image(subj_path, fit="cover", size=[W, H]), 0, 1)
    before = os.path.join(OUT, "feat_chroma_before.png")
    pb.thumbnail(before, 0)

    # after: same, but key the green out so the subject composites cleanly
    pa = vf.Project(W, H, background="#0b0e16")
    pa.track("video", "bg").add(vf.Project.image(os.path.join(GEN, "texture.png"),
                                                 fit="cover", size=[W, H]), 0, 1)
    (pa.track("video", "subj").add(vf.Project.image(subj_path, fit="cover", size=[W, H]), 0, 1)
       .effect("chroma_key", key="#00ff00", tolerance=0.35, softness=0.12, spill=0.6))
    after = os.path.join(OUT, "feat_chroma_after.png")
    pa.thumbnail(after, 0)
    _side_by_side(before, after, os.path.join(OUT, "feat_chroma.png"),
                  ("GREEN SCREEN", "KEYED + COMPOSITED"))
    print("chroma:", os.path.join(OUT, "feat_chroma.png"))


# --------------------------------------------------------------------------
# 3. Camera + parallax + fog motion clip
# --------------------------------------------------------------------------
def parallax_video():
    p = vf.Project(W, H, fps=30, background="#070b14", name="parallax")
    # far backdrop (locked), mid texture, near shapes, foreground title
    p.track("video", "sky").add(
        vf.Project.gradient([[0, "#1b2f5e"], [1, "#070b14"]], kind="radial",
                            center=[0.5, 0.35]), 0, 6).depth(0.0)
    p.track("video", "neb").add(
        vf.Project.image(os.path.join(GEN, "texture.png"), fit="cover", size=[W, H]),
        0, 6).blend("screen").opacity(0.5).depth(0.15)
    mid = p.track("video", "mid")
    for i, (x, col, r) in enumerate([(260, "#5cc8ff", 90), (1000, "#9a7bff", 70), (640, "#54e0b0", 50)]):
        (mid.add(vf.Project.shape("circle", size=[r * 2, r * 2], fill=col), 0, 6)
            .position([x, 300 + (i % 2) * 160]).depth(0.5 + i * 0.12).opacity(0.85))
    (p.track("video", "title").add(
        vf.Project.text("PARALLAX", size=140, font="display", color="#eaf2ff"), 0, 6)
        .position([W / 2, H / 2]).depth(1.0).effect("glow", intensity=0.4))

    # camera: slow push-in + pan right -> layers shift by depth (parallax)
    p.camera(pan=K((0, [0, 0]), (6, [180, -40], "ease_in_out")),
             zoom=K((0, 1.0), (6, 1.25, "ease_in_out")))
    p.master_effect("fog", color="#9fb4d6", density=0.5, height=0.55, speed=30)
    p.master_effect("vignette", amount=0.4)
    p.master_effect("grain", amount=0.02)

    out = os.path.join(OUT, "features_parallax.mp4")
    p.render(out, crf=20, preset="veryfast")
    print("parallax video:", out)
    p.thumbnail(os.path.join(OUT, "feat_parallax_frame.png"), 4.0)


def main():
    inpaint_demo()
    chroma_demo()
    parallax_video()


if __name__ == "__main__":
    main()
