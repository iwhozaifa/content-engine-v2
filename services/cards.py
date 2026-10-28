"""Content cards: page layout, the engine data block, edit detection and the originality check.

A card page holds both variations as tables (rows labelled A1, A2 … / B1, B2 …), captions, thumbnails and
a toggle "Engine data" with the generated JSON. On a revision, any spoken line on the page that differs
from the JSON is one you edited, so it is passed to the writer as locked.
"""
import json

from services import props as P
from services.notion import plain
from tools.engine import similarity as text_similarity

DATA_TOGGLE = "Engine data (don't edit)"


def ready_to_read(v):
    return "\n".join([v["hook"], *(b["line"] for b in v["beats"]), v["cta"]])


def word_count(text):
    return len(text.split())


def all_text(v):
    """Every line of a variation, alternates included (used for the originality check)."""
    lines = [v["hook"], *v["hook_alts"], v["cta"], v["cta_alt"]]
    for b in v["beats"]:
        lines += [b["line"], *b["alt_lines"]]
    return "\n".join(lines)


def check(v, source_text, settings):
    return text_similarity(all_text(v), source_text or "", settings["similarity.review_pct"],
                           settings["similarity.too_close_pct"], settings["similarity.max_run"])


def _cells(*values):
    return {"type": "table_row", "table_row": {"cells": [P._chunks(str(x or ""), 1) for x in values]}}


def table(header, rows):
    return {"type": "table", "table": {"table_width": len(header), "has_column_header": True,
                                       "has_row_header": False, "children": [_cells(*header), *(_cells(*r) for r in rows)]}}


def variation_blocks(v, sim, extras, wps):
    text = ready_to_read(v)
    words = word_count(text)
    head = ["Beat", "Spoken line", "Alt line 1", "Alt line 2"] + (["B-roll", "On-screen text"] if extras else [])
    rows = []
    for i, b in enumerate(v["beats"], 1):
        rows.append([f"{v['label']}{i}", b["line"], *b["alt_lines"]] + ([b["broll"], b["on_screen"]] if extras else []))
    rows.append([f"{v['label']}-CTA", v["cta"], v["cta_alt"], ""] + (["", ""] if extras else []))
    out = [P.heading(f"Variation {v['label']} · {v['hook_family']}"),
           P.para(f"Angle: {v['angle']}"),
           table(["#", "Hook (first 3 seconds)"], [[f"{v['label']}-H1 ✅", v["hook"]],
                                                   *[[f"{v['label']}-H{i}", h] for i, h in enumerate(v["hook_alts"], 2)]]),
           table(head, rows),
           P.heading("Ready to read", 3), *[P.para(line) for line in text.splitlines()],
           P.para(f"{words} words · ~{round(words / wps)} s · originality: {sim['flag']}"
                  + (f" ({sim['similarity_pct']}% shared 5-grams, longest run {sim['longest_run']})"
                     if sim.get("similarity_pct") is not None else ""))]
    if v["creator_input_required"]:
        out += P.bullets([f"⚠️ CREATOR INPUT REQUIRED: {x}" for x in v["creator_input_required"]])
    return out


def caption_blocks(c):
    yt, ig, tt = c["youtube"], c["instagram"], c["tiktok"]
    return [P.heading("Publishing package"),
            P.heading("YouTube Shorts", 3), *P.bullets([f"Title: {t}" for t in yt["titles"]]),
            P.para(yt["description"]), P.para(" ".join(yt["hashtags"])),
            P.heading("Instagram", 3), P.para(ig["caption"]), P.para(" ".join(ig["hashtags"])),
            P.heading("TikTok", 3), P.para(tt["caption"]), P.para(" ".join(tt["hashtags"])),
            P.heading("Thumbnails", 3), *P.bullets([f"“{t['text']}” · {t['visual']}" for t in c["thumbnails"]])]


def page_blocks(title, variations, sims, captions, judge_notes, data, extras, wps):
    blocks = [P.para(f"{title} · pick one: set Chosen variation = A or B. For changes, write Feedback, "
                     "set Status = Needs revision, and the next generate-cards run makes a new version "
                     "(lines you edited on this page are kept word for word).")]
    for v in variations:
        blocks += variation_blocks(v, sims[v["label"]], extras, wps)
    if captions:
        blocks += caption_blocks(captions)
    if judge_notes:
        blocks += [P.heading("Originality notes", 3), *P.bullets(judge_notes)]
    blocks += [P.heading("Feedback for next version", 3), P.para("(Write notes here or in the Feedback property.)")]
    blocks.append({"type": "toggle", "toggle": {"rich_text": P._chunks(DATA_TOGGLE, 1), "children": [
        {"type": "code", "code": {"language": "json", "rich_text": P._chunks(json.dumps(data, ensure_ascii=False))}}]}})
    return blocks


def read_data(notion, page_id):
    """The generated JSON stored on a card page, or None."""
    for block in notion.children(page_id):
        if block["type"] == "toggle" and plain(block["toggle"]["rich_text"]) == DATA_TOGGLE:
            for child in notion.children(block["id"]):
                if child["type"] == "code":
                    return json.loads(plain(child["code"]["rich_text"]))
    return None


def edited_lines(notion, page_id, data):
    """{row label: text} for spoken lines you changed on the page (compared with the generated JSON)."""
    generated = {}
    for v in data.get("variations", []):
        generated[f"{v['label']}-H1 ✅"] = v["hook"]
        for i, b in enumerate(v["beats"], 1):
            generated[f"{v['label']}{i}"] = b["line"]
        generated[f"{v['label']}-CTA"] = v["cta"]
    edits = {}
    for row in notion.page_table_rows(page_id):
        if len(row) >= 2 and row[0] in generated and row[1].strip() != generated[row[0]].strip():
            edits[row[0]] = row[1].strip()
    return edits

