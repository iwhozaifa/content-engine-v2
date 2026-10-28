"""Scan Active creators: baselines, Engine trend score, rich topics -> Raw Content (Status New = idea queue)."""
import json
from datetime import datetime, timedelta, timezone

from services import brand, sources, trend
from services import props as P
from services.plan import ChangeSet

WRITES = True


def add_arguments(p):
    p.add_argument("--creator", action="append", default=[], help="only creators whose name contains this (repeatable)")
    p.add_argument("--state", default="Active", help="creator State to scan (default Active; e.g. Suggested to preview)")


def run(ctx):
    ctx.load_notion_settings()
    s = ctx.settings
    cs = ChangeSet("scan-creators")
    now = datetime.now(timezone.utc)
    ds = {k: v["data_source"] for k, v in ctx.ids["databases"].items()}
    creators = list(ctx.notion.query(ds["content_creators"], filter={"property": "State", "select": {"equals": ctx.args.state}},
                                     sorts=[{"property": "Last scanned", "direction": "ascending"}]))
    if ctx.args.creator:
        want = [c.lower() for c in ctx.args.creator]
        creators = [c for c in creators if any(w in (P.values(c).get("Name") or "").lower() for w in want)]
    cap = ctx.args.limit or s["scan.max_creators_per_run"]
    if not creators:
        ctx.out(f"No creators with State = {ctx.args.state}. Set State = Active on the Content Creators rows to scan.")
    since = now - timedelta(days=s["scan.lookback_days"])
    labels = existing_labels(ctx, ds["raw_content"], since)
    n_list = max(s["trend.baseline_posts"], s["scan.max_posts_per_creator"])
    scanned = []
    for page in creators[:cap]:
        c = P.values(page)
        try:
            scanned.append(scan_one(ctx, page, c, n_list, now, since, labels))
        except Exception as e:  # noqa: BLE001 - record on the creator row and continue (rule 8)
            msg = f"{type(e).__name__}: {e}"[:1800]
            ctx.log.error(f"{c.get('Name')}: {msg}")
            cs.update("content_creators", f"creator:{page['id']}", page["id"],
                      {"Scan error": P.text(f"{now:%Y-%m-%d %H:%M} {msg}"), "Last scanned": P.date(now.isoformat())},
                      {"Name": c.get("Name"), "Scan error": msg[:60]}, expected_edit=page.get("last_edited_time"))

    # Recurrence: how many creators cover each topic label in the lookback window.
    covering = {}
    for label, who in labels.items():
        covering.setdefault(label, set()).update(who)
    for item in scanned:
        for post in item["candidates"]:
            if post.get("topic_label"):
                covering.setdefault(post["topic_label"].lower(), set()).add(item["page"]["id"])
    rows = []
    for item in scanned:
        write_creator(cs, item, now)
        for post in item["posts_in_window"]:
            label = (post.get("topic_label") or "").lower()
            post["signals"]["recurrence"] = len(covering.get(label, ())) if label else 0
            post["score"] = trend.score(post["signals"], s)
            write_post(cs, item, post, now)
            if post.get("judged"):
                rows.append((post["score"], post.get("rich_topic"), item["name"], post.get("title") or "", post.get("rich_reason") or ""))
    ctx.execute(cs)
    ctx.out(f"\n{'trend':>5} {'rich':>4}  creator · post · why")
    for score, rich, name, title, why in sorted(rows, key=lambda r: -r[0]):
        ctx.out(f"{score:>5} {'✓' if rich else '·':>4}  {name} · {title[:50]} · {why[:60]}")
    return cs


def existing_labels(ctx, raw_ds, since):
    """{topic label (lower): {creator ids}} from Raw Content rows added in the lookback window."""
    flt = {"and": [{"property": "Topic label", "rich_text": {"is_not_empty": True}},
                   {"property": "Added", "date": {"on_or_after": since.date().isoformat()}}]}
    out = {}
    for page in ctx.notion.query(raw_ds, filter=flt):
        v = P.values(page)
        out.setdefault(v["Topic label"].lower(), set()).update(v.get("Creator") or ["?"])
    return out


