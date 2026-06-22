"""Generate procedural assets used by the demos.

Produces a logo PNG, a soft noise texture, and a synthesized ambient audio
bed under ``assets/generated/``. This shows how upstream tools can prepare
assets that the engine then composites.
"""
from __future__ import annotations

import os
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "assets", "generated")
os.makedirs(OUT, exist_ok=True)


def make_logo(path: str, size: int = 512):
    """A glowing concentric 'aperture' mark."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = size // 2
    blades = 6
    r = size * 0.36
    import math
    pts = []
    for i in range(blades):
        a = math.radians(i * 360 / blades - 90)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, outline=(120, 200, 255, 255), width=int(size * 0.02))
    for k, col in enumerate([(80, 160, 255, 220), (150, 220, 255, 255)]):
        rr = r * (0.62 - k * 0.18)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=col, width=int(size * 0.015))
    glow = img.filter(ImageFilter.GaussianBlur(size * 0.02))
    img = Image.alpha_composite(glow, img)
    img.save(path)


def make_texture(path: str, w: int = 1280, h: int = 720):
    """Soft cloudy nebula texture from layered value noise."""
    rng = np.random.default_rng(7)
    acc = np.zeros((h, w), np.float32)
    for octave, amp in [(4, 1.0), (8, 0.5), (16, 0.25), (32, 0.12)]:
        small = rng.random((octave, octave)).astype(np.float32)
        up = np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
        acc += up * amp
    acc = (acc - acc.min()) / (np.ptp(acc) + 1e-6)
    # map to a blue/purple palette
    rgb = np.stack([
        0.10 + 0.35 * acc,
        0.12 + 0.25 * acc ** 1.5,
        0.25 + 0.55 * acc,
    ], axis=2)
    arr = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(arr, "RGB").save(path)


def make_ambient(path: str, seconds: float = 16.0, sr: int = 44100):
    """A gentle evolving ambient pad (sum of detuned sines + slow swell)."""
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    base = 110.0  # A2
    sig = np.zeros_like(t)
    for mult, amp, detune in [(1, 0.5, 0.0), (2, 0.25, 0.6), (3, 0.15, -0.8), (4, 0.1, 1.1)]:
        sig += amp * np.sin(2 * np.pi * (base * mult + detune) * t)
    # slow amplitude swell + gentle tremolo
    swell = np.clip(np.sin(np.pi * t / seconds), 0, 1) ** 0.5
    tremolo = 0.85 + 0.15 * np.sin(2 * np.pi * 0.2 * t)
    sig = sig * swell * tremolo
    # global fade in/out
    fade = int(sr * 1.5)
    env = np.ones_like(sig)
    env[:fade] = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    sig *= env
    sig = sig / (np.max(np.abs(sig)) + 1e-9) * 0.6
    pcm = (sig * 32767).astype(np.int16)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def main():
    make_logo(os.path.join(OUT, "logo.png"))
    make_texture(os.path.join(OUT, "texture.png"))
    make_ambient(os.path.join(OUT, "ambient.wav"))
    print("Assets written to", OUT)
    for f in sorted(os.listdir(OUT)):
        print(" -", f, os.path.getsize(os.path.join(OUT, f)), "bytes")


if __name__ == "__main__":
    main()
