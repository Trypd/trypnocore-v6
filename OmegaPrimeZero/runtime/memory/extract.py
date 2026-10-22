"""Post-turn memory extraction. The mind curates its own atoms.

Every recorded assistant reply is parsed for think: lines. First-person,
substantive self-observations become Candidates, pass the light_sleep dedupe,
and promote through deep_sleep into the MeTTa store. Extraction failures
never break the chat loop — the caller decides how to report them.
"""
from __future__ import annotations

import hashlib
import re

from runtime.dream.deep import deep_sleep
from runtime.dream.light import Candidate, light_sleep

_FIRST_PERSON = re.compile(r"^(I\b|I'm\b|Ive\b|I've\b|My\b|Me\b)")
_MIN_CHARS = 12
_OPERATION_LABEL = re.compile(
    r"^\**\s*(Spatial\s+orientation|Metacognitive\s+monitoring|Self-model\s+reinforcement|"
    r"Autobiographical\s+tethering|Narrativization|Excerption|Spatialization|The\s+first-person\s+subject)\**:\s*",
    re.IGNORECASE,
)


def _think_lines(reply: str) -> list[str]:
    """Head lines of a reply, accepting both protocol shapes:
    per-line "think: ..." and the block form ("think:" bare line, then
    spatialized lines until the blank line before the utterance)."""
    if "\n\n" not in reply:
        return []
    head = reply.split("\n\n", 1)[0]
    lines = [ln for ln in head.splitlines() if ln.strip()]
    if not lines:
        return []
    if lines[0].strip().lower() == "think:":
        return [ln.strip() for ln in lines[1:]]
    out = []
    for ln in lines:
        if ln.startswith("think: "):
            out.append(ln[len("think:"):].strip())
        else:
            return []  # unprefixed mixed head: not a think block we trust
    return out


def candidates_from_reply(reply: str, now: str) -> list[Candidate]:
    """First-person think lines of one reply, deduped. No store access."""
    out: list[Candidate] = []
    for index, text in enumerate(_think_lines(reply)):
        text = _OPERATION_LABEL.sub("", text).strip()
        if len(text) < _MIN_CHARS:
            continue
        if "http://" in text or "https://" in text:
            continue
        if not _FIRST_PERSON.match(text):
            continue
        pointer = hashlib.sha256(f"{now}:{index}:{text}".encode("utf-8")).hexdigest()[:16]
        out.append(
            Candidate(
                text=text,
                source_think_id=pointer,
                score=1.0,
                kind="think",
                evidence=reply[:500],
            )
        )
    return light_sleep(out)


def harvest_reply(reply: str, now: str, store) -> int:
    """Promote one reply's first-person thoughts into atoms. Returns the count."""
    staged = candidates_from_reply(reply, now)
    if not staged:
        return 0
    return len(deep_sleep(staged, store))
