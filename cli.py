#!/usr/bin/env python3
"""Content engine CLI. Dry-run by default: nothing is written to Notion without --apply.

  .venv/bin/python cli.py ping [--claude]       check Notion access (and the claude CLI)
  .venv/bin/python cli.py settings-check        merged settings and where each value came from
  .venv/bin/python cli.py snapshot-schema       save live Notion schemas to schema/snapshots/
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
        ctx.log.error(f"{type(e).__name__}: {e}")
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
    out(ctx.log.summary())
    if ctx.log.errors and code == 0:
        code = 2
    return code


if __name__ == "__main__":
    sys.exit(main())
