# Changelog

All notable changes. Format: [Keep a Changelog](https://keepachangelog.com), versions tagged per merged phase.

## [Unreleased]

## [0.6.0] - 2026-10-28 (P4 weekly plan)

### Added
- `weekly-plan`: slot maths from cadence, fill order Must-Do → approved news → creator ideas, topic locking, Suggested post date (slot date + offset, configurable base), Weekly Plans page, idempotent re-runs, Must-Do overflow reporting.
- `services/slots.py`.

## [0.5.0] - 2026-10-28 (P3 creator scan)

### Added
- `scan-creators`: baselines (median of last N, respects Lock baseline), Engine trend score from configurable weights/caps/thresholds, rich topics via `trend_judge.v1`, recurrence across creators, Scan error on failure.
- `services/trend.py`, `services/sources.py` (YouTube Data API or yt-dlp; Instagram/TikTok via yt-dlp).
- `add-url --from-notion` turns scanned rich topics into ideas (Origin = Creator scan, Rich topic ticked).

### Changed
- A failed fetch for a non-Must-Do link creates the Raw Content row only (Needs Input), as the original /add-url did; Must-Do links also get a Needs Input idea.

## [0.4.0] - 2026-10-28 (P2 Must-Do URLs + brand fit)

### Added
- `add-url`: Must-Do priority, canonical-URL dedupe, Needs Input on fetch failure with resume from a pasted transcript (`--from-notion`), topic merge/flag, brand fit + fit score, outline-only idea pages.
- `score`: brand fit 0–10, reason, pass/fail (threshold from Engine Settings), transformative angle, fit score.
- Prompts `idea_extract.v1`, `brand_fit.v1`; `services/brand.py`, `services/ingest.py` (fetch cache in `raw/fetch/`), `services/props.py`.
- `tools/fetch.py` uses `ENGINE_COOKIES_FILE` (cookies.txt) when set, for servers without a browser.

### Changed
- `/add-url` and `/score` slash commands call the CLI.

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
