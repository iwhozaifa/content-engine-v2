from types import SimpleNamespace

import pytest

from services import notify
from services import settings as st
from services.runlog import RunLog


def settings(**kw):
    s = st.load()
    for k, v in kw.items():
        s.set(k, v, "test")
    return s


def test_only_changes_or_errors_notify():
    log = RunLog("news-radar", True)
    log.finish({"create": 0, "update": 0})
    assert not notify.should_send(settings(**{"notify.enabled": True}), log)
    log.finish({"create": 2})
    assert notify.should_send(settings(**{"notify.enabled": True}), log)
    assert not notify.should_send(settings(**{"notify.enabled": False}), log)


def test_message_links_next_step():
    log = RunLog("news-radar", True)
    log.finish({"create": 3})
    text = notify.message(log, {"databases": {"news_candidates": {"database": "ab-cd"}}})
    assert "Review new News Candidates" in text and "https://www.notion.so/abcd" in text


def test_telegram_send(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    sent = []
    notify.send(settings(**{"notify.channel": "telegram"}), "hi",
                post=lambda url, json, timeout: sent.append((url, json)) or SimpleNamespace(status_code=200))
    assert sent[0][1] == {"chat_id": "c", "text": "hi", "disable_web_page_preview": True}


def test_missing_config_is_clear(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        notify.send(settings(**{"notify.channel": "telegram"}), "hi")
