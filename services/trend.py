"""Trend math, computed in code (the LLM never does it). Mirrors the Raw Content formulas, but the
weights, caps and thresholds come from settings (Engine Settings → Trend scoring).

  days live   = max(hours since published / 24, 0.5)
  engagement% = (likes + 2·comments + 3·shares) / views · 100
  outlier     = views / baseline views
  velocity    = (views / days live) / baseline velocity
  engagement  = engagement% / baseline engagement%
  recurrence  = number of creators covering the same topic
  score       = 100 · Σ weight · min(signal / cap, 1)
"""
from datetime import datetime, timezone
from statistics import median


def parse_time(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    value = str(value)
    if len(value) == 10:
        value += "T00:00:00+00:00"
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def days_live(published, now):
    p = parse_time(published)
    if not p:
        return None
    return max((now - p).total_seconds() / 86400, 0.5)


def engagement_pct(post):
    views = post.get("views") or 0
    if not views:
        return 0.0
    return ((post.get("likes") or 0) + 2 * (post.get("comments") or 0) + 3 * (post.get("shares") or 0)) / views * 100


def velocity(post, now):
    d = days_live(post.get("published"), now)
    return (post.get("views") or 0) / d if d else 0.0


def baseline(posts, now, n):
    """Median views / velocity / engagement% over the last n posts with views."""
    recent = [p for p in sorted(posts, key=lambda p: str(p.get("published") or ""), reverse=True)
              if p.get("views") is not None][:n]
    if not recent:
        return None
    return {"views": round(median(p["views"] for p in recent)),
            "velocity": round(median(velocity(p, now) for p in recent), 1),
            "engagement": round(median(engagement_pct(p) for p in recent), 2),
            "posts": len(recent)}


def signals(post, base, now, recurrence=0):
    return {"outlier": round((post.get("views") or 0) / max(base["views"] or 0, 1), 2),
            "velocity": round(velocity(post, now) / max(base["velocity"] or 0, 1), 2),
            "engagement": round(engagement_pct(post) / max(base["engagement"] or 0, 0.1), 2),
            "recurrence": recurrence}


ORDER = ("outlier", "velocity", "engagement", "recurrence")


def score(sig, settings):
    weights, caps = settings["trend.weights"], settings["trend.caps"]
    return round(100 * sum(w * min(sig[k] / c, 1) for k, w, c in zip(ORDER, weights, caps)))


def is_candidate(sig, value, settings):
    """Trend score ≥ candidate score, or any single signal at its threshold."""
    return value >= settings["trend.candidate_score"] or any(
        sig[k] >= t for k, t in zip(ORDER, settings["trend.thresholds"]))
