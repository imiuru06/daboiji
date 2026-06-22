"""Shared, disk-backed project store.

This is the single source of truth that lets the MCP server (driven by an
agent such as Claude Code) and the Studio web UI (driven by a human) operate
on the *same* projects. Every project is a JSON file under the store root;
each operation loads the current state, mutates and saves, so the two
front-ends stay in sync (last writer wins).

The store root and the render-output dir are configurable via the
``VIDEOFORGE_STORE`` / ``VIDEOFORGE_OUTPUT`` environment variables, so the
MCP process and the Studio process can be pointed at the same place.
"""
from __future__ import annotations

import json
import os
from typing import List


class ProjectStore:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def _path(self, pid: str) -> str:
        return os.path.join(self.root, f"{pid}.json")

    def __contains__(self, pid: str) -> bool:
        return os.path.exists(self._path(pid))

    def __getitem__(self, pid: str) -> dict:
        if pid not in self:
            raise KeyError(pid)
        with open(self._path(pid)) as f:
            return json.load(f)

    def __setitem__(self, pid: str, spec: dict) -> None:
        tmp = self._path(pid) + ".tmp"
        with open(tmp, "w") as f:
            json.dump(spec, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path(pid))   # atomic

    def save(self, pid: str, spec: dict) -> None:
        self[pid] = spec

    def ids(self) -> List[str]:
        return sorted(f[:-5] for f in os.listdir(self.root) if f.endswith(".json"))

    def delete(self, pid: str) -> None:
        if pid in self:
            os.remove(self._path(pid))


STORE = ProjectStore(os.environ.get("VIDEOFORGE_STORE", os.path.abspath(".vf_projects")))
OUTPUT_DIR = os.environ.get("VIDEOFORGE_OUTPUT", os.path.abspath("output"))
