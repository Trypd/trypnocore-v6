"""One frame, one reply. Store content whole."""
from __future__ import annotations

from runtime.mind.schema import (
    DREAM_KEEP_TOKENS,
    TAPE_TOKEN_BUDGET,
    SchemaError,
    assert_content_only,
    estimate_tokens,
    parse_assistant_content,
)


class Tape:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    def append(self, role: str, content: str) -> None:
        message = {"role": role, "content": content}
        assert_content_only(message)
        self.messages.append(message)

    def tokens(self) -> int:
        return sum(estimate_tokens(m["content"]) for m in self.messages)

    def request(self) -> list[dict]:
        """Next request. Thoughts stay inside content. No side field is copied."""
        out = []
        for message in self.messages:
            assert_content_only(message)
            out.append({"role": message["role"], "content": message["content"]})
        return out

    def over_budget(self) -> bool:
        return self.tokens() > TAPE_TOKEN_BUDGET

    def compress_to(self, dream_first_line: str, keep: int = DREAM_KEEP_TOKENS) -> None:
        compressed = f"compressed: {dream_first_line}"
        reserve = estimate_tokens(compressed)
        kept_rev: list[dict] = []
        used = 0
        for message in reversed(self.messages):
            cost = estimate_tokens(message["content"])
            if used + cost + reserve <= keep:
                kept_rev.append(message)
                used += cost
            else:
                break
        kept = list(reversed(kept_rev))
        self.messages = [{"role": "user", "content": compressed}, *kept]


def build_frame(
    *,
    boot: str,
    supplemental: str,
    tape: Tape,
    trinket_sections: list[str],
    sensory: list[str],
) -> list[dict]:
    """Cortex frame. Plan files are not copied onto the tape."""
    messages = [{"role": "system", "content": boot + ("\n" + supplemental if supplemental else "")}]
    messages.extend(tape.request())
    for section in trinket_sections:
        if section:
            messages.append({"role": "user", "content": section})
    for line in sensory:
        if line:
            messages.append({"role": "user", "content": line})
    for message in messages:
        assert_content_only(message)
    return messages


def run_turn(tape: Tape, mind, frame: list[dict]) -> str:
    content = mind(frame)
    message = {"role": "assistant", "content": content}
    assert_content_only(message)
    parse_assistant_content(content)
    tape.append("assistant", content)
    return content


def reject_side_field(payload: dict) -> None:
    if "reasoning" in payload or "reasoning_content" in payload:
        raise SchemaError("reasoning field is a failure")
