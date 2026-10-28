# Progress

Plan: phases P0–P8 (see CLAUDE.md for the workflow). Update this file at the end of every phase or session.

| Phase | Branch | Status | Tag |
|---|---|---|---|
| Baseline | main | Done | v0.1.0 |
| P0 Foundation | feature/p0-foundation | Merged | v0.2.0 |
| P1 Notion schema | feature/p1-notion-schema | Not started | |
| P2 Must-Do + brand fit | feature/p2-mustdo-brandfit | Not started | |
| P3 Creator scan | feature/p3-creator-scan | Not started | |
| P4 Weekly plan + topic locking | feature/p4-weekly-plan | Not started | |
| P5 Content cards | feature/p5-content-cards | Not started | |
| P6 News radar | feature/p6-news-radar | Not started | |
| P7 Approval + reschedule | feature/p7-reschedule | Not started | |
| P8 Scheduling, notifications, hardening | feature/p8-scheduling-hardening | Not started | |

## Waiting on you
| Item | Needed for | Status |
|---|---|---|
| YouTube login in Firefox (or `ENGINE_COOKIES_FILE`) | `tools/fetch.py` on this machine: YouTube currently answers "Sign in to confirm you're not a bot" (same before and after the reorg) | open |

## Decisions (2026-10-28)
- Standing OK: each phase merges once tests are green, the live dry-run is clean and the diff summary is below. Additive Notion schema changes and `[engine-test]` rows are applied without asking. Notion renames/deletes wait for you.
- LLM via `claude -p` (subscription), no API key. Dev on WSL; production on Mac or a Linux server.
- Weekly plan pool: Must-Do → approved news → Shortlisted/Approved creator ideas passing brand fit.
- Settings: config file defaults + Engine Settings overrides.
- Post date = slot Date + 3 days (configurable `post_date.base`). Brand Profile = extended DNA page.
- Must-Do never bumps a locked topic. Cards are generated while Approval is Pending; Approval gates "Ready to Post".

## P0 log
- Done: git baseline (v0.1.0), CLI, services, prompts dir, config, tests (47 passing), secret-scan hook, docs.
- Live check 2026-10-28: `ping` OK on 4 pages + 7 databases; `settings-check` read 18 Engine Settings rows with no errors; pre-P1 schema snapshot saved in `schema/snapshots/2026-10-28-pre-p1/`.
- Reorg: files sorted into `tools/`, `docs/`, `scripts/`; all paths updated; 48 tests pass; `ping` OK.
- Diff (P0 → main): 11 commits, CLI + services + config + docs + tests; existing files only moved or path-updated.
- Note: `claude` isn't on PATH in WSL; the runner falls back to the VS Code extension's bundled binary. On a server, install Claude Code and set CLAUDE_CODE_OAUTH_TOKEN.
