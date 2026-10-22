"""Boot-required entry. Refuses to read weight bytes."""
from __future__ import annotations

from pathlib import Path

from runtime.mind.boot import load_boot
from runtime.paths import AUDIO_STACK, MIND_GGUF, VL_GGUF


class LoaderError(RuntimeError):
    pass


def checkpoint_present(path: Path) -> bool:
    """Stat only. Does not read the file."""
    return path.is_file()


def prepare_mind(boot_path: Path, *, train: bool = False) -> str:
    if train:
        raise LoaderError("tests and the request path must not pass train")
    text = load_boot(boot_path)
    for path in (MIND_GGUF, VL_GGUF, *AUDIO_STACK):
        if not checkpoint_present(path):
            raise LoaderError(f"checkpoint missing: {path}")
    return text
