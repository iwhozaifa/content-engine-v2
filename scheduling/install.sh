#!/usr/bin/env bash
# Install the engine's schedules from scheduling/jobs.txt.
#   scheduling/install.sh [systemd|cron|launchd] [--apply] [--dry-run-commands] [--remove]
# Default: print what would be installed. --apply installs it. --dry-run-commands strips --apply from every
# job (the schedule runs, Notion is never written). --remove uninstalls. Platform defaults: Linux with a
# systemd user session → systemd, macOS → launchd, otherwise cron.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$ROOT/scheduling/run.sh"
KIND="" APPLY=0 DRY_CMDS=0 REMOVE=0
for a in "$@"; do case "$a" in
  systemd|cron|launchd) KIND="$a" ;; --apply) APPLY=1 ;; --dry-run-commands) DRY_CMDS=1 ;; --remove) REMOVE=1 ;;
  *) echo "unknown argument: $a"; exit 2 ;; esac; done
if [ -z "$KIND" ]; then
  if [ "$(uname -s)" = "Darwin" ]; then KIND=launchd
  elif systemctl --user is-system-running >/dev/null 2>&1 || systemctl --user status >/dev/null 2>&1; then KIND=systemd
  else KIND=cron; fi
fi
say() { if [ $APPLY = 1 ]; then echo "+ $*"; else echo "would: $*"; fi; }
write() { # path, content
  if [ $APPLY = 1 ]; then mkdir -p "$(dirname "$1")"; printf '%s\n' "$2" >"$1"; echo "+ wrote $1"
  else echo "--- would write $1"; printf '%s\n' "$2"; fi; }

DOW=(Sun Mon Tue Wed Thu Fri Sat Sun)
jobs() { grep -v '^\s*#' "$ROOT/scheduling/jobs.txt" | grep -v '^\s*$' | while IFS='|' read -r name when cmd; do
  name="$(echo $name)"; cmd="$(echo $cmd)"; read -r m h d <<<"$when"
  [ $DRY_CMDS = 1 ] && cmd="${cmd// --apply/}"
  echo "$name|$m|$h|$d|$cmd"; done; }

case "$KIND" in
systemd)
  DIR="$HOME/.config/systemd/user"
  jobs | while IFS='|' read -r name m h d cmd; do
    unit="content-engine-$name"
    if [ $REMOVE = 1 ]; then say "systemctl --user disable --now $unit.timer; rm $DIR/$unit.{service,timer}"
      [ $APPLY = 1 ] && { systemctl --user disable --now "$unit.timer" 2>/dev/null || true; rm -f "$DIR/$unit".{service,timer}; }
      continue; fi
    day="*-*-*"; [ "$d" != "*" ] && day="${DOW[$d]} *-*-*"
    write "$DIR/$unit.service" "[Unit]
Description=Content engine: $cmd
[Service]
Type=oneshot
ExecStart=\"$RUN\" $cmd"
    write "$DIR/$unit.timer" "[Unit]
Description=Content engine schedule: $name
[Timer]
OnCalendar=$day $(printf '%02d:%02d' "$h" "$m")
Persistent=true
[Install]
WantedBy=timers.target"
  done
  if [ $REMOVE = 0 ]; then
    say "systemctl --user daemon-reload && enable --now every content-engine-*.timer"
    if [ $APPLY = 1 ]; then systemctl --user daemon-reload
      jobs | while IFS='|' read -r name _; do systemctl --user enable --now "content-engine-$name.timer"; done
      systemctl --user list-timers 'content-engine-*'
      echo "Tip: 'loginctl enable-linger $USER' keeps timers running when you're logged out (servers)."; fi
  fi ;;
cron)
  BLOCK="$(jobs | while IFS='|' read -r name m h d cmd; do echo "$m $h * * $d \"$RUN\" $cmd  # content-engine:$name"; done)"
  CURRENT="$(crontab -l 2>/dev/null | grep -v '# content-engine:' || true)"
  NEW="$CURRENT"; [ $REMOVE = 0 ] && NEW="$(printf '%s\n%s' "$CURRENT" "$BLOCK" | sed '/^$/d')"
  if [ $APPLY = 1 ]; then printf '%s\n' "$NEW" | crontab -; echo "+ crontab updated"; crontab -l | grep content-engine || true
  else echo "--- would set crontab to:"; printf '%s\n' "$NEW"; fi ;;
launchd)
  DIR="$HOME/Library/LaunchAgents"
  jobs | while IFS='|' read -r name m h d cmd; do
    label="com.content-engine.$name"; plist="$DIR/$label.plist"
    if [ $REMOVE = 1 ]; then say "launchctl unload $plist; rm $plist"
      [ $APPLY = 1 ] && { launchctl unload "$plist" 2>/dev/null || true; rm -f "$plist"; }; continue; fi
    args="<string>$RUN</string>"; for w in $cmd; do args="$args<string>$w</string>"; done
    wd=""; [ "$d" != "*" ] && wd="<key>Weekday</key><integer>$d</integer>"
    write "$plist" "<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\"><dict>
<key>Label</key><string>$label</string>
<key>ProgramArguments</key><array>$args</array>
<key>StartCalendarInterval</key><dict><key>Hour</key><integer>$h</integer><key>Minute</key><integer>$m</integer>$wd</dict>
<key>WorkingDirectory</key><string>$ROOT</string>
</dict></plist>"
    [ $APPLY = 1 ] && { launchctl unload "$plist" 2>/dev/null || true; launchctl load "$plist"; echo "+ loaded $label"; }
  done ;;
esac
[ $APPLY = 1 ] || echo "(dry-run: nothing installed. Add --apply to install.)"
