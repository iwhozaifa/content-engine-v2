+++
task = "idea_extract"
tools = []
+++
Analyse one source video/article and reframe it as an idea for the creator's channel.

## Creator brand (Content DNA)
{{brand}}

## Source
{{source}}

## Open ideas already in the Idea Bank (for duplicate and novelty checks)
{{open_ideas}}

## What to return
1. Analyse the source: topic, its first line (verbatim, for reference only), hook pattern family
   (e.g. contrarian, mistake, how-to, list, story, proof, question), 3–8 outline beats, key points.
   Work from the transcript, but write the outline and key points in your own words.
2. Reframe for the creator: an idea title in the creator's voice, pillar (one of the DNA pillars), content job
   (Reach, Trust or Conversion), 1–4 topic tags, a short cluster label, why it works (one line), a suggested hook
   in the creator's own words (never the source's wording), a differentiation note (what the creator adds that the
   source didn't), the audience pain, key claims that would need verifying, and whether the creator's own proof
   is needed.
3. Score 1–10: audience_fit, phase_fit, pillar_fit, trend_signal (from the source's engagement and timeliness),
   novelty (against the open ideas; a near-duplicate scores ≤ 3), originality (room for a genuinely new angle),
   scriptability (works as a 25–35 s short).
4. Duplicate check: the open idea closest in topic and meaning, with a confidence 0–1 that it is the same idea
   (0 when the list is empty or nothing is close). Use its "i" number, or -1.
5. off_brand = true only if the topic is outside every pillar or hits a "Topics to avoid" guardrail; say why.
