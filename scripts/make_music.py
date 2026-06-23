#!/usr/bin/env python3
"""Synthesize an original, license-free emotional piano + string-pad bed for
the 'recovery / growth' film. No samples, no external audio — everything is
generated from scratch with numpy, so the result is wholly original and safe
to publish.

Arc (matches the 6 cuts, ~59.3s): sparse minor-leaning piano (burnout) ->
warming progression with a soft pad entering (recovery) -> fuller, resolving
strings + brighter piano (growth). Dynamics rise from quiet/dark to warm/full.
"""
import numpy as np

SR = 44100
DUR = 60.0
N = int(SR * DUR)
t = np.arange(N) / SR

rng = np.random.default_rng(7)

def midi(name):
    # note name like 'A2','C#4' -> frequency
    names = {'C':0,'C#':1,'D':2,'D#':3,'E':4,'F':5,'F#':6,'G':7,'G#':8,'A':9,'A#':10,'B':11}
    n = name[:-1]; octv = int(name[-1])
    semi = names[n] + (octv+1)*12
    return 440.0 * 2 ** ((semi - 69) / 12.0)

def piano_note(freq, start, dur, amp, tau=1.4, bright=1.0):
    """A soft felt-piano-ish tone: a few harmonics, fast attack, exp decay,
    a slightly detuned twin for warmth."""
    i0 = int(start * SR); n = int(dur * SR)
    if i0 >= N: return
    n = min(n, N - i0)
    lt = np.arange(n) / SR
    # harmonic series, gently rolled off; 'bright' adds upper partials later in film
    harms = [1.0, 0.55*bright, 0.32*bright, 0.16*bright, 0.09*bright, 0.05*bright]
    sig = np.zeros(n)
    for k, h in enumerate(harms, start=1):
        inharm = 1.0 + 0.0008 * k * k         # subtle piano inharmonicity
        sig += h * np.sin(2*np.pi*freq*inharm*lt)
        sig += 0.5*h * np.sin(2*np.pi*freq*inharm*1.002*lt)   # detuned twin
    # envelope: 6ms attack, exponential decay
    env = np.exp(-lt / tau)
    atk = int(0.006 * SR)
    if atk > 0:
        env[:atk] *= np.linspace(0, 1, atk)
    sig *= env
    out[i0:i0+n, 0] += amp * sig
    out[i0:i0+n, 1] += amp * sig

def pad_chord(freqs, start, dur, amp):
    """Sustained, slow-swelling string-ish pad (stacked soft saws), stereo."""
    i0 = int(start * SR); n = int(dur * SR)
    if i0 >= N: return
    n = min(n, N - i0)
    lt = np.arange(n) / SR
    for ch in (0, 1):
        sig = np.zeros(n)
        for f in freqs:
            det = 1.0 + (0.003 if ch == 0 else -0.003)   # stereo detune width
            # soft saw via summed harmonics
            for k in range(1, 7):
                sig += (1.0/k) * np.sin(2*np.pi*f*det*k*lt + rng.random()*2*np.pi)
        sig /= (len(freqs) * 3.0)
        # slow swell in/out
        env = np.ones(n)
        a = int(min(0.8, dur*0.4) * SR); r = int(min(1.2, dur*0.4) * SR)
        env[:a] *= np.linspace(0, 1, a)**1.5
        env[-r:] *= np.linspace(1, 0, r)**1.5
        out[i0:i0+n, ch] += amp * sig * env

out = np.zeros((N, 2))

