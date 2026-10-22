"""Operator boot. Only the marker interior may change."""
from __future__ import annotations

from pathlib import Path

START = "<!-- LIVE_STATE_START -->"
END = "<!-- LIVE_STATE_END -->"


class BootError(ValueError):
    pass


def load_boot(path: Path) -> str:
    if not path.is_file():
        raise BootError(f"boot missing: {path}")
    text = path.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise BootError("boot is unmarked")
    if text.index(START) > text.index(END):
        raise BootError("markers out of order")
    return text


def outside_markers(text: str) -> tuple[str, str]:
    pre, rest = text.split(START, 1)
    _inner, post = rest.split(END, 1)
    return pre, post


def inject(path: Path, lens: str) -> None:
    """Replace only the bytes between the markers."""
    text = load_boot(path)
    pre, post = outside_markers(text)
    if START in lens or END in lens:
        raise BootError("lens must not contain the markers")
    path.write_text(f"{pre}{START}\n{lens}\n{END}{post}", encoding="utf-8")


def outside_unchanged(before: str, after: str) -> bool:
    return outside_markers(before) == outside_markers(after)
