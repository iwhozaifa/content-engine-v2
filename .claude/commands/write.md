---
description: Write draft scripts for every Approved idea (or the ones named)
---

Read Engine Settings (Notion page), the Brand Voice & Style Guide (Notion page) and Aliyan_AI_Content_DNA.md first. Use the Notion MCP tools to read and write the databases, using the exact property names that exist there.

Input: $ARGUMENTS = idea titles, or empty for every Idea Bank row with Status = Approved and no Scripts row yet.

For each idea:

1. Set the idea's Status = Scripting.
2. **Research check:** if the idea has claims to verify or anything time-sensitive, verify them with web search first, and add a short "Research" section to the idea page: verified facts with links, risky claims to soften or drop, FACT / INTERPRETATION / MY POV labels. If it needs my proof and I haven't given it, write ⚠️ CREATOR INPUT REQUIRED: [exactly what] on the idea, set it back to Approved, skip it, and tell me.
3. **Inputs to the writer:**
   - The idea fields (why it works, suggested hook, differentiation, pillar, job), the source **outline and key points only** (not the transcript), and the research.
   - The Brand Voice & Style Guide in full, including its examples and rules learned.
   - Engine Settings script values, and a CTA from the CTA Bank matched to the content job.
4. **Write a short vertical script** (25–35 s; Settings may say otherwise):
   - 3 hook alternates for the first 3 seconds, from 3 different Hook Library families. Mark the strongest H1.
   - 4–6 beats. Each beat has the spoken line plus 2 alternate lines that make the same point differently, so any choice still flows.
   - One CTA line + 1 alternate.
   - A loop ending only if loop potential is Medium or High.
   - Language mix and tone from the voice guide. No invented numbers or personal claims.
   - Spoken lines only: no B-roll, on-screen text, titles, hashtags or thumbnails.
5. **"Ready to read":** H1 + the main spoken lines + CTA, one beat per line. Count the words and estimate seconds at 2.6 words/second. If it's over the target, cut filler from the main lines (never from lines I've edited) and say what you cut.
6. **Originality check:**
   - Save the "Ready to read" text plus all alternates to `tmp/<idea>-script.txt` and the source transcript to `tmp/<idea>-source.txt`.
   - Run `python3 engine.py similarity --script ... --source ...` with the Settings thresholds.
   - Also judge whether any example, story, number or the distinctive structure was lifted from the source.
   - If the flag is Too close, rewrite the flagged lines once and re-run. If it's still Too close, keep the result and list the flagged lines for me.
   - With no transcript, the flag is Not checked and only the judgement applies; say so.
7. **Save:**
   - New Scripts row: Script = "<idea title> v1", Idea relation, Version = 1, Status = Draft, Format = Short, Platform = Instagram + TikTok + YouTube Shorts, Target length, Hook alternates, Word count, Est. seconds, Similarity %, Longest shared run, Similarity flag, DNA version, Voice guide version.
   - The page body follows the Short script template.
   - Set the idea's Status = Scripted.

Finish with a table: idea · script link · words · est. seconds · similarity flag · anything that needs me.
