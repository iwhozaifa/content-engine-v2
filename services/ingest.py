"""Fetch one URL into a source record (video via tools/fetch.py, articles via a plain HTTP GET).

Records are cached in raw/fetch/<hash>.json so a dry-run followed by --apply fetches once.
Only successful fetches are cached; failures are retried on the next run.
"""
import hashlib
import html
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path

import requests

from tools import fetch as video
from tools.engine import canon

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "raw" / "fetch"
LANGUAGES = {"en": "English", "ur": "Urdu", "hi": "Hindi"}


def language_name(code):
    if not code:
        return None
    code = str(code).lower()
    return LANGUAGES.get(code[:2], code.title() if code.title() in ("English", "Urdu", "Hindi", "Mixed") else "Other")


class _Text(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "aside", "form", "noscript"}

    def __init__(self):
        super().__init__()
        self.title, self.parts, self._skip, self._in_title = "", [], 0, False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        self._in_title = tag == "title"

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag in ("p", "h1", "h2", "h3", "li", "br", "div"):
            self.parts.append("\n")
        self._in_title = False

    def handle_data(self, data):
        if self._in_title and not self.title:
            self.title = data.strip()
        elif not self._skip:
            self.parts.append(data)


def fetch_article(url, get=requests.get):
    rec = {"url": url, "canonical_url": canon(url), "platform": "Web", "content_type": "Article",
           "transcript_source": "Article text", "fetch_status": "OK", "fetch_error": "", "hint": ""}
    try:
        r = get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (content-engine)"})
        r.raise_for_status()
    except requests.RequestException as e:
        return {**rec, "fetch_status": "Failed", "fetch_error": str(e)[:500], "transcript_source": "None",
                "hint": "Couldn't open the page. Paste the article text into the Raw Content Transcript field."}
    p = _Text()
    p.feed(r.text)
    body = re.sub(r"\n\s*\n+", "\n\n", html.unescape("".join(p.parts))).strip()
    if len(body.split()) < 80:
        return {**rec, "title": p.title, "transcript": body, "fetch_status": "Partial",
                "hint": "Little readable text on the page. Paste the article text for a better idea."}
    return {**rec, "title": p.title or url, "transcript": body}


def fetch_url(url, settings, cache=CACHE, fetch_video=None, get=requests.get):
    """Return a source record for url, from cache when a previous fetch succeeded."""
    url = url if "://" in url else "https://" + url
    key = hashlib.sha1(canon(url).encode()).hexdigest()[:16]
    path = Path(cache) / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    platform = video.platform_of(url)
    if platform == "Web":
        rec = fetch_article(url, get)
    else:
        if not video.tool("yt-dlp"):
            return {"url": url, "canonical_url": canon(url), "platform": platform, "fetch_status": "Failed",
                    "fetch_error": "yt-dlp isn't installed", "hint": "Run scripts/setup.sh, then retry."}
        out = ROOT / "raw"
        out.mkdir(parents=True, exist_ok=True)
        browser = video.resolve_browser(settings.get("fetch.browser", "firefox"))
        rec = (fetch_video or video.fetch_video)(url, platform, browser, settings.get("fetch.whisper_model", "small"), out)
    rec["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if rec.get("fetch_status") in ("OK", "Partial"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def needs_input(rec):
    return rec.get("fetch_status") not in ("OK", "Partial") or not (rec.get("transcript") or rec.get("description"))
