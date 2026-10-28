#!/usr/bin/env bash
# Run one engine command from a scheduler: one at a time per command (lock), output appended to
# logs/cron/<command>.log (rotated at 1 MB, 5 kept), changesets older than 30 days pruned.
# Usage: scheduling/run.sh <cli command> [args...]     e.g. scheduling/run.sh news-radar --apply
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
NAME="${1:?usage: run.sh <command> [args]}"
mkdir -p logs/cron
LOG="logs/cron/$NAME.log"

if [ -f "$LOG" ] && [ "$(wc -c <"$LOG")" -gt 1048576 ]; then
  for i in 4 3 2 1; do [ -f "$LOG.$i" ] && mv "$LOG.$i" "$LOG.$((i + 1))"; done
  mv "$LOG" "$LOG.1"
fi
find logs -maxdepth 1 -name 'changeset-*.json' -mtime +30 -delete 2>/dev/null

LOCK="logs/cron/$NAME.lock"
if command -v flock >/dev/null; then
  exec 9>"$LOCK"
  flock -n 9 || { echo "$(date '+%F %T') $NAME is already running; skipped" >>"$LOG"; exit 0; }
else  # macOS has no flock
  if ! mkdir "$LOCK.d" 2>/dev/null; then
    if [ -n "$(find "$LOCK.d" -maxdepth 0 -mmin +360 2>/dev/null)" ]; then rmdir "$LOCK.d"; mkdir "$LOCK.d"
    else echo "$(date '+%F %T') $NAME is already running; skipped" >>"$LOG"; exit 0; fi
  fi
  trap 'rmdir "$LOCK.d"' EXIT
fi

echo "=== $(date '+%F %T') $*" >>"$LOG"
"$ROOT/.venv/bin/python" cli.py "$@" >>"$LOG" 2>&1
CODE=$?
echo "=== exit $CODE" >>"$LOG"
exit $CODE
