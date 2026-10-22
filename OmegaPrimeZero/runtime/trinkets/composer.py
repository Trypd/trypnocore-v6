"""Place sections. Do not assemble the prompt."""
from __future__ import annotations

from runtime.trinkets.base import EventAwareTrinket


def compose(trinkets: list[EventAwareTrinket], ctx: dict) -> list[str]:
    return [trinket.publish(ctx) for trinket in trinkets]