# ---- harmonic plan: vi-IV-I-V family in C (hopeful, recovery-friendly) ----
# (chord, low root, melody note) per 4s slot
plan = [
    ('Am', 'A2', 'A4'),  # 0  burnout: bare, minor
    ('F',  'F2', 'C5'),  # 4
    ('C',  'C3', 'E4'),  # 8  first light
    ('G',  'G2', 'D5'),  # 12
    ('Am', 'A2', 'E5'),  # 16 recovery begins
    ('F',  'F2', 'C5'),  # 20
    ('C',  'C3', 'G4'),  # 24
    ('G',  'G2', 'D5'),  # 28
    ('Am', 'A2', 'A4'),  # 32 effort / growth
    ('F',  'F2', 'F4'),  # 36
    ('C',  'C3', 'E5'),  # 40
    ('G',  'G2', 'D5'),  # 44
    ('F',  'F2', 'C5'),  # 48 lift
    ('G',  'G2', 'B4'),  # 52
    ('C',  'C3', 'E5'),  # 56 resolve, full & bright
]
chord_tones = {
    'Am': ['A3','C4','E4'], 'F': ['F3','A3','C4'],
    'C':  ['C4','E4','G4'], 'G': ['G3','B3','D4'],
}

SLOT = 4.0
for idx, (chord, root, mel) in enumerate(plan):
    ts = idx * SLOT
    prog = idx / (len(plan) - 1)           # 0..1 across the film (dark->bright)
    dyn = 0.45 + 0.55 * prog               # dynamics swell over time
    bright = 0.5 + 0.9 * prog              # timbre opens up later
    # left-hand low root (long tail), a touch louder/longer for low notes
    piano_note(midi(root), ts, SLOT+2.5, amp=0.16*dyn, tau=2.6, bright=0.6)
    # melody: two sparse notes per slot, with breathing space
    piano_note(midi(mel), ts+0.15, 3.2, amp=0.22*dyn, tau=1.5, bright=bright)
    # gentle mid harmony note halfway (an inner voice from the chord)
    inner = chord_tones[chord][1]
    piano_note(midi(inner), ts+2.0, 2.4, amp=0.12*dyn, tau=1.3, bright=bright)
    # string pad: enters from ~16s, grows toward the end
    if ts >= 14:
        pad_amp = 0.10 * (0.3 + 0.7 * prog)
        freqs = [midi(x) for x in chord_tones[chord]]
        pad_chord(freqs, ts, SLOT+0.3, pad_amp)

# ---- light feedback reverb (block method) for space ----
def comb(x, delay_s, g):
    D = int(delay_s * SR); y = x.copy()
    for s in range(D, len(x), D):
        e = min(s+D, len(x))
        y[s:e] += g * y[s-D:s-D+(e-s)]
    return y

def reverberate(mono):
    combs = [(0.0297, 0.78), (0.0371, 0.76), (0.0411, 0.74), (0.0437, 0.72)]
    acc = np.zeros_like(mono)
    for d, g in combs:
        acc += comb(mono, d, g)
    return acc / len(combs)

wet_l = reverberate(out[:, 0]); wet_r = reverberate(out[:, 1])
mix = np.stack([out[:,0]*0.7 + wet_l*0.5, out[:,1]*0.7 + wet_r*0.5], axis=1)

# gentle one-pole low-pass for warmth
def lp(x, a=0.18):
    y = np.empty_like(x); acc = 0.0
    # vectorized-ish via lfilter substitute (simple loop over channels in chunks)
    for c in range(x.shape[1]):
        col = x[:, c]; out_c = np.empty_like(col); prev = 0.0
        # chunked recursive smoothing
        for i in range(len(col)):
            prev = prev + a * (col[i] - prev)
            out_c[i] = prev
        y[:, c] = out_c
    return y

# low-pass is slow in pure python at 2.6M*2; use a cheap FIR moving average instead
def warm(x, k=3):
    ker = np.ones(k)/k
    return np.stack([np.convolve(x[:,c], ker, mode='same') for c in range(x.shape[1])], axis=1)

mix = warm(mix, 3)

# master: fade in/out + normalize
fi = int(1.5*SR); fo = int(3.0*SR)
mix[:fi] *= np.linspace(0,1,fi)[:,None]
mix[-fo:] *= np.linspace(1,0,fo)[:,None]
peak = np.max(np.abs(mix))
mix = mix / peak * 0.89

# write 16-bit PCM wav
import wave, struct
data = (mix * 32767).astype('<i2')
with wave.open('assets/audio/recovery_bed.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(data.tobytes())
print('wrote assets/audio/recovery_bed.wav', round(len(mix)/SR,2), 's')
