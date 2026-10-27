---
description: Phase 0 - migrate the v1 Notion databases to the v2 structure (run once)
---

Read Engine Settings (Notion page), the Brand Voice & Style Guide (Notion page) and Aliyan_AI_Content_DNA.md first. Use the Notion MCP tools to read and write the databases, using the exact property names that exist there. (Engine Settings and the voice guide may not exist yet; that's expected.)

Follow setup/Notion migration checklist.md (or the path I give in $ARGUMENTS) step by step.

1. First, list every database under the Content Engine page with its properties, and compare with the checklist. Show me a short table of differences (missing, extra, renamed) and **wait for my "go"** before changing anything.
2. Then do sections 1–6 in order. For each: renames first, then type/option changes, then new properties, then relations, then formulas. Never delete a property that still holds data unless the checklist says to move the data first, and do that move before deleting.
3. Status moves (Idea Bank Hold → Shortlisted, Planned → Approved, Used → Published; Sources Active → State): update every row, then report the counts.
4. Re-link text columns to relations (Raw Content "Source creator" → Creator, Idea Bank "Source links" → Sources) by matching names and URLs. List anything you couldn't match, and keep the old text column until I confirm.
5. Create the Scripts database and import the pages in notion-pages/ if they're missing.
6. You can't create views through the API: finish by printing the section 8 view table for me to make by hand.
7. Run the phase 0 done test and report pass/fail per line.

If any API call is refused, stop that step, tell me exactly what to click in Notion, and continue with the next step.
