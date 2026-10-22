"""Collective memory import: the shared C:/Trypnocore/.wolf -> every agent's pool.

Same chunking and pointer scheme as import_memories.py, with rel paths
relative to C:/Trypnocore — so a collective chunk identical to one an agent
already has from their own .wolf/ produces the SAME pointer and dedupes
away. Only new or divergent collective content lands.

Skips .txt (root .wolf's only .txt files are command-output dumps).
Run from anywhere: python C:/Trypnocore/fleet/import_collective.py
STOP the OPZ chat server first (it caches pools in memory).
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
from importlib import import_module

REGISTRY = Path(r"C:\Trypnocore\fleet\fleet-registry.json")
ROOT = Path(r"C:\Trypnocore")
METTA_DIR = Path(r"C:\Trypnocore\OmegaPrimeZero\out\metta")

MAX_ATOMS_PER_AGENT = 40
MAX_ATOMS_PER_FILE = 8
MAX_CLAIM_CHARS = 600
MIN_CLAIM_CHARS = 40

# reuse the proven chunker
imp = import_module("import_memories")
chunks = imp.chunks


def main() -> None:
    wolf = ROOT / ".wolf"
    files = sorted(
        (p for p in wolf.rglob("*.md") if p.is_file() and ".bak" not in p.name.lower()),
        key=lambda f: -f.stat().st_mtime,
    )
    print(f"collective .wolf: {len(files)} md files")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    total = 0
    for agent in registry["agents"]:
        slug = agent["slug"]
        if slug == "memory":
            continue
        store = MettaSpace.for_pool(METTA_DIR, slug)
        written = 0
        for f in files:
            if written >= MAX_ATOMS_PER_AGENT:
                break
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            mtime = time.strftime("%Y-%m-%d", time.localtime(f.stat().st_mtime))
            rel = f.relative_to(ROOT)
            file_atoms = 0
            for index, claim in enumerate(chunks(text)):
                if written >= MAX_ATOMS_PER_AGENT or file_atoms >= MAX_ATOMS_PER_FILE:
                    break
                pointer = hashlib.sha256(f"{slug}:{rel}:{index}:{claim[:80]}".encode("utf-8")).hexdigest()[:16]
                if store.exists(pointer):
                    continue
                store.remember(Proof(claim, pointer, f"import 2026-10-07 from collective {rel} (mtime {mtime})"))
                written += 1
                file_atoms += 1
        print(f"{slug:38s} +{written:3d} atoms (pool now {store.count()})")
        total += written
    print(f"TOTAL: {total} collective atoms imported")


if __name__ == "__main__":
    main()
