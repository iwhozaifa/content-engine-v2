import json

import cli
from services import runlog


def test_settings_check_file_only(tmp_path, monkeypatch):
    monkeypatch.setattr(runlog, "LOGS", tmp_path)
    monkeypatch.setattr(runlog.RunLog.__init__, "__defaults__", (None, tmp_path))
    lines = []
    assert cli.main(["settings-check", "--file-only"], out=lines.append) == 0
    text = "\n".join(lines)
    assert "brand_fit.threshold" in text and "No-op" in text
    rec = json.loads((tmp_path / "runs.jsonl").read_text().splitlines()[-1])
    assert rec["command"] == "settings-check" and rec["mode"] == "Dry-run"


def test_failure_is_logged_with_exit_code(tmp_path, monkeypatch):
    monkeypatch.setattr(runlog.RunLog.__init__, "__defaults__", (None, tmp_path))
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.setattr(cli.settings_mod, "load_env", lambda: None)
    lines = []
    assert cli.main(["ping"], out=lines.append) == 1
    assert "NOTION_TOKEN" in "\n".join(lines)


def test_read_only_commands_have_no_apply_flag():
    p = cli.build_parser()
    for name in ("ping", "settings-check", "snapshot-schema"):
        args = p.parse_args([name])
        assert not hasattr(args, "apply")
