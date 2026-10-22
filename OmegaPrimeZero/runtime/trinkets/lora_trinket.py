from runtime.trinkets.base import EventAwareTrinket


class LoraTrinket(EventAwareTrinket):
    section = "lora"

    def publish(self, ctx: dict) -> str:
        if "lora_loaded" not in ctx:
            return ""
        return "loaded" if ctx["lora_loaded"] else "not loaded"
