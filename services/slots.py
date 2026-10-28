"""Slots, weeks and post dates. Pure functions, so the weekly plan's maths is easy to test."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from services.settings import DAYS


def today(settings):
    return datetime.now(ZoneInfo(settings.get("general.timezone", "UTC"))).date()


def next_week_start(day):
    """The Monday after `day` (a Friday plans the following Monday–Sunday)."""
    return day + timedelta(days=7 - day.weekday())


def week_slots(week_start, cadence):
    """[(slot key, date, n)] for the cadence's days in the week starting week_start (a Monday)."""
    out = []
    for name in cadence["days"]:
        d = week_start + timedelta(days=DAYS.index(name))
        for n in range(1, cadence.get("slots_per_day", 1) + 1):
            out.append((f"slot:{d.isoformat()}#{n}", d, n))
    return out


def week_key(week_start):
    y, w, _ = week_start.isocalendar()
    return f"week:{y}-W{w:02d}"


def post_date(slot_date, added, settings):
    """Suggested post date and the rationale shown in Notion."""
    offset = int(settings["post_date.offset_days"])
    base_name = settings.get("post_date.base", "slot_date")
    base = added if base_name == "added_date" else slot_date
    when = base + timedelta(days=offset)
    return when, f"{base_name.replace('_', ' ')} {base.isoformat()} + {offset} days (Engine Settings: post-date offset/base)"


def parse_date(value):
    return date.fromisoformat(str(value)[:10]) if value else None
