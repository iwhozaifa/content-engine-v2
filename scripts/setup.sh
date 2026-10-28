#!/bin/bash
# One-time setup on Ubuntu (tested on WSL2, Ubuntu 26.04). Free tools only. Safe to re-run: it also updates yt-dlp.
set -e
cd "$(dirname "$0")/.."

if ! command -v apt-get >/dev/null; then
  echo "apt-get is missing. This script is for Ubuntu/Debian (including WSL)."; exit 1
fi

echo "1/4 ffmpeg + Python (apt, asks for your sudo password)"
sudo apt-get update -qq
sudo apt-get install -y -qq ffmpeg python3 python3-venv python3-pip >/dev/null
PY="$(command -v python3)"

echo "2/4 Local Python environment in .venv"
[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/pip install --quiet --upgrade pip

echo "3/4 yt-dlp (latest; sites change often, so re-run this script when fetching breaks)"
.venv/bin/pip install --quiet --upgrade "yt-dlp[default]"

echo "4/4 Whisper speech-to-text (first install downloads ~1-2 GB, takes a few minutes)"
.venv/bin/pip install --quiet --upgrade openai-whisper

echo
echo "Checks:"
.venv/bin/yt-dlp --version
.venv/bin/whisper --help >/dev/null && echo "whisper OK"
ffmpeg -version | head -1
.venv/bin/python -m unittest test_engine test_fetch 2>&1 | tail -1

cat <<'MSG'

Done. Two things left:
  - yt-dlp reads logins from a Firefox installed inside Ubuntu, not from Windows. Either:
      a) sudo snap install firefox   (opens via WSLg), then log in to Instagram there
         (a secondary account is safer), and to TikTok if TikTok links start failing; or
      b) use your Windows Firefox profile:
         export ENGINE_BROWSER="firefox:/mnt/c/Users/<you>/AppData/Roaming/Mozilla/Firefox/Profiles/<xxxx.default-release>"
  - Try one link:  .venv/bin/python fetch.py "https://www.youtube.com/shorts/<id>"
MSG
