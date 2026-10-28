---
description: Daily news radar into News Candidates (via the engine CLI)
---

1. Dry-run: `.venv/bin/python cli.py news-radar`. It reads the feeds in `config/feeds.toml` (last 48 h), drops anything already in News Candidates, and asks `prompts/news_judge` which items fit the brand (at most the "News candidates per day" Engine Setting). It also turns candidates I set to Approved into ideas (Origin News).
2. Run the same command with `--apply`. New candidates are always Approval = Pending; nothing is approved for me.
3. Show the kept candidates: headline · brand fit · urgency · suggested angle.

To use one: set Approval = Approved in News Candidates; the next run creates the idea, and the weekly plan picks it right after Must-Do items. Rejected candidates never become ideas.
