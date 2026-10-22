"""Sleep when the tape overflows or a segment has been quiet for 60 minutes."""
from __future__ import annotations

from pathlib import Path

from runtime.dream.deep import deep_sleep
from runtime.dream.light import Candidate, light_sleep
from runtime.dream.rem import rem
from runtime.memory import MemoryDouble
from runtime.mind.schema import QUIET_SEGMENT_MINUTES
from runtime.mind.turn import Tape


def maybe_dream(
    tape: Tape,
    store: MemoryDouble,
    dreams_path: Path,
    stretch: list[Candidate],
    *,
    quiet_minutes: int = 0,
    mid_turn: bool = False,
) -> None:
    if mid_turn:
        return
    if not tape.over_budget() and quiet_minutes < QUIET_SEGMENT_MINUTES:
        return
    staged = light_sleep(stretch)
    materialized = rem(staged, dreams_path)
    deep_sleep(materialized, store)
    first = ""
    if dreams_path.is_file():
        body = dreams_path.read_text(encoding="utf-8").strip()
        first = body.splitlines()[0] if body else ""
    tape.compress_to(first)
