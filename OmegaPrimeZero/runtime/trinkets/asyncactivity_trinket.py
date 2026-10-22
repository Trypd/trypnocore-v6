from runtime.trinkets.base import EventAwareTrinket


class AsyncActivityTrinket(EventAwareTrinket):
    section = "asyncactivity"

    def publish(self, ctx: dict) -> str:
        if not (ctx.get("channels") or {}).get("asyncactivity"):
            return ""
        return ctx.get("asyncactivity") or ""
