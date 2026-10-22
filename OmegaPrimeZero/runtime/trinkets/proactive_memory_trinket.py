from runtime.trinkets.base import EventAwareTrinket


class ProactiveMemoryTrinket(EventAwareTrinket):
    section = "proactive_memory"

    def publish(self, ctx: dict) -> str:
        # Already chosen. This does not search.
        memories = ctx.get("memories") or []
        return "\n".join(memories)
