from datetime import date

from services import slots
from services.props import values
from tests.fakes import FakeNotion
from tests.helpers import ids, run_cli


def row(n, title, d, approval, status="Card Ready", key=None, **extra):
    return n.add("ds-content_plan", {"Video": {"title": [{"text": {"content": title}}]}, "Date": {"date": {"start": d}},
                                     "Approval": {"select": {"name": approval}}, "Status": {"select": {"name": status}},
                                     "Slot key": {"rich_text": [{"text": {"content": key or f"slot:{d}#1"}}]},
                                     "Topic locked": {"checkbox": True}, **extra})


def test_postpone_moves_to_first_open_slot_next_week_and_keeps_card(tmp_path, monkeypatch):
    monkeypatch.setattr(slots, "today", lambda s: date(2026, 10, 28))
    n = FakeNotion()
    p = row(n, "Postponed one", "2026-11-04", "Postponed", **{"Content card": {"relation": [{"id": "card1"}]}})
    row(n, "Busy Monday", "2026-11-09", "Pending")  # first slot of the following week is taken
    code, out, _ = run_cli(["reschedule", "--apply"], monkeypatch, tmp_path, n, ids(dbs=["weekly_plans"]))
    assert code == 0, out
    v = values(p)
    assert v["Date"] == "2026-11-10" and v["Slot key"] == "slot:2026-11-10#1" and v["Original date"] == "2026-11-04"
    assert v["Approval"] == "Pending" and "2026-11-04 → 2026-11-10" in v["Date history"]
    assert v["Content card"] == ["card1"] and v["Suggested post date"] == "2026-11-13"
    n.writes.clear()
    code, out, _ = run_cli(["reschedule", "--apply"], monkeypatch, tmp_path, n, ids(dbs=["weekly_plans"]))
    assert code == 0 and n.writes == []


def test_two_postponed_get_different_slots(tmp_path, monkeypatch):
    monkeypatch.setattr(slots, "today", lambda s: date(2026, 10, 28))
    n = FakeNotion()
    a = row(n, "A", "2026-11-04", "Postponed")
    b = row(n, "B", "2026-11-05", "Postponed")
    run_cli(["reschedule", "--apply"], monkeypatch, tmp_path, n, ids(dbs=["weekly_plans"]))
    assert values(a)["Date"] != values(b)["Date"]


def test_ready_to_post_only_when_approved_and_chosen(tmp_path, monkeypatch):
    n = FakeNotion()
    ok = row(n, "Approved + chosen", "2026-11-04", "Approved", status="Script Chosen")
    waiting = row(n, "Approved, no choice", "2026-11-05", "Approved", status="Card Ready")
    pending = row(n, "Chosen, not approved", "2026-11-06", "Pending", status="Script Chosen")
    code, out, _ = run_cli(["reschedule", "--apply"], monkeypatch, tmp_path, n, ids(dbs=["weekly_plans"]))
    assert code == 0, out
    assert values(ok)["Status"] == "Ready to Post"
    assert values(waiting)["Status"] == "Card Ready" and values(pending)["Status"] == "Script Chosen"
    assert "waiting for a chosen variation" in out


def test_rejected_releases_slot_for_weekly_plan(tmp_path, monkeypatch):
    n = FakeNotion()
    idea = n.add("ds-idea_bank", {"Status": {"select": {"name": "Topic Locked"}}})
    r = row(n, "Rejected one", "2026-11-04", "Rejected", **{"Idea": {"relation": [{"id": idea["id"]}]}})
    code, out, _ = run_cli(["reschedule", "--apply"], monkeypatch, tmp_path, n, ids(dbs=["weekly_plans"]))
    assert code == 0, out
    assert values(r)["Topic locked"] is False and values(r)["Slot key"] == "" and values(idea)["Status"] == "Rejected"
    from commands.weekly_plan import week_openings
    from types import SimpleNamespace
    from services import settings as st
    ctx = SimpleNamespace(notion=n, settings=st.load())
    _, open_ = week_openings(ctx, {"content_plan": "ds-content_plan"}, date(2026, 11, 2))
    assert any(d == date(2026, 11, 4) for _, d, _ in open_)
