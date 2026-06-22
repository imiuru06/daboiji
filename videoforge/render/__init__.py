"""Rendering subsystem.

Kept import-light to avoid cycles (leaf modules import ``render.compositor``
/ ``render.context`` directly). Use ``from videoforge.render.engine import
render`` or the top-level ``videoforge.render`` re-export.
"""
