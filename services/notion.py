"""Notion REST client: rate-limited, retried, and read-only unless a command runs with --apply.

Needs NOTION_TOKEN (an internal integration token) with the Content Engine page shared to it.
"""
import os
import time

import requests

from services.retry import RetryableError, with_retries

API = "https://api.notion.com/v1"
RETRY_STATUS = {429, 500, 502, 503, 504}
HINTS = {
    401: "NOTION_TOKEN is missing or invalid. Copy the integration secret into .env.",
    403: "The integration lacks this capability. In Notion → Settings → Integrations, enable read/update/insert content.",
    404: "Not found, or not shared with the integration. Open the Content Engine page → ••• → Connections → add the integration.",
}


class NotionError(Exception):
    def __init__(self, status, code, message):
        hint = HINTS.get(status, "")
        super().__init__(f"Notion {status} {code}: {message}" + (f" | {hint}" if hint else ""))
        self.status, self.code = status, code


class ReadOnlyError(Exception):
    """A write was attempted in dry-run mode. This is a bug in the command, never a user error."""


class Notion:
    def __init__(self, token=None, writable=False, version="2025-09-03", requests_per_second=3,
                 max_attempts=5, session=None, sleep=time.sleep, log=None):
        self.token = token or os.environ.get("NOTION_TOKEN", "")
        if not self.token:
            raise NotionError(401, "missing_token", "NOTION_TOKEN is not set")
        self.writable = writable
        self.version = version
        self.min_interval = 1.0 / requests_per_second
        self.max_attempts = max_attempts
        self.session = session or requests.Session()
        self.sleep = sleep
        self.log = log or (lambda msg: None)
        self._last = 0.0
        self.calls = 0

    @classmethod
    def from_settings(cls, settings, writable=False, **kw):
        return cls(writable=writable, version=settings["notion.api_version"],
                   requests_per_second=settings["notion.requests_per_second"],
                   max_attempts=settings["notion.max_attempts"], **kw)

    # -- transport -------------------------------------------------------------
    def _throttle(self):
        wait = self._last + self.min_interval - time.monotonic()
        if wait > 0:
            self.sleep(wait)
        self._last = time.monotonic()

    def request(self, method, path, body=None, params=None):
        if method != "GET" and not self._is_read(method, path) and not self.writable:
            raise ReadOnlyError(f"{method} {path} blocked: dry-run mode (pass --apply to write)")
        headers = {"Authorization": f"Bearer {self.token}", "Notion-Version": self.version,
                   "Content-Type": "application/json"}

        def once():
            self._throttle()
            self.calls += 1
            try:
                r = self.session.request(method, API + path, json=body, params=params, headers=headers, timeout=60)
            except (requests.ConnectionError, requests.Timeout) as e:
                raise RetryableError(f"network: {e}")
            if r.status_code in RETRY_STATUS:
                after = r.headers.get("Retry-After")
                raise RetryableError(f"HTTP {r.status_code}", wait=float(after) if after else None)
            if r.status_code >= 400:
                data = _json(r)
                raise NotionError(r.status_code, data.get("code", ""), data.get("message", r.text[:300]))
            return _json(r)

        def note(n, wait, err):
            self.log(f"Notion {method} {path}: {err}; retry {n} in {wait:.1f}s")

        try:
            return with_retries(once, self.max_attempts, sleep=self.sleep, on_retry=note)
        except RetryableError as e:
            raise NotionError(0, "retries_exhausted", f"{method} {path} failed after {self.max_attempts} tries: {e}")

    @staticmethod
    def _is_read(method, path):
        # Queries and searches are POSTs that don't write.
        return method == "POST" and (path.endswith("/query") or path == "/search")

    # -- reads -----------------------------------------------------------------
    def get_database(self, database_id):
        return self.request("GET", f"/databases/{database_id}")

    def get_data_source(self, data_source_id):
        return self.request("GET", f"/data_sources/{data_source_id}")

    def get_page(self, page_id):
        return self.request("GET", f"/pages/{page_id}")

    def query(self, data_source_id, filter=None, sorts=None, limit=None):
        """Yield every page of a data source matching filter (handles pagination)."""
        body, seen = {"page_size": 100}, 0
        if filter:
            body["filter"] = filter
        if sorts:
            body["sorts"] = sorts
        while True:
            data = self.request("POST", f"/data_sources/{data_source_id}/query", body)
            for page in data.get("results", []):
                yield page
                seen += 1
                if limit and seen >= limit:
                    return
            if not data.get("has_more"):
                return
            body["start_cursor"] = data["next_cursor"]

    def children(self, block_id):
        cursor = None
        while True:
            params = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
            data = self.request("GET", f"/blocks/{block_id}/children", params=params)
            yield from data.get("results", [])
            if not data.get("has_more"):
                return
            cursor = data["next_cursor"]

    def page_table_rows(self, page_id):
        """Every row of every table on a page (one level of nesting), as lists of plain-text cells."""
        rows = []
        for block in self.children(page_id):
            if block["type"] == "table":
                for row in self.children(block["id"]):
                    if row["type"] == "table_row":
                        rows.append([plain(cell) for cell in row["table_row"]["cells"]])
            elif block.get("has_children") and block["type"] in ("toggle", "column_list", "column", "callout"):
                rows.extend(self.page_table_rows(block["id"]))
        return rows

    def page_text(self, page_id, depth=2):
        """A page body as plain markdown-ish text (headings, paragraphs, lists, tables, toggles)."""
        lines = []
        for block in self.children(page_id):
            t = block["type"]
            body = block.get(t, {})
            if t == "table":
                for row in self.children(block["id"]):
                    if row["type"] == "table_row":
                        lines.append(" | ".join(plain(c) for c in row["table_row"]["cells"]))
                continue
            text = plain(body.get("rich_text"))
            if t.startswith("heading_"):
                lines.append("#" * int(t[-1]) + " " + text)
            elif t in ("bulleted_list_item", "numbered_list_item", "to_do"):
                lines.append("- " + text)
            elif text:
                lines.append(text)
            if block.get("has_children") and depth > 0 and t not in ("child_page", "child_database"):
                lines.append(self.page_text(block["id"], depth - 1))
        return "\n".join(l for l in lines if l)

    # -- writes (blocked unless writable) ---------------------------------------
    def create_page(self, data_source_id, properties, children=None):
        body = {"parent": {"type": "data_source_id", "data_source_id": data_source_id}, "properties": properties}
        if children:
            body["children"] = children
        return self.request("POST", "/pages", body)

    def update_page(self, page_id, properties):
        return self.request("PATCH", f"/pages/{page_id}", {"properties": properties})

    def create_database(self, body):
        return self.request("POST", "/databases", body)

    def update_data_source(self, data_source_id, body):
        return self.request("PATCH", f"/data_sources/{data_source_id}", body)

    def update_block(self, block_id, body):
        return self.request("PATCH", f"/blocks/{block_id}", body)

    def table_row_blocks(self, page_id):
        """(block, [cell texts]) for every table row on a page (one level of nesting), for in-place edits."""
        out = []
        for block in self.children(page_id):
            if block["type"] == "table":
                out += [(row, [plain(c) for c in row["table_row"]["cells"]])
                        for row in self.children(block["id"]) if row["type"] == "table_row"]
            elif block.get("has_children") and block["type"] in ("toggle", "column_list", "column", "callout"):
                out += self.table_row_blocks(block["id"])
        return out

    def archive_page(self, page_id):
        """Move a page to Notion's trash (restorable). Only used for engine-test rows."""
        return self.request("PATCH", f"/pages/{page_id}", {"in_trash": True})

    def append_children(self, block_id, children):
        return self.request("PATCH", f"/blocks/{block_id}/children", {"children": children})


def _json(r):
    try:
        return r.json()
    except ValueError:
        return {}


def plain(rich_text):
    return "".join(t.get("plain_text", t.get("text", {}).get("content", "")) for t in rich_text or [])


def prop_value(prop):
    """Plain Python value of a page property (title/text/number/select/... ) for comparisons and logs."""
    t = prop.get("type")
    v = prop.get(t)
    if t in ("title", "rich_text"):
        return plain(v)
    if t in ("select", "status"):
        return v["name"] if v else None
    if t == "multi_select":
        return [o["name"] for o in v]
    if t == "date":
        return v["start"] if v else None
    if t == "relation":
        return [r["id"] for r in v]
    if t == "formula":
        return v.get(v.get("type"))
    if t == "rollup":
        return v.get(v.get("type"))
    return v
