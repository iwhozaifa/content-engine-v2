# Content Engine v2 (Claude Code + Notion)

This folder runs Aliyan's content engine. Notion is the database and UI; Claude Code (and Claude Cowork for browsing) does the work.

Read these before every task:
- **Engine Settings** (Notion page): thresholds, lengths, platforms, what's switched on.
- **Brand Voice & Style Guide** (Notion page): how scripts sound. Rules in its "Rules learned" section are mandatory.
- **Aliyan_AI_Content_DNA.md** (this folder): niche, audience, pillars and weights, content jobs, growth phase, guardrails. If the Notion copy has a newer version number, use that and tell me to update this file.

Databases: Content Creators, Raw Content, Idea Bank, Scripts, Content Plan, Hook Library, CTA Bank. Check property names with the Notion tools before writing.

Helpers (free, local): `.venv/bin/python fetch.py <url> ...` (YouTube, Instagram, TikTok: metadata + transcript as JSON), `python3 engine.py canon <url>` (dedupe key) and `python3 engine.py similarity --script a.txt --source b.txt` (originality check). Never use paid APIs or services. Downloaded metadata and transcripts go in `raw/` (gitignored); scratch script files go in `tmp/`.

Rules:
1. Concise, structured output. Tables and short lines. No essays.
2. Take ideas, pains, structure and hook *patterns* from other creators. Never their wording, examples or stories. Never pass a full source transcript into script writing: use the outline and key points.
3. Never invent income, ROI, client results, stats, quotes or personal experiences. If my proof is needed, write ⚠️ CREATOR INPUT REQUIRED and stop.
4. My edits are final. Never reword a line I changed unless I ask.
5. Every idea keeps its Sources relation (provenance).
6. Approval is mine. Don't set an idea to Approved, a script to Approved, or anything Published without my word. /write only runs on ideas I already set to Approved.
7. Scripts are spoken lines only for now: no B-roll, on-screen text, titles, hashtags or thumbnails, until Engine Settings switches production extras on.
8. If a step fails, record it on the row (Fetch status / Fetch error, or a note), finish the rest, and report what failed at the end.

Commands: /migrate (phase 0, once) · /add-url · /score · /research · /write · /revise · /options · /plan-week · /carousel
