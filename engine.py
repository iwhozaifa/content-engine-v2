#!/usr/bin/env python3
"""Deterministic helpers for the content engine (no network, standard library only).

  python3 engine.py canon <url> [<url> ...]
      Canonical URL per input, as JSON. Used as the dedupe key in Raw Content.

  python3 engine.py similarity --script script.txt --source transcript.txt
      Overlap between a draft script and its source transcript, as JSON:
      shared 5-gram %, longest identical run (words), flag, and the shared runs.
      Thresholds default to the Engine Settings values and can be overridden
      with --review, --too-close and --max-run.
"""
import argparse
import json
import re
import sys
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"si", "feature", "pp", "igsh", "igshid", "is_from_webapp", "sender_device",
                   "share_app_id", "share_link_id", "t", "ref", "ref_src", "s", "fbclid", "gclid"}


def canon(url):
    url = url.strip()
    if not re.match(r"^[a-z]+://", url, re.I):
        url = "https://" + url
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.").removeprefix("m.")
    path = parts.path.rstrip("/")
    query = dict(parse_qsl(parts.query))

    if host == "youtu.be" and path:
        return f"https://youtube.com/watch?v={path.lstrip('/')}"
    if host in ("youtube.com", "music.youtube.com"):
        if path.startswith("/shorts/"):
            return f"https://youtube.com/watch?v={path.split('/')[2]}"
        if path == "/watch" and "v" in query:
            return f"https://youtube.com/watch?v={query['v']}"
    if host == "instagram.com":
        m = re.match(r"^/(?:[^/]+/)?(reel|reels|p|tv)/([^/]+)", path)
        if m:
            kind = "reel" if m.group(1) in ("reel", "reels", "tv") else "p"
            return f"https://instagram.com/{kind}/{m.group(2)}"
    if host == "tiktok.com":
        m = re.match(r"^/(@[^/]+)/video/(\d+)", path)
        if m:
            return f"https://tiktok.com/{m.group(1)}/video/{m.group(2)}"

    kept = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in TRACKING_PARAMS
            and not k.lower().startswith("utm_")]
    return urlunsplit(("https", host, path, urlencode(sorted(kept)), ""))


def words(text):
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"\d{1,2}:\d{2}(:\d{2})?(\.\d+)?", " ", text)  # caption timestamps
    return re.findall(r"[^\W_]+(?:'[^\W_]+)?", text)


def ngrams(tokens, n):
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def shared_runs(script, source, min_len):
    """Maximal runs of identical consecutive words, at least min_len long."""
    index = {}
    for j in range(len(source) - min_len + 1):
        index.setdefault(tuple(source[j:j + min_len]), []).append(j)
    runs, i = [], 0
    while i <= len(script) - min_len:
        best = 0
        for j in index.get(tuple(script[i:i + min_len]), []):
            k = min_len
            while i + k < len(script) and j + k < len(source) and script[i + k] == source[j + k]:
                k += 1
            best = max(best, k)
        if best:
            runs.append(" ".join(script[i:i + best]))
            i += best
        else:
            i += 1
    return runs


def similarity(script_text, source_text, review=4.0, too_close=8.0, max_run=10, n=5):
    s, src = words(script_text), words(source_text)
    if not src:
        return {"similarity_pct": None, "longest_run": None, "flag": "Not checked",
                "reason": "no source transcript", "runs": []}
    grams = ngrams(s, n)
    pct = round(100 * len(grams & ngrams(src, n)) / len(grams), 1) if grams else 0.0
    runs = shared_runs(s, src, n)
    longest = max((len(r.split()) for r in runs), default=0)
    if pct >= too_close or longest >= max_run:
        flag = "Too close"
    elif pct >= review:
        flag = "Review"
    else:
        flag = "OK"
    return {"similarity_pct": pct, "longest_run": longest, "flag": flag,
            "script_words": len(s), "runs": sorted(runs, key=len, reverse=True)[:10]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("canon")
    c.add_argument("urls", nargs="+")
    m = sub.add_parser("similarity")
    m.add_argument("--script", required=True)
    m.add_argument("--source", required=True)
    m.add_argument("--review", type=float, default=4.0)
    m.add_argument("--too-close", type=float, default=8.0)
    m.add_argument("--max-run", type=int, default=10)
    a = p.parse_args(argv)

    if a.cmd == "canon":
        out = {u: canon(u) for u in a.urls}
    else:
        with open(a.script, encoding="utf-8") as f1, open(a.source, encoding="utf-8") as f2:
            out = similarity(f1.read(), f2.read(), a.review, a.too_close, a.max_run)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
