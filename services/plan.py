"""ChangeSet: every command describes its Notion writes here first.

Dry-run (default) prints and saves the set. --apply executes it: each update re-reads its page and
is skipped if someone edited it after the command read it, so a run never overwrites your edits.
One failed change is recorded and the rest still run.
"""
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"


@dataclass
class Change:
    op: str                      # create | update | schema | database | blocks
    db: str                      # key under [databases] in notion_ids.toml
    key: str                     # stable idempotency key
    properties: dict             # Notion API property payload (or schema body for op=schema)
    summary: dict                # field -> plain value, for humans
    page_id: str | None = None
    expected_edit: str | None = None  # last_edited_time seen when the command read the page
    children: list | None = None
    reason: str = ""
    status: str = "pending"      # pending | done | skipped | conflict | failed
    result_id: str | None = None
    error: str = ""
    after: object = field(default=None, repr=False, compare=False)  # callback(change) once applied


class ChangeSet:
    def __init__(self, command):
        self.command = command
        self.changes: list[Change] = []
        self.skipped: list[tuple[str, str]] = []  # (key, reason) for things deliberately left alone

    def create(self, db, key, properties, summary, children=None, reason="", after=None):
        c = Change("create", db, key, properties, summary, children=children, reason=reason, after=after)
        self.changes.append(c)
        return c

    def update(self, db, key, page_id, properties, summary, expected_edit=None, reason="", after=None):
        c = Change("update", db, key, properties, summary, page_id=page_id,
                   expected_edit=expected_edit, reason=reason, after=after)
        self.changes.append(c)
        return c

    def schema(self, db, key, body, summary, reason=""):
        c = Change("schema", db, key, body, summary, reason=reason)
        self.changes.append(c)
        return c

    def database(self, db, key, body, summary, reason="", after=None):
        """Create a database (body = POST /databases payload)."""
        c = Change("database", db, key, body, summary, reason=reason, after=after)
        self.changes.append(c)
        return c

    def blocks(self, db, key, page_id, children, summary, reason=""):
        """Append blocks to a page (db = the page's key under [pages])."""
        c = Change("blocks", db, key, {}, summary, page_id=page_id, children=children, reason=reason)
        self.changes.append(c)
        return c

    def skip(self, key, reason):
        self.skipped.append((key, reason))

    def keys(self):
        return {c.key for c in self.changes}

    def counts(self):
        out = {"create": 0, "update": 0, "schema": 0, "skip": len(self.skipped)}
        for c in self.changes:
            out[c.op] = out.get(c.op, 0) + 1
        for c in self.changes:
            if c.status in ("conflict", "failed"):
                out[c.status] = out.get(c.status, 0) + 1
        return out

    def render(self, width=70):
        if not self.changes and not self.skipped:
            return f"{self.command}: nothing to change."
        lines = [f"{'op':<7} {'db':<17} {'key':<34} changes", "-" * 100]
        for c in self.changes:
            fields = ", ".join(f"{k}={_short(v)}" for k, v in c.summary.items())
            flag = f"  [{c.status}{': ' + c.error if c.error else ''}]" if c.status != "pending" else ""
            lines.append(f"{c.op:<7} {c.db:<17} {_short(c.key, 34):<34} {_short(fields, width)}{flag}")
        for key, reason in self.skipped:
            lines.append(f"{'skip':<7} {'':<17} {_short(key, 34):<34} {reason}")
        n = self.counts()
        lines.append("-" * 100)
        lines.append(" · ".join(f"{k}: {v}" for k, v in n.items()))
        return "\n".join(lines)

    def to_dict(self):
        return {"command": self.command, "counts": self.counts(),
                "changes": [{k: v for k, v in asdict(c).items() if k != "after"} for c in self.changes],
                "skipped": self.skipped}

    def save(self, logs=None):
        logs = Path(logs or LOGS)
        logs.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = logs / f"changeset-{self.command}-{stamp}.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def apply(self, notion, ids):
        """Execute every pending change. Returns the list of errors (strings)."""
        errors = []
        for c in self.changes:
            if c.status != "pending":
                continue
            try:
                db = ids["databases"].get(c.db, {})
                if c.op == "create":
                    page = notion.create_page(db["data_source"], c.properties, c.children)
                    c.result_id = page["id"]
                elif c.op == "update":
                    if c.expected_edit:
                        current = notion.get_page(c.page_id)
                        if current.get("last_edited_time") != c.expected_edit:
                            c.status, c.error = "conflict", "edited in Notion during the run; left as is"
                            errors.append(f"{c.key}: {c.error}")
                            continue
                    notion.update_page(c.page_id, c.properties)
                    c.result_id = c.page_id
                elif c.op == "schema":
                    notion.update_data_source(db["data_source"], c.properties)
                elif c.op == "database":
                    c.result_id = notion.create_database(c.properties)["id"]
                elif c.op == "blocks":
                    notion.append_children(c.page_id, c.children)
                c.status = "done"
                if c.after:
                    c.after(c)
            except Exception as e:  # noqa: BLE001 - record and continue (CLAUDE.md rule 8)
                c.status, c.error = "failed", str(e)[:300]
                errors.append(f"{c.key}: {c.error}")
        return errors


def _short(value, n=24):
    s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[: n - 1] + "…"
