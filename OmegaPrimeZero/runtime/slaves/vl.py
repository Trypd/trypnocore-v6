"""Pixels to saw:. No boot. No think:."""
from __future__ import annotations

from runtime.paths import VL_GGUF


def slave_prompt(payload: str, boot: str = "") -> str:
    if boot and boot in payload:
        raise RuntimeError("slave prompt must not contain the boot")
    return payload


def saw_line(pixels: str | bytes | None) -> str | None:
    if not pixels:
        return None
    text = pixels if isinstance(pixels, str) else "frame"
    line = f"saw: {text}"
    if line.startswith("think:"):
        raise RuntimeError("slave must not emit think:")
    return line


def checkpoint() -> str:
    return str(VL_GGUF)
