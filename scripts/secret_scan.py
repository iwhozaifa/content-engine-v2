#!/usr/bin/env python3
"""Block commits that contain secrets. Scans staged files (or the paths given).

  python3 scripts/secret_scan.py            # staged files (pre-commit hook)
  python3 scripts/secret_scan.py a.txt b.py # specific files
"""
import re
import subprocess
import sys

PATTERNS = {
    "Notion token": r"\b(?:ntn|secret)_[A-Za-z0-9]{40,}",
    "Anthropic key": r"\bsk-ant-[A-Za-z0-9_-]{20,}",
    "Claude OAuth token": r"\bsk-ant-oat[A-Za-z0-9_-]{20,}",
    "OpenAI-style key": r"\bsk-[A-Za-z0-9]{32,}",
    "Google API key": r"\bAIza[0-9A-Za-z_-]{35}",
    "Telegram bot token": r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b",
    "Private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "Assigned secret": r"(?im)^[ \t]*(?:NOTION_TOKEN|CLAUDE_CODE_OAUTH_TOKEN|YOUTUBE_API_KEY|TELEGRAM_BOT_TOKEN|SMTP_PASSWORD)[ \t]*=[ \t]*['\"]?[^\s'\"#]{12,}",
}
BLOCKED_FILES = re.compile(r"(^|/)(\.env|cookies\.txt|.*\.cookies)$")


def staged():
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                         capture_output=True, text=True, check=True).stdout
    return [p for p in out.splitlines() if p]


def scan(paths):
    problems = []
    for path in paths:
        if BLOCKED_FILES.search(path):
            problems.append(f"{path}: this file must never be committed")
            continue
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except (FileNotFoundError, IsADirectoryError):
            continue
        for name, pattern in PATTERNS.items():
            for m in re.finditer(pattern, text):
                line = text.count("\n", 0, m.start()) + 1
                problems.append(f"{path}:{line}: looks like a {name}")
    return problems


def main(argv):
    problems = scan(argv or staged())
    for p in problems:
        print("secret-scan:", p, file=sys.stderr)
    if problems:
        print("secret-scan: commit blocked. Move secrets to .env (gitignored).", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
