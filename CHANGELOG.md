# Changelog

All notable changes. Format: [Keep a Changelog](https://keepachangelog.com), versions tagged per merged phase.

## [Unreleased]

## [0.3.0] - 2026-10-28 (P1 Notion schema)

### Added
- `migrate-schema`: diffs `schema/target.json` against live Notion and adds only what is missing (databases, properties, select options, Engine Settings rows, Brand Profile sections). Dry-run by default; idempotent.
- Notion databases: Run Log, News Candidates, Weekly Plans. New properties on Content Creators, Raw Content, Idea Bank, Content Plan, Scripts.
- `schema/ROLLBACK.md`, pre/post-P1 snapshots, manual view checklist (`migrate-schema --views`).

## [0.2.0] - 2026-10-28 (P0 foundation)

### Added
- `cli.py` with dry-run by default and `--apply` for writes; `ping`, `settings-check`, `snapshot-schema`.
- `services/notion.py`: Notion REST client (API 2025-09-03), rate-limited, retries with backoff and Retry-After, read-only unless `--apply`, clear error hints.
- `services/claude.py`: versioned prompt files run through `claude -p`, JSON-schema validated, cached, cost/tokens tracked.
- `services/settings.py`: `config/settings.toml` defaults + Engine Settings page overrides, with the source of each value.
- `services/plan.py` ChangeSet (dry-run table, saved JSON, conflict-safe apply); `services/runlog.py` (local JSONL + Notion Run Log row).
- Secret-scan pre-commit hook; `.env.example`; `tests/` with Notion and Claude fakes.

### Changed
- Tests moved to `tests/`; CLAUDE.md gains the CLI, conventions and git workflow.
- Files sorted into directories: `tools/` (fetch.py, engine.py), `docs/` (getting started, brand DNA, Notion page sources, setup, Cowork), `scripts/setup.sh`.

## [0.1.0] - 2026-10-28
- Baseline import of engine v2: `fetch.py`, `engine.py`, slash commands, Notion page sources.
