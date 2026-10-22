from runtime.trinkets.base import EventAwareTrinket


class DomainDocTrinket(EventAwareTrinket):
    section = "domaindoc"

    def publish(self, ctx: dict) -> str:
        title = ctx.get("domain_title")
        if not title:
            return ""
        if ctx.get("domain_open"):
            return f"{title}\n{ctx.get('domain_body') or ''}"
        return title
