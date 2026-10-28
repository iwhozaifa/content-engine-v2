from services.plan import ChangeSet
from tests.fakes import FakeNotion

IDS = {"databases": {"idea_bank": {"data_source": "ds-idea"}}}


def test_render_and_counts():
    cs = ChangeSet("demo")
    cs.create("idea_bank", "url:https://x", {}, {"Idea": "A"})
    cs.skip("url:https://y", "already in Idea Bank")
    assert cs.counts() == {"create": 1, "update": 0, "schema": 0, "skip": 1}
    text = cs.render()
    assert "url:https://x" in text and "already in Idea Bank" in text


def test_empty_set_says_nothing_to_change():
    assert "nothing to change" in ChangeSet("demo").render()


def test_apply_skips_conflicts_and_continues_after_failure():
    n = FakeNotion()
    page = n.create_page("ds-idea", {"Status": "New"})
    n.writes.clear()
    cs = ChangeSet("demo")
    stale = cs.update("idea_bank", "k1", page["id"], {"Status": "Shortlisted"}, {}, expected_edit="old")
    broken = cs.update("idea_bank", "k2", "missing-page", {}, {})
    created = cs.create("idea_bank", "k3", {"Idea": "B"}, {})
    errors = cs.apply(n, IDS)
    assert stale.status == "conflict" and broken.status == "failed" and created.status == "done"
    assert len(errors) == 2
    assert [w[0] for w in n.writes] == ["create"]


def test_after_callback_gets_created_id():
    n, seen = FakeNotion(), []
    cs = ChangeSet("demo")
    cs.create("idea_bank", "k", {}, {}, after=lambda c: seen.append(c.result_id))
    cs.apply(n, IDS)
    assert seen and seen[0] in n.pages


def test_save_writes_json(tmp_path):
    cs = ChangeSet("demo")
    cs.create("idea_bank", "k", {}, {"a": 1})
    path = cs.save(tmp_path)
    assert path.exists() and '"command": "demo"' in path.read_text()
