"""Review a skill candidate. Do not commit it."""
from __future__ import annotations

MAX_BYTES = 15 * 1024
MAX_TOOL_CHARS = 500


class GepaReject(ValueError):
    pass


def review_candidate(
    *,
    text: str,
    purpose_before: str,
    purpose_after: str,
    tests_pass: bool,
    tool_descriptions: list[str],
    mid_conversation: bool,
) -> str:
    if mid_conversation:
        raise GepaReject("not applied mid-conversation")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise GepaReject("candidate over 15KB")
    if any(len(item) > MAX_TOOL_CHARS for item in tool_descriptions):
        raise GepaReject("tool description over 500 characters")
    if purpose_before != purpose_after:
        raise GepaReject("purpose changed")
    if not tests_pass:
        raise GepaReject("tests failed")
    return text
