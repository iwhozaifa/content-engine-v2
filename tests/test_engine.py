import unittest
from tools.engine import canon, similarity

SOURCE = """00:01 Everyone tells you to learn ten AI tools but that is exactly why you are still broke.
00:05 The market does not pay for tools, it pays for outcomes. Pick one problem a business has
and solve it with one tool. That is your offer."""


class Canon(unittest.TestCase):
    def test_youtube_variants(self):
        want = "https://youtube.com/watch?v=abc123"
        for u in ["https://youtu.be/abc123?si=x", "youtube.com/shorts/abc123?feature=share",
                  "https://www.youtube.com/watch?v=abc123&t=30s", "https://m.youtube.com/watch?v=abc123"]:
            self.assertEqual(canon(u), want, u)

    def test_instagram_and_tiktok(self):
        self.assertEqual(canon("https://www.instagram.com/reel/C1x2y3/?igsh=abc"), "https://instagram.com/reel/C1x2y3")
        self.assertEqual(canon("https://www.instagram.com/someone/reels/C1x2y3/"), "https://instagram.com/reel/C1x2y3")
        self.assertEqual(canon("https://www.tiktok.com/@maker/video/7301?is_from_webapp=1"), "https://tiktok.com/@maker/video/7301")

    def test_article_strips_tracking(self):
        self.assertEqual(canon("https://blog.example.com/post/?utm_source=x&id=4"), "https://blog.example.com/post?id=4")


class Similarity(unittest.TestCase):
    def test_original_script_is_ok(self):
        script = "Das AI tools seekh liye, ek rupaya nahi kamaya? Problem tools nahi hain. Clients outcome kharidte hain, software nahi."
        self.assertEqual(similarity(script, SOURCE)["flag"], "OK")

    def test_copied_run_is_too_close(self):
        script = "Suno yaar. Everyone tells you to learn ten AI tools but that is exactly why you are still broke. Bas."
        r = similarity(script, SOURCE)
        self.assertEqual(r["flag"], "Too close")
        self.assertGreaterEqual(r["longest_run"], 10)

    def test_no_source(self):
        self.assertEqual(similarity("anything", "")["flag"], "Not checked")


if __name__ == "__main__":
    unittest.main()
