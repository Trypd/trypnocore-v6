"""Deep sleep. The only automatic atom write."""
from __future__ import annotations

from runtime.dream.light import Candidate
from runtime.harness.lifecycle import Stage
from runtime.memory import MemoryDouble, Proof


def deep_sleep(candidates: list[Candidate], store: MemoryDouble) -> list[Candidate]:
    promoted: list[Candidate] = []
    previous = store.phase
    store.phase = "deep_sleep"
    try:
        for item in candidates:
            if item.kind in {"saw", "heard"}:
                continue
            if item.score < 1 or not item.source_think_id or not item.evidence:
                continue
            store.assert_atom(Proof(item.text, item.source_think_id, item.evidence))
            promoted.append(
                Candidate(
                    item.text,
                    item.source_think_id,
                    item.score,
                    item.kind,
                    item.evidence,
                    Stage.STABILIZED,
                )
            )
    finally:
        store.phase = previous
    return promoted
