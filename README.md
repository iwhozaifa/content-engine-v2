# Content Engine

Notion is the UI and the approval surface. Claude does the work. This repo holds the engine: the URL fetcher, the engine CLI, versioned prompts and the schedules.

- **New here / first install:** see [docs/getting-started.md](docs/getting-started.md) (install, Notion phase 0, the phase 1 done test).
- **Rules every run follows:** [CLAUDE.md](CLAUDE.md).
- **Where the build is:** [PROGRESS.md](PROGRESS.md) · [CHANGELOG.md](CHANGELOG.md).

## Layout

| Path | What |
|---|---|
| `cli.py` | The engine CLI (single entry point) |
| `commands/` | One module per CLI command |
| `services/` | Notion, Claude, settings, ChangeSet, Run Log, retries |
| `prompts/` | Versioned prompts (`<name>.v<N>.md` + `.schema.json`) |
| `config/` | `settings.toml` defaults, `notion_ids.toml` |
| `schema/` | Notion schema target, snapshots, rollback notes |
| `tools/` | Standalone helpers: `fetch.py` (link fetcher), `engine.py` (dedupe key, similarity) |
| `scripts/` | `setup.sh`, git hooks, secret scan |
| `docs/` | Getting started, brand DNA, Notion page sources, setup checklists, Cowork |
| `.claude/commands/` | Slash commands for Claude Code |
| `tests/` | `pytest` suite |
| `raw/ tmp/ cache/ logs/` | Runtime files (gitignored) |

## Setup for the engine CLI

```bash
cp .env.example .env                       # then add NOTION_TOKEN (see comments in the file)
.venv/bin/pip install -r requirements.txt
git config core.hooksPath scripts/hooks    # secret scan + tests before each commit
.venv/bin/python -m pytest                 # should end with "passed"
.venv/bin/python cli.py ping               # Notion access + stored IDs
.venv/bin/python cli.py settings-check     # merged settings and where each came from
```

## How it runs

| Step | Command | Writes to Notion |
|---|---|---|
| Check | `cli.py ping [--claude]` | never |
| Settings | `cli.py settings-check` | never |
| Schema snapshot | `cli.py snapshot-schema --label <x>` | never (local files) |
| Schema migration | `cli.py migrate-schema [--views]` | additive schema changes |
| Add links | `cli.py add-url <url…> [--must-do]` or `--from-notion` | Raw Content + Idea Bank |
| Brand fit | `cli.py score` | Idea Bank scores |
| Creator scan | `cli.py scan-creators`, then `cli.py add-url --from-notion` turns rich topics into ideas | Creators, Raw Content |

Every command is a **dry-run unless you add `--apply`**. A dry-run prints what would change and saves it to `logs/changeset-*.json`. Re-running a command never duplicates rows. Each run is logged to `logs/runs.jsonl` (and to the Notion Run Log with `--apply`).

LLM steps call headless Claude Code (`claude -p`) on your Claude subscription, so no API key is needed. The cost shown in the Run Log is the API-equivalent figure Claude Code reports, not a bill.

## Roll back a phase

1. `git revert <squash commit of the phase>` on `main`.
2. If the phase changed Notion schema, follow `schema/ROLLBACK.md` for that phase (snapshots in `schema/snapshots/`).
