"""Rendering subsystem.

Kept import-light to avoid cycles (leaf modules import ``render.compositor``
/ ``render.context`` directly). Use ``from dabwayo.render.engine import
render`` or the top-level ``dabwayo.render`` re-export.
"""
