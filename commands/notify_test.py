"""Send a test notification (prints it unless --apply)."""
from services import notify

WRITES = True


def add_arguments(p):
    pass


def run(ctx):
    ctx.load_notion_settings()
    text = "Content engine · test notification. If you can read this, run notifications work."
    ctx.out(f"channel: {ctx.settings.get('notify.channel')} · enabled: {ctx.settings.get('notify.enabled')}")
    if not ctx.apply:
        ctx.out(f"would send: {text}\n(add --apply to send)")
        return None
    notify.send(ctx.settings, text)
    ctx.out("sent")
    return None
