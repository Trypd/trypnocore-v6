"""REM. First person into DREAMS.md. Still not an atom."""
from __future__ import annotations

from pathlib import Path

from runtime.dream.light import Candidate
from runtime.harness.lifecycle import Stage


class DreamError(ValueError):
    pass


def rem(candidates: list[Candidate], dreams_path: Path) -> list[Candidate]:
    lines: list[str] = []
    materialized: list[Candidate] = []
    for item in candidates:
        if item.kind in {"saw", "heard"}:
            continue
        text = item.text.strip()
        if "The assistant" in text or "the assistant" in text:
            raise DreamError("third-person collapse is refused")
        if "yesterday" in text.lower():
            raise DreamError("dates must be absolute")
        if not text.startswith("I "):
            raise DreamError("REM is first person")
        lines.append(text)
        materialized.append(
            Candidate(text, item.source_think_id, item.score, item.kind, item.evidence, Stage.MATERIALIZED)
        )
    dreams_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return materialized