def scan_one(ctx, page, c, n_list, now, since, labels):
    s = ctx.settings
    posts, channel_id, errors = [], None, []
    for url in sources.profile_urls(c):
        try:
            found, cid = sources.list_posts(url, n_list, s)
            posts += found
            channel_id = channel_id or cid
        except sources.SourceError as e:
            errors.append(str(e))
    if not posts:
        raise sources.SourceError("; ".join(errors) or "no profile URL on the creator row")
    if c.get("Lock baseline") and c.get("Baseline views"):
        base = {"views": c["Baseline views"], "velocity": c.get("Baseline velocity") or 0,
                "engagement": c.get("Baseline engagement %") or 0, "posts": c.get("Baseline posts"), "locked": True}
    else:
        base = trend.baseline(posts, now, s["trend.baseline_posts"])
    min_age = timedelta(hours=s["scan.min_post_age_hours"])
    window = [p for p in posts if (t := trend.parse_time(p.get("published"))) and since <= t <= now - min_age]
    for p in window:
        p["signals"] = trend.signals(p, base, now)
        p["score"] = trend.score(p["signals"], s)
    candidates = sorted((p for p in window if trend.is_candidate(p["signals"], p["score"], s)),
                        key=lambda p: -p["score"])[: s["scan.max_posts_per_creator"]]
    if candidates:
        listing = [{"n": i, "title": p.get("title"), "description": (p.get("description") or "")[:400],
                    "views": p.get("views"), "trend_score": p["score"], **p["signals"]} for i, p in enumerate(candidates)]
        out = ctx.claude.run("trend_judge", {"brand": brand.profile(ctx),
                                             "labels": ", ".join(sorted(labels)) or "(none yet)",
                                             "posts": json.dumps(listing, ensure_ascii=False)}).output
        for j in out["posts"]:
            if 0 <= j["n"] < len(candidates):
                candidates[j["n"]].update(judged=True, **{k: j[k] for k in ("rich_topic", "rich_reason", "topic_label")})
    return {"page": page, "name": c.get("Name"), "values": c, "base": base, "channel_id": channel_id,
            "posts_in_window": window, "candidates": candidates, "errors": errors,
            "existing": existing_rows(ctx, page["id"])}


def existing_rows(ctx, creator_id):
    flt = {"property": "Creator", "relation": {"contains": creator_id}}
    return {P.values(p).get("Canonical URL"): p for p in
            ctx.notion.query(ctx.ids["databases"]["raw_content"]["data_source"], filter=flt)}


def write_creator(cs, item, now):
    base, c = item["base"], item["values"]
    props = {"Last scanned": P.date(now.isoformat()), "Scan error": P.text("; ".join(item["errors"])[:1800])}
    if base and not base.get("locked"):
        props.update({"Baseline views": P.number(base["views"]), "Baseline velocity": P.number(base["velocity"]),
                      "Baseline engagement %": P.number(base["engagement"]), "Baseline posts": P.number(base["posts"]),
                      "Baseline updated": P.date(now.date().isoformat())})
    if item["channel_id"] and not c.get("YouTube channel ID"):
        props["YouTube channel ID"] = P.text(item["channel_id"])
    page = item["page"]
    cs.update("content_creators", f"creator:{page['id']}", page["id"], props,
              {"Name": item["name"], "baseline views": base and base["views"], "posts": len(item["posts_in_window"])},
              expected_edit=page.get("last_edited_time"))


def write_post(cs, item, post, now):
    key = post["canonical_url"]
    existing = item["existing"].get(key)
    metrics = {"Views": P.number(post.get("views")), "Likes": P.number(post.get("likes")),
               "Comments": P.number(post.get("comments")), "Shares": P.number(post.get("shares")),
               "Metrics captured at": P.date(now.isoformat()), "Engine trend score": P.number(post["score"]),
               "Recurrence": P.number(post["signals"]["recurrence"])}
    judged = {}
    if post.get("judged"):
        judged = {"Rich topic": P.checkbox(post["rich_topic"]), "Rich reason": P.text(post["rich_reason"]),
                  "Topic label": P.text(post["topic_label"])}
    summary = {"Title": (post.get("title") or "")[:30], "trend": post["score"], "rich": post.get("rich_topic")}
    if existing:
        cs.update("raw_content", f"raw:{key}", existing["id"], P.clean({**metrics, **judged}),
                  summary, expected_edit=existing.get("last_edited_time"))
    elif post.get("judged"):  # only trend candidates are stored; rich ones queue up for add-url --from-notion
        cs.create("raw_content", f"raw:{key}", P.clean({
            "Title": P.title(post.get("title") or key), "Video URL": P.url(post.get("url")),
            "Canonical URL": P.text(key), "Platform": P.text(post.get("platform")),
            "Content type": P.select(post.get("content_type")), "Published": P.date(post.get("published")),
            **metrics, **judged, "Creator": P.relation([item["page"]["id"]]),
            "Discovered via": P.select("Auto scan"), "Added": P.date(now.date().isoformat()),
            "Status": P.select("New" if post["rich_topic"] else "Skipped"), "Priority": P.select("Normal")}), summary)
