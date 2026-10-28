"""Turn URLs into Raw Content + Idea Bank rows (Must-Do, dedupe, brand fit, Needs Input on failure)."""
import json
from datetime import datetime, timezone
from pathlib import Path

from services import brand, ingest
from services import props as P
from services.plan import ChangeSet
from tools.engine import canon

WRITES = True
MAX_WORDS = 12000
DONE = ("Processed", "Duplicate", "Skipped")
ORIGINS = {"Auto scan": "Creator scan", "News": "News", "Manual": "Manual URL"}


def add_arguments(p):
    p.add_argument("urls", nargs="*", help="links to add")
    p.add_argument("--must-do", action="store_true", help="Priority = Must-Do (guaranteed a slot in the next weekly plan)")
    p.add_argument("--transcript-file", help="pasted transcript for the last URL (wins over a fetched one)")
    p.add_argument("--from-notion", action="store_true",
                   help="also process Raw Content rows with Status New, and Needs Input rows that now have a Transcript")


def run(ctx):
    ctx.load_notion_settings()
    items = []
    priority = "Must-Do" if ctx.args.must_do else "Normal"
    pasted = Path(ctx.args.transcript_file).read_text(encoding="utf-8") if ctx.args.transcript_file else None
    for i, url in enumerate(ctx.args.urls):
        items.append({"url": url, "priority": priority, "raw": None,
                      "pasted": pasted if i == len(ctx.args.urls) - 1 else None})
    if ctx.args.from_notion:
        items += notion_items(ctx)
    cap = ctx.args.limit or ctx.settings["caps.add_url"]
    if len(items) > cap:
        ctx.log.warn(f"{len(items)} links; handling the first {cap} (caps.add_url). Re-run for the rest.")
    run_ = Run(ctx)
    for item in items[:cap]:
        try:
            run_.process(**item)
        except Exception as e:  # noqa: BLE001 - record and continue (rule 8)
            ctx.log.error(f"{item['url']}: {type(e).__name__}: {e}")
            run_.results.append((item["url"], "Error", "", "", str(e)[:80]))
    ctx.execute(run_.cs)
    ctx.out(f"\n{'result':<12} {'fit':>5} {'brand':>6}  url · note")
    for url, result, fit, bfit, note in run_.results:
        ctx.out(f"{result:<12} {'' if fit is None else fit:>5} {bfit:>6}  {url} · {note}")
    return run_.cs


def notion_items(ctx):
    ds = ctx.ids["databases"]["raw_content"]["data_source"]
    flt = {"or": [{"property": "Status", "select": {"equals": "New"}},
                  {"and": [{"property": "Status", "select": {"equals": "Needs Input"}},
                           {"property": "Transcript", "rich_text": {"is_not_empty": True}}]}]}
    out = []
    for page in ctx.notion.query(ds, filter=flt):
        v = P.values(page)
        url = v.get("Video URL") or v.get("Canonical URL")
        if not url:
            ctx.log.warn(f"Raw Content '{v.get('Title')}' has no Video URL; skipped")
            continue
        pasted = v.get("Transcript") if v.get("Status") == "Needs Input" else None
        out.append({"url": url, "priority": v.get("Priority") or "Normal", "raw": page, "pasted": pasted})
    return out


