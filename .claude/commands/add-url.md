---
description: Manual discovery - turn pasted URLs into reframed ideas in the Idea Bank
---

Read Engine Settings (Notion page), the Brand Voice & Style Guide (Notion page) and docs/brand/Aliyan_AI_Content_DNA.md first. Use the Notion MCP tools to read and write the databases, using the exact property names that exist there.

Input: $ARGUMENTS = one or more URLs separated by spaces, optionally followed by "transcript:" and pasted text for the last URL.

For each URL, in order:

1. **Normalise:** `python3 tools/engine.py canon <url>`.
2. **Duplicate URL?** Search Raw Content for that Canonical URL. If it's found: refresh Views/Likes/Comments and Metrics captured at if you can fetch them, reply "Already in Idea Bank: <idea link>", and go to the next URL.
3. **Fetch (free, no API keys):**
   - YouTube, Shorts, Instagram, TikTok: run `.venv/bin/python tools/fetch.py <url>` (all video URLs in one call is fine; it pauses 3–6 s between links). It returns JSON per link with metadata, transcript, transcript_source, language, fetch_status, fetch_error and hint. It tries captions first, then Whisper on the audio, and uses the Firefox login for Instagram (and for YouTube/TikTok only if they ask).
   - Use the JSON's `canonical_url` for the duplicate check again, because share links like vm.tiktok.com only resolve after fetching.
   - Article, blog, thread or any other page: fetch it with web fetch and extract title, author, date and main text.
   - A pasted transcript always wins over a fetched one (Transcript source = Pasted).
4. **Failures:** copy `fetch_status` and `fetch_error` into Raw Content and show me the `hint`.
   - Private, Failed or Unsupported: create the Raw Content row only, no idea.
   - Partial (caption only, no transcript): create the idea only if the caption has enough substance, tag it "Thin source", and suggest pasting the transcript.
   - If every Instagram link fails with a login hint, tell me once: "Log in to Instagram in Firefox, then retry".
5. **Long or non-English text:**
   - Over ~12k words: split it into chunks, summarise each into beats, and analyse from the summaries.
   - Set Language. Analyse in English, but keep the source's first line in its original language as the hook reference.
6. **Analyse the source:** topic, the hook's first line (kept in Raw Content only, for reference), hook pattern (family), format, outline (3–8 beats), key points, engagement signals.
7. **Reframe for my channel:**
   - Idea title in my voice, Pillar, Content job, Topic tags, Cluster.
   - Why it works (one line).
   - Suggested hook: mine, not theirs.
   - Differentiation note: what I add that the source didn't.
   - Audience pain, Key claims to verify, Needs creator proof.
   - If it's outside my pillars or against my guardrails, still save it but set Status = Rejected with the reason.
8. **Duplicate topic?** Compare with open ideas (Status New through Scripted) on Cluster, Topic tags and meaning. Give the closest match a confidence from 0 to 1:
   - At or above the Settings merge threshold (0.8): add this source to that idea's Sources, set the new Raw Content Status = Duplicate, and don't create a new idea.
   - At or above the flag threshold (0.5): create the idea, tick Possible duplicate and set Duplicate of.
   - Below that: create it normally.
9. **Fit score:** score the 8 dimensions (Brand fit, Audience fit, Phase fit, Pillar fit, Trend signal, Novelty against the last 60 days of ideas and scripts, Originality, Scriptability) from 1 to 10. Set Fit score = the weighted average using the DNA weights. If Fit score ≥ the Settings auto-shortlist value, set Status = Shortlisted, otherwise New.
10. **Write:**
    - Raw Content row: Title, Creator (relation; create a Content Creators row with State = Suggested if the creator is new), Video URL, Canonical URL, Platform, Content type, Published, Views, Likes, Comments, Shares, Metrics captured at = now, Transcript (long text goes in the page body), Transcript source, Language, Fetch status, Discovered via = Manual, Status = Processed.
    - Idea row: everything from steps 7–9, Sources = that Raw Content row, with the source analysis in the page body (Idea page template).

Finish with one table: URL · result (New idea / Shortlisted / Merged into X / Possible duplicate / Rejected / Failed) · idea link · Fit score · what to do if it failed.
