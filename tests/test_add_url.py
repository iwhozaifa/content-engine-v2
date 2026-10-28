import pytest

from commands import add_url
from services import brand, ingest
from tests.fakes import FakeClaude, FakeNotion
from tests.helpers import ids, run_cli

URL = "https://www.youtube.com/shorts/abc123"
KEY = "https://youtube.com/watch?v=abc123"


def extract(title="Ship one AI workflow a week", dup_i=-1, conf=0.0, off=False):
    return {"topic": "AI workflows", "source_first_line": "Stop learning tools.", "hook_pattern": "contrarian",
            "outline": ["Problem", "Reframe", "Example"], "key_points": ["Workflows beat tools"],
            "idea_title": title, "pillar": "AI to Income", "content_job": "Reach", "topic_tags": ["AI workflows"],
            "cluster": "workflows over tools", "why_it_works": "Clear pain", "suggested_hook": "Tools don't pay.",
            "differentiation_note": "Builder view", "audience_pain": "Learning without earning", "key_claims": "",
            "needs_creator_proof": False,
            "scores": {"audience_fit": 8, "phase_fit": 8, "pillar_fit": 9, "trend_signal": 6, "novelty": 7,
                       "originality": 7, "scriptability": 8},
            "duplicate": {"i": dup_i, "confidence": conf}, "off_brand": off, "off_brand_reason": "off" if off else ""}


def fit(score=8, flags=()):
    return {"brand_fit": score, "reason": "On pillar, builder angle", "pillar": "AI to Income", "content_job": "Reach",
            "transformative_angle": "Show my own n8n build", "differentiation_note": "Real system",
            "red_flags": [{"flag": f, "severity": s} for f, s in flags], "needs_creator_proof": False}


@pytest.fixture
def fetched(monkeypatch):
    records = {}

    def fake_fetch(url, settings, **kw):
        return dict(records.get(url) or {"url": url, "canonical_url": ingest.canon(url), "platform": "YouTube",
                                         "fetch_status": "Failed", "fetch_error": "bot check", "hint": "log in"})
    monkeypatch.setattr(ingest, "fetch_url", fake_fetch)
    return records


def ok_record(url=URL, creator="Some Creator"):
    return {"url": url, "canonical_url": ingest.canon(url), "platform": "YouTube", "title": "Stop learning tools",
            "creator": creator, "content_type": "Short", "views": 1000, "likes": 50, "comments": 5,
            "transcript": "words " * 50, "transcript_source": "Captions", "language": "en", "fetch_status": "OK"}


def ideas(n):
    return [p for p in n.pages.values() if p["parent_ds"] == "ds-idea_bank"]


def raws(n):
    return [p for p in n.pages.values() if p["parent_ds"] == "ds-raw_content"]


def v(page):
    from services.props import values
    return values(page)


def test_fit_score_and_pass_rules():
    w = {"brand_fit": 20, "audience_fit": 20, "novelty": 10}
    assert brand.fit_score({"brand_fit": 8, "audience_fit": 6, "novelty": None}, w) == 7.0
    assert brand.passes(fit(7), 7) and not brand.passes(fit(6.9), 7)
    assert not brand.passes(fit(9, [("get-rich-quick", "block")]), 7)
    assert brand.passes(fit(9, [("minor", "warn")]), 7)


def test_dry_run_plans_rows_and_writes_nothing(tmp_path, monkeypatch, fetched):
    fetched[URL] = ok_record()
    n = FakeNotion()
    code, out, _ = run_cli(["add-url", URL], monkeypatch, tmp_path, n, runner=FakeClaude(extract(), fit()))
    assert code == 0, out
    assert n.writes == [] and not n.pages
    assert "creator:some creator" in out and "create 3" in out and "Shortlisted" in out


def test_apply_then_rerun_creates_nothing(tmp_path, monkeypatch, fetched):
    fetched[URL] = ok_record()
    n = FakeNotion()
    code, out, _ = run_cli(["add-url", URL, "--must-do", "--apply"], monkeypatch, tmp_path, n,
                           runner=FakeClaude(extract(), fit()))
    assert code == 0, out
    [idea], [raw] = ideas(n), raws(n)
    iv, rv = v(idea), v(raw)
    assert iv["Priority"] == "Must-Do" and iv["Engine key"] == f"url:{KEY}" and iv["Brand fit pass"] is True
    assert iv["Sources"] == [raw["id"]] and iv["Fit score"] == pytest.approx(7.5)
    assert rv["Canonical URL"] == KEY and rv["Status"] == "Processed" and rv["Creator"]
    assert idea["children"] and "transcript" not in str(idea["children"]).lower()  # outline only, no transcript
    raw["properties"]["Idea"] = {"type": "relation", "relation": [{"id": idea["id"]}]}

    n.writes.clear()
    code, out, _ = run_cli(["add-url", URL, "--apply"], monkeypatch, tmp_path, n, runner=FakeClaude())
    assert code == 0, out
    assert n.writes == [] and "Already in" in out


