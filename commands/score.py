"""Brand-fit (re)scoring for Idea Bank rows: Brand fit 0–10, reason, pass/fail, angle, Fit score."""
from services import brand
from services import props as P
from services.plan import ChangeSet

WRITES = True


def add_arguments(p):
    p.add_argument("ideas", nargs="*", help="idea titles (default: open ideas without a brand-fit reason)")
    p.add_argument("--rescore", action="store_true", help="also re-judge ideas that already have a brand-fit reason")


def run(ctx):
    ctx.load_notion_settings()
    cs = ChangeSet("score")
    open_ = brand.open_ideas(ctx, limit=500)
    wanted = [t.lower() for t in ctx.args.ideas]
    cap = ctx.args.limit or ctx.settings["caps.score"]
    done = 0
    rows = []
    for o in open_:
        if wanted and not any(w in (o["title"] or "").lower() for w in wanted):
            continue
        page = ctx.notion.get_page(o["id"])
        v = P.values(page)
        if v.get("Brand fit reason") and not ctx.args.rescore and not wanted:
            continue
        if done >= cap:
            ctx.log.warn(f"Stopped at {cap} ideas (caps.score). Re-run for the rest.")
            break
        done += 1
        try:
            bf, passed, prompt = brand.judge(ctx, candidate(v), (v.get("Origin") or "idea").lower(),
                                             brand.recent_text([x for x in open_ if x["id"] != o["id"]]))
        except Exception as e:  # noqa: BLE001 - record and continue
            ctx.log.error(f"{o['title']}: {e}")
            continue
        scores = {k: v.get(prop) for k, prop in brand.SCORE_PROPS.items()}
        scores["brand_fit"] = bf["brand_fit"]
        fit = brand.fit_score(scores, ctx.settings["fit_weights"])
        update = {**brand.brand_props(bf, passed), "Fit score": P.number(fit),
                  "Engine notes": P.text(brand.flags_text(bf)),
                  "Prompt versions": P.text(", ".join(filter(None, [v.get("Prompt versions"), prompt])))}
        status = v.get("Status")
        if status == "New" and fit is not None and fit >= ctx.settings["review.auto_shortlist"]:
            update["Status"] = P.select("Shortlisted")
            status = "Shortlisted"
        cs.update("idea_bank", f"score:{o['id']}", o["id"], update,
                  {"Idea": o["title"], "Brand fit": bf["brand_fit"], "pass": passed, "Fit": fit, "Status": status},
                  expected_edit=page.get("last_edited_time"))
        rows.append((o["title"], bf["brand_fit"], passed, fit, bf["reason"]))
    ctx.execute(cs)
    ctx.out(f"\n{'brand':>5} {'pass':>4} {'fit':>5}  idea · reason")
    for title, b, ok, fit, reason in sorted(rows, key=lambda r: -(r[3] or 0)):
        ctx.out(f"{b:>5g} {'✓' if ok else '✗':>4} {'' if fit is None else fit:>5}  {title} · {reason}")
    return cs


def candidate(v):
    lines = [f"Title: {v.get('Idea')}", f"Pillar: {v.get('Pillar') or ''}", f"Job: {v.get('Content job') or ''}",
             f"Why it works: {v.get('Why it works') or ''}", f"Hook: {v.get('Suggested hook') or ''}",
             f"Differentiation: {v.get('Differentiation note') or ''}", f"Audience pain: {v.get('Audience pain') or ''}",
             f"Priority: {v.get('Priority') or 'Normal'}"]
    return "\n".join(lines)
