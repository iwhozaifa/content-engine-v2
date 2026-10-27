#!/usr/bin/env python3
"""Fetch a YouTube, Instagram or TikTok link (or an article) for free, as JSON.

  python3 fetch.py <url> [<url> ...] [--browser firefox] [--model small] [--out raw]

Per link it prints one record with the fields /add-url writes to Raw Content:
title, creator, creator_url, platform, content_type, published, views, likes,
comments, shares, description, transcript, transcript_source, language,
canonical_url, fetch_status (OK, Partial, Failed, Private, Unsupported),
fetch_error and hint (what to do when it failed).

How it gets the words, cheapest first:
  1. captions/subtitles via yt-dlp (YouTube usually has them)
  2. audio via yt-dlp + Whisper on this Mac (Reels and TikToks usually need this)
  3. the caption/description only (fetch_status = Partial)

Instagram always uses the Instagram login of the browser given by --browser
(default firefox). YouTube and TikTok try without a login first and retry with
it if the site asks. No API keys, no paid services.
"""
import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from engine import canon

HERE = Path(__file__).resolve().parent
SUB_LANGS = "en.*,ur.*,hi.*,en"
LOGIN_HINTS = ("login required", "log in", "sign in", "cookies", "rate-limit", "rate limit",
               "not a bot", "requested content is not available", "empty media response")


def tool(name):
    """Prefer the copy installed by setup_mac.sh in .venv, then anything on PATH."""
    local = HERE / ".venv" / "bin" / name
    return str(local) if local.exists() else shutil.which(name)


def resolve_browser(browser):
    """On WSL with no Linux Firefox, point plain "firefox" at the Windows Firefox default profile."""
    if browser != "firefox" or (Path.home() / ".mozilla" / "firefox").exists():
        return browser
    for ini in Path("/mnt/c/Users").glob("*/AppData/Roaming/Mozilla/Firefox/profiles.ini"):
        text = ini.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"^\[Install[^\]]*\][^\[]*?^Default=(.+)$", text, re.M) or re.search(r"^Path=(.+)$", text, re.M)
        if m:
            profile = ini.parent / m.group(1).strip()
            if (profile / "cookies.sqlite").exists():
                return f"firefox:{profile}"
    return browser


def platform_of(url):
    host = re.sub(r"^(www\.|m\.|vm\.|vt\.)", "", url.split("/")[2].lower()) if "://" in url else ""
    if host in ("youtube.com", "youtu.be", "music.youtube.com"):
        return "YouTube"
    if host in ("instagram.com", "instagr.am"):
        return "Instagram"
    if host == "tiktok.com":
        return "TikTok"
    return "Web"


def classify(stderr):
    """Map a yt-dlp error message to (fetch_status, hint)."""
    e = stderr.lower()
    if "private" in e:
        return "Private", "The post is private. Use a public link or paste the transcript."
    if "unsupported url" in e:
        return "Unsupported", "This link type isn't supported. Paste the text or transcript instead."
    if any(h in e for h in LOGIN_HINTS):
        return "Failed", ("The site wants a login. Open Firefox, log in to the site (Instagram/TikTok/YouTube) "
                          "and retry. Or paste the transcript.")
    if any(h in e for h in ("removed", "deleted", "not available", "404", "does not exist", "unavailable")):
        return "Failed", "The post looks deleted or unavailable. Check the link or paste the transcript."
    if any(h in e for h in ("urlopen error", "timed out", "connection", "name resolution")):
        return "Failed", "Network problem. Check the internet connection and retry."
    return "Failed", "Fetch failed. Re-run ./setup_mac.sh to update yt-dlp, retry later, or paste the transcript."


def run_ytdlp(args, browser, use_login):
    cmd = [tool("yt-dlp"), "--no-warnings", "--no-playlist", *args]
    if use_login:
        cmd[1:1] = ["--cookies-from-browser", browser]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def ytdlp(args, url, platform, browser):
    """Run yt-dlp, logging in for Instagram, or as a retry when another site asks for it."""
    first_login = platform == "Instagram"
    r = run_ytdlp([*args, url], browser, first_login)
    if r.returncode != 0 and not first_login and any(h in r.stderr.lower() for h in LOGIN_HINTS):
        r = run_ytdlp([*args, url], browser, True)
    return r


def vtt_to_text(vtt):
    lines, last = [], None
    for line in vtt.splitlines():
        line = line.strip()
        if (not line or line == "WEBVTT" or "-->" in line or line.isdigit()
                or line.startswith(("Kind:", "Language:", "NOTE", "STYLE"))):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line and line != last:
            lines.append(line)
            last = line
    return " ".join(lines)


