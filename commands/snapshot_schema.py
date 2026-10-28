"""Save every database's live schema to schema/snapshots/<date>/ (read-only on Notion)."""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def add_arguments(p):
    p.add_argument("--label", default="", help="suffix for the snapshot folder, e.g. pre-p1")


def normalize(prop):
    """Keep what defines a property; drop volatile ids/urls so snapshots diff cleanly."""
    t = prop["type"]
    out = {"type": t}
    body = prop.get(t) or {}
    if t in ("select", "multi_select", "status"):
        out["options"] = [o["name"] for o in body.get("options", [])]
    elif t == "relation":
        out["data_source_id"] = body.get("data_source_id")
        out["kind"] = body.get("type")
    elif t == "formula":
        out["expression"] = body.get("expression")
    elif t == "rollup":
        out.update({k: body.get(k) for k in ("relation_property_name", "rollup_property_name", "function")})
    elif t == "number":
        out["format"] = body.get("format")
    return out


def snapshot(notion, ids):
    result = {}
    for name, db in ids["databases"].items():
        source = db.get("data_source") or notion.get_database(db["database"])["data_sources"][0]["id"]
        ds = notion.get_data_source(source)
        result[name] = {"database": db["database"], "data_source": source,
                        "title": "".join(t.get("plain_text", "") for t in ds.get("title", [])),
                        "properties": {k: normalize(v) for k, v in sorted(ds["properties"].items())}}
    return result


def run(ctx):
    data = snapshot(ctx.notion, ctx.ids)
    folder = ROOT / "schema" / "snapshots" / (date.today().isoformat() + (f"-{ctx.args.label}" if ctx.args.label else ""))
    folder.mkdir(parents=True, exist_ok=True)
    for name, schema in data.items():
        (folder / f"{name}.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ctx.out(f"{name:<18} {len(schema['properties'])} properties → {folder.relative_to(ROOT)}/{name}.json")
    return None
