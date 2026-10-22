"""Tape compression primitives. The mind summarizes its own past.

`compress_tape` is pure: the caller supplies the summarizer (the loaded
model), so tests never touch the network. On success the old span collapses
into one `compressed:` line and the recent tail survives verbatim.
"""
from __future__ import annotations

from collections.abc import Callable

from runtime.mind.schema import estimate_tokens


def tape_token_count(messages: list[dict]) -> int:
    return sum(estimate_tokens(str(message.get("content") or "")) for message in messages)


def compress_tape(
    messages: list[dict],
    summarizer: Callable[[list[dict]], str],
    keep_last: int = 6,
    min_span: int = 4,
) -> list[dict] | None:
    """Collapse all but the last `keep_last` messages via the summarizer.

    Returns the new tape, or None when compression does not apply or the
    summarizer produced nothing.
    """
    if len(messages) <= keep_last + min_span:
        return None
    head, tail = messages[:-keep_last], messages[-keep_last:]
    summary = (summarizer(head) or "").strip()
    if not summary:
        return None
    return [{"role": "user", "content": "compressed: " + summary}, *tail]
