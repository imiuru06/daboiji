# VideoForge

A modular, scriptable **video rendering engine** with a first-class **MCP
interface** so AI agents can author and render high-quality video from plain
JSON. Think "a tiny, programmable motion-graphics compositor" — timelines,
tracks, clips, keyframed transforms, cinematic lighting, effects, transitions
and audio — all serializable and driven by tools.

```
                 ┌────────────────────────────────────────────┐
   agent ──MCP──▶│  videoforge.mcp_server  (FastMCP, 16 tools) │
                 └───────────────┬────────────────────────────┘
                                 ▼
        Project (JSON spec) ─▶ Timeline ─▶ Render engine ─▶ H.264 MP4
                                 │
   elements · effects · transitions · lighting · keyframes · audio
```

## Why it's built this way
- **Declarative & serializable** — a project is a plain JSON `dict` (the
  *spec*). Agents can build it incrementally or hand over a whole timeline;
  it round-trips to disk and is trivially diff-able.
- **Modular registries** — elements, effects and transitions self-register,
  so adding a new capability is a single decorated class. Nothing else changes.
- **Quality first** — float RGBA compositing, anti-aliased affine placement,
  Lanczos scaling, alpha-correct blend modes, x264 CRF 18 output.
- **Self-contained** — bundled fonts and a static `ffmpeg` (via
  `imageio-ffmpeg`); no system installs required.

## Install
```bash
pip install -r requirements.txt      # numpy, Pillow, imageio[-ffmpeg], mcp
# or:  pip install -e .
```

## Quick start (Python)
```python
import videoforge as vf
from videoforge import keyframes as K

p = vf.Project(1920, 1080, fps=30, background="#0b0e16")
bg = p.track("video", "bg")
bg.add(vf.Project.gradient([[0, "#1a2c5e"], [1, "#0b0e16"]], kind="radial"), 0, 4)

title = p.track("video", "title")
(title.add(vf.Project.text("Hello, agents.", size=120, font="display"), 0.3, 3.4)
      .scale(K((0.3, 1.1), (1.1, 1.0, "ease_out_cubic")))
      .effect("glow", intensity=0.4)
      .transition_in("fade", 0.5).transition_out("fade", 0.5))

p.master_effect("color_grade", contrast=1.05, saturation=1.1)
p.master_effect("vignette", amount=0.4)
p.render("output/hello.mp4")
```

## Quick start (declarative JSON)
```python
import json, videoforge as vf
spec = json.load(open("examples/quickstart_spec.json"))
vf.render(vf.Timeline.from_spec(spec), "output/quickstart.mp4")
```

## Run as an MCP server
```bash
python -m videoforge.mcp_server          # stdio transport
# or the installed entry point:
videoforge-mcp
```

Register it with any MCP client (e.g. Claude):
```json
{
  "mcpServers": {
    "videoforge": { "command": "python", "args": ["-m", "videoforge.mcp_server"] }
  }
}
```

### MCP tools
| Tool | Purpose |
|------|---------|
| `get_capabilities` / `get_help` | Discover element/effect/transition names + authoring guide |
| `create_project` | Start a project, returns `project_id` |
| `add_track` | Add a named video/audio track |
| `add_clip` | Add any element clip with transform/effects/transitions |
| `add_text` · `add_background` · `add_media` | Ergonomic clip helpers |
| `add_effect` | Attach an effect to a clip or the master chain |
| `add_audio` | Add a mixed audio clip (music/VO/SFX) |
| `get_project` · `update_project` · `estimate` | Inspect / edit / measure |
| `preview_frame` | Render a single PNG for review |
| `render_project` · `render_from_spec` | Render to MP4 (stateful or stateless) |

## The spec model
A `Timeline` owns ordered **tracks**; video tracks composite **bottom → top**.
Each **clip** places an **element** at an absolute `start`/`duration` and has:
- a **transform** — `position [x,y]`, `scale`, `rotation`, `opacity`, `anchor`
  (every field may be a **keyframed property** with per-keyframe easing);
- a **blend mode** (`normal, add, screen, multiply, overlay, soft_light, …`);
- a list of **effects**; and optional **in/out transitions**.

**Keyframed property**
```json
{"keyframes": [
  {"time": 0.0, "value": [0, 540], "easing": "ease_out_cubic"},
  {"time": 1.0, "value": [960, 540]}
]}
```

### Built-in capabilities
- **Elements**: `solid`, `gradient` (linear/radial), `text` (wrapping, shadow,
  stroke, letter-spacing), `image`, `video`, `shape` (rect/rounded/ellipse/line).
- **Effects**: `color_grade`, `lift_gamma_gain`, `blur`, `sharpen`, `glow`,
  `vignette`, `grain`, `chromatic_aberration`.
- **Lighting**: `light` (radial point light), `ambient`, `light_leak`.
- **Transitions**: `fade`, `fade_color`, `slide`, `zoom`, `blur_in`, `wipe`.
- **Easings**: linear, quad/cubic/quart, expo, back, elastic, bounce, sine …

## Layout
```
videoforge/
  core/        types, color, easing, keyframes, transform, timeline
  elements/    backgrounds, text, media (image/video), shapes  (+registry)
  effects/     color grade, stylize (glow/blur/grain/…), lighting (+registry)
  transitions/ fade/slide/zoom/wipe/blur (+registry)
  render/      compositor (blend modes), rasterizer (affine), encoder, engine
  audio/       ffmpeg-based mixer
  builder.py   fluent Project API over the JSON spec
  mcp_server.py
assets/fonts/  bundled OFL fonts
examples/      generate_assets.py, demo_showcase.py, *_spec.json
tests/         test_engine.py
```

## Extending
Add an effect in ~10 lines — it auto-registers and is immediately available
to the builder, the JSON spec and the MCP tools:
```python
from videoforge.effects.base import Effect, register

@register("invert")
class Invert(Effect):
    def apply(self, img, ctx, t):
        out = img.copy(); out[..., :3] = 1.0 - out[..., :3]; return out
```

## Demo
```bash
python examples/generate_assets.py     # procedural logo, texture, ambient audio
PYTHONPATH=. python examples/demo_showcase.py   # -> output/showcase.mp4
```
