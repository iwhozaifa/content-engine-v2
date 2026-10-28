"""Plan next week: fill open slots Must-Do → approved news → creator ideas, lock the topics, write the
Weekly Plans page. No scripts are written here (generate-cards does that)."""
from datetime import date, datetime, timedelta, timezone

from services import props as P
from services import slots
from services.plan import ChangeSet
from services.settings import DAYS

WRITES = True
UNPLANNABLE = {"Rejected", "Archived", "Published", "Topic Locked", "Scripting", "Scripted", "In Production"}


def add_arguments(p):
    p.add_argument("--week", help="week start (a Monday, YYYY-MM-DD); default: the Monday after today")


def run(ctx):
    ctx.load_notion_settings()
    s = ctx.settings
    cs = ChangeSet("weekly-plan")
    ds = {k: v["data_source"] for k, v in ctx.ids["databases"].items()}
    added = slots.today(s)
    start = date.fromisoformat(ctx.args.week) if ctx.args.week else slots.next_week_start(added)
    if start.weekday() != 0:
        raise ValueError(f"--week must be a Monday, got {start} ({DAYS[start.weekday()]})")
    all_slots = slots.week_slots(start, s["cadence"])
    end = start + timedelta(days=6)

    # Occupied slots: rows with a Slot key, and legacy rows counted per day.
    flt = {"and": [{"property": "Date", "date": {"on_or_after": start.isoformat()}},
                   {"property": "Date", "date": {"on_or_before": end.isoformat()}}]}
    existing = [P.values(p) for p in ctx.notion.query(ds["content_plan"], filter=flt)]
    taken = {v["Slot key"] for v in existing if v.get("Slot key")}
    legacy_per_day = {}
    for v in existing:
        if not v.get("Slot key") and v.get("Date"):
            legacy_per_day[v["Date"][:10]] = legacy_per_day.get(v["Date"][:10], 0) + 1
    open_slots = []
    for key, d, n in all_slots:
        if key in taken:
            continue
        if legacy_per_day.get(d.isoformat(), 0) >= n:
            continue
        open_slots.append((key, d, n))

    pool, waiting = build_pool(ctx, ds)
    placements = []
    used_clusters = set()
    for bucket in ("Must-Do", "News", "Creator"):
        for idea in pool[bucket]:
            if not open_slots:
                break
            cl = (idea.get("Cluster") or "").strip().lower()
            if bucket != "Must-Do" and cl and cl in used_clusters:
                cs.skip(idea["key"], f"same cluster as another idea this week ({cl})")
                continue
            used_clusters.add(cl)
            slot = open_slots.pop(0)
            placements.append((slot, idea, bucket))

    left_must = [i for i in pool["Must-Do"] if i["id"] not in {p[1]["id"] for p in placements}]
    if left_must:
        ctx.log.warn(f"{len(left_must)} Must-Do idea(s) didn't fit this week and wait for the next open slot: "
                     + "; ".join(i["Idea"] or "?" for i in left_must))
    for w in waiting:
        ctx.log.warn(w)

    wkey = slots.week_key(start)
    plan_page = next(iter(ctx.notion.query(ds["weekly_plans"], filter={"property": "Engine key", "rich_text": {"equals": wkey}},
                                           limit=1)), None)
    if not open_slots and not placements and plan_page is not None:
        ctx.out(f"{wkey}: every slot is taken; nothing to plan.")
    now = datetime.now(timezone.utc)
    plan_change = None
    filled = len(all_slots) - len(open_slots)
    rows = [(slot[1], slot[2], idea, bucket, slots.post_date(slot[1], added, s)[0]) for slot, idea, bucket in placements]
    if plan_page is None:
        title = f"Week {wkey[5:]} ({start:%b %d} – {end:%b %d})"
        plan_change = cs.create("weekly_plans", wkey, {
            "Week": P.title(title), "Engine key": P.text(wkey), "Week start": P.date(start.isoformat()),
            "Status": P.select("Draft"), "Slots": P.number(len(all_slots)), "Filled": P.number(filled),
            "Summary": P.text(summary_text(rows, left_must))}, {"Week": title, "Slots": len(all_slots), "Filled": filled},
            children=plan_body(rows, left_must))
    elif placements:
        pv = P.values(plan_page)
        cs.update("weekly_plans", wkey, plan_page["id"], {"Filled": P.number(filled), "Summary": P.text(
            ((pv.get("Summary") or "") + "\n" + summary_text(rows, left_must)).strip())},
            {"Filled": filled}, expected_edit=plan_page.get("last_edited_time"))
        cs.blocks("weekly_plans", f"{wkey}#rerun-{now:%Y%m%dT%H%M}", plan_page["id"],
                  [P.heading(f"Added {now:%Y-%m-%d %H:%M} UTC", 3), *plan_body(rows, left_must)[1:]],
                  {"append": f"{len(rows)} placements"})
    plan_id = (lambda: plan_page["id"]) if plan_page is not None else (lambda: plan_change.result_id)

    for (key, d, n), idea, bucket in placements:
        post, why = slots.post_date(d, added, s)
        props = P.clean({
            "Video": P.title(idea.get("Idea") or "Untitled"), "Date": P.date(d.isoformat()), "Day": P.text(DAYS[d.weekday()]),
            "Slot key": P.text(key), "Status": P.select("Topic Locked"), "Topic locked": P.checkbox(True),
            "Locked at": P.date(now.isoformat(timespec="seconds")), "Approval": P.select("Pending"),
            "Added to calendar": P.date(added.isoformat()), "Suggested post date": P.date(post.isoformat()),
            "Post date rationale": P.text(why), "Pillar": P.text(idea.get("Pillar")), "Content job": P.text(idea.get("Content job")),
            "Brand fit": P.number(idea.get("Brand fit")), "Brand fit reason": P.text(idea.get("Brand fit reason")),
            "Priority": P.select(idea.get("Priority") or "Normal"), "Origin": P.select(idea.get("Origin")),
            "Platforms": P.multi(idea.get("Target platforms") or ["Instagram", "TikTok", "YouTube Shorts"]),
            "Format": P.select("Short"), "Original angle": P.text(idea.get("Transformative angle") or idea.get("Differentiation note")),
            "Creator input required": P.checkbox(idea.get("Needs creator proof")), "Template": P.text("Educational Short"),
            "Source inspiration": P.url(idea.get("source_url")), "Idea": P.relation([idea["id"]])})
        cs.create("content_plan", key, lambda props=props: {**props, "Weekly plan": P.relation([plan_id()])},
                  {"Date": f"{DAYS[d.weekday()]} {d}", "Idea": (idea.get("Idea") or "")[:30], "from": bucket,
                   "post": post.isoformat()})
        cs.update("idea_bank", f"lock:{idea['id']}", idea["id"], {"Status": P.select("Topic Locked")},
                  {"Idea": (idea.get("Idea") or "")[:30], "Status": "Topic Locked"},
                  expected_edit=idea.get("_edited"), reason=f"placed in {key}")
    ctx.execute(cs)
    ctx.out(f"\n{wkey}: {len(all_slots)} slots · {filled - len(placements)} already taken · {len(placements)} placed · "
            f"{len(open_slots)} still open")
    for d, n, idea, bucket, post in rows:
        ctx.out(f"  {DAYS[d.weekday()]} {d} #{n}  [{bucket:<8}] {idea.get('Idea')} · post {post}")
    return cs


