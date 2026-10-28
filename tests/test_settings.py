import re
from pathlib import Path

from services import settings as S

ROOT = Path(__file__).resolve().parent.parent


def engine_settings_rows():
    """Table rows of the Engine Settings page source, as the Notion API would return them."""
    rows = []
    for line in (ROOT / "docs" / "notion-pages" / "Engine Settings.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and not re.match(r"^\|\s*-", line):
            rows.append([c.strip() for c in line.strip("|").split("|")])
    return rows


def test_file_defaults_load():
    s = S.load()
    assert s["brand_fit.threshold"] == 7
    assert s["post_date.offset_days"] == 3
    assert s["cadence.days"] == ["Mon", "Tue", "Wed", "Thu", "Fri"]
    assert s.source_of("brand_fit.threshold") == "file"


def test_current_engine_settings_page_overrides_cleanly():
    s = S.load()
    applied, errors = s.apply_rows(engine_settings_rows())
    assert errors == []
    assert s["trend.weights"] == [0.35, 0.25, 0.2, 0.2]
    assert s["trend.caps"] == [4, 4, 3, 5]
    assert s["similarity.too_close_pct"] == 8 and s["similarity.max_run"] == 10
    assert s["fetch.whisper_model"] == "small"
    assert s["cadence.days"] == ["Mon", "Tue", "Wed", "Thu", "Fri"] and s["cadence.slots_per_day"] == 1
    assert s.source_of("trend.weights").startswith("notion:")
    assert "review.auto_shortlist" in applied


def test_bad_row_falls_back_to_file_value():
    s = S.load()
    _, errors = s.apply_rows([["Brand-fit pass threshold", "high"], ["Unknown row", "5"]])
    assert s["brand_fit.threshold"] == 7
    assert len(errors) == 1 and "Brand-fit pass threshold" in errors[0]


def test_cadence_parser():
    assert S.cadence("Mon, Wed, Fri, 2 shorts per day") == {"days": ["Mon", "Wed", "Fri"], "slots_per_day": 2}
    assert S.cadence("Mon–Sat") == {"days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], "slots_per_day": 1}


def test_notion_failure_degrades_to_file():
    class Broken:
        def page_table_rows(self, _):
            raise RuntimeError("down")
    s, errors = S.load_with_notion(Broken(), {"pages": {"engine_settings": "x"}})
    assert s["brand_fit.threshold"] == 7 and "file values only" in errors[0]


def test_load_env_does_not_override(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# c\nFOO_TEST='bar'\nKEEP_TEST=new\n")
    monkeypatch.setenv("KEEP_TEST", "old")
    monkeypatch.delenv("FOO_TEST", raising=False)
    S.load_env(env)
    import os
    assert os.environ["FOO_TEST"] == "bar" and os.environ["KEEP_TEST"] == "old"
