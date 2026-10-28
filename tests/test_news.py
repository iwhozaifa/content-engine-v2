from datetime import datetime, timedelta, timezone

from services import news
from services.props import values
from tests.fakes import FakeClaude, FakeNotion
from tests.helpers import ids, run_cli

NOW = datetime.now(timezone.utc)
RSS = f"""<?xml version="1.0"?><rss><channel>
<item><title>New model ships</title><link>https://example.com/a?utm_source=x</link>
<pubDate>{(NOW - timedelta(hours=3)).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate><description>&lt;p&gt;Big &amp; fast&lt;/p&gt;</description></item>
<item><title>Old news</title><link>https://example.com/old</link><pubDate>Mon, 01 Jan 2024 00:00:00 +0000</pubDate></item>
</channel></rss>"""
ATOM = f"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Agent tooling</title>
<link rel="alternate" href="https://blog.example.com/b"/><updated>{(NOW - timedelta(hours=5)).isoformat()}</updated>
<summary>Agents</summary></entry></feed>"""


def test_parse_rss_and_atom():
    a = news.parse(RSS, "Ex")
    assert a[0]["headline"] == "New model ships" and a[0]["summary"] == "Big & fast" and a[0]["published"]
    b = news.parse(ATOM, "Blog")
    assert b[0]["url"] == "https://blog.example.com/b" and b[0]["headline"] == "Agent tooling"


def keep(*ns):
    return {"keep": [{"n": n, "why_it_matters": "why", "brand_fit": 8, "reason": "r", "suggested_angle": "angle",
                      "pillar": "AI Leverage", "urgency": "High", "time_sensitive": True, "expires_in_days": 5} for n in ns]}


def setup(monkeypatch):
    monkeypatch.setattr(news, "load_feeds", lambda: [{"name": "Ex", "url": "u1"}, {"name": "Blog", "url": "u2"}])
    monkeypatch.setattr(news, "fetch_all", lambda feeds: (news.parse(RSS, "Ex") + news.parse(ATOM, "Blog"), []))


def cands(n):
    return [p for p in n.pages.values() if p["parent_ds"] == "ds-news_candidates"]


def test_radar_twice_same_day_no_duplicates(tmp_path, monkeypatch):
    setup(monkeypatch)
    n, idmap = FakeNotion(), ids(dbs=["news_candidates"])
    claude = FakeClaude(keep(0))
    code, out, _ = run_cli(["news-radar", "--apply"], monkeypatch, tmp_path, n, idmap, runner=claude)
    assert code == 0, out
    [c] = cands(n)
    v = values(c)
    assert v["Approval"] == "Pending" and v["Engine key"] == "news:https://example.com/a" and v["Time-sensitive"]
    assert "Old news" not in claude.calls[0]["input"]  # outside the lookback window
    code, out, _ = run_cli(["news-radar", "--apply"], monkeypatch, tmp_path, n, idmap, runner=FakeClaude(keep()))
    assert code == 0, out
    assert len(cands(n)) == 1


def test_daily_cap_stops_judging(tmp_path, monkeypatch):
    setup(monkeypatch)
    n, idmap = FakeNotion(), ids(dbs=["news_candidates"])
    for i in range(5):
        n.add("ds-news_candidates", {"Found at": {"date": {"start": NOW.isoformat()}}})
    claude = FakeClaude()
    code, out, _ = run_cli(["news-radar", "--apply"], monkeypatch, tmp_path, n, idmap, runner=claude)
    assert code == 0 and "Daily cap reached" in out and not claude.calls


def test_approved_becomes_idea_rejected_never(tmp_path, monkeypatch):
    n, idmap = FakeNotion(), ids(dbs=["news_candidates"])
    ok = n.add("ds-news_candidates", {"Headline": {"title": [{"text": {"content": "Approved one"}}]},
                                       "Approval": {"select": {"name": "Approved"}}, "Brand fit": {"number": 8},
                                       "Source URL": {"url": "https://example.com/a"}, "Time-sensitive": {"checkbox": True},
                                       "Engine key": {"rich_text": [{"text": {"content": "news:https://example.com/a"}}]}})
    n.add("ds-news_candidates", {"Headline": {"title": [{"text": {"content": "Rejected one"}}]},
                                 "Approval": {"select": {"name": "Rejected"}}, "Brand fit": {"number": 9}})
    code, out, _ = run_cli(["news-radar", "--no-fetch", "--apply"], monkeypatch, tmp_path, n, idmap, runner=FakeClaude())
    assert code == 0, out
    ideas = [values(p) for p in n.pages.values() if p["parent_ds"] == "ds-idea_bank"]
    assert len(ideas) == 1 and ideas[0]["Idea"] == "Approved one"
    i = ideas[0]
    assert i["Origin"] == "News" and i["Status"] == "Approved" and i["Priority"] == "Time-sensitive" and i["Brand fit pass"]
    assert i["Sources"] and i["News candidate"] == [ok["id"]]
    ok["properties"]["Idea"] = {"type": "relation", "relation": [{"id": "x"}]}  # Notion's dual relation
    n.writes.clear()
    run_cli(["news-radar", "--no-fetch", "--apply"], monkeypatch, tmp_path, n, idmap, runner=FakeClaude())
    assert n.writes == []