def test_failed_fetch_needs_input_then_resume_from_pasted_transcript(tmp_path, monkeypatch, fetched):
    n = FakeNotion()
    code, out, _ = run_cli(["add-url", URL, "--must-do", "--apply"], monkeypatch, tmp_path, n, runner=FakeClaude())
    assert code == 0, out
    [idea], [raw] = ideas(n), raws(n)
    assert v(idea)["Status"] == "Needs Input" and v(idea)["Priority"] == "Must-Do"
    assert v(raw)["Status"] == "Needs Input" and v(raw)["Fetch status"] == "Failed"

    # You paste the transcript into the Raw Content row; the next --from-notion run picks it up.
    raw["properties"]["Transcript"] = {"type": "rich_text", "rich_text": [{"plain_text": "pasted words " * 30}]}
    code, out, _ = run_cli(["add-url", "--from-notion", "--apply"], monkeypatch, tmp_path, n,
                           runner=FakeClaude(extract(), fit()))
    assert code == 0, out
    assert len(ideas(n)) == 1 and len(raws(n)) == 1          # updated in place, no duplicates
    assert v(ideas(n)[0])["Status"] == "Shortlisted" and v(ideas(n)[0])["Priority"] == "Must-Do"
    assert v(raws(n)[0])["Status"] == "Processed" and v(raws(n)[0])["Transcript source"] == "Pasted"


def test_existing_url_with_must_do_upgrades_priority(tmp_path, monkeypatch, fetched):
    n = FakeNotion()
    idea = n.add("ds-idea_bank", {"Idea": {"title": [{"text": {"content": "Old"}}]},
                                   "Priority": {"select": {"name": "Normal"}}, "Status": {"select": {"name": "New"}}})
    n.add("ds-raw_content", {"Canonical URL": {"rich_text": [{"text": {"content": KEY}}]},
                             "Status": {"select": {"name": "Processed"}}, "Idea": {"relation": [{"id": idea["id"]}]}})
    code, out, _ = run_cli(["add-url", URL, "--must-do", "--apply"], monkeypatch, tmp_path, n, runner=FakeClaude())
    assert code == 0, out
    assert v(idea)["Priority"] == "Must-Do" and len(ideas(n)) == 1


def test_high_confidence_duplicate_merges_into_existing_idea(tmp_path, monkeypatch, fetched):
    fetched[URL] = ok_record()
    n = FakeNotion()
    old = n.add("ds-idea_bank", {"Idea": {"title": [{"text": {"content": "Workflows beat tools"}}]},
                                  "Status": {"select": {"name": "Shortlisted"}}, "Sources": {"relation": []}})
    code, out, _ = run_cli(["add-url", URL, "--apply"], monkeypatch, tmp_path, n,
                           runner=FakeClaude(extract(dup_i=0, conf=0.9), fit()))
    assert code == 0, out
    assert len(ideas(n)) == 1 and "Merged" in out
    [raw] = raws(n)
    assert v(raw)["Status"] == "Duplicate" and v(old)["Sources"] == [raw["id"]]


def test_off_brand_normal_is_rejected_but_must_do_is_kept(tmp_path, monkeypatch, fetched):
    fetched[URL] = ok_record()
    n = FakeNotion()
    run_cli(["add-url", URL, "--apply"], monkeypatch, tmp_path, n, runner=FakeClaude(extract(off=True), fit(2)))
    assert v(ideas(n)[0])["Status"] == "Rejected" and v(ideas(n)[0])["Brand fit pass"] is False
    url2 = "https://www.youtube.com/shorts/zzz999"
    fetched[url2] = ok_record(url2)
    run_cli(["add-url", url2, "--must-do", "--apply"], monkeypatch, tmp_path, n,
            runner=FakeClaude(extract("Other", off=True), fit(2)))
    must = [p for p in ideas(n) if v(p)["Priority"] == "Must-Do"][0]
    assert v(must)["Status"] != "Rejected"


def test_score_command_updates_brand_fit_once(tmp_path, monkeypatch):
    n = FakeNotion()
    idea = n.add("ds-idea_bank", {"Idea": {"title": [{"text": {"content": "Legacy idea"}}]},
                                   "Status": {"select": {"name": "New"}}, "Audience fit": {"number": 8},
                                   "Novelty": {"number": 8}})
    code, out, _ = run_cli(["score", "--apply"], monkeypatch, tmp_path, n, runner=FakeClaude(fit(9)))
    assert code == 0, out
    assert v(idea)["Brand fit"] == 9 and v(idea)["Brand fit pass"] is True and v(idea)["Status"] == "Shortlisted"
    n.writes.clear()
    code, out, _ = run_cli(["score", "--apply"], monkeypatch, tmp_path, n, runner=FakeClaude())
    assert code == 0 and n.writes == []


def test_needs_input_placeholder_is_archived_when_merged(tmp_path, monkeypatch, fetched):
    n = FakeNotion()
    old = n.add("ds-idea_bank", {"Idea": {"title": [{"text": {"content": "Existing"}}]},
                                  "Status": {"select": {"name": "Shortlisted"}}})
    run_cli(["add-url", URL, "--apply"], monkeypatch, tmp_path, n, runner=FakeClaude())
    [raw] = raws(n)
    raw["properties"]["Transcript"] = {"type": "rich_text", "rich_text": [{"plain_text": "same topic " * 30}]}
    code, out, _ = run_cli(["add-url", "--from-notion", "--apply"], monkeypatch, tmp_path, n,
                           runner=FakeClaude(extract(dup_i=0, conf=0.9), fit()))
    assert code == 0, out
    placeholder = [p for p in ideas(n) if p["id"] != old["id"]][0]
    assert v(placeholder)["Status"] == "Archived" and v(placeholder)["Duplicate of"] == [old["id"]]
    assert v(old)["Sources"] == [raw["id"]]
