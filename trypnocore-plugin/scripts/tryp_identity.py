"""Shared identity resolution for the tryp hook helpers.

Given a cwd (from a CC hook payload), find the owning agent in
fleet-registry.json: longest folder path that prefixes the cwd wins,
so worktrees and subdirs of a boot folder still resolve to their agent.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

REGISTRY = Path(os.environ.get("TRYP_FLEET_REGISTRY", r"C:\Trypnocore\fleet\fleet-registry.json"))


def _norm(p: str) -> str:
    # WSL gives /mnt/c/... ; registry has C:\...
    if p.startswith("/mnt/"):
        rest = p[5:]  # e.g. c/Trypnocore/...
        drive, _, tail = rest.partition("/")
        p = f"{drive}:\\{tail}"
    p = p.replace("/", "\\")
    return p.rstrip("\\").lower()


def _solo_agent(cwd: str) -> dict | None:
    slug = os.environ.get("TRYP_AGENT_SLUG", "").strip()
    if slug:
        return {
            "slug": slug,
            "folder": os.environ.get("TRYP_BOOT_FOLDER") or cwd,
            "pool": os.environ.get("OPZ_POOL") or slug,
            "lane": os.environ.get("AGENT_LANE", ""),
            "note": "solo",
        }
    current = Path(cwd or ".").resolve()
    for folder in (current, *current.parents):
        candidate = folder / "trypnocore.json"
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            return None
        data = data.get("agent", data)
        slug = str(data.get("slug") or data.get("name") or "").strip()
        if not slug:
            return None
        boot = Path(data.get("folder") or folder)
        if not boot.is_absolute():
            boot = folder / boot
        return {
            "slug": slug,
            "folder": str(boot),
            "pool": data.get("pool") or slug,
            "lane": data.get("lane", ""),
            "note": data.get("note", "solo"),
        }
    return None


def resolve(cwd: str) -> dict | None:
    """Resolve solo config first, then the collective registry, if present."""
    solo = _solo_agent(cwd)
    if solo is not None:
        return solo
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
