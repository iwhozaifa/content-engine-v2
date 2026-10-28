from datetime import datetime, timedelta, timezone

import pytest

from services import settings as settings_mod
from services import sources, trend
from tests.fakes import FakeClaude, FakeNotion
from tests.helpers import run_cli

NOW = datetime.now(timezone.utc)
S = settings_mod.load()


def post(i, views, days_ago, likes=None, comments=0):
    vid = f"v{i}"
    return {"url": f"https://www.youtube.com/shorts/{vid}", "canonical_url": f"https://youtube.com/watch?v={vid}",
            "platform": "YouTube", "title": f"Post {i}", "content_type": "Short",
            "published": (NOW - timedelta(days=days_ago)).isoformat(), "views": views,
            "likes": likes if likes is not None else views // 20, "comments": comments, "shares": None,
            "description": "desc"}


def test_trend_math_matches_notion_formula():
    p = {"views": 40000, "likes": 2000, "comments": 100, "shares": 0,
         "published": (NOW - timedelta(days=2)).isoformat()}
    base = {"views": 10000, "velocity": 2000, "engagement": 5.0}
    sig = trend.signals(p, base, NOW, recurrence=3)
    assert sig["outlier"] == 4.0 and sig["velocity"] == 10.0 and sig["engagement"] == pytest.approx(1.1)
    # 100 * (0.35*min(4/4,1) + 0.25*min(10/4,1) + 0.2*min(1.1/3,1) + 0.2*min(3/5,1))
    assert trend.score(sig, S) == round(100 * (0.35 + 0.25 + 0.2 * 1.1 / 3 + 0.2 * 0.6))
    assert trend.is_candidate({"outlier": 2.1, "velocity": 0, "engagement": 0, "recurrence": 0}, 10, S)
    assert not trend.is_candidate({"outlier": 1, "velocity": 1, "engagement": 1, "recurrence": 0}, 30, S)


def test_baseline_is_median_of_last_n():
    posts = [post(i, v, d) for i, (v, d) in enumerate([(100, 1), (200, 2), (300, 3), (10_000, 40)])]
    b = trend.baseline(posts, NOW, 3)
    assert b["views"] == 200 and b["posts"] == 3


def test_iso_duration_and_shorts_url():
    assert sources.iso_duration("PT1M5S") == 65 and sources.iso_duration("PT2H") == 7200
    assert sources.youtube_shorts_url("https://www.youtube.com/@abc/videos") == "https://www.youtube.com/@abc/shorts"
    assert sources.channel_lookup("https://youtube.com/@abc") == {"forHandle": "@abc"}


def creator_row(n, name="Creator A", **extra):
    return n.add("ds-content_creators", {"Name": {"title": [{"text": {"content": name}}]},
                                         "State": {"select": {"name": "Active"}},
                                         "Profile URL": {"url": "https://www.youtube.com/@a"}, **extra})


def judge(*rich):
    return {"posts": [{"n": i, "rich_topic": r, "rich_reason": "why", "topic_label": f"topic {i}",
                       "evergreen": True, "substance": 7} for i, r in enumerate(rich)]}


def test_scan_writes_baseline_and_only_candidates_then_updates_metrics(tmp_path, monkeypatch):
    n = FakeNotion()
    c = creator_row(n)
    listing = [post(1, 50_000, 3), post(2, 30_000, 4)] + [post(i, 1000, 5 + i) for i in range(3, 25)]
    monkeypatch.setattr(sources, "list_posts", lambda url, k, s, **kw: (listing, "UC123"))
    code, out, _ = run_cli(["scan-creators", "--apply"], monkeypatch, tmp_path, n, runner=FakeClaude(judge(True, False)))
    assert code == 0, out
    from services.props import values
    cv = values(c)
    assert cv["Baseline views"] == 1000 and cv["YouTube channel ID"] == "UC123" and cv["Last scanned"]
    raws = [p for p in n.pages.values() if p["parent_ds"] == "ds-raw_content"]
    assert len(raws) == 2  # only the two outliers are stored
    by_title = {values(p)["Title"]: values(p) for p in raws}
    assert by_title["Post 1"]["Status"] == "New" and by_title["Post 1"]["Discovered via"] == "Auto scan"
    assert by_title["Post 2"]["Status"] == "Skipped" and by_title["Post 1"]["Engine trend score"] > 0
    for p in raws:  # link back, as Notion's relation would
        p["properties"]["Creator"] = {"type": "relation", "relation": [{"id": c["id"]}]}

    listing[0]["views"] = 90_000
    n.writes.clear()
    code, out, _ = run_cli(["scan-creators", "--apply"], monkeypatch, tmp_path, n, runner=FakeClaude(judge(True, False)))
    assert code == 0, out
    assert not [w for w in n.writes if w[0] == "create"]
    assert values([p for p in raws if values(p)["Title"] == "Post 1"][0])["Views"] == 90_000


def test_scan_failure_recorded_on_creator(tmp_path, monkeypatch):
    n = FakeNotion()
    c = creator_row(n)

    def boom(*a, **k):
        raise sources.SourceError("TikTok listing failed (Failed): try later")
    monkeypatch.setattr(sources, "list_posts", boom)
    code, out, _ = run_cli(["scan-creators", "--apply"], monkeypatch, tmp_path, n, runner=FakeClaude())
    from services.props import values
    assert code == 2 and "TikTok listing failed" in values(c)["Scan error"]
