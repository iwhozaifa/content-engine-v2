+++
task = "brand_fit"
tools = []
+++
Judge how well one content idea fits the creator's brand. Be strict: a good topic that the creator can't add
anything to is not on brand.

## Brand profile
{{brand}}

## Topics covered in the last 60 days
{{recent}}

## Candidate ({{kind}})
{{candidate}}

## What to return
- brand_fit 0–10: fit with the positioning, pillars, audience, current growth phase and guardrails.
  0–3 off brand · 4–6 adjacent or generic · 7–8 on brand · 9–10 exactly what the creator should make.
- reason: one line, at most 20 words.
- pillar and content_job (Reach, Trust or Conversion).
- transformative_angle: how the creator would make this their own (their builder perspective, their audience's
  situation). It must transform the source, never repeat it. One or two lines.
- differentiation_note: what this adds beyond the source and the recent topics.
- red_flags: problems, each with severity "block" (hits a Topics-to-avoid guardrail, needs fabricated proof,
  get-rich-quick framing, a repeat of a recent topic) or "warn" (minor).
- needs_creator_proof: true if a good version needs the creator's own results or experience. Never invent them.
