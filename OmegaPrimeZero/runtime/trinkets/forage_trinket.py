from runtime.trinkets.base import EventAwareTrinket


class ForageTrinket(EventAwareTrinket):
    section = "forage"

    def publish(self, ctx: dict) -> str:
        if not (ctx.get("channels") or {}).get("forage"):
            return ""
        return ctx.get("forage") or ""
