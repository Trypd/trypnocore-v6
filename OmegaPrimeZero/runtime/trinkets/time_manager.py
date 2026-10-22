from runtime.trinkets.base import EventAwareTrinket


class TimeManager(EventAwareTrinket):
    section = "time"

    def publish(self, ctx: dict) -> str:
        now = ctx.get("now")
        if not now:
            return ""
        text = now if isinstance(now, str) else now.isoformat()
        if "yesterday" in text.lower():
            raise ValueError("time is absolute")
        return text
