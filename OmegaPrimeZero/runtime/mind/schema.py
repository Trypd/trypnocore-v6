"""Content-only turn schema. The chain of thought lives in content."""
from __future__ import annotations

import math
from dataclasses import dataclass

TAPE_TOKEN_BUDGET = 10_000
DREAM_KEEP_TOKENS = 7_000
QUIET_SEGMENT_MINUTES = 60

PREFIXES = ("think:", "saw:", "heard:", "near:", "compressed:")
ASSISTANT_PREFIXES = ("think:", "compressed:")
FORBIDDEN_KEYS = frozenset({"reasoning", "reasoning_content"})
ALLOWED_KEYS = frozenset({"role", "content"})
ALLOWED_ROLES = frozenset({"system", "user", "assistant"})


class SchemaError(ValueError):
    pass


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return math.ceil(len(text) / 4)


def assert_content_only(message: dict) -> None:
    if not isinstance(message, dict):
        raise SchemaError("message must be a dict")
    forbidden = FORBIDDEN_KEYS.intersection(message)
    if forbidden:
        raise SchemaError(f"reasoning field is a failure: {sorted(forbidden)}")
    extra = set(message) - ALLOWED_KEYS
    if extra:
        raise SchemaError(f"only role and content are allowed, got {sorted(extra)}")
    if not isinstance(message.get("content"), str):
        raise SchemaError("content must be a string")
    if message.get("role") not in ALLOWED_ROLES:
        raise SchemaError(f"bad role: {message.get('role')!r}")


@dataclass(frozen=True)
class AssistantContent:
    think_lines: tuple[str, ...]
    other_prefixed: tuple[str, ...]
    utterance: str


def _prefixed(line: str, names: tuple[str, ...]) -> bool:
    return any(line.startswith(name + " ") for name in names)


def parse_assistant_content(content: str) -> AssistantContent:
    if "\n\n" not in content:
        raise SchemaError("utterance must follow a blank line")
    head, utterance = content.split("\n\n", 1)
    lines = [ln for ln in head.splitlines() if ln.strip()]
    if not lines:
        raise SchemaError("at least one think: line is required")
    think: list[str] = []
    other: list[str] = []
    for line in lines:
        if not _prefixed(line, ASSISTANT_PREFIXES):
            raise SchemaError(f"assistant head must be think: or compressed:: {line!r}")
        if line.startswith("think: "):
            think.append(line)
        else:
            other.append(line)
    if not think:
        raise SchemaError("at least one think: line is required")
    for line in utterance.splitlines():
        if line.startswith("think:") or line.startswith("saw:") or line.startswith("heard:"):
            raise SchemaError("prefixed lines belong above the blank line")
    return AssistantContent(tuple(think), tuple(other), utterance)


def utterance_of(content: str) -> str:
    return parse_assistant_content(content).utterance
