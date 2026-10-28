"""Change one value on the Engine Settings page (dry-run unless --apply)."""
from services import props as P
from services.plan import ChangeSet

WRITES = True


def add_arguments(p):
    p.add_argument("label", help='row label, or its start, e.g. "Production extras"')
    p.add_argument("value", help="new value, e.g. On")


def run(ctx):
    cs = ChangeSet("settings-set")
    page = ctx.ids["pages"]["engine_settings"]
    want = ctx.args.label.strip().lower()
    matches = [(b, cells) for b, cells in ctx.notion.table_row_blocks(page) if cells and cells[0].strip().lower().startswith(want)]
    if not matches:
        raise ValueError(f"No Engine Settings row starts with '{ctx.args.label}'")
    if len(matches) > 1:
        raise ValueError("Several rows match: " + "; ".join(c[0] for _, c in matches) + ". Use more of the label.")
    block, cells = matches[0]
    if len(cells) > 1 and cells[1].strip() == ctx.args.value.strip():
        cs.skip(cells[0], f"already '{ctx.args.value}'")
    else:
        new = [P._chunks(c, 1) for c in cells]
        new[1] = P._chunks(ctx.args.value, 1)
        cs.block("engine_settings", f"setting:{cells[0]}", block["id"], {"table_row": {"cells": new}},
                 {"row": cells[0], "from": cells[1] if len(cells) > 1 else "", "to": ctx.args.value})
    return ctx.execute(cs)
