"""Usage tracking + decay for the skills and rules pools.

Each surfacing (injection into a prompt) refreshes an atom's decay clock —
the cerebrum's "reinforced entries decay slower" made literal. Sweeping moves
atoms past their half-life to a quarantine file instead of deleting them.

Sidecar: out/metta/usage-<pool>.json  {pointer: {"last": iso, "uses": n}}
Pools not registered here (agents, collective) are untouched by decay — they
keep the plain MAX_ATOMS rolling window.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

METTA_DIR = Path(__file__).resolve().parent.parent.parent / "out" / "metta"

# Days without a surfacing before an atom is quarantined.
HALF_LIVES = {"skills": 14, "rules": 60}


def _path(pool: str) -> Path:
    return METTA_DIR / f"usage-{pool}.json"


def load(pool: str) -> dict:
    try:
        return json.loads(_path(pool).read_text(encoding="utf-8"))
    except Exception:
        return {}


def touch(pool: str, pointers: list[str]) -> None:
    """Mark atoms as surfaced just now (resets their decay clock)."""
    if pool not in HALF_LIVES or not pointers:
        return
    usage = load(pool)
    now = datetime.now(timezone.utc).isoformat()
    for pointer in pointers:
        entry = usage.setdefault(pointer, {"uses": 0})
        entry["last"] = now
        entry["uses"] = entry.get("uses", 0) + 1
    _path(pool).write_text(json.dumps(usage, indent=1), encoding="utf-8")


def sweep(store, pool: str, now: datetime | None = None) -> list[str]:
    """Quarantine atoms in store not surfaced within the pool's half-life.

    Returns the quarantined claims. Atoms never surfaced decay from their
    pointer-recorded creation (sidecar missing = never used = decaying).
    """
    days = HALF_LIVES.get(pool)
    if days is None:
        return []
    now = now or datetime.now(timezone.utc)
    usage = load(pool)
    cutoff = now.timestamp() - days * 86400
    stale: list[tuple[str, str, str]] = []
    now_iso = now.isoformat()
    for claim, pointer, evidence in store._match():
        record = usage.get(pointer)
        if record is None:
            # Never surfaced AND never seen by a sweep: first-seen grace —
            # the decay clock starts now, not at the unix epoch. Seeded atoms
            # get their full half-life to prove themselves.
            usage[pointer] = {"last": now_iso, "uses": 0}
            continue
        try:
            last_ts = datetime.fromisoformat(record.get("last", "")).timestamp()
        except Exception:
            last_ts = 0.0
        if last_ts < cutoff:
            stale.append((claim, pointer, evidence))
    if not stale:
        _path(pool).write_text(json.dumps(usage, indent=1), encoding="utf-8")
        return []
    quarantine = METTA_DIR / f"{store.path.stem}.quarantined-{now.date().isoformat()}"
    with open(quarantine, "a", encoding="utf-8") as fh:
        for claim, pointer, evidence in stale:
            fh.write(json.dumps({"claim": claim, "pointer": pointer, "evidence": evidence}, ensure_ascii=False) + "\n")
    keep = set(store._order) - {pointer for _c, pointer, _e in stale}
    by_pointer = {pointer: (claim, evidence) for claim, pointer, evidence in store._match() if pointer in keep}
    from hyperon import E, MeTTa, S, ValueAtom

    store._metta = MeTTa()
    store._order = [pointer for pointer in store._order if pointer in by_pointer]
    for pointer in store._order:
        claim, evidence = by_pointer[pointer]
        store._metta.space().add_atom(
            E(S("memory"), ValueAtom(claim), ValueAtom(pointer), ValueAtom(evidence))
        )
    store._persist()
    for _c, pointer, _e in stale:
        usage.pop(pointer, None)
    _path(pool).write_text(json.dumps(usage, indent=1), encoding="utf-8")
    return [claim for claim, _p, _e in stale]
