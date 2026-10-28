from services import schema as sch
from tests.fakes import FakeNotion, _live
from tests.helpers import ids, run_cli


def live_from_target(props, idmap):
    return {n: _live(sch.property_payload(s, idmap)) for n, s in props.items() if s["type"] != "relation"}


def seed(notion, idmap, target, skip=()):
    """Make the fake's existing databases match the target, except properties named in skip."""
    for key, spec in target["databases"].items():
        if key in idmap["databases"]:
            props = {n: s for n, s in spec["properties"].items() if n not in skip}
            notion.sources[idmap["databases"][key]["data_source"]] = {"properties": live_from_target(props, idmap)}


def test_property_payloads():
    idmap = ids()
    assert sch.property_payload({"type": "rich_text"}, idmap) == {"rich_text": {}}
    assert sch.property_payload({"type": "select", "options": ["A"]}, idmap) == {"select": {"options": [{"name": "A"}]}}
    rel = sch.property_payload({"type": "relation", "db": "scripts", "synced": "Plan item"}, idmap)
    assert rel["relation"]["data_source_id"] == "ds-scripts"
    assert rel["relation"]["dual_property"] == {"synced_property_name": "Plan item"}
    assert sch.property_payload({"type": "relation", "db": "run_log"}, idmap) is None


def test_diff_adds_missing_and_keeps_existing_options():
    target = {"Status": {"type": "select", "options": ["Planned", "Topic Locked"]},
              "Approval": {"type": "select", "options": ["Pending"]},
              "Brand fit": {"type": "rich_text"}}
    live = {"Status": {"type": "select", "select": {"options": [{"id": "x1", "name": "Planned"}, {"id": "x2", "name": "Mine"}]}},
            "Brand fit": {"type": "number", "number": {}}}
    add, options, pending, conflicts = sch.diff_properties(target, live, ids())
    assert list(add) == ["Approval"]
    opts = options["Status"]["select"]["options"]
    assert {"id": "x2", "name": "Mine"} in opts and {"name": "Topic Locked"} in opts  # user option kept
    assert conflicts and "Brand fit" in conflicts[0]


def test_dry_run_plans_everything_and_writes_nothing(tmp_path, monkeypatch):
    target = sch.load_target()
    notion, idmap = FakeNotion(), ids()
    seed(notion, idmap, target, skip={"Approval", "Engine key", "Rich topic"})
    code, out, _ = run_cli(["migrate-schema"], monkeypatch, tmp_path, notion, idmap)
    assert code == 0, out
    assert notion.writes == []
    assert "create database" in out and "Run Log" in out
    assert "page:engine_settings.rows" in out and "page:brand_profile.sections" in out
    assert "Views to add by hand" in out


def test_apply_then_rerun_is_noop(tmp_path, monkeypatch):
    target = sch.load_target()
    notion, idmap = FakeNotion(), ids()
    seed(notion, idmap, target, skip={"Approval", "Engine key", "Rich topic", "Engine trend score", "Content card"})
    notion.table_rows["pg-settings"] = [["Cadence", "Mon–Fri"]]
    code, out, _ = run_cli(["migrate-schema", "--apply"], monkeypatch, tmp_path, notion, idmap)
    assert code == 0, out
    assert {"run_log", "news_candidates", "weekly_plans"} <= set(idmap["databases"])
    created = [w[1] for w in notion.writes if w[0] == "database"]
    assert sorted(created) == ["News Candidates", "Run Log", "Weekly Plans"]
    news = notion.sources[idmap["databases"]["news_candidates"]["data_source"]]["properties"]
    assert "Idea" in news  # relation added in the same run, after the database existed
    rows = [w for w in notion.writes if w[0] == "blocks" and w[1] == "pg-settings"][0][2]
    labels = [r["table_row"]["cells"][0][0]["text"]["content"] for r in rows[1]["table"]["children"]]
    assert "Cadence" not in labels and "Brand-fit pass threshold" in labels

    # Second run: make the fake reflect the appended blocks, then expect zero changes.
    notion.table_rows["pg-settings"] += [[l, "x"] for l in labels[1:]]
    notion.writes.clear()
    code, out, _ = run_cli(["migrate-schema", "--apply"], monkeypatch, tmp_path, notion, idmap)
    assert code == 0, out
    assert notion.writes == [], notion.writes
    assert "nothing to change" in out
