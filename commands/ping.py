"""Check Notion access and the stored IDs (read-only). --claude also runs a tiny claude -p call."""
from services.notion import NotionError, plain


def add_arguments(p):
    p.add_argument("--claude", action="store_true", help="also check the claude CLI with one small call")


def run(ctx):
    n = ctx.notion
    ctx.out(f"{'name':<18} {'status':<8} detail")
    for name, page_id in ctx.ids["pages"].items():
        try:
            page = n.get_page(page_id)
            title = next((plain(p["title"]) for p in page["properties"].values() if p["type"] == "title"), "")
            ctx.out(f"{name:<18} {'OK':<8} {title}")
        except NotionError as e:
            ctx.out(f"{name:<18} {'FAIL':<8} {e}")
            ctx.log.error(f"page {name}: {e}")
    for name, db in ctx.ids["databases"].items():
        try:
            info = n.get_database(db["database"])
            sources = [s["id"] for s in info.get("data_sources", [])]
            title = plain(info.get("title"))
            stored = db.get("data_source")
            if stored and stored not in sources:
                note = f"stored data_source {stored} not in {sources}"
                ctx.log.warn(f"{name}: {note}")
            else:
                ds = n.get_data_source(stored or sources[0])
                note = f"{len(ds.get('properties', {}))} properties" + ("" if stored else f" · data_source {sources[0]} (add to notion_ids.toml)")
            ctx.out(f"{name:<18} {'OK':<8} {title} · {note}")
        except NotionError as e:
            ctx.out(f"{name:<18} {'FAIL':<8} {e}")
            ctx.log.error(f"database {name}: {e}")
    if ctx.args.claude:
        r = ctx.claude.run("ping", {"word": "engine"})
        ctx.out(f"{'claude':<18} {'OK':<8} {r.model} → {r.output} ({'cached' if r.cached else f'${r.cost_usd:.4f}'})")
    return None
