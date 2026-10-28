"""Stop-gate seal (Windows side of tryp-stop-seal.sh).

Fast, synchronous: seals a `turn` ring on the agent's soulchain when the
session ends with an unsealed stop, and seals an `epoch` ring if identity
docs drifted. This is the enforce.py organ ported: the boot ritual becomes a
mechanism — a session that produced no ring announces itself on next boot.

Reads the CC Stop payload on stdin ({"cwd", ...}). Fails silent.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, os.environ.get("TRYP_SOULCHAIN", r"C:\Trypnocore\fleet"))
from tryp_identity import resolve


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return
    agent = resolve(payload.get("cwd", ""))
    if not agent:
        return
    try:
        from soulchain import Soulchain
        chain = Soulchain(agent["folder"])
        drifted = chain.seal_epoch_if_drifted()
        chain.seal("turn", {"note": "session end", **({"drifted": drifted} if drifted else {})})
    except Exception:
        pass


if __name__ == "__main__":
    main()
