"""Content cards for locked topics: Variations A and B, captions, titles, thumbnails, originality check.
Also makes the next version of cards marked Needs revision (your edited lines kept word for word) and moves
cards with a Chosen variation to Script Chosen."""
import json
import re

from services import brand, cards
from services import props as P
from services.plan import ChangeSet

WRITES = True


def add_arguments(p):
    p.add_argument("targets", nargs="*", help="Content Plan titles (parts) to make a card for")
    p.add_argument("--locked", action="store_true", help="every Topic Locked slot without a card")


def run(ctx):
    ctx.load_notion_settings()
    cs = ChangeSet(ctx.args.command)
    g = Generator(ctx, cs)
    budget = ctx.args.limit or ctx.settings["caps.generate_cards"]
    for kind, items in (("revise", g.revisions()), ("new", g.locked_slots())):
        for item in items:
            if budget <= 0:
                ctx.log.warn(f"Stopped at caps.generate_cards; re-run for the rest.")
                break
            try:
                done = g.revise(item) if kind == "revise" else g.new_card(item)
                budget -= 1 if done else 0
            except Exception as e:  # noqa: BLE001 - record and continue (rule 8)
                ctx.log.error(f"{kind} {item.get('title', item['id'])}: {type(e).__name__}: {e}")
    g.sync_choices()
    ctx.execute(cs)
    for line in g.report:
        ctx.out(line)
    return cs


