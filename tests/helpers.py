"""Run a CLI command end to end against FakeNotion (and optionally FakeClaude), writing logs to tmp."""
import copy

import cli
from services import plan, runlog
from services.claude import Claude

IDS = {
    "pages": {"content_engine": "pg-root", "brand_profile": "pg-brand", "engine_settings": "pg-settings",
              "voice_guide": "pg-voice"},
    "databases": {k: {"database": f"db-{k}", "data_source": f"ds-{k}"}
                  for k in ("content_creators", "raw_content", "idea_bank", "scripts", "content_plan",
                            "hook_library", "cta_bank")},
}


def ids(**extra):
    out = copy.deepcopy(IDS)
    for key in extra.get("dbs", []):
        out["databases"][key] = {"database": f"db-{key}", "data_source": f"ds-{key}"}
    return out


def run_cli(argv, monkeypatch, tmp_path, notion, ids_=None, runner=None):
    """Returns (exit code, output text, Context)."""
    ids_ = ids_ if ids_ is not None else ids()
    monkeypatch.setattr(runlog, "LOGS", tmp_path)
    monkeypatch.setattr(plan, "LOGS", tmp_path)
    monkeypatch.setattr(cli.settings_mod, "load_env", lambda: None)
    monkeypatch.setattr(cli.settings_mod, "load_ids", lambda: ids_)
    monkeypatch.setattr(cli.settings_mod, "save_db_ids", lambda *a, **k: True)
    monkeypatch.setattr(runlog.RunLog, "write_notion", lambda self, n, i: None)
    seen = {}

    def notion_prop(self):
        notion.writable = self.apply
        seen["ctx"] = self
        return notion

    def claude_prop(self):
        if self._claude is None:
            self._claude = Claude(self.settings, runner=runner, cache_dir=tmp_path / "llm", sleep=lambda s: None)
        return self._claude
    monkeypatch.setattr(cli.Context, "notion", property(notion_prop))
    monkeypatch.setattr(cli.Context, "claude", property(claude_prop))
    lines = []
    code = cli.main(argv, out=lines.append)
    return code, "\n".join(lines), seen.get("ctx")
