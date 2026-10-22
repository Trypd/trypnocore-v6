"""Supplemental harness only. Snapshot first. Rollback is byte-exact."""
from __future__ import annotations

from pathlib import Path

from runtime.mind.boot import END, START


class RefineError(ValueError):
    pass


def snapshot(path: Path) -> bytes:
    return path.read_bytes()


def apply_patch(supplement: Path, boot: Path, patch: str, *, base_prompt: str = "") -> None:
    if START in patch or END in patch:
        raise RefineError("patch touches the marker region")
    boot_text = boot.read_text(encoding="utf-8") if boot.is_file() else ""
    if boot_text and boot_text in patch:
        raise RefineError("patch touches the boot")
    if base_prompt and base_prompt in patch:
        raise RefineError("patch touches the base prompt")
    if "RECURSSFF" in patch:
        raise RefineError("patch touches RECURSSFF")
    existing = supplement.read_text(encoding="utf-8") if supplement.is_file() else ""
    supplement.write_text(existing + patch, encoding="utf-8")


def rollback(path: Path, snap: bytes) -> None:
    path.write_bytes(snap)
