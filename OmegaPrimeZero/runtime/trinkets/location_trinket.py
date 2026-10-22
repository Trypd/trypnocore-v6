from runtime.trinkets.base import EventAwareTrinket


class LocationTrinket(EventAwareTrinket):
    section = "location"

    def publish(self, ctx: dict) -> str:
        return ctx.get("location") or ""
