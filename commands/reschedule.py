"""Act on your Approval decisions in the Content Plan:
  Postponed → first open slot in a later week (card kept, history logged, Approval back to Pending)
  Rejected  → slot released (topic unlocked; the idea is set Rejected with the reason)
  Approved + Script Chosen → Ready to Post (nothing reaches Ready to Post without your Approved)."""
from datetime import date, datetime, timedelta, timezone

from commands.weekly_plan import week_openings
from services import props as P
from services import slots
from services.plan import ChangeSet
from services.settings import DAYS

WRITES = True
MAX_WEEKS = 8


def add_arguments(p):
    pass


def run(ctx):
    ctx.load_notion_settings()
    s = ctx.settings
    cs = ChangeSet("reschedule")
    ds = {k: v["data_source"] for k, v in ctx.ids["databases"].items()}
    today = slots.today(s)
    now = datetime.now(timezone.utc)
    q = lambda approval: list(ctx.notion.query(ds["content_plan"], filter={"property": "Approval", "select": {"equals": approval}},  # noqa: E731
                                                sorts=[{"property": "Date", "direction": "ascending"}]))
    report = []

    reserved = {}  # week start -> open slots still free during this run
    for page in q("Postponed"):
        v = P.values(page)
        current = slots.parse_date(v.get("Date")) or today
        slot = first_open(ctx, ds, slots.next_week_start(max(current, today)), reserved)
        if slot is None:
            ctx.log.warn(f"No open slot in the next {MAX_WEEKS} weeks for '{v.get('Video')}'; left Postponed")
            continue
        key, d, n = slot
        post, why = slots.post_date(d, today, s)
        history = ((v.get("Date history") or "") + f"\n{today}: {v.get('Date') or '—'} → {d} (postponed)").strip()
        wk = slots.week_key(d - timedelta(days=d.weekday()))
        plan_page = next(iter(ctx.notion.query(ds["weekly_plans"], filter={"property": "Engine key", "rich_text": {"equals": wk}},
                                               limit=1)), None) if "weekly_plans" in ds else None
        props = {"Date": P.date(d.isoformat()), "Day": P.text(DAYS[d.weekday()]), "Slot key": P.text(key),
                 "Suggested post date": P.date(post.isoformat()), "Post date rationale": P.text(why),
                 "Date history": P.text(history), "Approval": P.select("Pending")}
        if not v.get("Original date") and v.get("Date"):
            props["Original date"] = P.date(v["Date"][:10])
        if plan_page is not None:
            props["Weekly plan"] = P.relation([plan_page["id"]])
        cs.update("content_plan", f"postpone:{page['id']}:{today}", page["id"], props,
                  {"Video": (v.get("Video") or "")[:30], "from": v.get("Date"), "to": d.isoformat()},
                  expected_edit=page.get("last_edited_time"))
        report.append(f"moved     {v.get('Video')} · {v.get('Date')} → {DAYS[d.weekday()]} {d} (post {post})")

    for page in q("Rejected"):
        v = P.values(page)
        if not v.get("Topic locked") and not v.get("Slot key"):
            continue  # already released
        cs.update("content_plan", f"reject:{page['id']}", page["id"],
                  {"Topic locked": P.checkbox(False), "Slot key": P.text(""),
                   "Date history": P.text(((v.get("Date history") or "") + f"\n{today}: rejected, slot released").strip())},
                  {"Video": (v.get("Video") or "")[:30], "slot": "released"}, expected_edit=page.get("last_edited_time"))
        for idea_id in v.get("Idea") or []:
            cs.update("idea_bank", f"reject-idea:{idea_id}", idea_id,
                      {"Status": P.select("Rejected"), "Rejection reason": P.text(f"Rejected in the Content Plan ({today})")},
                      {"Status": "Rejected"})
        report.append(f"released  {v.get('Video')} · {v.get('Date')}")

    for page in q("Approved"):
        v = P.values(page)
        if v.get("Status") == "Script Chosen":
            cs.update("content_plan", f"ready:{page['id']}", page["id"], {"Status": P.select("Ready to Post")},
                      {"Video": (v.get("Video") or "")[:30], "Status": "Ready to Post"}, expected_edit=page.get("last_edited_time"))
            report.append(f"ready     {v.get('Video')} · post {v.get('Suggested post date') or v.get('Date')}")
        elif v.get("Status") in ("Topic Locked", "Card Ready"):
            report.append(f"approved  {v.get('Video')} · waiting for a chosen variation (A/B) before Ready to Post")

    ctx.execute(cs)
    for line in report:
        ctx.out(line)
    return cs


def first_open(ctx, ds, start, reserved):
    week = start
    for _ in range(MAX_WEEKS):
        if week not in reserved:
            reserved[week] = week_openings(ctx, ds, week)[1]
        if reserved[week]:
            return reserved[week].pop(0)
        week = date.fromordinal(week.toordinal() + 7)
    return None
