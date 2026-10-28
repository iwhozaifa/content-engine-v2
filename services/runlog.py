"""Run Log: one record per command run. Always appended to logs/runs.jsonl; with --apply also
written as a row in the Notion Run Log database (once that database exists, from P1)."""
import json
import socket
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from services.settings import snapshot

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"


def git_sha():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=ROOT, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def now():
    return datetime.now(timezone.utc)


class RunLog:
    def __init__(self, command, apply, settings=None, logs=None):
        self.id = uuid.uuid4().hex[:12]
        self.command = command
        self.mode = "Apply" if apply else "Dry-run"
        self.settings = settings
        self.logs = Path(logs or LOGS)
        self.started = now()
        self.finished = None
        self.counts = {}
        self.errors = []
        self.warnings = []
        self.cost_usd = 0.0
        self.tokens = 0
        self.status = None

    def error(self, message):
        self.errors.append(str(message))

    def warn(self, message):
        self.warnings.append(str(message))

    def finish(self, counts=None, claude=None, status=None):
        self.finished = now()
        self.counts = counts or self.counts
        if claude is not None:
            self.cost_usd, self.tokens = round(claude.cost_usd, 4), claude.tokens
        changed = sum(v for k, v in self.counts.items() if k in ("create", "update", "schema", "database", "blocks", "block"))
        self.status = status or ("Failed" if self.errors and not changed
                                 else "Partial" if self.errors else "OK" if changed else "No-op")
        return self.record()

    def record(self):
        return {
            "run_id": self.id, "command": self.command, "mode": self.mode,
            "started": self.started.isoformat(), "finished": self.finished.isoformat() if self.finished else None,
            "status": self.status, "counts": self.counts, "errors": self.errors, "warnings": self.warnings,
            "cost_usd": self.cost_usd, "tokens": self.tokens, "git_sha": git_sha(), "host": socket.gethostname(),
            "settings_used": snapshot(self.settings) if self.settings else {},
        }

    def write_local(self):
        self.logs.mkdir(parents=True, exist_ok=True)
        with open(self.logs / "runs.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(self.record(), ensure_ascii=False, default=str) + "\n")

    def write_notion(self, notion, ids):
        """Write the Run Log row. Only called with --apply. Silently skipped before P1 creates the DB."""
        db = ids.get("databases", {}).get("run_log")
        if not db:
            return None
        r = self.record()
        props = {
            "Run": {"title": [{"text": {"content": f"{self.command} {self.started:%Y-%m-%d %H:%M}"}}]},
            "Command": {"select": {"name": self.command}},
            "Mode": {"select": {"name": self.mode}},
            "Status": {"select": {"name": r["status"]}},
            "Started": {"date": {"start": r["started"]}},
            "Finished": {"date": {"start": r["finished"]}},
            "Created": {"number": self.counts.get("create", 0)},
            "Updated": {"number": self.counts.get("update", 0)},
            "Skipped": {"number": self.counts.get("skip", 0)},
            "Errors": {"rich_text": [{"text": {"content": "\n".join(self.errors)[:1900]}}]},
            "Est. cost (API-equiv $)": {"number": self.cost_usd},
            "Tokens": {"number": self.tokens},
            "Git SHA": {"rich_text": [{"text": {"content": r["git_sha"]}}]},
            "Host": {"rich_text": [{"text": {"content": r["host"]}}]},
            "Settings used": {"rich_text": [{"text": {"content": json.dumps(r["settings_used"])[:1900]}}]},
        }
        return notion.create_page(db["data_source"], props)

    def summary(self):
        r = self.record()
        parts = [f"{self.command} [{self.mode}] {r['status']}",
                 " · ".join(f"{k} {v}" for k, v in self.counts.items())]
        if self.tokens:
            parts.append(f"~{self.tokens} tokens, ${self.cost_usd:.4f} API-equiv")
        out = " | ".join(p for p in parts if p)
        for w in self.warnings:
            out += f"\n  ! {w}"
        for e in self.errors:
            out += f"\n  ✗ {e}"
        return out
