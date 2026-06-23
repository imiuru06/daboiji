"""Local, dependency-light procedural generator.

This is the always-available fallback: no GPU, no network, no API key. It will
never be photoreal — instead it synthesises an *abstract, prompt-tinted moving
image* (t2v) or brings a still image to life with parallax + light motion
(i2v). The point is that ``generate_video`` works end-to-end out of the box, and
swapping in a real diffusion model later is purely a config change.
"""
from __future__ import annotations

import hashlib

import numpy as np

from .base import GenRequest, GenResult, VideoGenProvider, write_mp4

# Prompt keyword -> two-colour palette (background gradient + accent blobs).
_PALETTES = {
    "sunset":  [(255, 94, 58), (120, 24, 74), (255, 196, 92)],
    "ocean":   [(8, 40, 80), (10, 120, 150), (130, 220, 230)],
    "forest":  [(12, 40, 24), (40, 120, 60), (180, 220, 120)],
    "neon":    [(10, 6, 30), (220, 30, 160), (60, 220, 255)],
    "night":   [(4, 8, 24), (20, 30, 70), (120, 150, 220)],
    "fire":    [(30, 6, 4), (200, 60, 10), (255, 200, 80)],
    "snow":    [(120, 140, 170), (210, 225, 240), (255, 255, 255)],
    "gold":    [(40, 28, 6), (160, 110, 20), (255, 210, 110)],
    "space":   [(2, 2, 12), (40, 10, 70), (120, 90, 230)],
    "desert":  [(60, 40, 20), (200, 150, 80), (240, 220, 160)],
    "cyber":   [(6, 10, 24), (20, 200, 200), (255, 60, 180)],
    "neutral": [(14, 18, 30), (40, 60, 100), (150, 190, 240)],
}
_KW = {
    "sunset": "sunset", "dusk": "sunset", "dawn": "sunset", "golden": "gold",
    "sea": "ocean", "ocean": "ocean", "water": "ocean", "wave": "ocean",
    "forest": "forest", "jungle": "forest", "tree": "forest", "green": "forest",
    "neon": "neon", "synth": "neon", "vapor": "neon", "cyber": "cyber",
    "night": "night", "dark": "night", "moon": "night", "star": "space",
    "fire": "fire", "flame": "fire", "lava": "fire", "ember": "fire",
    "snow": "snow", "ice": "snow", "winter": "snow", "frost": "snow",
    "gold": "gold", "space": "space", "galaxy": "space", "nebula": "space",
    "desert": "desert", "sand": "desert", "dune": "desert",
}


def _palette_for(prompt: str) -> list[tuple[int, int, int]]:
    p = prompt.lower()
    for kw, name in _KW.items():
        if kw in p:
            return _PALETTES[name]
    return _PALETTES["neutral"]


