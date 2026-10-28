# Progress

Plan: phases P0–P8 (see CLAUDE.md for the workflow). Update this file at the end of every phase or session.

| Phase | Branch | Status | Tag |
|---|---|---|---|
| Baseline | main | Done | v0.1.0 |
| P0 Foundation | feature/p0-foundation | Merged | v0.2.0 |
| P1 Notion schema | feature/p1-notion-schema | Merged | v0.3.0 |
| P2 Must-Do + brand fit | feature/p2-mustdo-brandfit | Merged | v0.4.0 |
| P3 Creator scan | feature/p3-creator-scan | Merged | v0.5.0 |
| P4 Weekly plan + topic locking | feature/p4-weekly-plan | Merged | v0.6.0 |
| P5 Content cards | feature/p5-content-cards | Merged | v0.7.0 |
| P6 News radar | feature/p6-news-radar | Merged | v0.8.0 |
| P7 Approval + reschedule | feature/p7-reschedule | Merged | v0.9.0 |
| P8 Scheduling, notifications, hardening | feature/p8-scheduling-hardening | Merged | v0.10.0 |

## Waiting on you
| Item | Needed for | Status |
|---|---|---|
| YouTube login in Firefox (or `ENGINE_COOKIES_FILE`) | `tools/fetch.py` on this machine: YouTube currently answers "Sign in to confirm you're not a bot" (same before and after the reorg) | open |
| Rename `Hook Library.csv` → `Hook Library`, `CTA Bank.csv` → `CTA Bank` (Notion renames need your OK; the engine uses IDs so nothing depends on it) | Tidiness | open |
| Set State = Active on the creators to scan (only Jack Roberts exists, State = Suggested), ideally 1 YouTube + 1 Instagram + 1 TikTok | P3 done test with real creators | open |
| `YOUTUBE_API_KEY` in `.env` (free, Google Cloud console → YouTube Data API v3) | Faster, more reliable YouTube scans (yt-dlp fallback works without it) | open |
| Review the 5 real News Candidates found 2026-10-28 (Approval = Pending) | Daily news flow | open |
| Pick the production machine (Mac or Linux server), run `scripts/setup.sh`, then `scheduling/install.sh --apply` (docs/operations.md). Nothing is scheduled on this dev box yet | Daily automation | open |
| Optional: Telegram bot token + chat id, then `settings-set "Notifications" On --apply` | Run notifications | open |
| Run `cli.py score --apply` once to add brand fit to your 1 open legacy idea (without brand-fit pass, ideas can't fill slots) | Weekly plan pool | open |
| Add the views listed by `cli.py migrate-schema --views` (API can't create views) | Notion UI | open |
| Fill the 3 new Brand Profile sections on the DNA page (Topics to avoid, Example good/bad ideas) | Better brand-fit scoring | open |

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

## P1 log
- `schema/target.json` + `migrate-schema` (additive only; type conflicts reported, never changed).
- Applied 2026-10-28: created Run Log, News Candidates, Weekly Plans; 12 property/option changes; Engine Settings "Engine v3 settings" table (4 rows); 3 Brand Profile sections.
- Re-run with `--apply` → "nothing to change". Snapshots: `schema/snapshots/2026-10-28-pre-p1` → `-post-p1`. Run Log rows now written to Notion on `--apply`.
- Existing rows/formulas untouched; `/add-url` flow uses only pre-existing properties, so it is unaffected.

## P2 log
- `add-url` (CLI args, `--must-do`, `--transcript-file`, `--from-notion` for Raw Content rows Status New and Needs Input rows with a pasted transcript), `score`. Prompts `idea_extract.v1` (Sonnet), `brand_fit.v1` (Haiku). Fit score uses DNA §11 weights from `[fit_weights]`.
- Brand fit pass = score ≥ `brand_fit.threshold` (Engine Settings) and no blocking red flag; decided in code.
- Failed fetch → Raw Content + idea with Status Needs Input (Priority kept); after a transcript is pasted, `--from-notion` completes the same idea (no duplicate). If it turns out to be the same topic as an open idea, it merges and the placeholder is archived.
- Dedupe: canonical URL (works across rows created by the old slash command), Engine key `url:<canonical>`, and topic duplicates (merge ≥ 0.8, flag ≥ 0.5).
- Live test 2026-10-28: article → Shortlisted (fit 7.5, brand 8 ✓); dead link → Needs Input; pasted transcript → Shortlisted; re-runs → skip only. Test rows archived; one test merge into your real idea was reverted.
- `/add-url` and `/score` are now thin wrappers over the CLI. Raw Content gained a `Priority` property (migrate-schema).
- Not run on your real ideas yet: `cli.py score --apply` will add brand fit to the 1 open legacy idea.

## P3 log
- `services/trend.py` mirrors the Raw Content formulas with weights/caps/thresholds from settings; `services/sources.py` lists posts (YouTube Data API when `YOUTUBE_API_KEY` is set, else yt-dlp; Instagram/TikTok via yt-dlp). `trend_judge.v1` (Haiku) labels rich topics; recurrence = creators per topic label in the lookback window.
- Only trend candidates are stored in Raw Content. Rich topics get Status New (the idea queue for `add-url --from-notion`, Origin = Creator scan); others Status Skipped. Existing rows only get metrics/trend updated.
- Baseline = median of last N posts, unless Lock baseline. Failures go to the creator's `Scan error`.
- Live 2026-10-28 (dry-run, `--state Suggested`, Jack Roberts via yt-dlp): baseline 12,505 views over 10 posts; 4 candidates judged (1 rich); the post already in Raw Content was updated, not duplicated.
- Pending: done test with 3 Active creators (1 per platform) needs your creator choice; Instagram listing needs Firefox login or cookies.

## P4 log
- `weekly-plan`: next week's slots from the cadence (Engine Settings "Cadence"), fill order Must-Do → approved news → Shortlisted/Approved creator ideas that pass brand fit (Approved first, then Review rank / Fit score). One idea per cluster per week (Must-Do exempt). Must-Do never bumps a taken slot; overflow is reported and waits.
- Each placement: Content Plan row (Slot key, Status Topic Locked, Topic locked ✓, Locked at, Approval Pending, Added to calendar, Suggested post date = slot date + offset, rationale), Idea → Topic Locked, Weekly Plans page (`week:<ISO week>`) with the slot list. No scripts.
- Legacy rows without a Slot key still occupy their day. Re-run → no-op.
- Live 2026-10-28 on test week 2027-W01 with 8 `[engine-test]` ideas: order Must-Do, Must-Do, News, Creator 0, Creator 1; brand-fit fail skipped; post dates slot+3; re-run No-op. Test rows kept for the P5/P7 live tests, then archived.

## P5 log
- `generate-cards --locked` / `generate-card <title>`: `script_variations.v1` (Sonnet) writes A and B; code requires different hook families and angles (one retry). `captions.v1` (Haiku) writes YouTube/Instagram/TikTok packages + 3 thumbnail concepts when production extras are On. Originality: `tools/engine.py` similarity first; `similarity_judge.v1` only when flagged.
- Card = Scripts row (Card key `card:<idea>#v<n>`, Plan item, Hook/Angle A/B, flags A/B, Prompt versions) with tables A1…/B1…, ready-to-read, captions, and an "Engine data" toggle holding the generated JSON.
- Chosen variation → card + slot Script Chosen, slot Final script (from the page, your edits included), idea Scripted. Needs revision + Feedback → v+1 (edited lines restored word for word in code), v1 Superseded and unlinked from the slot.
- `settings-set` edits one Engine Settings cell. Production extras switched **On** 2026-10-28 (`cli.py settings-set "Production extras" Off --apply` reverts). CLAUDE.md rule 7 updated to follow that setting.
- Live 2026-10-28 on a test slot: card v1 (A Pain / B Contrarian, B-roll + on-screen, 74 words ≈ 28 s), choosing A → Script Chosen with Final script; re-run No-op.
- `/plan-week` and new `/cards` wrap the CLI. `/write` and `/revise` stay for Approved ideas outside the weekly plan.

## P6 log
- `news-radar`: `config/feeds.toml` (8 feeds, stdlib RSS/Atom parser), last 48 h, dedupe by `news:<canonical URL>`, `news_judge.v1` (Haiku) keeps at most the daily cap (Engine Settings "News candidates per day", counted per day). Rows: Approval Pending, brand fit + reason, angle, urgency, time-sensitive, expires.
- Approved candidates without an idea → Raw Content row (Discovered via News, provenance) + Idea (Origin News, Status Approved, Priority Time-sensitive when flagged, brand fit pass from the threshold, News candidate relation). Rejected never become ideas.
- Live 2026-10-28: 2,417 feed items → 40 new → 5 real candidates written (Pending) across two runs (cap 5/day respected, no duplicates). Test approval → idea + raw created; re-run No-op.
- `/news` slash command wraps the CLI.

## P7 log
- `reschedule`: Postponed → first open slot in a later week (up to 8 weeks ahead; several postponed items get different slots), Original date set once, Date history appended, Suggested post date recomputed, Weekly plan relinked, card kept, Approval → Pending. Rejected → Topic locked off, Slot key cleared (weekly-plan no longer counts Rejected rows), idea → Rejected with reason. Approved + Script Chosen → Ready to Post; Approved without a choice waits.
- Live 2026-10-28 on the test week: postponed slot 2027-01-05 → Mon 2027-01-11 (post 2027-01-14); approved slot with a chosen card → Ready to Post; re-run No-op.
- `/reschedule` slash command wraps the CLI.

## P8 log
- `scheduling/`: `jobs.txt` (6 jobs), `run.sh` (lock per command, log rotation, changeset pruning, PATH for cron/systemd), `install.sh` (systemd user timers / launchd / cron; prints by default, `--apply` installs, `--dry-run-commands` rehearsal, `--remove`), `windows/register-tasks.ps1` (Task Scheduler → wsl.exe), `.github/workflows/scheduled.yml` (opt-in via `ENGINE_ACTIONS=on`).
- Notifications: `services/notify.py` (Telegram or SMTP, free), sent after `--apply` runs that changed something or failed, with a link to the Notion database to act on. Engine Settings row "Notifications" (Off) added; `notify-test`.
- `scripts/setup.sh` now supports macOS (Homebrew) and Ubuntu/Debian, installs requirements, sets the git hook, creates `.env`.
- Error hint for missing database IDs; `docs/operations.md` (server install, schedules, notifications, costs, troubleshooting); README "Your week in Notion".
- Live 2026-10-28: a systemd user timer fired `scheduling/run.sh ping` and `ping --claude` on this box (Notion + Claude OK from the scheduler environment). All `[engine-test]` rows (18) archived. Final dry-run sweep of every command against live Notion: clean.

## Final state (2026-10-28)
All phases P0–P8 merged; 88 tests. Commands: ping, settings-check, snapshot-schema, migrate-schema, add-url, score, scan-creators, weekly-plan, generate-card(s), settings-set, news-radar, reschedule, notify-test. Slash commands /add-url, /score, /plan-week, /cards, /news, /reschedule wrap the CLI.
