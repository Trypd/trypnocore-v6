"""Shared identity resolution for the tryp hook helpers.

Given a cwd (from a CC hook payload), find the owning agent in
fleet-registry.json: longest folder path that prefixes the cwd wins,
so worktrees and subdirs of a boot folder still resolve to their agent.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REGISTRY = Path(r"C:\Trypnocore\fleet\fleet-registry.json")


def _norm(p: str) -> str:
    # WSL gives /mnt/c/... ; registry has C:\...
    if p.startswith("/mnt/"):
        rest = p[5:]  # e.g. c/Trypnocore/...
        drive, _, tail = rest.partition("/")
        p = f"{drive}:\\{tail}"
    p = p.replace("/", "\\")
    return p.rstrip("\\").lower()


def resolve(cwd: str) -> dict | None:
    """Registry entry for the agent whose folder contains cwd, or None."""
    try:
        agents = json.loads(REGISTRY.read_text(encoding="utf-8"))["agents"]
    except Exception:
        return None
    target = _norm(cwd)
    best = None
    for agent in agents:
        folder = _norm(agent.get("folder", ""))
        if folder and (target == folder or target.startswith(folder + "\\")):
            if best is None or len(folder) > len(_norm(best["folder"])):
                best = agent
    return best


def slugify(name: str) -> str:
    fold = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss", "é": "e", "è": "e"})
    s = name.lower().strip().translate(fold)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    return re.sub(r"-{2,}", "-", s).strip("-")
