"""Refresh the fleet roster atom in every pool.

The roster atom is content-addressed (pointer = sha256 of the claim), so a
changed roster lands as a NEW atom and the stale one stays. This script
strips every existing roster atom from the pool files, then re-injects via
inject_roster.py.

STOP the OPZ chat server before running (it caches pools in memory).
Run: python C:/Trypnocore/fleet/refresh_roster.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

METTA_DIR = Path(r"C:\Trypnocore\OmegaPrimeZero\out\metta")
INJECT = Path(r"C:\Trypnocore\fleet\inject_roster.py")


def main() -> None:
    stripped = 0
    for pool in sorted(METTA_DIR.glob("pool-*.metta")):
        lines = pool.read_text(encoding="utf-8").splitlines(keepends=True)
        kept = [ln for ln in lines if "the fleet roster is:" not in ln]
        if len(kept) != len(lines):
            pool.write_text("".join(kept), encoding="utf-8")
            stripped += len(lines) - len(kept)
    print(f"stripped {stripped} stale roster atoms")
    result = subprocess.run([sys.executable, str(INJECT)], capture_output=True, text=True)
    print(result.stdout.strip() or result.stderr.strip())


if __name__ == "__main__":
    main()
