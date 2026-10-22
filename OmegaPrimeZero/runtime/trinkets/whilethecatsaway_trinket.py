from runtime.trinkets.base import EventAwareTrinket


class WhileTheCatsAwayTrinket(EventAwareTrinket):
    section = "whilethecatsaway"

    def publish(self, ctx: dict) -> str:
        if not (ctx.get("channels") or {}).get("whilethecatsaway"):
            return ""
        return ctx.get("whilethecatsaway") or ""
