from runtime.trinkets.base import EventAwareTrinket


class LiveContextCompactionTrinket(EventAwareTrinket):
    """A rolling brief. It does not dream."""

    section = "live_brief"

    def publish(self, ctx: dict) -> str:
        return ctx.get("live_brief") or ""
