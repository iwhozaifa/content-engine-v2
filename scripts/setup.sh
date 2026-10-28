#!/bin/bash
# One-time setup on macOS (Homebrew) or Ubuntu/Debian (incl. WSL). Free tools only.
# Safe to re-run: it also updates yt-dlp, which sites break often.
set -e
cd "$(dirname "$0")/.."

OS="$(uname -s)"
echo "1/5 ffmpeg + Python"
if [ "$OS" = "Darwin" ]; then
  command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
  brew install ffmpeg python@3.13 >/dev/null
  PY="$(brew --prefix)/bin/python3.13"
elif command -v apt-get >/dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq ffmpeg python3 python3-venv python3-pip >/dev/null
  PY="$(command -v python3)"
else
  echo "Unsupported system: install ffmpeg and Python 3.11+ yourself, then re-run with PY=/path/to/python3"
  PY="${PY:?}"
fi

echo "2/5 Local Python environment in .venv"
[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/pip install --quiet --upgrade pip

echo "3/5 Python packages (yt-dlp latest; Whisper's first install downloads ~1-2 GB)"
.venv/bin/pip install --quiet --upgrade -r requirements.txt "yt-dlp[default]"

echo "4/5 Repo config"
git config core.hooksPath scripts/hooks 2>/dev/null || true
[ -f .env ] || { cp .env.example .env; echo "  created .env from .env.example: add NOTION_TOKEN"; }
mkdir -p raw tmp logs cache

echo "5/5 Checks"
.venv/bin/yt-dlp --version
.venv/bin/whisper --help >/dev/null && echo "whisper OK"
ffmpeg -version | head -1
.venv/bin/python -m pytest -q 2>&1 | tail -1
if command -v claude >/dev/null || [ -n "${CLAUDE_BIN:-}" ]; then echo "claude CLI OK"; else
  echo "claude CLI not found: install Claude Code (https://claude.com/claude-code); on a server run 'claude setup-token'"
  echo "  and put the token in .env as CLAUDE_CODE_OAUTH_TOKEN"; fi

cat <<'MSG'

Next:
  1. Put NOTION_TOKEN in .env, then: .venv/bin/python cli.py ping
  2. Logins for Instagram (and YouTube/TikTok when they ask): log in with Firefox on this machine, or on a
     server export cookies.txt and set ENGINE_COOKIES_FILE in .env. A secondary account is safer.
  3. Schedules: scheduling/install.sh (prints what it would install; add --apply to install).
MSG
