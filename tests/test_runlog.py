import json

from services import settings as S
from services.runlog import RunLog
from tests.fakes import FakeNotion


def test_status_rules(tmp_path):
    assert RunLog("x", False, logs=tmp_path).finish({"create": 0})["status"] == "No-op"
    assert RunLog("x", False, logs=tmp_path).finish({"create": 2})["status"] == "OK"
    r = RunLog("x", False, logs=tmp_path)
    r.error("boom")
    assert r.finish({"create": 1})["status"] == "Partial"
    r = RunLog("x", False, logs=tmp_path)
    r.error("boom")
    assert r.finish({})["status"] == "Failed"


def test_local_log_and_settings_snapshot(tmp_path):
    s = S.load()
    s.set("brand_fit.threshold", 6, "notion:Brand-fit pass threshold")
    r = RunLog("weekly-plan", True, s, logs=tmp_path)
    r.finish({"create": 1})
    r.write_local()
    rec = json.loads((tmp_path / "runs.jsonl").read_text())
    assert rec["mode"] == "Apply" and rec["settings_used"]["brand_fit.threshold"] == 6
    assert "trend.weights" not in rec["settings_used"]


def test_notion_row_skipped_until_run_log_db_exists(tmp_path):
    n = FakeNotion()
    r = RunLog("x", True, logs=tmp_path)
    r.finish({})
    assert r.write_notion(n, {"databases": {}}) is None and not n.writes
    r.write_notion(n, {"databases": {"run_log": {"data_source": "ds-log"}}})
    assert n.writes[0][1] == "ds-log"