class Generator:
    def __init__(self, ctx, cs):
        self.ctx, self.cs, self.s = ctx, cs, ctx.settings
        self.ds = {k: v["data_source"] for k, v in ctx.ids["databases"].items()}
        self.report = []
        self._voice = None
        self.extras = bool(self.s.get("production.extras"))
        lo, hi = self.s["script.length_s"]
        self.seconds = round((lo + hi) / 2)

    # -- inputs ------------------------------------------------------------------------
    @property
    def voice(self):
        if self._voice is None:
            self._voice = self.ctx.notion.page_text(self.ctx.ids["pages"]["voice_guide"])
        return self._voice

    def hooks(self):
        rows = [P.values(p) for p in self.ctx.notion.query(self.ds["hook_library"])]
        return "\n".join(f"- {r.get('Family') or r.get('Hook')}: e.g. {r.get('Example') or ''}"
                         for r in rows if r.get("Status") in (None, "Active")) or "(none: choose any two families)"

    def ctas(self, job):
        rows = [P.values(p) for p in self.ctx.notion.query(self.ds["cta_bank"])]
        fit = [r for r in rows if not job or not r.get("Content job") or job.lower() in r["Content job"].lower()]
        return "\n".join(f"- {r.get('Exact wording') or r.get('CTA')} ({r.get('Content job')}; {r.get('Notes') or ''})"
                         for r in fit or rows) or "(none: write a soft follow/save CTA)"

    def idea_text(self, idea_id):
        v = P.values(self.ctx.notion.get_page(idea_id))
        body = self.ctx.notion.page_text(idea_id)
        body = "\n".join(l for l in body.splitlines() if "source first line" not in l.lower())  # never reuse their wording
        fields = {k: v.get(k) for k in ("Idea", "Pillar", "Content job", "Why it works", "Suggested hook",
                                         "Differentiation note", "Transformative angle", "Audience pain", "Key claims",
                                         "Needs creator proof", "Engine notes") if v.get(k)}
        return v, json.dumps(fields, ensure_ascii=False, indent=1) + "\n\n" + body[:6000]

    def source_text(self, idea):
        out = []
        for sid in (idea.get("Sources") or [])[:2]:
            try:
                out.append(P.values(self.ctx.notion.get_page(sid)).get("Transcript") or "")
            except Exception:  # noqa: BLE001
                pass
        return "\n".join(out)

    def find_card(self, key):
        return next(iter(self.ctx.notion.query(self.ds["scripts"], filter={"property": "Card key", "rich_text": {"equals": key}},
                                               limit=1)), None)

    # -- what to do -------------------------------------------------------------------
    def locked_slots(self):
        if not (self.ctx.args.locked or self.ctx.args.targets):
            return []
        flt = {"and": [{"property": "Topic locked", "checkbox": {"equals": True}},
                       {"property": "Status", "select": {"equals": "Topic Locked"}}]}
        rows = []
        for page in self.ctx.notion.query(self.ds["content_plan"], filter=flt, sorts=[{"property": "Date", "direction": "ascending"}]):
            v = P.values(page)
            if self.ctx.args.targets and not any(t.lower() in (v.get("Video") or "").lower() for t in self.ctx.args.targets):
                continue
            if v.get("Content card"):
                continue
            rows.append({"id": page["id"], "title": v.get("Video"), "page": page, "values": v})
        return rows

    def revisions(self):
        flt = {"property": "Status", "select": {"equals": "Needs revision"}}
        out = []
        for page in self.ctx.notion.query(self.ds["scripts"], filter=flt):
            v = P.values(page)
            if v.get("Card key"):  # only engine cards; old /write scripts stay with /revise
                out.append({"id": page["id"], "title": v.get("Script"), "page": page, "values": v})
        return out

    # -- generation -------------------------------------------------------------------
    def write(self, idea_text, job, revision=""):
        inputs = {"voice": self.voice, "brand": brand.profile(self.ctx), "idea": idea_text, "hooks": self.hooks(),
                  "ctas": self.ctas(job), "seconds": str(self.seconds),
                  "words": str(round(self.seconds * self.s["script.words_per_second"])),
                  "extras": "ON" if self.extras else "OFF", "revision": revision}
        r = self.ctx.claude.run("script_variations", inputs)
        a, b = sorted(r.output["variations"], key=lambda v: v["label"])
        if a["hook_family"].strip().lower() == b["hook_family"].strip().lower() or a["angle"].strip().lower() == b["angle"].strip().lower():
            inputs["revision"] = revision + ("\n\nYour last answer gave A and B the same hook family or angle. "
                                             "Make B use a different hook family AND a different angle.")
            r = self.ctx.claude.run("script_variations", inputs)
            a, b = sorted(r.output["variations"], key=lambda v: v["label"])
            if a["hook_family"].strip().lower() == b["hook_family"].strip().lower():
                self.ctx.log.warn("Variations A and B still share a hook family; review the card")
        return [a, b], r.prompt

    def package(self, variations, source, topic):
        sims, notes, prompts = {}, [], []
        for v in variations:
            sims[v["label"]] = cards.check(v, source, self.s)
            if source and sims[v["label"]]["flag"] in ("Review", "Too close"):
                j = self.ctx.claude.run("similarity_judge", {"script": cards.all_text(v), "source": source[:8000],
                                                             "runs": json.dumps(sims[v["label"]].get("runs", [])[:10])})
                sims[v["label"]]["flag"] = max(sims[v["label"]]["flag"], j.output["verdict"],
                                               key=["OK", "Review", "Too close"].index)
                notes += [f"{v['label']}: {x['type']} · {x['line']}" for x in j.output["lifted"]]
                notes += [f"{v['label']} hint: {h}" for h in j.output["rewrite_hints"]]
                prompts.append(j.prompt)
        captions = None
        if self.extras:
            c = self.ctx.claude.run("captions", {"voice": self.voice[:3000], "topic": topic,
                                                 "a": cards.ready_to_read(variations[0]), "b": cards.ready_to_read(variations[1]),
                                                 "rules": json.dumps(self.s["platforms"], ensure_ascii=False)})
            captions = c.output
            prompts.append(c.prompt)
        return sims, notes, captions, prompts

    def card_props(self, key, title, idea_id, plan_id, version, variations, sims, prompts, prev=None, platforms=None):
        a, b = variations
        wps = self.s["script.words_per_second"]
        words = cards.word_count(cards.ready_to_read(a))
        return P.clean({
            "Script": P.title(f"{title} · card v{version}"), "Card key": P.text(key), "Idea": P.relation([idea_id]),
            "Plan item": P.relation([plan_id]) if plan_id else P.relation([]), "Version": P.number(version),
            "Status": P.select("Card Ready"), "Format": P.select("Short"),
            "Platform": P.multi(platforms or ["Instagram", "TikTok", "YouTube Shorts"]),
            "Target length (s)": P.number(self.seconds), "Hook A": P.text(a["hook"]), "Hook B": P.text(b["hook"]),
            "Angle A": P.text(a["angle"]), "Angle B": P.text(b["angle"]),
            "Similarity flag A": P.select(sims["A"]["flag"]), "Similarity flag B": P.select(sims["B"]["flag"]),
            "Similarity flag": P.select(max(sims["A"]["flag"], sims["B"]["flag"], key=FLAGS.index)),
            "Similarity %": P.number(max((s["similarity_pct"] or 0) for s in sims.values())),
            "Longest shared run": P.number(max((s["longest_run"] or 0) for s in sims.values())),
            "Word count": P.number(words), "Est. seconds": P.number(round(words / wps)),
            "Hook alternates": P.text("\n".join(f"{v['label']}: {h}" for v in variations for h in [v["hook"], *v["hook_alts"]])),
            "Prompt versions": P.text(", ".join(prompts)),
            "Voice guide version": P.text(version_of(self.voice)), "DNA version": P.text(version_of(brand.profile(self.ctx))),
            **({"Previous version": P.relation([prev])} if prev else {})})

    def new_card(self, slot):
        v = slot["values"]
        idea_id = (v.get("Idea") or [None])[0]
        if not idea_id:
            self.cs.skip(slot["id"], "slot has no Idea")
            return False
        key = f"card:{idea_id}#v1"
        if self.find_card(key):
            self.cs.skip(key, "card already exists")
            return False
        idea, text = self.idea_text(idea_id)
        if idea.get("Status") == "Needs Input":
            self.cs.skip(key, "idea still Needs Input (paste the transcript first)")
            self.report.append(f"waiting  {slot['title']} · needs a transcript")
            return False
        variations, prompt = self.write(text, idea.get("Content job"))
        sims, notes, captions, extra = self.package(variations, self.source_text(idea), idea.get("Idea"))
        title = idea.get("Idea") or slot["title"]
        data = {"key": key, "variations": variations, "captions": captions}
        props = self.card_props(key, title, idea_id, slot["id"], 1, variations, sims, [prompt, *extra],
                                platforms=v.get("Platforms"))
        self.cs.create("scripts", key, props, {"Card": title[:30], "A": variations[0]["hook_family"],
                                               "B": variations[1]["hook_family"], "flags": f"{sims['A']['flag']}/{sims['B']['flag']}"},
                       children=cards.page_blocks(title, variations, sims, captions, notes, data, self.extras,
                                                  self.s["script.words_per_second"]))
        self.cs.update("content_plan", f"plan:{slot['id']}#card", slot["id"], {"Status": P.select("Card Ready")},
                       {"Status": "Card Ready"}, expected_edit=slot["page"].get("last_edited_time"))
        self.report.append(f"card v1  {title} · A {variations[0]['hook_family']} / B {variations[1]['hook_family']}"
                           f" · originality {sims['A']['flag']}/{sims['B']['flag']}")
        return True

    def revise(self, card):
        v = card["values"]
        version = int(v.get("Version") or 1)
        idea_id = (v.get("Idea") or [None])[0]
        key = re.sub(r"#v\d+$", "", v["Card key"]) + f"#v{version + 1}"
        if self.find_card(key):
            self.cs.skip(key, "next version already exists")
            return False
        data = cards.read_data(self.ctx.notion, card["id"]) or {}
        edits = cards.edited_lines(self.ctx.notion, card["id"], data) if data else {}
        feedback = (v.get("Feedback") or "").strip() + "\n" + feedback_section(self.ctx.notion.page_text(card["id"]))
        idea, text = self.idea_text(idea_id)
        revision = ("\n## Revision\nThis is version " + str(version + 1) + ". Apply the feedback exactly; change only what it touches.\n"
                    f"Feedback:\n{feedback.strip() or '(none given: tighten and improve)'}\n"
                    f"Previous version:\n{json.dumps(data.get('variations', []), ensure_ascii=False)[:8000]}\n"
                    f"Locked lines (the creator edited these; keep them word for word in the same place):\n"
                    f"{json.dumps(edits, ensure_ascii=False)}")
        variations, prompt = self.write(text, idea.get("Content job"), revision)
        apply_edits(variations, edits)
        sims, notes, captions, extra = self.package(variations, self.source_text(idea), idea.get("Idea"))
        plan_id = (v.get("Plan item") or [None])[0]
        title = idea.get("Idea") or v.get("Script")
        data = {"key": key, "variations": variations, "captions": captions}
        props = self.card_props(key, title, idea_id, plan_id, version + 1, variations, sims, [prompt, *extra],
                                prev=card["id"], platforms=v.get("Platform"))
        self.cs.create("scripts", key, props, {"Card": title[:30], "version": version + 1, "kept edits": len(edits)},
                       children=cards.page_blocks(title, variations, sims, captions, notes, data, self.extras,
                                                  self.s["script.words_per_second"]))
        self.cs.update("scripts", f"{v['Card key']}#superseded", card["id"],
                       {"Status": P.select("Superseded"), "Plan item": P.relation([])}, {"Status": "Superseded"},
                       expected_edit=card["page"].get("last_edited_time"))
        if plan_id:
            self.cs.update("content_plan", f"plan:{plan_id}#v{version + 1}", plan_id, {"Status": P.select("Card Ready")},
                           {"Status": "Card Ready"})
        self.report.append(f"card v{version + 1}  {title} · kept {len(edits)} edited line(s)")
        return True

    def sync_choices(self):
        """Cards where you picked A or B: card → Script Chosen, slot → Script Chosen + Final script, idea → Scripted."""
        flt = {"and": [{"property": "Status", "select": {"equals": "Card Ready"}},
                       {"property": "Chosen variation", "select": {"is_not_empty": True}}]}
        for page in self.ctx.notion.query(self.ds["scripts"], filter=flt):
            v = P.values(page)
            label = v["Chosen variation"]
            final = chosen_text(self.ctx.notion.page_table_rows(page["id"]), label)
            self.cs.update("scripts", f"{v.get('Card key')}#chosen", page["id"], {"Status": P.select("Script Chosen")},
                           {"Card": (v.get("Script") or "")[:30], "Chosen": label}, expected_edit=page.get("last_edited_time"))
            for plan_id in v.get("Plan item") or []:
                self.cs.update("content_plan", f"plan:{plan_id}#chosen", plan_id,
                               {"Status": P.select("Script Chosen"), "Final script": P.text(final)}, {"Status": "Script Chosen"})
            for idea_id in v.get("Idea") or []:
                self.cs.update("idea_bank", f"idea:{idea_id}#scripted", idea_id, {"Status": P.select("Scripted")},
                               {"Status": "Scripted"})
            self.report.append(f"chosen   {v.get('Script')} · variation {label}")


