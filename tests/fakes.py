"""In-memory stand-ins for Notion and the claude CLI, so tests never touch the network."""
import json
import subprocess
import uuid


class FakeNotion:
    def __init__(self, writable=True):
        self.writable = writable
        self.pages = {}       # id -> {"id", "parent_ds", "properties", "last_edited_time"}
        self.writes = []      # (op, args) log
        self.table_rows = {}  # page_id -> rows
        self.sources = {}     # data_source_id -> {"properties": {...}}
        self.blocks = {}      # page_id -> [blocks]
        self.databases = {}   # database_id -> {"id", "data_sources": [{"id"}]}
        self.texts = {}       # page_id -> page_text

    def _guard(self, op):
        if not self.writable:
            from services.notion import ReadOnlyError
            raise ReadOnlyError(op)

    def add(self, data_source_id, properties, pid=None):
        """Seed a page (API-shaped properties are built from write payloads)."""
        pid = pid or uuid.uuid4().hex
        self.pages[pid] = {"id": pid, "parent_ds": data_source_id, "properties": {}, "last_edited_time": "t0",
                           "children": []}
        self.pages[pid]["properties"].update(api_props(properties))
        return self.pages[pid]

    def _register(self, parent_id, children):
        """Store blocks like the API: each gets an id; nested children are listed under that id."""
        out = []
        for b in children or []:
            b = {**b, "id": uuid.uuid4().hex}
            t = b["type"]
            nested = b.get(t, {}).get("children")
            if nested:
                b[t] = {k: v for k, v in b[t].items() if k != "children"}
                b["has_children"] = True
                self._register(b["id"], nested)
            out.append(b)
        self.blocks[parent_id] = self.blocks.get(parent_id, []) + out
        return out

    def create_page(self, data_source_id, properties, children=None):
        self._guard("create_page")
        page = self.add(data_source_id, properties)
        page["children"] = children or []
        self._register(page["id"], children)
        self.writes.append(("create", data_source_id, properties))
        return page

    def update_page(self, page_id, properties):
        self._guard("update_page")
        self.pages[page_id]["properties"].update(api_props(properties))
        self.pages[page_id]["last_edited_time"] = uuid.uuid4().hex[:6]
        self.writes.append(("update", page_id, properties))
        return self.pages[page_id]

    def query(self, data_source_id, filter=None, sorts=None, limit=None):
        from services.props import values
        rows = [p for p in self.pages.values() if p["parent_ds"] == data_source_id
                and (filter is None or _match(filter, values(p)))]
        return iter(rows[:limit] if limit else rows)

    def page_text(self, page_id):
        return self.texts.get(page_id, "")

    def update_data_source(self, data_source_id, body):
        self._guard("update_data_source")
        self.writes.append(("schema", data_source_id, body))
        props = self.sources.setdefault(data_source_id, {"properties": {}})["properties"]
        for name, v in body.get("properties", {}).items():
            props[name] = _live(v)
        return {}

    def create_database(self, body):
        self._guard("create_database")
        db, ds = uuid.uuid4().hex, uuid.uuid4().hex
        self.databases[db] = {"id": db, "data_sources": [{"id": ds}]}
        self.sources[ds] = {"properties": {n: _live(v) for n, v in body["initial_data_source"]["properties"].items()}}
        self.writes.append(("database", body["title"][0]["text"]["content"], body))
        return self.databases[db]

    def get_database(self, database_id):
        return self.databases[database_id]

    def get_data_source(self, data_source_id):
        return self.sources[data_source_id]

    def children(self, block_id):
        return iter(self.blocks.get(block_id, []))

    def append_children(self, block_id, children):
        self._guard("append_children")
        self._register(block_id, children)
        self.writes.append(("blocks", block_id, children))
        return {}

    def table_row_blocks(self, page_id):
        from services.notion import Notion
        return Notion.table_row_blocks(self, page_id)

    def update_block(self, block_id, body):
        self._guard("update_block")
        self.writes.append(("block", block_id, body))
        return {}

    def get_page(self, page_id):
        return self.pages[page_id]

    def page_table_rows(self, page_id):
        if page_id in self.table_rows:
            return self.table_rows[page_id]
        from services.notion import plain
        return [[plain(c) for c in row["table_row"]["cells"]]
                for b in self.blocks.get(page_id, []) if b["type"] == "table"
                for row in self.blocks.get(b["id"], [])]


def api_props(payload):
    """Write payload -> the shape the API returns when reading a page."""
    out = {}
    for name, v in payload.items():
        if not isinstance(v, dict):  # plain values used by simple tests
            out[name] = v
            continue
        t = next(iter(v))
        body = v[t]
        if t in ("title", "rich_text"):
            body = [{**r, "plain_text": r["text"]["content"]} for r in body]
        out[name] = {"type": t, t: body}
    return out


def _match(flt, v):
    if "or" in flt:
        return any(_match(f, v) for f in flt["or"])
    if "and" in flt:
        return all(_match(f, v) for f in flt["and"])
    value = v.get(flt["property"])
    cond = next(iter(x for k, x in flt.items() if k != "property"))
    if "equals" in cond:
        return value == cond["equals"]
    if "is_not_empty" in cond:
        return bool(value)
    if "is_empty" in cond:
        return not value
    if "contains" in cond:
        return cond["contains"] in (value or [])
    if "on_or_after" in cond:
        return bool(value) and value >= cond["on_or_after"]
    if "on_or_before" in cond:
        return bool(value) and value <= cond["on_or_before"]
    raise NotImplementedError(cond)


def _live(payload):
    """Turn a property payload into what Notion would return (type + options with ids)."""
    t = next(iter(payload))
    body = dict(payload[t])
    if "options" in body:
        body["options"] = [{"id": o.get("id") or uuid.uuid4().hex[:4], "name": o["name"]} for o in body["options"]]
    return {"type": t, t: body}


class FakeClaude:
    """Replaces subprocess.run for services.claude.Claude. `replies` are dicts (structured output)
    or ready-made stdout strings, returned in order."""

    def __init__(self, *replies, cost=0.002, tokens=150):
        self.replies = list(replies)
        self.calls = []
        self.cost, self.tokens = cost, tokens

    def __call__(self, cmd, input=None, **kw):
        self.calls.append({"cmd": cmd, "input": input, **kw})
        reply = self.replies.pop(0)
        if isinstance(reply, str):
            return subprocess.CompletedProcess(cmd, 0, reply, "")
        out = {"type": "result", "is_error": False, "result": json.dumps(reply), "structured_output": reply,
               "total_cost_usd": self.cost, "usage": {"input_tokens": self.tokens - 50, "output_tokens": 50}}
        return subprocess.CompletedProcess(cmd, 0, json.dumps(out), "")