def build_pool(ctx, ds):
    """{'Must-Do': [...], 'News': [...], 'Creator': [...]} of plannable ideas, best first."""
    flt = {"or": [{"property": "Priority", "select": {"equals": "Must-Do"}},
                  {"property": "Status", "select": {"equals": "Approved"}},
                  {"property": "Status", "select": {"equals": "Shortlisted"}}]}
    pool = {"Must-Do": [], "News": [], "Creator": []}
    waiting = []
    for page in ctx.notion.query(ds["idea_bank"], filter=flt):
        v = P.values(page)
        if v.get("Status") in UNPLANNABLE or v.get("Plan item"):
            continue
        idea = {**v, "id": page["id"], "_edited": page.get("last_edited_time"), "key": v.get("Engine key") or page["id"]}
        if v.get("Priority") == "Must-Do":
            if v.get("Status") == "Needs Input":
                waiting.append(f"Must-Do '{v.get('Idea')}' holds a slot but still needs a transcript (Needs Input)")
            pool["Must-Do"].append(idea)
        elif v.get("Status") in ("Approved", "Shortlisted") and v.get("Brand fit pass"):
            pool["News" if v.get("Origin") == "News" else "Creator"].append(idea)
    for bucket in pool.values():
        bucket.sort(key=rank)
    for idea in pool["Must-Do"] + pool["News"] + pool["Creator"]:
        idea["source_url"] = None
    attach_sources(ctx, pool)
    return pool, waiting


def rank(idea):
    """Approved before Shortlisted; time-sensitive first; then Review rank, Fit score, Brand fit."""
    return (0 if idea.get("Status") == "Approved" else 1, 0 if idea.get("Priority") == "Time-sensitive" else 1,
            -(idea.get("Review rank") or 0), -(idea.get("Fit score") or 0), -(idea.get("Brand fit") or 0))


def attach_sources(ctx, pool, per_bucket=10):
    for bucket in pool.values():
        for idea in bucket[:per_bucket]:
            src = idea.get("Sources") or []
            if src:
                try:
                    idea["source_url"] = P.values(ctx.notion.get_page(src[0])).get("Video URL")
                except Exception:  # noqa: BLE001 - a missing source link isn't worth failing the plan
                    pass


def summary_text(rows, left_must):
    out = [f"{DAYS[d.weekday()]} {d}: {idea.get('Idea')} [{bucket}]" for d, n, idea, bucket, _ in rows]
    if left_must:
        out.append(f"Waiting Must-Do: {len(left_must)}")
    return "\n".join(out)[:1900]


def plan_body(rows, left_must):
    lines = [P.heading("Slots")]
    lines += P.bullets([f"{DAYS[d.weekday()]} {d} #{n} · {bucket} · {idea.get('Idea')} · post {post}"
                        f" · brand fit {idea.get('Brand fit') or '–'}" for d, n, idea, bucket, post in rows])
    if left_must:
        lines += [P.heading("Must-Do waiting for a slot", 3), *P.bullets([i.get("Idea") for i in left_must])]
    lines.append(P.para("Topics are locked; approve each one in the Content Plan (Approval). "
                        "Content cards come from `cli.py generate-cards --locked`."))
    return lines
