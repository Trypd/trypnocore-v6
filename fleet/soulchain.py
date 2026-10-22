"""soulchain — tamper-evident, hash-chained per-agent continuity ledger.

Derived from the organ harvest of cypher-tempre-genesis (MIT), cyberphysicsai.
Covenant, creed, and formula removed. Chain mechanics only.

Every ring: {index, ts, type, payload, prev_hash, hash} — hash = sha256 over the
canonical JSON of the rest. Genesis payload = sha256 of the agent's identity
documents, so the chain's root is the identity itself, not a creed.

Ring types:
  genesis — one per chain, carries the identity-document hashes
  epoch   — a side-file changed; stores the new hash (silent edits fail verify)
  turn    — a soul cast (the trailing half-thought points to the next ring)
  seal    — session seal

CLI:
  python soulchain.py status  <folder>
  python soulchain.py seal    <folder> [--note "..."]
  python soulchain.py verify  <folder>
  python soulchain.py rehydrate <folder> [--last 5]

Library: Soulchain(folder) → .seal(type, payload), .verify(), .rehydrate(n)
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

CHAIN_NAME = ".soulchain.jsonl"
# Identity documents hashed into genesis + tracked as epochs. Missing files
# are simply skipped — an agent with no soul.md yet still gets a chain.
IDENTITY_DOCS = ["CORE.md", "AGENTS.md", "soul.md"]
EPOCH_DOCS = ["CORE.md", "AGENTS.md", "soul.md", "xcore.md", "IGORRR.md", "TS-PAP.md"]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(ring: dict) -> str:
    body = {k: v for k, v in ring.items() if k != "hash"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Soulchain:
    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)
        self.path = self.folder / CHAIN_NAME

    def _read(self) -> list[dict]:
        if not self.path.is_file():
            return []
        rings = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rings.append(json.loads(line))
        return rings

    def _write(self, rings: list[dict]) -> None:
        self.path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rings) + "\n",
            encoding="utf-8",
        )

    def _head_hash(self, rings: list[dict]) -> str:
        return rings[-1]["hash"] if rings else "0" * 64

    def _doc_hashes(self, docs: list[str]) -> dict:
        out = {}
        for name in docs:
            f = self.folder / name
            if f.is_file():
                out[name] = _sha(f.read_text(encoding="utf-8", errors="replace"))
        return out

    def _genesis_ring(self) -> dict:
        return {
            "index": 0,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "type": "genesis",
            "payload": {"identity_docs": self._doc_hashes(IDENTITY_DOCS)},
            "prev_hash": "0" * 64,
        }

    def seal(self, ring_type: str, payload: dict) -> dict:
        if ring_type == "genesis":
            raise ValueError("genesis is created by seal() automatically, never written directly")
        rings = self._read()
        if not rings:
            rings = [self._genesis_ring()]
            rings[0]["hash"] = _sha(_canonical(rings[0]))
        ring = {
            "index": len(rings),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "type": ring_type,
            "payload": payload,
            "prev_hash": self._head_hash(rings),
        }
        ring["hash"] = _sha(_canonical(ring))
        rings.append(ring)
        self._write(rings)
        return ring

    def epoch_check(self) -> list[str]:
        """Which tracked side-files drifted from their last sealed hash."""
        rings = self._read()
        if not rings:
            return []
        sealed: dict[str, str] = {}
        for r in rings:
            if r["type"] == "genesis":
                sealed.update(r["payload"].get("identity_docs", {}))
            elif r["type"] == "epoch":
                sealed.update(r["payload"].get("doc_hashes", {}))
        drifted = []
        for name, old in sealed.items():
            f = self.folder / name
            if f.is_file() and _sha(f.read_text(encoding="utf-8", errors="replace")) != old:
                drifted.append(name)
        return drifted

    def seal_epoch_if_drifted(self) -> list[str]:
        drifted = self.epoch_check()
        if drifted:
            self.seal("epoch", {"doc_hashes": self._doc_hashes(EPOCH_DOCS), "drifted": drifted})
        return drifted

    def verify(self) -> tuple[bool, str]:
        rings = self._read()
        if not rings:
            return False, "no chain"
        for i, ring in enumerate(rings):
            if ring.get("index") != i:
                return False, f"ring {i}: index mismatch"
            if _sha(_canonical(ring)) != ring.get("hash"):
                return False, f"ring {i}: hash mismatch (content tampered)"
            expected_prev = rings[i - 1]["hash"] if i else "0" * 64
            if ring.get("prev_hash") != expected_prev:
                return False, f"ring {i}: prev_hash mismatch (chain broken)"
        return True, f"{len(rings)} rings, head {rings[-1]['hash'][:16]}"

    def rehydrate(self, last: int = 5) -> str:
        rings = self._read()[-last:]
        if not rings:
            return "(no soulchain yet)"
        lines = []
        for r in rings:
            note = r["payload"].get("note") or json.dumps(r["payload"], ensure_ascii=False)
            lines.append(f"[ring {r['index']} · {r['type']} · {r['ts']}] {note[:200]}")
        return "\n".join(lines)


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        return
    cmd, folder = sys.argv[1], sys.argv[2]
    chain = Soulchain(folder)
    if cmd == "status":
        rings = chain._read()
        ok, msg = chain.verify() if rings else (True, "unsealed")
        print(f"rings: {len(rings)} | verify: {msg}")
        if rings:
            print("head:", json.dumps(rings[-1]["payload"], ensure_ascii=False)[:200])
    elif cmd == "seal":
        note = sys.argv[sys.argv.index("--note") + 1] if "--note" in sys.argv else ""
        drifted = chain.seal_epoch_if_drifted()
        ring = chain.seal("seal", {"note": note} if note else {})
        print(f"sealed ring {ring['index']} (hash {ring['hash'][:16]})" + (f"; epoch sealed for drifted: {drifted}" if drifted else ""))
    elif cmd == "verify":
        ok, msg = chain.verify()
        print(("OK: " if ok else "FAIL: ") + msg)
        sys.exit(0 if ok else 1)
    elif cmd == "rehydrate":
        last = int(sys.argv[sys.argv.index("--last") + 1]) if "--last" in sys.argv else 5
        print(chain.rehydrate(last))
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
