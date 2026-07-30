# ADR-0003 — Intent-level tool granularity for agent operation

**Status:** accepted — Phase 1 shipped (camera moves, depth-of-field/rack
focus, music ducking, multi-clip layout). All deterministic wrappers over
existing engine primitives; no new engine feature, no ML.

## Problem
A granularity review of the 95-tool surface (asking "is each tool at the right
*altitude* for a calling agent?") found ~70% well-placed at the intent level
(`generate_shot`, `trim_clip`, `add_callout`, `create_storyboard`) but four
dimensions stuck at **raw keyframe-math altitude** — the agent had to
re-derive motion/geometry every time:

1. **Camera movement.** A "slow push-in" meant hand-authoring `set_camera`
   zoom keyframes (1.0→1.15) + easing. No named moves.
2. **Focus / depth of field.** Focus was scattered across `camera.focus`
   (parallax pivot) + the raw `blur` effect + `spotlight`; no way to say
   "subject sharp, background soft" or "rack focus A→B" in one call.
3. **Audio mixing.** `add_audio` had gain + head/tail fades only — no
   auto-duck of music under narration (the single most common mix move).
4. **Layout.** `position` was absolute `[x,y]` only; aligning/distributing
   several overlays meant per-clip pixel math.

Benchmarks (Shotstack `motion`, Creatomate, Remotion springs, LTX camera
presets) all expose *named creative moves* that compile down to keyframes —
the altitude our four gaps were missing.

## Decision
Add a thin **intent-level tool layer** over the existing primitives — name the
creative action, dabwayo compiles it deterministically. New tools (95 → 100):

| Tool | Compiles to | Module |
|---|---|---|
| `camera_move(preset, …)` | `set_camera` pan/zoom/rotation keyframes | `mcp_tools/camera.py` |
| `set_focus(subject, aperture, pull_to)` | per-clip `blur` by `depth` distance (keyframed for rack focus) + `camera.focus` | `mcp_tools/camera.py` |
| `duck_audio(under=[…])` | ducking envelope on the music clip → ffmpeg `volume` expression in the mixer | `mcp_tools/audio.py` (+ `audio/mixer.py`) |
| `align_clips(mode, …)` | each clip's `transform.position` (anchor points) | `mcp_tools/layout.py` |

- **camera_move** presets: push_in/pull_out, pan_{left,right,up,down}, tilt,
  dutch, whip_pan, ken_burns, hold. Moves **compose** (push_in + pan_right =
  both channels animate).
- **set_focus** builds a depth-of-field from each clip's `depth` vs the focus
  plane (idempotent via a `_dof` marker); `pull_to` keyframes the blur for a
  rack focus. Reuses the existing `blur` effect — no new effect.
- **duck_audio** reads the real timeline spans of the VO/SFX clips (probing
  file durations when unset), merges them into ducking windows, and stores an
  envelope the mixer renders as a piecewise `volume` expression with
  attack/release. No sidechain graph, fully deterministic.
- **align_clips**: center/edges, distribute_h/v, grid, stack — over the canvas
  or a `safe` area or explicit bounds.

The named vocabularies are published from `capabilities()`
(`camera_moves`, `layout_modes`) and one source of truth in
`core/presets.py`, so agents discover them.

## Scope check
Every one of these is a deterministic compilation of existing state — keyframe
math, depth→blur geometry, VO-span→gain envelope, canvas geometry. No LLM
planner, no new engine capability. The raw escape hatches (`set_camera`,
`add_effect`, `add_audio`, `add_clip` transform) remain for full control.
Consistent with ADR-0001/0002: dabwayo owns structured state + deterministic
resolution; ML and bytes stay external.

## Phasing
1. **camera_move, set_focus, duck_audio, align_clips + discovery + tests.**
   ✅ shipped (17 tests; full suite 79 green, incl. a real-ffmpeg ducking
   assertion and an end-to-end render).
2. Possible follow-ups (not yet needed): named audio SFX/stingers,
   beat-sync cut alignment, orbit/parallax presets, per-clip motion presets
   (float/shake). Deferred until a concrete need appears.
