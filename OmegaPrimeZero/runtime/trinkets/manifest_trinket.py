from runtime.trinkets.base import EventAwareTrinket


class ManifestTrinket(EventAwareTrinket):
    section = "manifest"

    def publish(self, ctx: dict) -> str:
        return ctx.get("manifest") or ""
