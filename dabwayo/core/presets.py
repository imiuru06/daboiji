"""Canonical names for the intent-level tools' vocabularies.

Kept here (dependency-free) so both the engine's ``capabilities()`` discovery
summary and the MCP tool layer (``mcp_tools.camera`` / ``mcp_tools.layout``)
reference one source of truth instead of drifting copies.
"""
from __future__ import annotations

# Named camera moves compiled to pan/zoom/rotation keyframes by camera_move.
CAMERA_PRESETS = (
    "push_in", "pull_out", "pan_left", "pan_right", "pan_up", "pan_down",
    "tilt", "dutch", "whip_pan", "ken_burns", "hold",
)

# Multi-clip arrangements written by align_clips.
LAYOUT_MODES = (
    "center", "center_h", "center_v", "top", "bottom", "left", "right",
    "distribute_h", "distribute_v", "grid", "stack_v", "stack_h",
)

# Per-clip motion presets compiled to transform keyframes by animate_clip.
# Looping/idle: float, drift, sway, pulse, breathe, spin.
# One-shot: pop (entrance overshoot), shake (impact).
MOTION_PRESETS = (
    "float", "drift", "sway", "pulse", "breathe", "spin", "pop", "shake",
)
