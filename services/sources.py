"""List a creator's recent posts with metrics.

YouTube: the YouTube Data API v3 when YOUTUBE_API_KEY is set (free, ~3 quota units per creator),
otherwise yt-dlp. Instagram and TikTok: yt-dlp profile listing (fragile; failures are returned as an
error string so the scan records them on the creator row and moves on).
"""
import json
import os
import re
from datetime import datetime, timezone

import requests

from tools import fetch as video
from tools.engine import canon

YT_API = "https://www.googleapis.com/youtube/v3"


class SourceError(Exception):
    pass


def profile_urls(creator):
    """Every profile URL on a creator row: Profile URL plus any URLs in Other profiles."""
    urls = [creator.get("Profile URL")] + re.findall(r"https?://\S+", creator.get("Other profiles") or "")
    return [u.rstrip(").,") for u in urls if u]


def list_posts(url, n, settings, get=requests.get):
    platform = video.platform_of(url)
    if platform == "YouTube" and os.environ.get("YOUTUBE_API_KEY"):
        return youtube_api(url, n, os.environ["YOUTUBE_API_KEY"], get)
    if platform in ("YouTube", "Instagram", "TikTok"):
        target = youtube_shorts_url(url) if platform == "YouTube" else url
        return ytdlp_listing(target, platform, n, settings)
    raise SourceError(f"Can't scan {url}: only YouTube, Instagram and TikTok profiles are supported")


# -- YouTube Data API -------------------------------------------------------------
def _yt(get, path, key, **params):
    r = get(f"{YT_API}/{path}", params={**params, "key": key}, timeout=30)
    if r.status_code != 200:
        try:
            msg = r.json()["error"]["message"]
        except Exception:  # noqa: BLE001
            msg = r.text[:200]
        raise SourceError(f"YouTube API {r.status_code}: {msg}")
    return r.json()


def channel_lookup(url):
    m = re.search(r"youtube\.com/(?:channel/(UC[\w-]+)|@([\w.-]+)|c/([\w.-]+)|user/([\w.-]+))", url)
    if not m:
        raise SourceError(f"Not a YouTube channel URL: {url}")
    channel, handle, custom, user = m.groups()
    if channel:
        return {"id": channel}
    if handle or custom:
        return {"forHandle": "@" + (handle or custom)}
    return {"forUsername": user}


def youtube_api(url, n, key, get=requests.get):
    data = _yt(get, "channels", key, part="contentDetails,snippet", **channel_lookup(url))
    if not data.get("items"):
        raise SourceError(f"YouTube channel not found for {url}")
    ch = data["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = _yt(get, "playlistItems", key, part="contentDetails", playlistId=uploads, maxResults=min(n, 50))["items"]
    ids = [i["contentDetails"]["videoId"] for i in items]
    if not ids:
        return [], ch["id"]
    vids = _yt(get, "videos", key, part="snippet,statistics,contentDetails", id=",".join(ids))["items"]
    posts = []
    for v in vids:
        s, st = v["snippet"], v.get("statistics", {})
        secs = iso_duration(v["contentDetails"].get("duration", ""))
        watch = f"https://www.youtube.com/watch?v={v['id']}"
        posts.append({"url": watch if secs > 180 else f"https://www.youtube.com/shorts/{v['id']}",
                      "canonical_url": canon(watch), "platform": "YouTube", "id": v["id"], "title": s.get("title"),
                      "creator": s.get("channelTitle"), "content_type": "Short" if secs and secs <= 180 else "Long video",
                      "published": s.get("publishedAt"), "duration_s": secs or None,
                      "views": _int(st.get("viewCount")), "likes": _int(st.get("likeCount")),
                      "comments": _int(st.get("commentCount")), "shares": None,
                      "description": (s.get("description") or "")[:1500]})
    return posts, ch["id"]


def iso_duration(text):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", text or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def _int(v):
    return int(v) if v not in (None, "") else None


# -- yt-dlp -------------------------------------------------------------------------
def youtube_shorts_url(url):
    base = re.sub(r"/(shorts|videos|featured|streams)/?$", "", url.rstrip("/"))
    return base + "/shorts"


def ytdlp_listing(url, platform, n, settings):
    if not video.tool("yt-dlp"):
        raise SourceError("yt-dlp isn't installed (scripts/setup.sh)")
    args = ["--skip-download", "--dump-json", "--playlist-end", str(n), "--ignore-errors"]
    browser = video.resolve_browser(settings.get("fetch.browser", "firefox"))
    r = video.ytdlp(args, url, platform, browser)
    posts = []
    for line in r.stdout.splitlines():
        try:
            info = json.loads(line)
        except json.JSONDecodeError:
            continue
        rec = video.to_record(info, info.get("webpage_url") or url, platform)
        if info.get("timestamp"):
            rec["published"] = datetime.fromtimestamp(info["timestamp"], timezone.utc).isoformat()
        rec["description"] = rec.get("description", "")[:1500]
        posts.append(rec)
    if not posts:
        status, hint = video.classify(r.stderr or "no posts returned")
        raise SourceError(f"{platform} listing failed ({status}): {hint} {(r.stderr or '').strip()[-200:]}")
    return posts, None
