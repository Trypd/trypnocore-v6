"""A trinket publishes one section. Empty string if it has nothing."""
from __future__ import annotations


class EventAwareTrinket:
    section = "section"

    def publish(self, ctx: dict) -> str:
        return ""
