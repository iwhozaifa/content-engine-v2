# Running the engine on a schedule

The engine runs on whichever machine has the repo, `.env` and Claude Code: this WSL box while building, and a Mac or Linux server later. Notion stays the only UI.

## 1. Install on a new machine (Mac or Linux)

```bash
git clone <repo> content-engine && cd content-engine     # or copy the folder
scripts/setup.sh                                          # ffmpeg, .venv, yt-dlp, Whisper, hooks, .env
# fill .env: NOTION_TOKEN (required), YOUTUBE_API_KEY (recommended), ENGINE_COOKIES_FILE (servers)
claude setup-token                                        # servers: paste the token into .env as CLAUDE_CODE_OAUTH_TOKEN
.venv/bin/python cli.py ping --claude                     # every line should say OK
```

On a server the browser login for Instagram isn't available. Export `cookies.txt` from a logged-in browser (a secondary account is safer), copy it to the server and set `ENGINE_COOKIES_FILE=/path/cookies.txt`. Cookies expire every few weeks; when Instagram links start returning Needs Input, refresh the file.

## 2. Schedules

| Job | When (local time) | Command |
|---|---|---|
| reschedule | daily 07:30 | `reschedule --apply` |
| news-radar | daily 08:00 | `news-radar --apply` |
| add-url | daily 09:00 | `add-url --from-notion --apply` (Notion rows you added, pasted transcripts, scanned rich topics) |
| generate-cards | daily 09:30 | `generate-cards --locked --apply` (also revisions and A/B choices) |
| scan-creators | Thu 20:00 | `scan-creators --apply` |
| weekly-plan | Fri 17:00 | `weekly-plan --apply` |

Edit `scheduling/jobs.txt` to change times or jobs. Set the machine's time zone to Asia/Karachi (`sudo timedatectl set-timezone Asia/Karachi`; on a Mac, System Settings → Date & Time), or shift the hours.

```bash
scheduling/install.sh                       # prints what it would install (systemd on Linux, launchd on Mac)
scheduling/install.sh --apply               # installs
scheduling/install.sh --apply --dry-run-commands   # rehearsal: schedules run, nothing is written to Notion
scheduling/install.sh cron --apply          # crontab instead of systemd
scheduling/install.sh --remove --apply      # uninstall
loginctl enable-linger $USER                # Linux servers: keep timers running while logged out
```

Windows (this dev box): `powershell -ExecutionPolicy Bypass -File scheduling\windows\register-tasks.ps1` prints the tasks; add `-Apply` to register them (they run `wsl.exe … scheduling/run.sh`). The PC must be on.

GitHub Actions (optional, `.github/workflows/scheduled.yml`) runs reschedule, news-radar and weekly-plan, which need no Whisper or cookies. It stays off until you set the repository variable `ENGINE_ACTIONS=on` and the secrets `NOTION_TOKEN` and `CLAUDE_CODE_OAUTH_TOKEN`.

Every scheduled run goes through `scheduling/run.sh`, which:
- runs one copy of each command at a time;
- appends output to `logs/cron/<command>.log` (rotated at 1 MB);
- prunes changesets older than 30 days.

Each run also appends to `logs/runs.jsonl`. `--apply` runs also add a row to the Notion **Run Log**.

## 3. Notifications (optional, free)

1. Telegram: message @BotFather → `/newbot` → copy the token into `.env` as `TELEGRAM_BOT_TOKEN`. Send your bot any message, then open `https://api.telegram.org/bot<token>/getUpdates` and copy `chat.id` into `TELEGRAM_CHAT_ID`.
   Email instead: set `notify.channel = "email"` in `config/settings.toml` and the `SMTP_*` / `NOTIFY_EMAIL_TO` values.
2. `cli.py settings-set "Notifications" On --apply`. If the row doesn't exist yet, add a row "Notifications | On" to the Engine Settings table.
3. `cli.py notify-test --apply`.

You get one message per `--apply` run that changed something or failed, with a link to the Notion database to act on.

## 4. Cost and limits

LLM steps run through `claude -p` on your Claude subscription; no API key and no per-call bill. The Run Log's "Est. cost" is the API-equivalent figure Claude Code reports, which is useful for spotting runaway runs. Caps per run are in `config/settings.toml` `[caps]`. Models per task are in `[claude.models]` (Haiku for judging, Sonnet for writing). Prompt results are cached in `cache/llm/`, so a dry-run followed by `--apply` calls Claude once.

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `Notion 401` | NOTION_TOKEN missing or wrong in `.env` |
| `Notion 404` on a page or database | Content Engine page → ••• → Connections → add the integration |
| `KeyError: 'news_candidates'` … | `cli.py migrate-schema --apply` (creates the missing database and records its ID) |
| `Claude Code isn't signed in` | Run `claude` once and `/login`, or set `CLAUDE_CODE_OAUTH_TOKEN` |
| YouTube "Sign in to confirm you're not a bot" | Log in to YouTube in the browser yt-dlp reads, or set `ENGINE_COOKIES_FILE`; the link becomes Needs Input meanwhile |
| Instagram links all fail | Same as above, for Instagram |
| A scan shows `Scan error` on a creator | The message says why; the next scan retries |
| Something looks wrong after a run | `logs/changeset-<command>-*.json` lists every change; Notion page history restores a row |

Roll back a release: `git revert <squash commit>` on `main`. For schema, see `schema/ROLLBACK.md`.
