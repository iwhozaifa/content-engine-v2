"""Diff schema/target.json against live Notion and build additive changes.

Only ever adds: missing databases, missing properties, missing select options, missing Engine
Settings rows and Brand Profile sections. A property whose live type differs from the target is
reported as a conflict and left alone. Nothing is removed or renamed.
"""
import json
from pathlib import Path

from services.notion import plain

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "schema" / "target.json"
SELECTS = ("select", "multi_select")


def load_target(path=TARGET):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def property_payload(spec, ids):
    """Notion API body for one target property. Returns None if a relation's target DB doesn't exist yet."""
    t = spec["type"]
    if t in SELECTS:
        return {t: {"options": [{"name": n} for n in spec.get("options", [])]}}
    if t == "number":
        return {"number": {"format": spec.get("format", "number")}}
    if t == "relation":
        target = ids["databases"].get(spec["db"], {}).get("data_source")
        if not target:
            return None
        if spec.get("synced"):
            return {"relation": {"data_source_id": target, "type": "dual_property",
                                 "dual_property": {"synced_property_name": spec["synced"]}}}
        return {"relation": {"data_source_id": target, "type": "single_property", "single_property": {}}}
    if t == "rollup":
        return {"rollup": {"relation_property_name": spec["relation"], "rollup_property_name": spec["property"],
                           "function": spec["function"]}}
    return {t: {}}


def diff_properties(target_props, live_props, ids):
    """-> (add: {name: payload}, options: {name: payload}, pending: [names], conflicts: [str])."""
    add, options, pending, conflicts = {}, {}, [], []
    for name, spec in target_props.items():
        live = live_props.get(name)
        if live is None:
            payload = property_payload(spec, ids)
            if payload is None:
                pending.append(name)
            else:
                add[name] = payload
            continue
        if live["type"] != spec["type"]:
            conflicts.append(f"{name}: live type {live['type']}, target {spec['type']} (left as is)")
            continue
        if spec["type"] in SELECTS:
            have = live[live["type"]].get("options", [])
            names = {o["name"] for o in have}
            missing = [n for n in spec.get("options", []) if n not in names]
            if missing:
                keep = [{"id": o["id"], "name": o["name"]} for o in have]
                options[name] = {spec["type"]: {"options": keep + [{"name": n} for n in missing]}}
    return add, options, pending, conflicts


def create_database_body(spec, parent_page_id, ids):
    """Body for POST /databases: every non-relation property (relations are added in a second pass)."""
    props = {name: property_payload(s, ids) for name, s in spec["properties"].items() if s["type"] != "relation"}
    return {"parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": spec["title"]}}],
            "initial_data_source": {"properties": props}}


def heading_texts(blocks):
    return {plain(b[b["type"]].get("rich_text")).strip().lower()
            for b in blocks if b["type"] in ("heading_1", "heading_2", "heading_3")}


def text(content):
    return [{"type": "text", "text": {"content": content}}]


def settings_rows_block(heading, rows):
    table_rows = [{"type": "table_row", "table_row": {"cells": [text(a), text(b)]}}
                  for a, b in [("Setting", "Value"), *rows]]
    return [{"type": "heading_2", "heading_2": {"rich_text": text(heading)}},
            {"type": "table", "table": {"table_width": 2, "has_column_header": True, "has_row_header": False,
                                        "children": table_rows}}]


def section_blocks(sections):
    out = []
    for heading, body in sections:
        out.append({"type": "heading_2", "heading_2": {"rich_text": text(heading)}})
        out.append({"type": "paragraph", "paragraph": {"rich_text": text(body)}})
    return out
