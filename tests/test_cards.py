import copy

from services import cards
from services.props import values
from tests.fakes import FakeClaude, FakeNotion
from tests.helpers import ids, run_cli


def variation(label, family, angle, edited=None):
    return {"label": label, "angle": angle, "hook_family": family, "hook": f"{label} hook line",
            "hook_alts": [f"{label} alt hook 1", f"{label} alt hook 2"],
            "beats": [{"line": edited if (edited and i == 1) else f"{label} beat {i}", "alt_lines": [f"{label}{i} alt1", f"{label}{i} alt2"],
                       "broll": "screen recording", "on_screen": "3 steps"} for i in range(1, 5)],
            "cta": f"{label} follow for more", "cta_alt": f"{label} save this", "creator_input_required": []}


def script(a=("Curiosity", "workflow angle"), b=("Challenge", "mistake angle")):
    return {"variations": [variation("A", *a), variation("B", *b)]}


CAPTIONS = {"youtube": {"titles": ["t1", "t2", "t3"], "description": "d", "hashtags": ["#shorts"]},
            "instagram": {"caption": "c", "hashtags": ["#ai"]}, "tiktok": {"caption": "c", "hashtags": ["#ai"]},
            "thumbnails": [{"text": "x", "visual": "y"}] * 3}


def setup(n):
    idea = n.add("ds-idea_bank", {"Idea": {"title": [{"text": {"content": "Workflows beat tools"}}]},
                                   "Status": {"select": {"name": "Topic Locked"}},
                                   "Content job": {"rich_text": [{"text": {"content": "Reach"}}]}})
    slot = n.add("ds-content_plan", {"Video": {"title": [{"text": {"content": "Workflows beat tools"}}]},
                                      "Status": {"select": {"name": "Topic Locked"}}, "Topic locked": {"checkbox": True},
                                      "Date": {"date": {"start": "2026-11-02"}}, "Idea": {"relation": [{"id": idea["id"]}]}})
    return idea, slot


def card_pages(n):
    return [p for p in n.pages.values() if p["parent_ds"] == "ds-scripts"]


def extras_on(monkeypatch):
    from services import settings as st
    orig = st.load

    def load(*a, **k):
        s = orig(*a, **k)
        s.set("production.extras", True, "test")
        return s
    monkeypatch.setattr(st, "load", load)


def test_card_has_two_different_variations_captions_and_rerun_is_noop(tmp_path, monkeypatch):
    extras_on(monkeypatch)
    n = FakeNotion()
    idea, slot = setup(n)
    code, out, _ = run_cli(["generate-cards", "--locked", "--apply"], monkeypatch, tmp_path, n,
                           runner=FakeClaude(script(), CAPTIONS))
    assert code == 0, out
    [card] = card_pages(n)
    v = values(card)
    assert v["Status"] == "Card Ready" and v["Card key"] == f"card:{idea['id']}#v1" and v["Plan item"] == [slot["id"]]
    assert v["Hook A"] != v["Hook B"] and v["Similarity flag A"] == "Not checked"
    assert values(slot)["Status"] == "Card Ready"
    text = str(card["children"])
    assert "Publishing package" in text and "B-roll" in text and "Engine data" in text
    data = cards.read_data(n, card["id"])
    assert data["variations"][0]["hook_family"] == "Curiosity"

    slot["properties"]["Content card"] = {"type": "relation", "relation": [{"id": card["id"]}]}
    n.writes.clear()
    code, out, _ = run_cli(["generate-cards", "--locked", "--apply"], monkeypatch, tmp_path, n, runner=FakeClaude())
    assert code == 0 and n.writes == []


def test_same_hook_family_is_retried(tmp_path, monkeypatch):
    n = FakeNotion()
    setup(n)
    same = script(b=("Curiosity", "other angle"))
    claude = FakeClaude(same, script())
    code, out, _ = run_cli(["generate-cards", "--locked", "--apply"], monkeypatch, tmp_path, n, runner=claude)
    assert code == 0, out
    assert len(claude.calls) == 2 and "different hook family" in claude.calls[1]["input"]
    v = values(card_pages(n)[0])
    assert "B-roll" not in str(card_pages(n)[0]["children"])  # production extras off by default


def test_feedback_makes_v2_keeps_edited_line_and_supersedes_v1(tmp_path, monkeypatch):
    n = FakeNotion()
    idea, slot = setup(n)
    run_cli(["generate-cards", "--locked", "--apply"], monkeypatch, tmp_path, n, runner=FakeClaude(script()))
    [v1] = card_pages(n)
    # You edit beat A2 on the page, write feedback and set Needs revision.
    for b in n.blocks[v1["id"]]:
        if b["type"] == "table":
            for row in n.blocks[b["id"]]:
                cells = row["table_row"]["cells"]
                if cells[0][0]["text"]["content"] == "A2":
                    cells[1] = [{"type": "text", "text": {"content": "My own line, exactly"}, "plain_text": "My own line, exactly"}]
    n.update_page(v1["id"], {"Status": {"select": {"name": "Needs revision"}},
                             "Feedback": {"rich_text": [{"text": {"content": "more punchy"}}]}})
    claude = FakeClaude(script())  # the model "forgets" the edit; code must restore it
    code, out, _ = run_cli(["generate-cards", "--apply"], monkeypatch, tmp_path, n, runner=claude)
    assert code == 0, out
    assert "My own line, exactly" in claude.calls[0]["input"] and "more punchy" in claude.calls[0]["input"]
    v2 = [p for p in card_pages(n) if p["id"] != v1["id"]][0]
    assert values(v2)["Version"] == 2 and values(v2)["Previous version"] == [v1["id"]]
    assert values(v1)["Status"] == "Superseded" and values(v1)["Plan item"] == []
    data = cards.read_data(n, v2["id"])
    assert data["variations"][0]["beats"][1]["line"] == "My own line, exactly"


def test_choosing_a_variation_moves_to_script_chosen(tmp_path, monkeypatch):
    n = FakeNotion()
    idea, slot = setup(n)
    run_cli(["generate-cards", "--locked", "--apply"], monkeypatch, tmp_path, n, runner=FakeClaude(script()))
    [card] = card_pages(n)
    n.update_page(card["id"], {"Chosen variation": {"select": {"name": "B"}}})
    code, out, _ = run_cli(["generate-cards", "--apply"], monkeypatch, tmp_path, n, runner=FakeClaude())
    assert code == 0, out
    assert values(card)["Status"] == "Script Chosen"
    assert values(slot)["Status"] == "Script Chosen" and values(slot)["Final script"].startswith("B hook line")
    assert values(idea)["Status"] == "Scripted"


def test_settings_set_updates_one_cell(tmp_path, monkeypatch):
    n = FakeNotion()
    n._register("pg-settings", [{"type": "table", "table": {"table_width": 2, "children": [
        {"type": "table_row", "table_row": {"cells": [[{"plain_text": "Production extras (B-roll…)"}], [{"plain_text": "Off"}]]}}]}}])
    code, out, _ = run_cli(["settings-set", "Production extras", "On", "--apply"], monkeypatch, tmp_path, n)
    assert code == 0, out
    [(op, bid, body)] = n.writes
    assert body["table_row"]["cells"][1][0]["text"]["content"] == "On"
