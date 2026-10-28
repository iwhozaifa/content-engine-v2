---
description: Content cards (A/B variations, captions, thumbnails) for locked topics (via the engine CLI)
---

Input: $ARGUMENTS = Content Plan titles (or parts), or empty for every Topic Locked slot without a card.

1. Dry-run: `.venv/bin/python cli.py generate-cards --locked` (or `generate-card "<title>"`). Per slot it writes Variation A and B (different hook families and angles), and with production extras On also B-roll, on-screen text, per-platform captions, titles and thumbnail ideas, plus the originality check. The same run also makes the next version of any card set to Needs revision (edited lines kept word for word) and moves cards with a Chosen variation to Script Chosen.
2. Run the same command with `--apply`.
3. Show its report: card · A/B hook families · originality flags · anything marked ⚠️ CREATOR INPUT REQUIRED.

To choose: set Chosen variation = A or B on the card. To revise: write Feedback, set Status = Needs revision, run /cards again.
