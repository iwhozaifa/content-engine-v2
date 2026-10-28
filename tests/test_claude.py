import json

import pytest

from services import settings as S
from services.claude import Claude, ClaudeError, load_prompt, parse_output, render
from services.retry import RetryableError
from tests.fakes import FakeClaude


def make(tmp_path, *replies):
    fake = FakeClaude(*replies)
    s = S.load()
    s.set("claude.bin", "/bin/true", "test")
    return Claude(s, runner=fake, cache_dir=tmp_path, sleep=lambda _: None), fake


def test_ping_prompt_loads_and_renders():
    p = load_prompt("ping")
    assert p.id == "ping.v1" and p.meta["task"] == "default"
    assert '"echo": "x"' in render(p.body, {"word": "x"})


def test_render_requires_all_inputs():
    with pytest.raises(ClaudeError, match="no input"):
        render("{{a}} {{b}}", {"a": 1})


def test_run_validates_caches_and_counts_cost(tmp_path):
    c, fake = make(tmp_path, {"ok": True, "echo": "engine"})
    r = c.run("ping", {"word": "engine"})
    assert r.output == {"ok": True, "echo": "engine"} and not r.cached
    assert c.cost_usd == pytest.approx(0.002) and c.tokens == 150
    cmd = fake.calls[0]["cmd"]
    assert cmd[cmd.index("--model") + 1] == "claude-haiku-5-5"
    assert cmd[cmd.index("--tools") + 1] == ""
    again = c.run("ping", {"word": "engine"})
    assert again.cached and len(fake.calls) == 1


def test_invalid_output_retries_once_then_succeeds(tmp_path):
    c, fake = make(tmp_path, {"ok": "yes"}, {"ok": True, "echo": "e"})
    assert c.run("ping", {"word": "e"}).output["ok"] is True
    assert "not valid against the JSON schema" in fake.calls[1]["input"]


def test_gives_up_with_clear_error(tmp_path):
    c, _ = make(tmp_path, {"ok": "yes"}, {"ok": "still no"})
    with pytest.raises(ClaudeError, match="ping.v1 failed"):
        c.run("ping", {"word": "e"})


def test_auth_error_is_not_retried():
    out = json.dumps({"type": "result", "is_error": True, "result": "Invalid API key · Please run /login"})
    with pytest.raises(ClaudeError, match="signed in"):
        parse_output(out)


def test_result_text_with_fences_parses():
    out = json.dumps({"type": "result", "is_error": False, "result": "```json\n{\"ok\": true}\n```"})
    assert parse_output(out)[0] == {"ok": True}
    with pytest.raises(RetryableError):
        parse_output("not json")
