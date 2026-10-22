from runtime.trinkets.base import EventAwareTrinket


class PeanutGalleryTrinket(EventAwareTrinket):
    section = "peanut_gallery"

    def publish(self, ctx: dict) -> str:
        return ctx.get("peanut") or ""
