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

    def _guard(self, op):
        if not self.writable:
            from services.notion import ReadOnlyError
            raise ReadOnlyError(op)

    def create_page(self, data_source_id, properties, children=None):
        self._guard("create_page")
        pid = uuid.uuid4().hex
        self.pages[pid] = {"id": pid, "parent_ds": data_source_id, "properties": properties,
                           "last_edited_time": "t0"}
        self.writes.append(("create", data_source_id, properties))
        return self.pages[pid]

    def update_page(self, page_id, properties):
        self._guard("update_page")
        self.pages[page_id]["properties"].update(properties)
        self.writes.append(("update", page_id, properties))
        return self.pages[page_id]

    def update_data_source(self, data_source_id, body):
        self._guard("update_data_source")
        self.writes.append(("schema", data_source_id, body))
        return {}

    def get_page(self, page_id):
        return self.pages[page_id]

    def page_table_rows(self, page_id):
        return self.table_rows.get(page_id, [])


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
