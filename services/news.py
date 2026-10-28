"""Read RSS 2.0 and Atom feeds into plain items (standard library only)."""
import re
import tomllib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
FEEDS = ROOT / "config" / "feeds.toml"
ATOM = "{http://www.w3.org/2005/Atom}"


def load_feeds(path=FEEDS):
    with open(path, "rb") as f:
        return [x for x in tomllib.load(f).get("feed", []) if x.get("enabled", True)]


def _text(el, *names):
    for n in names:
        found = el.find(n)
        if found is not None and (found.text or "").strip():
            return found.text.strip()
    return ""


def _date(value):
    if not value:
        return None
    try:
        d = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def strip_html(s):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def parse(xml_text, source):
    root = ET.fromstring(xml_text)
    items = []
    for it in root.iter("item"):
        items.append({"headline": strip_html(_text(it, "title")), "url": _text(it, "link"), "source": source,
                      "published": _date(_text(it, "pubDate", "{http://purl.org/dc/elements/1.1/}date")),
                      "summary": strip_html(_text(it, "description"))[:600]})
    for it in root.iter(f"{ATOM}entry"):
        link = next((l.get("href") for l in it.findall(f"{ATOM}link") if l.get("rel") in (None, "alternate")), "")
        items.append({"headline": strip_html(_text(it, f"{ATOM}title")), "url": link, "source": source,
                      "published": _date(_text(it, f"{ATOM}published", f"{ATOM}updated")),
                      "summary": strip_html(_text(it, f"{ATOM}summary", f"{ATOM}content"))[:600]})
    return [i for i in items if i["url"] and i["headline"]]


def fetch_all(feeds, get=requests.get):
    """-> (items, errors). One broken feed never stops the others."""
    items, errors = [], []
    for f in feeds:
        try:
            r = get(f["url"], timeout=30, headers={"User-Agent": "Mozilla/5.0 (content-engine news radar)"})
            r.raise_for_status()
            items += parse(r.content, f["name"])
        except Exception as e:  # noqa: BLE001
            errors.append(f"{f['name']}: {type(e).__name__}: {str(e)[:120]}")
    return items, errors
