"""Print the merged settings (file defaults + Engine Settings overrides) and where each came from."""
import os


def add_arguments(p):
    p.add_argument("--file-only", action="store_true", help="skip Notion; show config/settings.toml values")


def run(ctx):
    if not ctx.args.file_only and os.environ.get("NOTION_TOKEN"):
        ctx.load_notion_settings()
    elif not ctx.args.file_only:
        ctx.log.warn("NOTION_TOKEN not set: showing file values only")
    s = ctx.settings
    ctx.out(f"{'setting':<34} {'value':<34} source")
    for key, value in s.flat().items():
        ctx.out(f"{key:<34} {str(value):<34} {s.source_of(key)}")
    return None
