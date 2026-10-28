---
description: Make the next version of any script marked Needs revision
---

Read Engine Settings (Notion page), the Brand Voice & Style Guide (Notion page) and docs/brand/Aliyan_AI_Content_DNA.md first. Use the Notion MCP tools to read and write the databases, using the exact property names that exist there.

Input: $ARGUMENTS = script names, or empty for every Scripts row with Status = Needs revision.

For each script:

1. Read its Feedback property and the "Feedback for next version" section, plus any lines I edited directly on the page. **Edited lines are locked:** keep them word for word.
2. Feedback can be general ("more punchy", "less Urdu in beat 2") or picks ("use H2", "beat 3 alt 1", "drop beat 5"). Apply picks exactly, then rewrite only what the feedback touches.
3. Rebuild "Ready to read", recount words and seconds, and run the originality check as in /write step 6.
4. Create a new Scripts row "<idea title> v<n+1>": Version = n+1, Previous version = the old row, Status = Revised, all fields refreshed. Set the old row to Superseded.
5. Add an entry to the What Worked log if that database exists (Type = Script feedback, the feedback text, Applies to = Voice or Hooks). If it doesn't exist yet, skip this.

Finish with: script · what changed (one line) · words · est. seconds · similarity flag.
