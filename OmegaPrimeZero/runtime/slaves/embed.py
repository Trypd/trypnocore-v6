"""Text to near:. A hint, not an assertion."""
from __future__ import annotations


def near_line(text: str | None, score: float | None = None) -> str | None:
    if not text:
        return None
    shown = f"{score:.2f}" if score is not None else "0.00"
    return f"near: {text} {shown}"
