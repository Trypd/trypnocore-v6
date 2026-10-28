"""Associational recall with a dependency-free lexical path."""
from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "that", "this", "what", "remember", "remind", "and", "for", "with", "you", "your"}


def _words(text: str) -> set[str]:
    return {word for word in _WORD.findall(text.lower()) if len(word) > 2 and word not in _STOP}


def choose_memories(claims_in_order: list[str], text: str, limit: int = 5, pool: str = "") -> list[str]:
    memories = [claim for claim in claims_in_order if not claim.startswith("reminder: ")]
    if not memories:
        return []
    semantic = None
    if pool:
        try:
            from embedder import rank
            semantic = rank(pool, memories, text)
        except Exception:
            semantic = None
    words = _words(text)
    total = max(len(memories) - 1, 1)

    def score(index: int, claim: str) -> float:
        recency = (index / total) * 0.5
        if semantic is not None:
            return semantic.get(claim, -1.0) * 4.0 + len(words & _words(claim)) * 0.5 + recency
        return len(words & _words(claim)) * 2.0 + recency

    ranked = sorted(((score(i, c), i, c) for i, c in enumerate(memories)), key=lambda row: (row[0], row[1]), reverse=True)
    picked: list[str] = []
    floor = 0.0 if semantic is not None else 2.0
    for weighted, _index, claim in ranked:
        if weighted < floor or claim in picked:
            continue
        picked.append(claim)
        if len(picked) >= limit:
            break
    newest = memories[-1]
    if newest not in picked:
        if len(picked) >= limit:
            picked[-1] = newest
        else:
            picked.append(newest)
    return picked
