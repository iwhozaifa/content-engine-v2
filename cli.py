#!/usr/bin/env python3
"""Content engine CLI. Dry-run by default: nothing is written to Notion without --apply.

  .venv/bin/python cli.py ping [--claude]       check Notion access (and the claude CLI)
  .venv/bin/python cli.py settings-check        merged settings and where each value came from
  .venv/bin/python cli.py snapshot-schema       save live Notion schemas to schema/snapshots/
  .venv/bin/python cli.py migrate-schema        add what schema/target.json needs (additive)
  .venv/bin/python cli.py add-url <url> [--must-do]   links -> Raw Content + Idea Bank (brand fit, dedupe)
  .venv/bin/python cli.py score                 (re)score ideas: brand fit, pass/fail, fit score
  .venv/bin/python cli.py scan-creators         Active creators -> baselines, trend scores, rich topics
  .venv/bin/python cli.py weekly-plan           fill next week's slots, lock topics, Weekly Plans page
  .venv/bin/python cli.py generate-cards --locked   A/B content cards for locked topics (+ revisions, choices)
  .venv/bin/python cli.py settings-set <row> <value>  change one Engine Settings value
  .venv/bin/python cli.py news-radar            RSS -> News Candidates (Pending); Approved -> ideas
  .venv/bin/python cli.py reschedule            Postponed -> next open slot; Rejected -> slot freed; Approved -> Ready to Post
  .venv/bin/python cli.py notify-test           send a test notification (Telegram or email)
"""
import argparse
import importlib
import sys

from services import settings as settings_mod
from services.runlog import RunLog

COMMANDS = {
    "ping": "commands.ping",
    "settings-check": "commands.settings_check",
    "snapshot-schema": "commands.snapshot_schema",
    "migrate-schema": "commands.migrate_schema",
    "add-url": "commands.add_url",
    "score": "commands.score",
    "scan-creators": "commands.scan_creators",
    "weekly-plan": "commands.weekly_plan",
    "generate-card": "commands.generate_cards",
    "generate-cards": "commands.generate_cards",
    "settings-set": "commands.settings_set",
    "news-radar": "commands.news_radar",
    "reschedule": "commands.reschedule",
    "notify-test": "commands.notify_test",
}


class Context:
    """What a command gets: settings, Notion IDs, clients (built lazily) and the run log."""

    def __init__(self, args, out=print):
        self.args = args
        self.apply = getattr(args, "apply", False)
        self.out = out
        self.ids = settings_mod.load_ids()
        self.settings = settings_mod.load()
        self.settings_errors = []
        self._notion = None
        self._claude = None
        self.log = None

    @property
    def notion(self):
        if self._notion is None:
            from services.notion import Notion
            self._notion = Notion.from_settings(self.settings, writable=self.apply,
                                                log=lambda m: self.out(f"  … {m}"))
        return self._notion

    @property
    def claude(self):
        if self._claude is None:
            from services.claude import Claude
            self._claude = Claude(self.settings)
        return self._claude

    def execute(self, changes):
        """Print the ChangeSet, save it to logs/, and apply it when --apply was given."""
        if self.apply and changes.changes:
            for e in changes.apply(self.notion, self.ids):
                self.log.error(e)
        self.out(changes.render())
        path = changes.save()
        self.out(f"  saved {path.relative_to(settings_mod.ROOT) if path.is_relative_to(settings_mod.ROOT) else path}")
        return changes

    def load_notion_settings(self):
        self.settings, self.settings_errors = settings_mod.load_with_notion(self.notion, self.ids)
        return self.settings


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    for name, module in COMMANDS.items():
        mod = importlib.import_module(module)
        sp = sub.add_parser(name, help=mod.__doc__.splitlines()[0])
        if getattr(mod, "WRITES", False):
            sp.add_argument("--apply", action="store_true", help="write to Notion (default: dry-run)")
        sp.add_argument("--limit", type=int, help="max items this run")
        mod.add_arguments(sp)
        sp.set_defaults(module=mod)
    return p


def main(argv=None, out=print):
    settings_mod.load_env()
    args = build_parser().parse_args(argv)
    ctx = Context(args, out)
    ctx.log = RunLog(args.command, ctx.apply, ctx.settings)
    code = 0
    try:
        changes = args.module.run(ctx)
    except KeyboardInterrupt:
        ctx.log.error("interrupted")
        changes, code = None, 130
    except Exception as e:  # noqa: BLE001 - every failure lands in the run log with a clear message
        ctx.log.error(f"{type(e).__name__}: {e}{hint(e, ctx)}")
        changes, code = None, 1
    for w in ctx.settings_errors:
        ctx.log.warn(w)
    ctx.log.settings = ctx.settings
    ctx.log.finish(changes.counts() if changes else {}, ctx._claude)
    ctx.log.write_local()
    if ctx.apply and changes is not None:
        try:
            ctx.log.write_notion(ctx.notion, ctx.ids)
        except Exception as e:  # noqa: BLE001
            out(f"  ! Run Log row not written: {e}")
    if ctx.apply:
        notify_run(ctx, out)
    out(ctx.log.summary())
    if ctx.log.errors and code == 0:
        code = 2
    return code


def hint(e, ctx):
    """Turn the common setup mistakes into a next step."""
    if isinstance(e, KeyError) and e.args and e.args[0] not in ctx.ids.get("databases", {}):
        return " (not in config/notion_ids.toml: run `cli.py migrate-schema --apply` to create it, or `cli.py ping`)"
    return ""


def notify_run(ctx, out):
    from services import notify
    try:
        if notify.should_send(ctx.settings, ctx.log):
            notify.send(ctx.settings, notify.message(ctx.log, ctx.ids))
    except Exception as e:  # noqa: BLE001 - a failed notification never fails the run
        out(f"  ! notification not sent: {e}")


if __name__ == "__main__":
    sys.exit(main())
