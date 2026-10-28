import pytest
import requests

from services.notion import Notion, NotionError, ReadOnlyError, prop_value


class Resp:
    def __init__(self, status, data=None, headers=None):
        self.status_code, self._data, self.headers, self.text = status, data or {}, headers or {}, ""

    def json(self):
        return self._data


class Session:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def client(*responses, writable=False):
    sleeps = []
    n = Notion(token="t", writable=writable, session=Session(*responses), sleep=sleeps.append,
               requests_per_second=1000)
    return n, sleeps


def test_retries_429_honouring_retry_after():
    n, sleeps = client(Resp(429, headers={"Retry-After": "2"}), Resp(200, {"id": "p"}))
    assert n.get_page("p") == {"id": "p"}
    assert 2.0 in sleeps


def test_retries_network_errors_then_gives_clear_error():
    n, _ = client(*[requests.ConnectionError("boom")] * 5)
    with pytest.raises(NotionError, match="failed after 5 tries"):
        n.get_page("p")


def test_404_has_sharing_hint():
    n, _ = client(Resp(404, {"code": "object_not_found", "message": "nope"}))
    with pytest.raises(NotionError, match="Connections"):
        n.get_page("p")


def test_dry_run_blocks_writes_but_allows_queries():
    n, _ = client(Resp(200, {"results": [{"id": 1}], "has_more": False}))
    assert list(n.query("ds")) == [{"id": 1}]
    with pytest.raises(ReadOnlyError):
        n.update_page("p", {})
    with pytest.raises(ReadOnlyError):
        n.create_page("ds", {})


def test_query_paginates_and_limits():
    n, _ = client(Resp(200, {"results": [{"id": 1}, {"id": 2}], "has_more": True, "next_cursor": "c"}),
                  Resp(200, {"results": [{"id": 3}], "has_more": False}))
    assert [p["id"] for p in n.query("ds")] == [1, 2, 3]
    assert n.session.calls[1][2]["json"]["start_cursor"] == "c"


def test_page_table_rows():
    cell = lambda s: [{"plain_text": s}]
    n, _ = client(Resp(200, {"results": [{"id": "tb", "type": "table", "has_children": True}], "has_more": False}),
                  Resp(200, {"results": [{"type": "table_row", "table_row": {"cells": [cell("Cadence"), cell("Mon–Fri")]}}],
                             "has_more": False}))
    assert n.page_table_rows("page") == [["Cadence", "Mon–Fri"]]


def test_missing_token(monkeypatch):
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    with pytest.raises(NotionError, match="NOTION_TOKEN"):
        Notion()


def test_prop_value():
    assert prop_value({"type": "select", "select": {"name": "OK"}}) == "OK"
    assert prop_value({"type": "title", "title": [{"plain_text": "a"}, {"plain_text": "b"}]}) == "ab"
    assert prop_value({"type": "relation", "relation": [{"id": "x"}]}) == ["x"]
    assert prop_value({"type": "formula", "formula": {"type": "number", "number": 4}}) == 4
