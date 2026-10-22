"""Test double for the 8B. Does not open a GGUF."""
from __future__ import annotations


def fake_mind(_frame: list[dict]) -> str:
    return (
        "think: gist of this pass\n"
        "think: the note is the claim\n"
        "\n"
        "The note says the workspace is the broadcast, not the store."
    )
