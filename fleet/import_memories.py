"""Fleet memory import: each agent's Individuals documents -> their MeTTa pool.

Sources per agent folder:
  - memory*, soul* (root and one level down), memory/ and .remember/ trees
  - .wolf/ trees (.md/.txt)
  - other root-level .md files (excluding instruction/config: AGENTS.md,
    CLAUDE.md, QWEN.md, tasks.md, task_plan.md, *.bak*)
Chunks markdown on blank lines (~600 chars max), caps 80 atoms/agent and
8/file, newest files first. Additive, pointer-deduped.
Run from the OmegaPrimeZero folder: python C:/Trypnocore/fleet/import_memories.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Trypnocore\OmegaPrimeZero")

from runtime.memory import Proof
from runtime.memory.metta_space import MettaSpace

REGISTRY = Path(r"C:\Trypnocore\fleet\fleet-registry.json")
METTA_DIR = Path(r"C:\Trypnocore\OmegaPrimeZero\out\metta")

EXCLUDE_NAMES = {"agents.md", "claude.md", "qwen.md", "tasks.md", "task_plan.md"}
MAX_ATOMS_PER_AGENT = 80
MAX_ATOMS_PER_FILE = 8
MAX_CLAIM_CHARS = 600
MIN_CLAIM_CHARS = 40


def candidate_files(folder: Path) -> list[Path]:
    files: list[Path] = []
    root = [f for f in folder.glob("*.md") if f.name.lower() not in EXCLUDE_NAMES]
    files.extend(root)
    for sub in ("memory", ".remember", ".wolf"):
        tree = folder / sub
        if tree.is_dir():
            files.extend(p for p in tree.rglob("*") if p.suffix.lower() in (".md", ".txt") and p.is_file())
    seen, out = set(), []
    for f in files:
        if f in seen:
            continue
        seen.add(f)
        out.append(f)
    out.sort(key=lambda f: -f.stat().st_mtime)
    return out


def chunks(text: str) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    size = 0
    for para in text.replace("\r\n", "\n").split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if size + len(para) > MAX_CLAIM_CHARS and buf:
            merged = "\n\n".join(buf).strip()
            if len(merged) >= MIN_CLAIM_CHARS:
                out.append(merged[:MAX_CLAIM_CHARS])
            buf, size = [], 0
        if len(para) > MAX_CLAIM_CHARS:
            if len(para) >= MIN_CLAIM_CHARS:
                out.append(para[:MAX_CLAIM_CHARS])
            continue
        buf.append(para)
        size += len(para)
    if buf:
        merged = "\n\n".join(buf).strip()
        if len(merged) >= MIN_CLAIM_CHARS:
            out.append(merged[:MAX_CLAIM_CHARS])
    return out


def main() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    total = 0
    for agent in registry["agents"]:
        slug = agent["slug"]
        if slug == "memory":
            continue
        folder = Path(agent["folder"])
        if not folder.is_dir():
            continue
        store = MettaSpace.for_pool(METTA_DIR, slug)
        written = 0
        for f in candidate_files(folder):
            if written >= MAX_ATOMS_PER_AGENT:
                break
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            mtime = time.strftime("%Y-%m-%d", time.localtime(f.stat().st_mtime))
            rel = f.relative_to(folder)
            file_atoms = 0
            for index, claim in enumerate(chunks(text)):
                if written >= MAX_ATOMS_PER_AGENT or file_atoms >= MAX_ATOMS_PER_FILE:
                    break
                pointer = hashlib.sha256(f"{slug}:{rel}:{index}:{claim[:80]}".encode("utf-8")).hexdigest()[:16]
                if store.exists(pointer):
                    continue
                store.remember(Proof(claim, pointer, f"import 2026-10-06 from {rel} (mtime {mtime})"))
                written += 1
                file_atoms += 1
        if written:
            print(f"{slug:38s} +{written:3d} atoms (pool now {store.count()})")
        total += written
    print(f"TOTAL: {total} atoms imported")


if __name__ == "__main__":
    main()
