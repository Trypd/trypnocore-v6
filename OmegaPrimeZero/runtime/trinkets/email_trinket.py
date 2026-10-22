from runtime.trinkets.base import EventAwareTrinket


class EmailTrinket(EventAwareTrinket):
    section = "email"

    def publish(self, ctx: dict) -> str:
        if not (ctx.get("channels") or {}).get("email"):
            return ""
        return ctx.get("email") or ""