def to_record(info, url, platform):
    date = info.get("upload_date")
    if date and len(date) == 8:
        published = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    elif info.get("timestamp"):
        published = datetime.fromtimestamp(info["timestamp"], timezone.utc).strftime("%Y-%m-%d")
    else:
        published = None
    duration = info.get("duration") or 0
    if platform == "YouTube":
        content_type = "Short" if "/shorts/" in url or (duration and duration <= 180) else "Long video"
    else:
        content_type = "Short" if duration and duration <= 180 else ("Long video" if duration else "Post")
    return {
        "url": url,
        "canonical_url": canon(info.get("webpage_url") or url),
        "platform": platform,
        "id": info.get("id"),
        "title": info.get("title") or (info.get("description") or "")[:80],
        "creator": info.get("uploader") or info.get("channel") or info.get("uploader_id"),
        "creator_url": info.get("uploader_url") or info.get("channel_url"),
        "content_type": content_type,
        "published": published,
        "duration_s": duration or None,
        "views": info.get("view_count"),
        "likes": info.get("like_count"),
        "comments": info.get("comment_count"),
        "shares": info.get("repost_count"),
        "description": info.get("description") or "",
        "transcript": "",
        "transcript_source": "None",
        "language": info.get("language"),
        "fetch_status": "OK",
        "fetch_error": "",
        "hint": "",
    }


def captions(url, platform, info, browser, out):
    has = info.get("subtitles") or info.get("automatic_captions")
    if not has:
        return ""
    r = ytdlp(["--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", SUB_LANGS,
               "--sub-format", "vtt", "-o", str(out / "%(id)s.%(ext)s")], url, platform, browser)
    if r.returncode != 0:
        return ""
    files = sorted(out.glob(f"{info['id']}*.vtt"), key=lambda p: (".en" not in p.name, p.name))
    return vtt_to_text(files[0].read_text(encoding="utf-8", errors="ignore")) if files else ""


def whisper(url, platform, info, browser, out, model):
    if not tool("whisper") or not shutil.which("ffmpeg"):
        return "", None, "Whisper or ffmpeg isn't installed (run setup_mac.sh), so only the caption was used."
    r = ytdlp(["-x", "--audio-format", "mp3", "-o", str(out / "%(id)s.%(ext)s")], url, platform, browser)
    audio = out / f"{info['id']}.mp3"
    if r.returncode != 0 or not audio.exists():
        return "", None, "Couldn't download the audio: " + r.stderr.strip()[-300:]
    w = subprocess.run([tool("whisper"), str(audio), "--model", model, "--output_format", "json",
                        "--output_dir", str(out), "--fp16", "False"], capture_output=True, text=True, timeout=1800)
    result = out / f"{info['id']}.json"
    if w.returncode != 0 or not result.exists():
        return "", None, "Whisper failed: " + w.stderr.strip()[-300:]
    data = json.loads(result.read_text(encoding="utf-8"))
    return data.get("text", "").strip(), data.get("language"), ""


def fetch_video(url, platform, browser, model, out):
    r = ytdlp(["--skip-download", "--dump-single-json"], url, platform, browser)
    if r.returncode != 0:
        status, hint = classify(r.stderr)
        return {"url": url, "canonical_url": canon(url), "platform": platform, "fetch_status": status,
                "fetch_error": r.stderr.strip()[-500:], "hint": hint}
    info = json.loads(r.stdout)
    rec = to_record(info, url, platform)

    text = captions(url, platform, info, browser, out)
    if text:
        rec["transcript"], rec["transcript_source"] = text, "Captions"
    else:
        text, lang, problem = whisper(url, platform, info, browser, out, model)
        if text:
            rec["transcript"], rec["transcript_source"] = text, "Whisper"
            rec["language"] = rec["language"] or lang
        else:
            rec["fetch_status"] = "Partial"
            rec["fetch_error"] = problem
            rec["hint"] = "Only the caption/description was available. Paste the transcript for a better idea."
    if rec["transcript"]:
        (out / f"{info['id']}.txt").write_text(rec["transcript"], encoding="utf-8")
        rec["transcript_file"] = str(out / f"{info['id']}.txt")
    return rec


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("urls", nargs="+")
    p.add_argument("--browser", default=os.environ.get("ENGINE_BROWSER", "firefox"),
                   help="browser whose Instagram/TikTok/YouTube login yt-dlp may use (firefox, safari, chrome)")
    p.add_argument("--model", default=os.environ.get("ENGINE_WHISPER_MODEL", "small"),
                   help="Whisper model: base (fast), small (default, better for Urdu), medium (slow)")
    p.add_argument("--out", default=str(HERE / "raw"))
    a = p.parse_args(argv)
    a.browser = resolve_browser(a.browser)

    if not tool("yt-dlp"):
        sys.exit("yt-dlp isn't installed. Run ./setup_mac.sh first.")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    records = []
    for i, url in enumerate(a.urls):
        if i:
            time.sleep(random.uniform(3, 6))  # human pace between links
        platform = platform_of(url if "://" in url else "https://" + url)
        if platform == "Web":
            records.append({"url": url, "canonical_url": canon(url), "platform": "Web",
                            "fetch_status": "Unsupported",
                            "hint": "Not a video link: fetch the page with web fetch instead."})
            continue
        try:
            records.append(fetch_video(url, platform, a.browser, a.model, out))
        except subprocess.TimeoutExpired:
            records.append({"url": url, "canonical_url": canon(url), "platform": platform, "fetch_status": "Failed",
                            "hint": "Timed out. Retry, or paste the transcript."})
    json.dump(records, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
