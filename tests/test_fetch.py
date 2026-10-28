import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import fetch

INFO = {"id": "abc123", "title": "3 AI skills", "uploader": "Maker", "uploader_url": "https://youtube.com/@maker",
        "upload_date": "20261020", "duration": 42, "view_count": 120000, "like_count": 8400,
        "comment_count": 310, "description": "caption text", "webpage_url": "https://www.youtube.com/shorts/abc123",
        "automatic_captions": {"en": [{}]}}
VTT = "WEBVTT\nKind: captions\n\n00:00:00.000 --> 00:00:02.000\nTools don't pay\n\n00:00:02.000 --> 00:00:04.000\nTools don't pay\noutcomes do\n"


def done(code=0, out="", err=""):
    return subprocess.CompletedProcess([], code, out, err)


class Basics(unittest.TestCase):
    def test_platform(self):
        self.assertEqual(fetch.platform_of("https://youtu.be/x"), "YouTube")
        self.assertEqual(fetch.platform_of("https://www.instagram.com/reel/x/"), "Instagram")
        self.assertEqual(fetch.platform_of("https://vm.tiktok.com/ZMabc/"), "TikTok")
        self.assertEqual(fetch.platform_of("https://blog.example.com/post"), "Web")

    def test_vtt(self):
        self.assertEqual(fetch.vtt_to_text(VTT), "Tools don't pay outcomes do")

    def test_classify(self):
        self.assertEqual(fetch.classify("ERROR: This video is private")[0], "Private")
        self.assertEqual(fetch.classify("ERROR: Unsupported URL: x")[0], "Unsupported")
        self.assertIn("login", fetch.classify("ERROR: [Instagram] login required")[1])

    def test_record(self):
        r = fetch.to_record(INFO, "https://youtu.be/abc123?si=z", "YouTube")
        self.assertEqual((r["published"], r["content_type"], r["views"]), ("2026-10-20", "Short", 120000))
        self.assertEqual(r["canonical_url"], "https://youtube.com/watch?v=abc123")


class Flow(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp())

    def test_instagram_uses_login_first(self):
        calls = []
        def fake(cmd, **kw):
            calls.append(cmd)
            return done(1, err="ERROR: This video is private")
        with mock.patch.object(fetch, "tool", return_value="yt-dlp"), mock.patch("subprocess.run", side_effect=fake):
            r = fetch.fetch_video("https://instagram.com/reel/x", "Instagram", "firefox", "small", self.out)
        self.assertIn("--cookies-from-browser", calls[0])
        self.assertEqual(r["fetch_status"], "Private")

    def test_tiktok_retries_with_login(self):
        calls = []
        def fake(cmd, **kw):
            calls.append(cmd)
            return done(1, err="ERROR: [TikTok] login required") if len(calls) == 1 else done(1, err="ERROR: video unavailable")
        with mock.patch.object(fetch, "tool", return_value="yt-dlp"), mock.patch("subprocess.run", side_effect=fake):
            fetch.fetch_video("https://tiktok.com/@a/video/1", "TikTok", "firefox", "small", self.out)
        self.assertNotIn("--cookies-from-browser", calls[0])
        self.assertIn("--cookies-from-browser", calls[1])

    def test_youtube_captions(self):
        def fake(cmd, **kw):
            if "--dump-single-json" in cmd:
                return done(0, out=json.dumps(INFO))
            (self.out / "abc123.en.vtt").write_text(VTT)
            return done(0)
        with mock.patch.object(fetch, "tool", return_value="yt-dlp"), mock.patch("subprocess.run", side_effect=fake):
            r = fetch.fetch_video("https://youtube.com/shorts/abc123", "YouTube", "firefox", "small", self.out)
        self.assertEqual((r["fetch_status"], r["transcript_source"]), ("OK", "Captions"))
        self.assertTrue(Path(r["transcript_file"]).exists())

    def test_no_captions_no_whisper_is_partial(self):
        info = dict(INFO, automatic_captions={}, subtitles={})
        tools = {"yt-dlp": "yt-dlp", "whisper": None}
        with mock.patch.object(fetch, "tool", side_effect=tools.get), \
             mock.patch("subprocess.run", return_value=done(0, out=json.dumps(info))):
            r = fetch.fetch_video("https://tiktok.com/@a/video/1", "TikTok", "firefox", "small", self.out)
        self.assertEqual(r["fetch_status"], "Partial")
        self.assertEqual(r["description"], "caption text")


if __name__ == "__main__":
    unittest.main()
