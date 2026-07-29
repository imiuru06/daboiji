"""Data-driven templates: a reusable spec with ``{{placeholder}}`` tokens that
you fill from a data dict to produce a finished project — the "feed data, get a
branded video" model (Creatomate/Shotstack style), at scale.

A template file is JSON: ``{name, description, defaults, spec}``. ``spec`` is a
normal project spec whose string values may contain ``{{token}}`` markers.
Filling substitutes them from ``defaults`` overlaid with the caller's data.

Whole-value tokens preserve type: a value that is exactly ``"{{duration}}"``
becomes the raw data value (e.g. the number ``4``), while an embedded token
(``"Hi {{name}}"``) is string-interpolated.
"""
from __future__ import annotations

import copy
import json
import os
import re
from typing import Dict, List, Set, Tuple

__all__ = ["templates_dir", "list_builtin", "load", "placeholders", "fill"]

_TOKEN = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def templates_dir() -> str:
    return os.environ.get("DABWAYO_TEMPLATES_DIR", "templates")


def list_builtin() -> List[str]:
    d = templates_dir()
    if not os.path.isdir(d):
        return []
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))


def load(name_or_path: str) -> Dict:
    """Load a template by builtin name or explicit .json path."""
    path = name_or_path
    if not (name_or_path.endswith(".json") and os.path.exists(name_or_path)):
        path = os.path.join(templates_dir(), name_or_path + ".json")
    if not os.path.exists(path):
        raise ValueError(f"template not found: {name_or_path}")
    with open(path, "r", encoding="utf-8") as f:
        tpl = json.load(f)
    if "spec" not in tpl:
        raise ValueError(f"template {name_or_path!r} has no 'spec'")
    return tpl


def placeholders(obj) -> Set[str]:
    """Collect every ``{{token}}`` name used anywhere in ``obj`` (a spec)."""
    found: Set[str] = set()

    def walk(o):
        if isinstance(o, str):
            found.update(_TOKEN.findall(o))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return found


def _sub_string(s: str, data: Dict, missing: Set[str]):
    whole = _TOKEN.fullmatch(s.strip())
    if whole:                                   # whole-value token → keep type
        key = whole.group(1)
        if key in data:
            return data[key]
        missing.add(key)
        return s

    def repl(mo):
        k = mo.group(1)
        if k in data:
            return str(data[k])
        missing.add(k)
        return mo.group(0)
    return _TOKEN.sub(repl, s)


def fill(spec: Dict, data: Dict) -> Tuple[Dict, List[str]]:
    """Substitute tokens in ``spec`` from ``data``. Returns the filled spec and
    a sorted list of any tokens that had no matching data key."""
    missing: Set[str] = set()

    def walk(o):
        if isinstance(o, str):
            return _sub_string(o, data, missing)
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        return o

    filled = walk(copy.deepcopy(spec))
    return filled, sorted(missing)
