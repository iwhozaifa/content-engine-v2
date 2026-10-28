"""Bring Notion up to schema/target.json (additive only; dry-run unless --apply)."""
from services import schema as sch
from services import settings as settings_mod
from services.plan import ChangeSet
from services.settings import OVERRIDES

WRITES = True

VIEWS = """Views to add by hand (the Notion API can't create views):
  Content Plan  · Calendar by Date · Board by Status · Table "This week" (Date is this week, sorted by Date)
                · Table "Awaiting approval" (Approval = Pending, Topic locked = checked)
  Idea Bank     · Table "Slot pool" (Status is Shortlisted/Approved, Brand fit pass = checked, sorted by Review rank)
                · Table "Needs Input" (Status = Needs Input)
  News Candidates · Table "Pending" (Approval = Pending, sorted by Found at desc)
  Scripts       · Table "Cards" (Status is Card Ready/Script Chosen)
  Run Log       · Table sorted by Started desc"""


def add_arguments(p):
    p.add_argument("--target", default=str(sch.TARGET), help="target schema JSON")
    p.add_argument("--views", action="store_true", help="print the manual view checklist")


def run(ctx):
    target = sch.load_target(ctx.args.target)
    cs = ChangeSet("migrate-schema")
    conflicts = []

    # 1. Missing databases (relations come in pass 2, once every database exists).
    for key, spec in target["databases"].items():
        if key in ctx.ids["databases"] or "title" not in spec:
            continue
        parent = ctx.ids["pages"][spec["parent"]]
        cs.database(key, f"db:{key}", sch.create_database_body(spec, parent, ctx.ids),
                    {"create database": spec["title"], "properties": len(spec["properties"])},
                    after=_remember(ctx, key))
    if ctx.apply and cs.changes:
        for e in cs.apply(ctx.notion, ctx.ids):
            ctx.log.error(e)

    # 2. Missing properties and select options.
    for key, spec in target["databases"].items():
        db = ctx.ids["databases"].get(key)
        if not db:
            for name, p in spec["properties"].items():
                if p["type"] == "relation":
                    cs.skip(f"{key}.{name}", f"relation added once {key} exists (next pass of --apply)")
            continue
        live = ctx.notion.get_data_source(db["data_source"])["properties"]
        add, options, pending, bad = sch.diff_properties(spec["properties"], live, ctx.ids)
        conflicts += [f"{key}.{c}" for c in bad]
        # Rollups need their relation and source property to exist first: add them in their own change.
        rollups = {n: v for n, v in add.items() if "rollup" in v}
        plain = {n: v for n, v in add.items() if n not in rollups}
        if plain:
            cs.schema(key, f"props:{key}", {"properties": plain}, {"add": sorted(plain)})
        for name, body in options.items():
            new = [o["name"] for o in body[next(iter(body))]["options"] if "id" not in o]
            cs.schema(key, f"options:{key}.{name}", {"properties": {name: body}}, {"options": f"{name} + {new}"})
        if rollups:
            cs.schema(key, f"rollups:{key}", {"properties": rollups}, {"add": sorted(rollups)})
        for name in pending:
            cs.skip(f"{key}.{name}", f"relation target {spec['properties'][name]['db']} doesn't exist yet")

    # 3. Engine Settings rows and Brand Profile sections (appended only when missing).
    pages = target.get("pages", {})
    if "engine_settings" in pages:
        page = ctx.ids["pages"]["engine_settings"]
        labels = [r[0].strip().lower() for r in ctx.notion.page_table_rows(page) if r and r[0].strip()]
        missing = [row for row in pages["engine_settings"]["rows"] if not _has_label(row[0], labels)]
        if missing:
            cs.blocks("engine_settings", "page:engine_settings.rows", page,
                      sch.settings_rows_block(pages["engine_settings"]["heading"], missing),
                      {"append rows": [r[0] for r in missing]})
    if "brand_profile" in pages:
        page = ctx.ids["pages"]["brand_profile"]
        have = sch.heading_texts(list(ctx.notion.children(page)))
        missing = [s for s in pages["brand_profile"]["sections"] if s[0].lower() not in have]
        if missing:
            cs.blocks("brand_profile", "page:brand_profile.sections", page, sch.section_blocks(missing),
                      {"append sections": [s[0] for s in missing]})

    for c in conflicts:
        ctx.log.warn(c)
    ctx.execute(cs)
    if ctx.args.views or any(c.op == "database" for c in cs.changes):
        ctx.out(VIEWS)
    return cs


def _has_label(label, labels):
    """Same matching as settings.apply_rows: a live row counts if it starts with the label's override key."""
    key = next((k for k in OVERRIDES if label.lower().startswith(k)), label.lower())
    return any(l.startswith(key) for l in labels)


def _remember(ctx, key):
    def after(change):
        db = ctx.notion.get_database(change.result_id)
        source = db["data_sources"][0]["id"]
        settings_mod.save_db_ids(key, change.result_id, source)
        ctx.ids["databases"][key] = {"database": change.result_id, "data_source": source}
    return after