FLAGS = ["Not checked", "OK", "Review", "Too close"]


def version_of(text):
    m = re.search(r"Version:\s*([\d.]+)", text or "")
    return m.group(1) if m else ""


def feedback_section(text):
    m = re.search(r"Feedback for next version\n(.*?)(?:\nEngine data|\Z)", text or "", re.S)
    body = (m.group(1) if m else "").strip()
    return "" if body.startswith("(Write notes here") else body


def apply_edits(variations, edits):
    """Put your edited lines back exactly, whatever the model returned (rule 4)."""
    by = {v["label"]: v for v in variations}
    for label, line in edits.items():
        m = re.fullmatch(r"([AB])(?:-H1 ✅|-CTA|(\d+))", label)
        if not m or m.group(1) not in by:
            continue
        v = by[m.group(1)]
        if label.endswith("H1 ✅"):
            v["hook"] = line
        elif label.endswith("-CTA"):
            v["cta"] = line
        else:
            i = int(m.group(2)) - 1
            if i < len(v["beats"]):
                v["beats"][i]["line"] = line


def chosen_text(rows, label):
    """Ready-to-read text of the chosen variation, from the page as it is now (your edits included)."""
    lines = {r[0]: r[1] for r in rows if len(r) >= 2}
    out = [lines.get(f"{label}-H1 ✅", "")]
    i = 1
    while f"{label}{i}" in lines:
        out.append(lines[f"{label}{i}"])
        i += 1
    out.append(lines.get(f"{label}-CTA", ""))
    return "\n".join(x for x in out if x)