def _seed_of(req: GenRequest) -> int:
    if req.seed is not None:
        return int(req.seed) & 0x7FFFFFFF
    h = hashlib.sha256(req.prompt.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _smooth_noise(h: int, w: int, scale: int, rng: np.random.Generator) -> np.ndarray:
    """Cheap value-noise: a small random grid bilinearly upsampled."""
    import cv2
    gh, gw = max(2, h // scale), max(2, w // scale)
    grid = rng.random((gh, gw), dtype=np.float32)
    return cv2.resize(grid, (w, h), interpolation=cv2.INTER_CUBIC)


def _vignette(h: int, w: int, strength: float = 0.55) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2.0, h / 2.0
    r = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
    return (1.0 - strength * np.clip(r - 0.2, 0, 1) ** 2)[:, :, None]


class LocalProvider(VideoGenProvider):
    name = "local"

    def available(self) -> tuple[bool, str]:
        return True, "procedural (no GPU/network) — abstract, not photoreal"

    def generate(self, req: GenRequest, out_path: str) -> GenResult:
        if req.mode == "i2v" and req.image:
            frames_iter, (w, h) = self._image_to_video(req)
        else:
            frames_iter, (w, h) = self._text_to_video(req)
        n, w, h = write_mp4(frames_iter, out_path, req.fps, crf=18, preset="medium")
        return GenResult(path=out_path, provider=self.name, frames=n, fps=req.fps,
                         width=w, height=h,
                         meta={"mode": req.mode, "synthesis": "procedural",
                               "prompt": req.prompt})

    # -- text -> video: drifting fluid metaballs over a tinted gradient --------
    def _text_to_video(self, req: GenRequest):
        import cv2
        w, h = req.width, req.height
        pal = _palette_for(req.prompt)
        rng = np.random.default_rng(_seed_of(req))
        bg0 = np.array(pal[0], np.float32) / 255.0
        bg1 = np.array(pal[1], np.float32) / 255.0
        accent = np.array(pal[2], np.float32) / 255.0
        # vertical base gradient (normalised 0..1)
        grad = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        base = bg0[None, None, :] * (1 - grad) + bg1[None, None, :] * grad
        base = np.broadcast_to(base, (h, w, 3)).copy()
        vig = _vignette(h, w)
        # organic detail texture (scrolled over time)
        tex = _smooth_noise(h, w * 2, max(6, w // 36), rng)  # wide -> seamless scroll
        # blob motion params
        nb = 5
        amp = rng.uniform(0.18, 0.34, nb)
        fx = rng.uniform(0.4, 1.1, nb)
        fy = rng.uniform(0.4, 1.1, nb)
        ph = rng.uniform(0, 2 * np.pi, (nb, 2))
        rad = rng.uniform(0.30, 0.52, nb) * min(w, h)
        tint = [accent, accent * 0.7 + bg1 * 0.3, (accent + 1.0) / 2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        N = req.num_frames

        def frames():
            for i in range(N):
                t = i / max(1, N - 1)
                img = base.copy()
                for b in range(nb):
                    cx = w * (0.5 + amp[b] * np.sin(2 * np.pi * fx[b] * t + ph[b, 0]))
                    cy = h * (0.5 + amp[b] * np.cos(2 * np.pi * fy[b] * t + ph[b, 1]))
                    d2 = (xx - cx) ** 2 + (yy - cy) ** 2
                    fall = np.exp(-d2 / (2 * (rad[b] ** 2)))[:, :, None]
                    col = tint[b % len(tint)][None, None, :] * (0.55 * fall)
                    img = 1.0 - (1.0 - img) * (1.0 - col)   # screen blend (no blowout)
                # scroll texture, gently modulate luminance
                off = int(t * w) % w
                tx = tex[:, off:off + w][:, :, None]
                img = img * (0.82 + 0.30 * tx)
                img = img * vig
                img += rng.standard_normal((h, w, 1)) * 0.012   # subtle grain
                yield np.clip(img, 0, 1) * 255.0

        return frames(), (w, h)

    # -- image -> video: Ken Burns + low-freq flow warp + light sweep ----------
    def _image_to_video(self, req: GenRequest):
        import cv2
        src = cv2.imread(req.image, cv2.IMREAD_COLOR)
        if src is None:
            raise FileNotFoundError(f"i2v source image not found: {req.image}")
        src = cv2.cvtColor(src, cv2.COLOR_BGR2RGB)
        w, h = req.width, req.height
        src = cv2.resize(src, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32)
        rng = np.random.default_rng(_seed_of(req))
        # smooth flow field for parallax "breathing"
        flow_x = _smooth_noise(h, w, max(8, w // 24), rng) - 0.5
        flow_y = _smooth_noise(h, w, max(8, w // 24), rng) - 0.5
        base_x, base_y = np.meshgrid(np.arange(w, dtype=np.float32),
                                     np.arange(h, dtype=np.float32))
        vig = _vignette(h, w, 0.35)
        N = req.num_frames

        def frames():
            for i in range(N):
                t = i / max(1, N - 1)
                # Ken Burns push-in
                zoom = 1.0 + 0.10 * t
                breathe = np.sin(2 * np.pi * (0.5 * t)) * 6.0     # px
                mx = (base_x - w / 2) / zoom + w / 2 + flow_x * breathe
                my = (base_y - h / 2) / zoom + h / 2 + flow_y * breathe
                mx = np.ascontiguousarray(mx, dtype=np.float32)
                my = np.ascontiguousarray(my, dtype=np.float32)
                warped = cv2.remap(src, mx, my, interpolation=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_REFLECT)
                # moving light sweep
                sweep_c = (t * 1.4 - 0.2) * w
                band = np.exp(-((base_x - sweep_c) ** 2) / (2 * (w * 0.18) ** 2))
                warped = warped * (1.0 + 0.12 * band[:, :, None])
                warped = warped * vig
                yield np.clip(warped, 0, 255)

        return frames(), (w, h)
