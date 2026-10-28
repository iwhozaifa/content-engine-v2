"""Brand profile, brand-fit judging and the weighted fit score. Pass/fail is decided here in code,
never by the model: pass = brand_fit >= threshold and no blocking red flag."""
from pathlib import Path

from services import props as P

ROOT = Path(__file__).resolve().parent.parent
SCORE_PROPS = {"brand_fit": "Brand fit", "audience_fit": "Audience fit", "phase_fit": "Phase fit",
               "pillar_fit": "Pillar fit", "trend_signal": "Trend signal", "novelty": "Novelty",
               "originality": "Originality", "scriptability": "Scriptability"}
OPEN_STATUSES = ["New", "Needs Input", "Shortlisted", "Approved", "Topic Locked", "Scripting", "Scripted"]


def profile(ctx):
    """The brand profile: the Notion DNA page (newest), falling back to the local DNA file."""
    cached = getattr(ctx, "_brand_profile", None)
    if cached:
        return cached
    text = ""
    try:
        text = ctx.notion.page_text(ctx.ids["pages"]["brand_profile"])
    except Exception as e:  # noqa: BLE001 - fall back to the file copy
        ctx.log.warn(f"Brand Profile page unreadable ({e}); using {ctx.settings['general.dna_file']}")
    if len(text) < 200:
        text = (ROOT / ctx.settings["general.dna_file"]).read_text(encoding="utf-8")
    ctx._brand_profile = text
    return text


def fit_score(scores, weights):
    """Weighted average of the scores that exist, using the DNA weights."""
    total = sum(w for k, w in weights.items() if scores.get(k) is not None)
    if not total:
        return None
    return round(sum(scores[k] * w for k, w in weights.items() if scores.get(k) is not None) / total, 1)


def passes(result, threshold):
    return result["brand_fit"] >= threshold and not any(f["severity"] == "block" for f in result["red_flags"])


def judge(ctx, candidate, kind, recent):
    """Run brand_fit.v1 and return (result dict, pass bool, prompt id)."""
    r = ctx.claude.run("brand_fit", {"brand": profile(ctx), "recent": recent or "(none)",
                                     "kind": kind, "candidate": candidate})
    return r.output, passes(r.output, ctx.settings["brand_fit.threshold"]), r.prompt


def flags_text(result):
    return "; ".join(f"{f['severity']}: {f['flag']}" for f in result.get("red_flags", []))


def brand_props(result, passed):
    return {"Brand fit": P.number(result["brand_fit"]),
            "Brand fit reason": P.text(result["reason"]),
            "Brand fit pass": P.checkbox(passed),
            "Transformative angle": P.text(result["transformative_angle"])}


def open_ideas(ctx, limit=150):
    """[{i, id, title, cluster, tags, status, key}] of open ideas (most recently edited first)."""
    flt = {"or": [{"property": "Status", "select": {"equals": s}} for s in OPEN_STATUSES]}
    out = []
    pages = ctx.notion.query(ctx.ids["databases"]["idea_bank"]["data_source"], filter=flt,
                             sorts=[{"timestamp": "last_edited_time", "direction": "descending"}], limit=limit)
    for i, page in enumerate(pages):
        v = P.values(page)
        out.append({"i": i, "id": page["id"], "title": v.get("Idea"), "cluster": v.get("Cluster"),
                    "tags": v.get("Topic tags"), "status": v.get("Status"), "key": v.get("Engine key"),
                    "priority": v.get("Priority")})
    return out


def recent_text(ideas, limit=60):
    return "\n".join(f"- {o['title']} [{o['cluster'] or ''}]" for o in ideas[:limit]) or "(none)"