class Run:
    def __init__(self, ctx):
        self.ctx = ctx
        self.cs = ChangeSet("add-url")
        self.results = []
        self.open = brand.open_ideas(ctx)
        self.creators = {}
        self.seen = set()
        self.ds = {k: v["data_source"] for k, v in ctx.ids["databases"].items()}

    # -- lookups -----------------------------------------------------------------
    def find(self, db, prop, kind, value):
        flt = {"property": prop, kind: {"equals": value}}
        return next(iter(self.ctx.notion.query(self.ds[db], filter=flt, limit=1)), None)

    def creator(self, rec):
        """Existing Content Creators row id, or a planned create (returns a callable resolving to the id)."""
        name = (rec.get("creator") or "").strip()
        if not name:
            return None
        if name not in self.creators:
            page = self.find("content_creators", "Name", "title", name)
            if page:
                self.creators[name] = page["id"]
            else:
                platform = {"YouTube": "YouTube", "Instagram": "Instagram", "TikTok": "TikTok"}.get(rec["platform"])
                c = self.cs.create("content_creators", f"creator:{name.lower()}", P.clean({
                    "Name": P.title(name), "Platforms": P.multi([platform]), "Profile URL": P.url(rec.get("creator_url")),
                    "State": P.select("Suggested"), "Suggested by": P.select("Claude"),
                    "Suggestion reason": P.text(f"Source of a manual URL: {rec.get('title', '')[:120]}")}),
                    {"Name": name, "State": "Suggested"})
                self.creators[name] = lambda c=c: c.result_id
        return self.creators[name]

    # -- one URL -------------------------------------------------------------------
    def process(self, url, priority, raw, pasted):
        ctx, cs = self.ctx, self.cs
        key = canon(url if "://" in url else "https://" + url)
        if key in self.seen:
            return
        self.seen.add(key)
        if raw is None:
            raw = self.find("raw_content", "Canonical URL", "rich_text", key)
        if raw is not None and P.values(raw).get("Status") in DONE:
            return self.already(url, key, raw, priority)

        if pasted and raw is not None:
            rec = self.record_from_row(raw, url, key)
        else:
            rec = ingest.fetch_url(url, ctx.settings)
            if rec.get("canonical_url") and rec["canonical_url"] != key:  # share links resolve after fetching
                key = rec["canonical_url"]
                again = self.find("raw_content", "Canonical URL", "rich_text", key)
                if again is not None and P.values(again).get("Status") in DONE:
                    return self.already(url, key, again, priority)
                raw = raw or again
        if pasted:
            rec.update(transcript=pasted, transcript_source="Pasted")
            if rec.get("fetch_status") not in ("OK", "Partial"):
                rec["fetch_status"] = "Partial"
        origin = ORIGINS.get(P.values(raw).get("Discovered via") if raw is not None else None, "Manual URL")
        rich = bool(raw is not None and P.values(raw).get("Rich topic"))
        idea_key = f"url:{key}"
        existing_idea = self.find("idea_bank", "Engine key", "rich_text", idea_key)

        if not pasted and ingest.needs_input(rec):
            return self.needs_input(url, key, rec, raw, existing_idea, priority, idea_key)

        source = self.source_text(rec)
        listing = [{"i": o["i"], "title": o["title"], "cluster": o["cluster"], "tags": o["tags"]} for o in self.open]
        ext = ctx.claude.run("idea_extract", {"brand": brand.profile(ctx), "source": source,
                                              "open_ideas": json.dumps(listing, ensure_ascii=False) if listing else "(none)"})
        x = ext.output
        candidate = "\n".join([f"Title: {x['idea_title']}", f"Pillar: {x['pillar']}", f"Job: {x['content_job']}",
                               f"Hook: {x['suggested_hook']}", "Outline: " + " / ".join(x["outline"]),
                               "Key points: " + " / ".join(x["key_points"]),
                               f"Differentiation: {x['differentiation_note']}",
                               f"Source: {rec.get('platform')} · {rec.get('creator') or ''} · {rec.get('title', '')}"])
        bf, passed, bf_prompt = brand.judge(ctx, candidate, "manual URL", brand.recent_text(self.open))
        scores = {**x["scores"], "brand_fit": bf["brand_fit"]}
        fit = brand.fit_score(scores, ctx.settings["fit_weights"])

        dup = self.open[x["duplicate"]["i"]] if 0 <= x["duplicate"]["i"] < len(self.open) else None
        conf = x["duplicate"]["confidence"] if dup else 0
        if dup and dup["id"] and conf >= ctx.settings["review.merge_confidence"] and dup["key"] != idea_key:
            return self.merge(url, key, rec, raw, dup, priority, conf, existing_idea)

        if x["off_brand"] and priority != "Must-Do":
            status, note = "Rejected", x["off_brand_reason"]
        elif fit is not None and fit >= ctx.settings["review.auto_shortlist"]:
            status, note = "Shortlisted", ""
        else:
            status, note = "New", ""
        if existing_idea and P.values(existing_idea).get("Status") not in ("Needs Input", "New"):
            status = P.values(existing_idea).get("Status")  # never move an idea you already progressed

        raw_change = self.write_raw(key, rec, raw, priority, "Processed")
        raw_id = self.resolver(raw_change, raw)
        idea_props = {
            "Idea": P.title(x["idea_title"]), "Status": P.select(status), "Priority": P.select(priority),
            "Origin": P.select(origin), "Engine key": P.text(idea_key), "Pillar": P.text(x["pillar"]),
            "Rich topic": P.checkbox(rich),
            "Content job": P.text(x["content_job"]), "Topic tags": P.multi(x["topic_tags"]),
            "Cluster": P.text(x["cluster"]), "Why it works": P.text(x["why_it_works"]),
            "Suggested hook": P.text(x["suggested_hook"]), "Differentiation note": P.text(x["differentiation_note"]),
            "Audience pain": P.text(x["audience_pain"]), "Key claims": P.text(x["key_claims"]),
            "Needs creator proof": P.checkbox(x["needs_creator_proof"] or bf["needs_creator_proof"]),
            "Hook pattern": P.text(x["hook_pattern"]), "Format": P.select("Short"),
            "Fit score": P.number(fit), **brand.brand_props(bf, passed),
            **{prop: P.number(scores[k]) for k, prop in brand.SCORE_PROPS.items()},
            "Possible duplicate": P.checkbox(bool(dup) and conf >= ctx.settings["review.flag_confidence"]),
            "Rejection reason": P.text(note) if status == "Rejected" else P.text(""),
            "Engine notes": P.text(brand.flags_text(bf)), "Prompt versions": P.text(f"{ext.prompt}, {bf_prompt}"),
        }
        if dup and dup["id"] and conf >= ctx.settings["review.flag_confidence"]:
            idea_props["Duplicate of"] = P.relation([dup["id"]])
        body = idea_body(url, rec, x, bf, passed)
        summary = {"Idea": x["idea_title"], "Status": status, "Priority": priority, "Fit": fit,
                   "Brand fit": bf["brand_fit"], "pass": passed}
        if existing_idea:
            cs.update("idea_bank", idea_key, existing_idea["id"],
                      lambda: {**P.clean(idea_props), "Sources": P.relation([raw_id()])}, summary,
                      expected_edit=existing_idea.get("last_edited_time"))
        else:
            cs.create("idea_bank", idea_key, lambda: {**P.clean(idea_props), "Sources": P.relation([raw_id()])},
                      summary, children=body)
        self.open.insert(0, {"i": len(self.open), "id": existing_idea["id"] if existing_idea else None,
                             "title": x["idea_title"], "cluster": x["cluster"], "tags": x["topic_tags"],
                             "status": status, "key": idea_key, "priority": priority})
        for i, o in enumerate(self.open):
            o["i"] = i
        self.results.append((url, status, fit, f"{bf['brand_fit']:g}{'✓' if passed else '✗'}", bf["reason"][:60]))

    # -- outcomes ------------------------------------------------------------------
    def already(self, url, key, raw, priority):
        v = P.values(raw)
        idea_ids = v.get("Idea") or []
        if priority == "Must-Do" and idea_ids:
            idea = self.ctx.notion.get_page(idea_ids[0])
            if P.values(idea).get("Priority") != "Must-Do":
                self.cs.update("idea_bank", f"url:{key}#priority", idea["id"], {"Priority": P.select("Must-Do")},
                               {"Priority": "Must-Do"}, expected_edit=idea.get("last_edited_time"),
                               reason="already in Idea Bank; upgraded to Must-Do")
                self.results.append((url, "Must-Do ↑", "", "", "already in Idea Bank; priority upgraded"))
                return
        self.cs.skip(key, f"already in Raw Content ({v.get('Status')})")
        self.results.append((url, "Already in", "", "", "already in Idea Bank"))

    def needs_input(self, url, key, rec, raw, existing_idea, priority, idea_key):
        raw_change = self.write_raw(key, rec, raw, priority, "Needs Input")
        raw_id = self.resolver(raw_change, raw)
        hint = rec.get("hint") or "Fetch failed. Paste the transcript into the Raw Content Transcript field."
        if existing_idea is None and priority == "Must-Do":
            props = {"Idea": P.title(f"[Needs Input] {rec.get('title') or url}"[:200]), "Status": P.select("Needs Input"),
                     "Priority": P.select(priority), "Origin": P.select("Manual URL"), "Engine key": P.text(idea_key),
                     "Engine notes": P.text(f"{rec.get('fetch_status')}: {hint} Then run `cli.py add-url --from-notion --apply`.")}
            self.cs.create("idea_bank", idea_key, lambda: {**props, "Sources": P.relation([raw_id()])},
                           {"Status": "Needs Input", "Priority": priority})
        self.results.append((url, "Needs Input", "", "", hint[:80]))

    def merge(self, url, key, rec, raw, dup, priority, conf, placeholder=None):
        raw_change = self.write_raw(key, rec, raw, priority, "Duplicate", idea_id=dup["id"])
        raw_id = self.resolver(raw_change, raw)
        page = self.ctx.notion.get_page(dup["id"])
        sources = P.values(page).get("Sources") or []
        upd = lambda: {"Sources": P.relation(sources + [raw_id()]),  # noqa: E731
                       **({"Priority": P.select("Must-Do")} if priority == "Must-Do" else {})}
        self.cs.update("idea_bank", f"merge:{key}", dup["id"], upd, {"Sources": f"+{key}", "into": dup["title"]},
                       expected_edit=page.get("last_edited_time"), reason=f"same idea (confidence {conf:.2f})")
        if placeholder is not None and P.values(placeholder).get("Status") == "Needs Input":
            self.cs.update("idea_bank", f"url:{key}#merged", placeholder["id"],
                           {"Status": P.select("Archived"), "Duplicate of": P.relation([dup["id"]]),
                            "Engine notes": P.text(f"Merged into '{dup['title']}' once the transcript arrived.")},
                           {"Status": "Archived", "into": dup["title"]}, expected_edit=placeholder.get("last_edited_time"))
        self.results.append((url, "Merged", "", "", f"into '{dup['title']}' ({conf:.2f})"))

    # -- writers -------------------------------------------------------------------
    def write_raw(self, key, rec, raw, priority, status, idea_id=None):
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        creator = self.creator(rec)
        props = {
            "Title": P.title(rec.get("title") or key), "Video URL": P.url(rec.get("url")),
            "Canonical URL": P.text(key), "Platform": P.text(rec.get("platform")),
            "Content type": P.select(rec.get("content_type")), "Published": P.date(rec.get("published")),
            "Views": P.number(rec.get("views")), "Likes": P.number(rec.get("likes")),
            "Comments": P.number(rec.get("comments")), "Shares": P.number(rec.get("shares")),
            "Metrics captured at": P.date(now if rec.get("views") is not None else None),
            "Transcript": P.text(rec.get("transcript")), "Transcript source": P.select(rec.get("transcript_source")),
            "Language": P.select(ingest.language_name(rec.get("language"))),
            "Fetch status": P.select(rec.get("fetch_status")), "Fetch error": P.text(rec.get("fetch_error")),
            "Status": P.select(status), "Priority": P.select(priority),
        }
        summary = {"Title": (rec.get("title") or key)[:40], "Status": status, "Fetch": rec.get("fetch_status")}

        def build():
            out = P.clean(props)
            if creator:
                out["Creator"] = P.relation([creator() if callable(creator) else creator])
            if idea_id:
                out["Idea"] = P.relation([idea_id])
            return out
        if raw is not None:
            return self.cs.update("raw_content", f"raw:{key}", raw["id"], build, summary,
                                  expected_edit=raw.get("last_edited_time"))
        return self.cs.create("raw_content", f"raw:{key}", lambda: {**build(), "Discovered via": P.select("Manual"),
                                                                     "Added": P.date(now[:10])}, summary)

    @staticmethod
    def resolver(change, raw):
        return lambda: raw["id"] if raw is not None else change.result_id

    @staticmethod
    def record_from_row(raw, url, key):
        v = P.values(raw)
        return {"url": url, "canonical_url": key, "platform": v.get("Platform"), "title": v.get("Title"),
                "views": v.get("Views"), "likes": v.get("Likes"), "comments": v.get("Comments"),
                "fetch_status": v.get("Fetch status")}

    @staticmethod
    def source_text(rec):
        words = (rec.get("transcript") or "").split()
        transcript = " ".join(words[:MAX_WORDS]) + (" […truncated]" if len(words) > MAX_WORDS else "")
        meta = {k: rec.get(k) for k in ("title", "platform", "creator", "published", "content_type", "duration_s",
                                         "views", "likes", "comments", "shares") if rec.get(k) is not None}
        return (json.dumps(meta, ensure_ascii=False) + "\n\nDescription:\n" + (rec.get("description") or "")[:1500]
                + "\n\nTranscript (" + (rec.get("transcript_source") or "None") + "):\n" + (transcript or "(none)"))


def idea_body(url, rec, x, bf, passed):
    return [P.heading("Source analysis"),
            *P.bullets([f"Source: {url}", f"Creator: {rec.get('creator') or '—'} · {rec.get('platform')}",
                        f"Source first line (reference only, never reuse): {x['source_first_line']}",
                        f"Hook pattern: {x['hook_pattern']}", f"Topic: {x['topic']}"]),
            P.heading("Outline", 3), *P.bullets(x["outline"]),
            P.heading("Key points", 3), *P.bullets(x["key_points"]),
            P.heading("Brand fit"),
            P.para(f"{bf['brand_fit']:g}/10 · {'pass' if passed else 'fail'} · {bf['reason']}"),
            P.para(f"Transformative angle: {bf['transformative_angle']}"),
            *P.bullets([f"{f['severity']}: {f['flag']}" for f in bf["red_flags"]])]
