# Content Engine v2 (Claude Code + Notion)

This folder runs Aliyan's content engine. Notion is the database and UI; Claude Code (and Claude Cowork for browsing) does the work.

Read these before every task:
- **Engine Settings** (Notion page): thresholds, lengths, platforms, what's switched on.
- **Brand Voice & Style Guide** (Notion page): how scripts sound. Rules in its "Rules learned" section are mandatory.
- **docs/brand/Aliyan_AI_Content_DNA.md**: niche, audience, pillars and weights, content jobs, growth phase, guardrails. If the Notion copy has a newer version number, use that and tell me to update this file.

Databases: Content Creators, Raw Content, Idea Bank, Scripts, Content Plan, Hook Library, CTA Bank. Check property names with the Notion tools before writing.

Helpers (free, local): `.venv/bin/python cli.py <command>` (the engine CLI, see below), `.venv/bin/python tools/fetch.py <url> ...` (YouTube, Instagram, TikTok: metadata + transcript as JSON), `python3 tools/engine.py canon <url>` (dedupe key) and `python3 tools/engine.py similarity --script a.txt --source b.txt` (originality check). Never use paid APIs or services (LLM steps run through `claude -p` on the Claude subscription; free API keys such as Notion and YouTube Data are fine). Downloaded metadata and transcripts go in `raw/` (gitignored); scratch script files go in `tmp/`.

Rules:
1. Concise, structured output. Tables and short lines. No essays.
2. Take ideas, pains, structure and hook *patterns* from other creators. Never their wording, examples or stories. Never pass a full source transcript into script writing: use the outline and key points.
3. Never invent income, ROI, client results, stats, quotes or personal experiences. If my proof is needed, write ⚠️ CREATOR INPUT REQUIRED and stop.
4. My edits are final. Never reword a line I changed unless I ask.
5. Every idea keeps its Sources relation (provenance).
6. Approval is mine. Don't set an idea to Approved, a script to Approved, or anything Published without my word. /write only runs on ideas I already set to Approved.
7. Scripts are spoken lines only unless Engine Settings "Production extras" is On (switched On 2026-10-28 for engine content cards: B-roll, on-screen text, captions, titles, thumbnails). If it is Off, cards are spoken lines only.
8. If a step fails, record it on the row (Fetch status / Fetch error, or a note), finish the rest, and report what failed at the end.

Slash commands: /migrate (phase 0, once) · /add-url · /score · /plan-week · /cards · /research · /write · /revise · /options · /carousel (/write and /revise remain for Approved ideas outside the weekly plan; /cards is the v3 flow)

## Engine CLI (v3)

`.venv/bin/python cli.py <command>`. **Dry-run is the default**: it prints the ChangeSet and saves it to `logs/`. Nothing is written to Notion without `--apply`, and the Notion client refuses writes otherwise.

| Command | Phase | Writes? |
|---|---|---|
| `ping [--claude]` | P0 | no: checks Notion access, stored IDs, claude CLI |
| `settings-check [--file-only]` | P0 | no: merged settings and their source (file / Engine Settings row) |
| `snapshot-schema [--label x]` | P0 | local files only: `schema/snapshots/<date>/` |
| `migrate-schema [--apply] [--views]` | P1 | schema only, additive (`schema/target.json`) |
| `add-url <url…> [--must-do] [--transcript-file f] [--from-notion]` | P2 | Raw Content, Idea Bank, Content Creators (Suggested) |
| `score [titles…] [--rescore]` | P2 | Idea Bank brand fit + fit score |
| `scan-creators [--creator x] [--state Active]` | P3 | Creator baselines, Raw Content (trend candidates; rich topics queued as Status New) |
| `weekly-plan [--week YYYY-MM-DD]` | P4 | Content Plan slots (Topic Locked, Approval Pending, Suggested post date), Idea Status, Weekly Plans page |
| `generate-cards --locked` / `generate-card <title>` | P5 | Scripts (cards A/B + captions), slot/idea status; also revisions and A/B choices |
| `settings-set <row> <value>` | P5 | one Engine Settings cell |

Layout: `commands/` (one module per CLI command), `services/` (notion, claude, settings, plan, runlog, retry), `prompts/` (`<name>.v<N>.md` + `.schema.json`, never inline prompt strings), `config/` (`settings.toml` defaults, `notion_ids.toml`), `schema/` (Notion schema snapshots), `tests/`.

Conventions:
- Every Notion write goes through a `ChangeSet` keyed by a stable key (canonical URL, idea ID, slot key) so re-runs never duplicate.
- Settings: `config/settings.toml` holds the defaults; whitelisted Engine Settings rows override them (`services/settings.py` OVERRIDES). Add a knob in both places.
- New prompt behaviour = new prompt version file (`.v2.md`); never edit a version that has produced rows.
- Every run appends to `logs/runs.jsonl`; `--apply` runs also write a Run Log row in Notion.
- Secrets live in `.env` only (see `.env.example`).

## Git workflow

- `main` is stable. Work on `feature/p<N>-<short-name>`, `fix/<name>` or `spike/<name>`.
- Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`), small and atomic. Never commit secrets, `raw/`, `cache/`, `logs/`.
- Pre-commit hook (`git config core.hooksPath scripts/hooks`): secret scan + tests.
- Merge to `main` only with: tests green, a dry-run of the affected commands, a diff summary reviewed by me, and my explicit OK. Then squash-merge (`git merge --squash`), tag `v0.<phase+1>.0`, and update CHANGELOG.md and PROGRESS.md.
- Never merge: `spike/*` (unless I promote it), a Notion schema change without a clean dry-run and my OK, failing tests, or anything that regresses `/add-url`.
- Never force-push `main`, rewrite published history, or delete a branch until I say so.
- Schema changes: commit the `schema/snapshots/` before/after with the migration. Rollback = `git revert <squash sha>` + `schema/ROLLBACK.md`.
- Resume work from PROGRESS.md.
