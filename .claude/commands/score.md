---
description: Score ideas in the Idea Bank for brand fit (via the engine CLI)
---

Input: $ARGUMENTS = idea titles (or parts of them), or empty for every open idea that has no brand-fit reason yet. Add `rescore` to re-judge ideas that already have one.

1. Dry-run: `.venv/bin/python cli.py score [titles…] [--rescore]`. It judges each idea with `prompts/brand_fit` (Brand fit 0–10, reason, transformative angle, red flags), sets Brand fit pass (score ≥ the Engine Settings threshold and no blocking flag), recomputes Fit score with the DNA weights, and moves New → Shortlisted when Fit score ≥ the auto-shortlist value.
2. Run the same command with `--apply`.
3. Show the table it prints: brand fit · pass · fit · idea · reason. Ideas that fail brand fit stay in the Idea Bank but are never used to fill weekly slots.

Approval stays mine: this never sets Approved or Rejected.
