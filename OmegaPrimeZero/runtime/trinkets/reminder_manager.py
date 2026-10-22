from runtime.trinkets.base import EventAwareTrinket


class ReminderManager(EventAwareTrinket):
    section = "reminders"

    def publish(self, ctx: dict) -> str:
        items = ctx.get("reminders") or []
        return "\n".join(items)
