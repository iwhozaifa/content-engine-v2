---
description: Plan next week's slots and lock topics (via the engine CLI)
---

Input: $ARGUMENTS = optional week start (a Monday, YYYY-MM-DD). Default: the Monday after today.

1. Dry-run: `.venv/bin/python cli.py weekly-plan [--week YYYY-MM-DD]`. It fills the open slots from Engine Settings "Cadence" in this order: Must-Do ideas → approved news ideas → Shortlisted/Approved creator ideas that pass brand fit (one per cluster). Each placement gets a Content Plan row with Status Topic Locked, Approval Pending and a Suggested post date, and the idea moves to Topic Locked. A Weekly Plans page lists the week.
2. If the dry-run looks right, run the same command with `--apply`.
3. Show the slot list it prints, any Must-Do that didn't fit, and remind me that approval is mine (Content Plan → Approval).

No scripts are written here. Cards come from `/cards`.
