# Engine Settings

Version: 1.0 · Last updated: 2026-10-24

> Every Claude run reads this page first. Change a value here and the next run uses it, with no code changes. The trend weights are also written into the Raw Content `Trend score` formula, so if you change them, update that formula too.

## Discovery

| Setting | Value |
| --- | --- |
| Content DNA file | Aliyan_AI_Content_DNA.md |
| Voice guide | Brand Voice & Style Guide (this workspace) |
| Niches in scope | AI to Income, AI Leverage, Proof / Journey, Psychology of Execution |
| Platforms (paste a link) | YouTube, Instagram, TikTok, articles |
| Platforms (auto scan, phase 2) | YouTube Shorts |
| Platforms (publish) | Instagram, TikTok, YouTube Shorts |
| Lookback window (days) | 14 |
| Max posts per creator per scan | 15 |
| Minimum post age (hours) | 24 |
| Browser pace | Human: 3–6 s between links, one at a time |
| Login browser for fetching | Firefox (logged in to Instagram; TikTok/YouTube only if they ask) |
| Whisper model | small (base = faster, medium = better Urdu but slow) |
| Paid APIs / services | None |
| Max creators per run | 15 |

## Trend scoring

| Setting | Value |
| --- | --- |
| Weights: Outlier / Velocity / Engagement / Recurrence | 0.35 / 0.25 / 0.20 / 0.20 |
| Caps: Outlier / Velocity / Engagement / Recurrence | 4× / 4× / 3× / 5 creators |
| Thresholds: Outlier / Velocity / Engagement / Recurrence | 2.0 / 2.0 / 1.5 / 3 |
| Candidate if Trend score ≥ | 60 (or any single threshold met) |
| Baseline = median of last N posts | 20 |
| Baseline refresh | Monthly, unless Lock baseline is ticked |

## Review and dedupe

| Setting | Value |
| --- | --- |
| Review rank weights: trend / fit | 0.4 / 0.6 |
| Auto-shortlist if Fit score ≥ | 7 |
| Dedupe: merge if confidence ≥ | 0.8 |
| Dedupe: flag if confidence ≥ | 0.5 |
| Open statuses checked for duplicates | New, Shortlisted, Approved, Scripting, Scripted |

## Scripts

| Setting | Value |
| --- | --- |
| Format | Short vertical |
| Default length (s) | 25–35 |
| Beats | 4–6 |
| Hook alternates | 3 |
| Alternate lines per beat | 2 |
| Language mix | As in Content DNA (70% English / 30% Roman Urdu) |
| Similarity: Review if shared 5-grams ≥ | 4% |
| Similarity: Too close if shared 5-grams ≥ | 8%, or any identical run of 10+ words |
| Auto-rewrite when Too close | 1 attempt |
| Auto-write on schedule | Off (scripts only when you run /write) |
| Production extras (B-roll, on-screen text, titles, hashtags, thumbnails) | Off until phase 4 |

## Schedule

| Setting | Value |
| --- | --- |
| Where runs happen | This laptop (Claude Cowork / Claude Code + Notion) |
| Sunday run | 09:00, from phase 2 |
| Cadence | Mon–Fri, 1 short per day |

## Change log

- 1.0 (2026-10-24): first version
