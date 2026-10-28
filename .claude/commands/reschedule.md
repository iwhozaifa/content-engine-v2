---
description: Apply my Approval decisions in the Content Plan (via the engine CLI)
---

1. Dry-run: `.venv/bin/python cli.py reschedule`.
   - **Postponed** → moved to the first open slot in a later week. Original date and Date history are kept, the content card stays linked, and Approval goes back to Pending.
   - **Rejected** → the slot is released (Topic locked off) and the idea is set to Rejected.
   - **Approved** with a chosen variation (Script Chosen) → Ready to Post. Approved without a chosen variation waits.
2. Run the same command with `--apply`.
3. Show its report (moved / released / ready / waiting).

Only I set Approval. This command never approves anything.
