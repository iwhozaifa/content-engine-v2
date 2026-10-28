"""Engine settings: config/settings.toml defaults, overridden by whitelisted rows
of the Notion Engine Settings page. Every value remembers where it came from."""
import os
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def load_env(path=ROOT / ".env"):
    """Minimal .env loader: KEY=VALUE lines, # comments, optional quotes. Never overrides the real env."""
    if not Path(path).exists():
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def numbers(text):
    return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", text.replace(",", " "))]


def first_number(text):
    n = numbers(text)
    if not n:
        raise ValueError(f"no number in {text!r}")
    return int(n[0]) if n[0].is_integer() else n[0]


def first_word(text):
    return text.split()[0].strip(",.;")


def number_list(count):
    def parse(text):
        n = numbers(text)
        if len(n) < count:
            raise ValueError(f"expected {count} numbers in {text!r}")
        return [int(x) if x.is_integer() else x for x in n[:count]]
    return parse


def cadence(text):
    """'Mon–Fri, 1 short per day' -> {'days': [...], 'slots_per_day': 1}"""
    found = re.findall(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*", text)
    if not found:
        raise ValueError(f"no days in {text!r}")
    if len(found) == 2 and re.search(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s*[–—-]\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)", text):
        a, b = DAYS.index(found[0]), DAYS.index(found[1])
        days = DAYS[a:b + 1]
    else:
        days = [d for d in DAYS if d in found]
    per_day = re.search(r"(\d+)\s*\w*\s*per day", text)
    return {"days": days, "slots_per_day": int(per_day.group(1)) if per_day else 1}


def too_close(text):
    """'8%, or any identical run of 10+ words' -> {'too_close_pct': 8, 'max_run': 10}"""
    n = numbers(text)
    out = {"too_close_pct": n[0]}
    if len(n) > 1:
        out["max_run"] = int(n[1])
    return out


def on_off(text):
    word = first_word(text).lower()
    if word in ("on", "yes", "true", "enabled"):
        return True
    if word in ("off", "no", "false", "disabled"):
        return False
    raise ValueError(f"expected On or Off in {text!r}")


# Engine Settings row label (case-insensitive, prefix match) -> (settings key, parser).
# A parser returning a dict sets several keys under the key's section.
OVERRIDES = {
    "auto-shortlist if fit score": ("review.auto_shortlist", first_number),
    "dedupe: merge if confidence": ("review.merge_confidence", first_number),
    "dedupe: flag if confidence": ("review.flag_confidence", first_number),
    "weights: outlier / velocity / engagement / recurrence": ("trend.weights", number_list(4)),
    "caps: outlier / velocity / engagement / recurrence": ("trend.caps", number_list(4)),
    "thresholds: outlier / velocity / engagement / recurrence": ("trend.thresholds", number_list(4)),
    "candidate if trend score": ("trend.candidate_score", first_number),
    "baseline = median of last n posts": ("trend.baseline_posts", first_number),
    "similarity: review if shared 5-grams": ("similarity.review_pct", first_number),
    "similarity: too close if shared 5-grams": ("similarity", too_close),
    "lookback window (days)": ("scan.lookback_days", first_number),
    "max posts per creator per scan": ("scan.max_posts_per_creator", first_number),
    "max creators per run": ("scan.max_creators_per_run", first_number),
    "minimum post age (hours)": ("scan.min_post_age_hours", first_number),
    "whisper model": ("fetch.whisper_model", first_word),
    "cadence": ("cadence", cadence),
    "brand-fit pass threshold": ("brand_fit.threshold", first_number),
    "post-date offset (days)": ("post_date.offset_days", first_number),
    "post-date base": ("post_date.base", first_word),
    "news candidates per day": ("caps.news_radar", first_number),
    "production extras": ("production.extras", on_off),
    "default length (s)": ("script.length_s", number_list(2)),
}


class Settings:
    def __init__(self, data, sources=None):
        self.data = data
        self.sources = sources or {}

    def get(self, key, default=None):
        node = self.data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def __getitem__(self, key):
        value = self.get(key, _MISSING)
        if value is _MISSING:
            raise KeyError(key)
        return value

    def set(self, key, value, source):
        parts = key.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        self.sources[key] = source

    def source_of(self, key):
        parts = key.split(".")
        for i in range(len(parts), 0, -1):
            if ".".join(parts[:i]) in self.sources:
                return self.sources[".".join(parts[:i])]
        return "file"

    def flat(self):
        out = {}

        def walk(prefix, node):
            for k, v in node.items():
                key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    walk(key, v)
                else:
                    out[key] = v
        walk("", self.data)
        return out

    def apply_rows(self, rows):
        """Apply [label, value] rows from Engine Settings tables. Returns (applied, errors)."""
        applied, errors = [], []
        for row in rows:
            if len(row) < 2 or not row[0].strip():
                continue
            label, value = row[0].strip(), row[1].strip()
            match = next((k for k in OVERRIDES if label.lower().startswith(k)), None)
            if not match or not value:
                continue
            key, parse = OVERRIDES[match]
            try:
                parsed = parse(value)
            except ValueError as e:
                errors.append(f"Engine Settings '{label}': {e}; using {key} from file")
                continue
            if isinstance(parsed, dict):
                for sub, v in parsed.items():
                    self.set(f"{key}.{sub}", v, f"notion:{label}")
            else:
                self.set(key, parsed, f"notion:{label}")
            applied.append(key)
        return applied, errors


_MISSING = object()


def load(path=CONFIG / "settings.toml"):
    with open(path, "rb") as f:
        return Settings(tomllib.load(f))


def load_ids(path=CONFIG / "notion_ids.toml"):
    with open(path, "rb") as f:
        return tomllib.load(f)


def save_db_ids(key, database, data_source, path=CONFIG / "notion_ids.toml"):
    """Record a database created by the engine (idempotent: an existing key is left alone)."""
    path = Path(path)
    if key in tomllib.loads(path.read_text(encoding="utf-8")).get("databases", {}):
        return False
    with open(path, "a", encoding="utf-8") as f:
        f.write(f'\n[databases.{key}]\ndatabase = "{database}"\ndata_source = "{data_source}"\n')
    return True


def load_with_notion(notion, ids=None, path=CONFIG / "settings.toml"):
    """Defaults from file, overridden by the Engine Settings page. Errors are returned, not raised,
    so a broken Notion row never stops a run."""
    settings = load(path)
    ids = ids or load_ids()
    errors = []
    try:
        rows = notion.page_table_rows(ids["pages"]["engine_settings"])
    except Exception as e:  # noqa: BLE001 - settings must degrade to file values
        return settings, [f"Couldn't read Engine Settings ({e}); using file values only"]
    _, errors = settings.apply_rows(rows)
    return settings, errors


def snapshot(settings):
    """Small dict for the Run Log: only values that came from Notion, plus models."""
    return {k: v for k, v in settings.flat().items()
            if settings.source_of(k) != "file" or k.startswith("claude.models")}

