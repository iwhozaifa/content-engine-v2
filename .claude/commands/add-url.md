---
description: Turn pasted URLs into reframed ideas in the Idea Bank (via the engine CLI)
---

Input: $ARGUMENTS = one or more URLs separated by spaces. Optional: the word `must-do` (guaranteed a slot in the next weekly plan), and `transcript:` followed by pasted text for the last URL.

1. If a transcript was pasted, save it to `tmp/transcript.txt`.
2. Dry-run: `.venv/bin/python cli.py add-url <urls> [--must-do] [--transcript-file tmp/transcript.txt]`. It fetches each link (`tools/fetch.py`, or the page for articles), dedupes by canonical URL, analyses and reframes with `prompts/idea_extract`, judges brand fit with `prompts/brand_fit`, and prints the ChangeSet and a result table.
3. If the dry-run shows no errors, run the same command with `--apply`. Nothing is written to Notion before this step.
4. Reply with the result table: URL · result (Shortlisted / New / Rejected / Merged / Needs Input / Already in) · fit · brand fit ✓/✗ · note.
   - **Needs Input:** show the hint. The fix is to paste the transcript into that Raw Content row's Transcript field, then run `/add-url` with no links (it runs `cli.py add-url --from-notion --apply`), or wait for the scheduled run.
   - If every Instagram link fails with a login hint, say once: "Log in to Instagram in Firefox (or set ENGINE_COOKIES_FILE), then retry".
   - An article the CLI can't read (login wall): open it with web fetch, save the main text to `tmp/transcript.txt`, and re-run with `--transcript-file`.

With no URLs: run `.venv/bin/python cli.py add-url --from-notion --apply`, which processes Raw Content rows you added with Status = New, and Needs Input rows that now have a transcript.

Never edit Notion rows by hand in this command; the CLI does every write.
