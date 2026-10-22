"""Light sleep. Stage candidates. No atom write."""
from __future__ import annotations

from dataclasses import dataclass

from runtime.harness.lifecycle import Stage


@dataclass(frozen=True)
class Candidate:
    text: str
    source_think_id: str | None
    score: float
    kind: str
    evidence: str
    stage: Stage = Stage.CAPTURED


def light_sleep(stretch: list[Candidate]) -> list[Candidate]:
    seen: list[str] = []
    staged: list[Candidate] = []
    for item in stretch:
        if item.text in seen:
            continue
        seen.append(item.text)
        staged.append(item)
    return staged
