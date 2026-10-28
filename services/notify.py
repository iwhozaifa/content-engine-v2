"""Optional run notifications (Engine Settings "Notifications" or settings notify.enabled).

Telegram: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID. Email: SMTP_HOST, SMTP_PORT (587), SMTP_USER,
SMTP_PASSWORD, NOTIFY_EMAIL_TO. Both are free. A failed notification never fails the run.
"""
import os
import smtplib
from email.message import EmailMessage

import requests

NEXT_STEP = {
    "news-radar": ("news_candidates", "Review new News Candidates (set Approval)"),
    "weekly-plan": ("content_plan", "Approve next week's topics in the Content Plan"),
    "generate-cards": ("scripts", "Pick A or B on the new cards"),
    "generate-card": ("scripts", "Pick A or B on the new card"),
    "add-url": ("idea_bank", "New ideas in the Idea Bank"),
    "scan-creators": ("raw_content", "Creator scan results in Raw Content"),
    "reschedule": ("content_plan", "Content Plan updated"),
}


def db_link(ids, key):
    db = ids.get("databases", {}).get(key, {}).get("database")
    return f"https://www.notion.so/{db.replace('-', '')}" if db else ""


def message(log, ids):
    text = log.summary()
    if log.command in NEXT_STEP and (log.counts.get("create") or log.counts.get("update")):
        key, step = NEXT_STEP[log.command]
        text += f"\n→ {step}: {db_link(ids, key)}"
    return f"Content engine · {text}"


def should_send(settings, log):
    if not settings.get("notify.enabled"):
        return False
    changed = any(log.counts.get(k) for k in ("create", "update"))
    return bool(changed or log.errors)


def send(settings, text, post=requests.post, smtp=smtplib.SMTP):
    channel = settings.get("notify.channel", "telegram")
    if channel == "telegram":
        token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        if not (token and chat):
            raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
        r = post(f"https://api.telegram.org/bot{token}/sendMessage",
                 json={"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True}, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Telegram {r.status_code}: {r.text[:200]}")
        return
    if channel == "email":
        host, to = os.environ.get("SMTP_HOST"), os.environ.get("NOTIFY_EMAIL_TO")
        if not (host and to):
            raise RuntimeError("SMTP_HOST and NOTIFY_EMAIL_TO must be set in .env")
        msg = EmailMessage()
        msg["Subject"] = text.splitlines()[0][:120]
        msg["From"] = os.environ.get("SMTP_USER") or to
        msg["To"] = to
        msg.set_content(text)
        with smtp(host, int(os.environ.get("SMTP_PORT", 587)), timeout=30) as s:
            s.starttls()
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
            s.send_message(msg)
        return
    raise RuntimeError(f"Unknown notify.channel {channel!r} (telegram or email)")
