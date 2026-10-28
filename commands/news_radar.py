"""Daily news radar: RSS → news_judge → News Candidates (Approval = Pending). Candidates you set to
Approved become ideas (Origin News); Rejected ones never do. Nothing is approved automatically."""
import json
from datetime import datetime, timedelta, timezone

from services import brand, news
from services import props as P
from services.plan import ChangeSet
from tools.engine import canon

WRITES = True


def add_arguments(p):
    p.add_argument("--no-fetch", action="store_true", help="only turn Approved candidates into ideas")


def run(ctx):
    ctx.load_notion_settings()
    s = ctx.settings
    cs = ChangeSet("news-radar")
    ds = {k: v["data_source"] for k, v in ctx.ids["databases"].items()}
    now = datetime.now(timezone.utc)
    if not ctx.args.no_fetch:
        radar(ctx, cs, ds, now)
    promote(ctx, cs, ds, now)
    ctx.execute(cs)
    return cs


def radar(ctx, cs, ds, now):
    s = ctx.settings
    today = now.date().isoformat()
    found_today = list(ctx.notion.query(ds["news_candidates"], filter={"property": "Found at", "date": {"on_or_after": today}}))
    room = (ctx.args.limit or s["caps.news_radar"]) - len(found_today)
    if room <= 0:
        ctx.out(f"Daily cap reached ({len(found_today)} candidates today); nothing new to judge.")
        return
    items, errors = news.fetch_all(news.load_feeds())
    for e in errors:
        ctx.log.warn(f"feed {e}")
    since = now - timedelta(hours=s["news.lookback_hours"])
    fresh, seen = [], set()
    for it in sorted(items, key=lambda i: i["published"] or now, reverse=True):
        key = f"news:{canon(it['url'])}"
        if key in seen or (it["published"] and it["published"] < since):
            continue
        seen.add(key)
        it["key"] = key
        fresh.append(it)
    known = existing_keys(ctx, ds, [i["key"] for i in fresh])
    fresh = [i for i in fresh if i["key"] not in known][: s["news.max_items_to_judge"]]
    ctx.out(f"{len(items)} feed items · {len(fresh)} new in the last {s['news.lookback_hours']} h · room for {room} today")
    if not fresh:
        return
    listing = [{"n": i, "headline": it["headline"], "source": it["source"], "summary": it["summary"][:400],
                "published": it["published"].isoformat() if it["published"] else None} for i, it in enumerate(fresh)]
    out = ctx.claude.run("news_judge", {"brand": brand.profile(ctx), "recent": brand.recent_text(brand.open_ideas(ctx)),
                                        "items": json.dumps(listing, ensure_ascii=False), "cap": str(room)}).output
    kept = sorted((k for k in out["keep"] if 0 <= k["n"] < len(fresh)), key=lambda k: -k["brand_fit"])[:room]
    for k in kept:
        it = fresh[k["n"]]
        expires = (now + timedelta(days=k["expires_in_days"])).date().isoformat() if k["expires_in_days"] else None
        cs.create("news_candidates", it["key"], P.clean({
            "Headline": P.title(it["headline"]), "Source URL": P.url(it["url"]), "Engine key": P.text(it["key"]),
            "Source": P.select(it["source"]), "Published": P.date(it["published"].isoformat() if it["published"] else None),
            "Summary": P.text(it["summary"]), "Why it matters": P.text(k["why_it_matters"]),
            "Brand fit": P.number(k["brand_fit"]), "Brand fit reason": P.text(k["reason"]),
            "Suggested angle": P.text(k["suggested_angle"]), "Pillar": P.text(k["pillar"]),
            "Urgency": P.select(k["urgency"]), "Time-sensitive": P.checkbox(k["time_sensitive"]),
            "Expires": P.date(expires), "Approval": P.select("Pending"), "Found at": P.date(now.isoformat(timespec="seconds"))}),
            {"Headline": it["headline"][:40], "fit": k["brand_fit"], "urgency": k["urgency"]})
    ctx.out(f"kept {len(kept)} of {len(fresh)} (Approval = Pending; approve the ones you want in News Candidates)")


def existing_keys(ctx, ds, keys):
    """Engine keys already in News Candidates (one query per key is fine at this volume)."""
    found = set()
    for key in keys:
        if next(iter(ctx.notion.query(ds["news_candidates"], filter={"property": "Engine key", "rich_text": {"equals": key}},
                                      limit=1)), None):
            found.add(key)
    return found


def promote(ctx, cs, ds, now):
    """Approved candidates without an idea → Raw Content (provenance) + Idea Bank (Origin News)."""
    s = ctx.settings
    flt = {"and": [{"property": "Approval", "select": {"equals": "Approved"}},
                   {"property": "Idea", "relation": {"is_empty": True}}]}
    for page in ctx.notion.query(ds["news_candidates"], filter=flt):
        v = P.values(page)
        key = v.get("Engine key") or f"news:{canon(v.get('Source URL') or page['id'])}"
        if next(iter(ctx.notion.query(ds["idea_bank"], filter={"property": "Engine key", "rich_text": {"equals": key}},
                                      limit=1)), None):
            cs.skip(key, "idea already exists")
            continue
        passed = (v.get("Brand fit") or 0) >= s["brand_fit.threshold"]
        raw = cs.create("raw_content", f"raw:{key}", P.clean({
            "Title": P.title(v.get("Headline")), "Video URL": P.url(v.get("Source URL")),
            "Canonical URL": P.text(canon(v.get("Source URL") or "")), "Platform": P.text("Web"),
            "Content type": P.select("Article"), "Published": P.date(v.get("Published")),
            "Transcript": P.text(v.get("Summary")), "Transcript source": P.select("Article text"),
            "Discovered via": P.select("News"), "Added": P.date(now.date().isoformat()),
            "Status": P.select("Processed"), "Priority": P.select("Time-sensitive" if v.get("Time-sensitive") else "Normal")}),
            {"Title": (v.get("Headline") or "")[:40]})
        props = P.clean({
            "Idea": P.title(v.get("Headline")), "Status": P.select("Approved"),
            "Priority": P.select("Time-sensitive" if v.get("Time-sensitive") else "Normal"),
            "Origin": P.select("News"), "Engine key": P.text(key), "Pillar": P.text(v.get("Pillar")),
            "Why it works": P.text(v.get("Why it matters")), "Transformative angle": P.text(v.get("Suggested angle")),
            "Suggested hook": P.text(v.get("Suggested angle")), "Brand fit": P.number(v.get("Brand fit")),
            "Brand fit reason": P.text(v.get("Brand fit reason")), "Brand fit pass": P.checkbox(passed),
            "Format": P.select("Short"), "Engine notes": P.text(f"From News Candidates; expires {v.get('Expires') or 'never'}"),
            "News candidate": P.relation([page["id"]])})
        body = [P.heading("News"), *P.bullets([f"Source: {v.get('Source URL')}", f"Published: {v.get('Published')}",
                                               f"Summary: {v.get('Summary')}", f"Why it matters: {v.get('Why it matters')}",
                                               f"Angle: {v.get('Suggested angle')}"])]
        cs.create("idea_bank", key, lambda props=props, raw=raw: {**props, "Sources": P.relation([raw.result_id])},
                  {"Idea": (v.get("Headline") or "")[:40], "Status": "Approved", "Origin": "News"}, children=body)
