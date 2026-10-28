import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("secret_scan", Path(__file__).parent.parent / "scripts" / "secret_scan.py")
secret_scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(secret_scan)


def test_flags_tokens_and_env_files(tmp_path):
    bad = tmp_path / "x.py"
    bad.write_text("token = 'ntn_" + "a" * 45 + "'\n")
    env_example = tmp_path / "ok.env.example"
    env_example.write_text("NOTION_TOKEN=\nTELEGRAM_BOT_TOKEN=\nTELEGRAM_CHAT_ID=\nSMTP_PASSWORD=\nNOTIFY_EMAIL_TO=\n")
    assert len(secret_scan.scan([str(bad)])) == 1
    assert secret_scan.scan([str(env_example)]) == []
    assert secret_scan.scan([".env"]) and secret_scan.scan(["sub/cookies.txt"])


def test_flags_assigned_secret_value(tmp_path):
    f = tmp_path / "conf.sh"
    f.write_text("SMTP_PASSWORD=hunter2hunter2xx\n")
    assert secret_scan.scan([str(f)])
