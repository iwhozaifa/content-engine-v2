from datetime import date

from services import settings as settings_mod
from services import slots
from services.props import values
from tests.fakes import FakeNotion
from tests.helpers import ids, run_cli

WEEK = "2026-11-02"  # a Monday
S = settings_mod.load()


def idea(n, title, status="Shortlisted", priority="Normal", origin="Creator scan", passed=True, fit=7, cluster=None):
    return n.add("ds-idea_bank", {
        "Idea": {"title": [{"text": {"content": title}}]}, "Status": {"select": {"name": status}},
        "Priority": {"select": {"name": priority}}, "Origin": {"select": {"name": origin}},
        "Brand fit pass": {"checkbox": passed}, "Fit score": {"number": fit}, "Brand fit": {"number": 8},
        "Cluster": {"rich_text": [{"text": {"content": cluster or title}}]}})


def plan_rows(n):
    return sorted((values(p) for p in n.pages.values() if p["parent_ds"] == "ds-content_plan"), key=lambda v: v["Date"])


def test_slot_and_post_date_maths():
    assert slots.next_week_start(date(2026, 10, 30)) == date(2026, 11, 2)  # Friday -> next Monday
    keys = [k for k, _, _ in slots.week_slots(date(2026, 11, 2), {"days": ["Mon", "Wed"], "slots_per_day": 2})]
    assert keys == ["slot:2026-11-02#1", "slot:2026-11-02#2", "slot:2026-11-04#1", "slot:2026-11-04#2"]
    when, why = slots.post_date(date(2026, 11, 4), date(2026, 10, 30), S)
    assert when == date(2026, 11, 7) and "slot date" in why
    assert slots.week_key(date(2026, 11, 2)) == "week:2026-W45"


def test_fill_order_lock_and_rerun_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(slots, "today", lambda s: date(2026, 10, 30))
    n = FakeNotion()
    creators = [idea(n, f"Creator idea {i}", fit=9 - i) for i in range(5)]
    news = idea(n, "News idea", status="Approved", origin="News")
    must = [idea(n, "Must A", status="New", priority="Must-Do", passed=False),
            idea(n, "Must B", status="Needs Input", priority="Must-Do")]
    failing = idea(n, "Fails brand fit", fit=10, passed=False)
    approved = idea(n, "Approved creator", status="Approved", fit=5)
    ids_ = ids(dbs=["weekly_plans"])
    code, out, _ = run_cli(["weekly-plan", "--week", WEEK, "--apply"], monkeypatch, tmp_path, n, ids_)
    assert code == 0, out
    rows = plan_rows(n)
    titles = [r["Video"] for r in rows]
    assert titles == ["Must A", "Must B", "News idea", "Approved creator", "Creator idea 0"]
    assert [r["Date"] for r in rows] == ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"]
    r0 = rows[0]
    assert r0["Status"] == "Topic Locked" and r0["Topic locked"] and r0["Approval"] == "Pending"
    assert r0["Suggested post date"] == "2026-11-05" and r0["Slot key"] == "slot:2026-11-02#1"
    assert r0["Weekly plan"] and r0["Idea"] == [must[0]["id"]]
    assert values(must[0])["Status"] == "Topic Locked" and values(failing)["Status"] == "Shortlisted"
    [plan] = [p for p in n.pages.values() if p["parent_ds"] == "ds-weekly_plans"]
    assert values(plan)["Filled"] == 5 and values(plan)["Engine key"] == "week:2026-W45"
    assert not any("script" in str(w).lower() and w[0] == "create" and "scripts" in w[1] for w in n.writes)

    n.writes.clear()
    code, out, _ = run_cli(["weekly-plan", "--week", WEEK, "--apply"], monkeypatch, tmp_path, n, ids_)
    assert code == 0, out
    assert n.writes == [] and "nothing to plan" in out


def test_must_do_overflow_waits_and_never_bumps_locked(tmp_path, monkeypatch):
    monkeypatch.setattr(slots, "today", lambda s: date(2026, 10, 30))
    n = FakeNotion()
    locked = n.add("ds-content_plan", {"Video": {"title": [{"text": {"content": "Locked already"}}]},
                                        "Date": {"date": {"start": "2026-11-02"}},
                                        "Slot key": {"rich_text": [{"text": {"content": "slot:2026-11-02#1"}}]},
                                        "Topic locked": {"checkbox": True}})
    for i in range(6):
        idea(n, f"Must {i}", priority="Must-Do")
    code, out, ctx = run_cli(["weekly-plan", "--week", WEEK, "--apply"], monkeypatch, tmp_path, n, ids(dbs=["weekly_plans"]))
    assert code == 0, out
    assert len(plan_rows(n)) == 5 and values(locked)["Video"] == "Locked already"
    assert "2 Must-Do idea(s) didn't fit" in out


def test_rejects_non_monday(tmp_path, monkeypatch):
    code, out, _ = run_cli(["weekly-plan", "--week", "2026-11-03"], monkeypatch, tmp_path, FakeNotion(), ids(dbs=["weekly_plans"]))
    assert code == 1 and "must be a Monday" in out
