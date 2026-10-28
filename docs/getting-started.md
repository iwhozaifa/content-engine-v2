# Content Engine v2: phases 0 and 1

This folder replaces your v1 `4-claude-code` folder. It adds manual URL discovery, the new idea lifecycle, full draft scripts with alternate lines, an originality check, and versioned revisions. Your Notion data isn't touched until you run the migration and say "go".

| Item | What it is |
| --- | --- |
| `CLAUDE.md` | Engine rules both Claude Code and Cowork follow |
| `.claude/commands/` | /migrate, /add-url, /write, /revise, /options, /score, /research, /plan-week, /carousel |
| `tools/fetch.py` | Free link fetcher for YouTube, Instagram and TikTok: details + transcript (captions, or Whisper on your Mac) |
| `scripts/setup.sh` | One-time Mac install of the free tools (re-run it to update) |
| `tools/engine.py` + tests | URL dedupe key + similarity check |
| `setup/Notion migration checklist.md` | Every Notion change for phase 0, with formulas and views |
| `docs/notion-pages/` | Engine Settings, Brand Voice & Style Guide, Idea page template, Short script template |
| `docs/cowork/Cowork setup.md` | How to run the same steps in Cowork with the browser |

## Install on the Mac (about 20 min, mostly downloads)

1. Copy this folder to the Mac, e.g. `~/content-engine-v2`, and copy your **`Aliyan_AI_Content_DNA.md`** into `docs/brand/`.
2. In Terminal: `cd ~/content-engine-v2 && scripts/setup.sh`. This installs ffmpeg, then the latest yt-dlp and Whisper into a local `.venv`, and runs the tests (should end with `OK`). It needs Homebrew ([brew.sh](https://brew.sh)). Everything is free.
3. Install **Firefox** and log in to **Instagram** there (a secondary account is safer). The fetcher borrows that login for Instagram links, and for TikTok or YouTube only if they ask for one.
4. Try one link: `.venv/bin/python tools/fetch.py "<a YouTube Short link>"`. You should see JSON with a title and a transcript.
5. Run `claude` in this folder, type `/mcp`, and check Notion is connected. If it isn't: quit, run `claude mcp add --transport http notion https://mcp.notion.com/mcp`, start `claude` again, type `/mcp` and sign in.
6. Cowork instead of the terminal: follow `docs/cowork/Cowork setup.md`.

**When fetching stops working** (sites change often): re-run `scripts/setup.sh` to update yt-dlp. For Instagram, log in again in Firefox. Pasting the transcript after a link always works.

## Phase 0: migrate Notion (about 1–2 h)

1. Export a Notion backup (Content Engine page → ••• → Export → Markdown & CSV, include subpages).
2. Run `/migrate`. It lists the differences first and waits for your "go". Then it renames, adds and re-links properties, creates Scripts, and imports the new pages.
3. Create the views from the table it prints (the Notion API can't make views).
4. Open the Brand Voice & Style Guide and paste 3–5 of your best scripts into "Example scripts". This is the single biggest lever on script quality.
5. Phase 0 passes when all old rows are intact, the Review Queue sorts by Review rank, and no formula shows an error.

## Phase 1: daily use

| Step | You | Claude |
| --- | --- | --- |
| Find | Paste links: `/add-url <url> <url>` | Fetches, analyses, reframes, dedupes, scores, files the idea in the Idea Bank |
| Review | Open the **Review Queue**, set Approved / Shortlisted / Rejected, optionally My rating | |
| Write | `/write` | Draft script v1 for every Approved idea: 3 hooks, 4–6 beats with 2 alternates each, CTA, originality check |
| Refine | Edit lines on the page, or write Feedback ("use H2, beat 3 alt 1, more punchy") and set Status = Needs revision, then `/revise` | Makes v2 and keeps your edited lines word for word |
| Approve | Set the script Status = Approved | |

Scripts are spoken lines only for now. B-roll, on-screen text, titles, hashtags and thumbnails are switched off in Engine Settings until phase 4.

## Phase 1 done test (about 30 min)

Run `/add-url` with these 6 links in one go:

1. A YouTube Short from a creator you follow
2. An Instagram Reel
3. A blog article on AI income
4. A private or deleted video link
5. Link 1 again, with `?si=abc` added
6. A Short in Urdu or Hindi

**Pass when:**
- [ ] 4 ideas are created (1, 2, 3, 6), or 3 plus 1 merged if two were on the same topic
- [ ] Link 4 is a Raw Content row with Fetch status = Private/Failed and a clear "what to paste" message
- [ ] Link 5 says "Already in Idea Bank" and creates no new rows
- [ ] Link 6 has Language set and an English analysis
- [ ] Approve 2 ideas and run `/write`: 2 scripts appear with Similarity flag OK (under 4%), 25–35 s
- [ ] Write feedback on one script and run `/revise`: v2 appears, v1 is Superseded, and your edited lines are unchanged

Tell me how each line went (or paste any errors) and I'll fix the commands before phase 2.

## Known limits

- Instagram needs the Firefox login, and that session expires every few weeks. When Instagram links start failing, log in again.
- Whisper takes roughly 10–60 seconds per clip on a MacBook. The first run downloads the model (~500 MB for `small`).
- yt-dlp is unofficial and against the platforms' terms in principle. Keep it to a handful of links at a time.
- The trend score formulas are in place but stay near 0 until phase 2 fills creator baselines.
