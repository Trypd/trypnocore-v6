from runtime.trinkets.base import EventAwareTrinket


class MemoryCuratorTrinket(EventAwareTrinket):
    section = "curator"

    def publish(self, ctx: dict) -> str:
        return ctx.get("curator_status") or ""
