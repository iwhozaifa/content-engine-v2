# Phase 0: Notion migration checklist

Turns the v1 starter kit into the v2 structure. Nothing is deleted, existing rows keep their data, and old property names are renamed rather than recreated, so relations and views survive.

**Before you start:** on the Content Engine page, go to ••• → Export → Markdown & CSV, include subpages, and keep the zip as a backup.

**Two ways to do it:**
- **With Claude Code:** run `/migrate` from this folder. It reads this file and does every step the Notion API allows. That covers properties, select options, renames and relations. Notion's API can't create views, so it prints the view list for you at the end.
- **By hand:** work down this list in Notion. It takes about 60–90 minutes.

Tick each box as you go. Labels: **R** = rename, **+** = add, **~** = change type/options.

---

## 1. Sources → Content Creators

- [ ] R database: `Sources` → `Content Creators`
- [ ] ~ `Platform` (select) → **Multi-select**, renamed `Platforms`. Options: Instagram, TikTok, YouTube, X, Blog
- [ ] R `Handle or URL` → `Profile URL` (type URL)
- [ ] + `Other profiles` (Text)
- [ ] R `Category` → `Niche`, ~ to **Multi-select**. Options = your 4 pillars + anything else you track
- [ ] `Priority`: keep (High, Medium, Low)
- [ ] + `State` (Select: Suggested, Active, Paused, Removed). Fill it from the old `Active` column (Yes → Active, No → Paused), then delete `Active`
- [ ] R `Last checked` → `Last scanned`
- [ ] R `Why I watch them` → `Notes`
- [ ] + `Baseline views` (Number), `Baseline velocity` (Number), `Baseline engagement %` (Number), `Baseline updated` (Date), `Lock baseline` (Checkbox)
- [ ] + `Suggested by` (Select: Me, Claude), `Suggestion reason` (Text)
- [ ] (Relations get added in step 2 and step 3.)

## 2. Raw Content

- [ ] ~ `Source creator` (text) → **Relation** to Content Creators, renamed `Creator`, two-way (the other side is named `Raw Content`). Re-link existing rows by name
- [ ] + `Canonical URL` (Text)
- [ ] + `Content type` (Select: Short, Long video, Article, Thread, Post)
- [ ] + `Shares` (Number), `Metrics captured at` (Date)
- [ ] + `Recurrence` (Number: how many watched creators posted the same topic in the lookback window; written by Claude)
- [ ] + `Transcript source` (Select: Captions, Whisper, Pasted, Article text, Browser, None)
- [ ] + `Language` (Select: English, Urdu, Hindi, Mixed, Other)
- [ ] + `Fetch status` (Select: OK, Partial, Failed, Private, Unsupported), `Fetch error` (Text)
- [ ] + `Discovered via` (Select: Manual, Auto scan)
- [ ] ~ `Status` options: New, Processed, Skipped, **Duplicate**
- [ ] + the formulas from section 6 below: `Days live`, `Outlier`, `Velocity ratio`, `Engagement %`, `Trend score`

## 3. Idea Bank

- [ ] ~ `Status` options, in this order: New, Shortlisted, Approved, Scripting, Scripted, In Production, Published, Archived, Rejected
- [ ] Move existing rows: Hold → Shortlisted, Planned → Approved, Used → Published. Then delete the Hold, Planned and Used options
- [ ] R `Original angle` → `Differentiation note`
- [ ] R `Total score` → `Fit score`
- [ ] + `Why it works` (Text), `Suggested hook` (Text)
- [ ] + `Topic tags` (Multi-select)
- [ ] + `Format` (Select: Short), `Target platforms` (Multi-select: Instagram, TikTok, YouTube Shorts)
- [ ] + `Sources` (**Relation** to Raw Content, two-way; the other side is named `Idea`). Keep the old `Source links` text column until the links are re-linked, then delete it
- [ ] + `Trend score` (Rollup: Sources → Trend score → Max)
- [ ] + `Review rank` (Formula, section 6)
- [ ] + `Duplicate of` (Relation to Idea Bank itself), `Possible duplicate` (Checkbox)
- [ ] + `My rating` (Select: 1, 2, 3, 4, 5)
- [ ] + `Is approved` (Formula, section 6)
- [ ] In Content Creators: + `Ideas` (Relation to Idea Bank), + `Ideas found` (Rollup: Ideas → count), + `Ideas approved` (Rollup: Ideas → Is approved → Checked), + `Hit rate` (Formula, section 6)

## 4. New database: Scripts

Create a full-page database named `Scripts` inside the Content Engine page with:

| Property | Type / options |
| --- | --- |
| Script | Title |
| Idea | Relation → Idea Bank (two-way; the other side is `Scripts`) |
| Version | Number |
| Previous version | Relation → Scripts |
| Status | Select: Draft, Needs revision, Revised, Approved, Superseded |
| Format | Select: Short |
| Platform | Multi-select: Instagram, TikTok, YouTube Shorts |
| Target length (s) | Number |
| Hook alternates | Text |
| Word count | Number |
| Est. seconds | Number |
| Similarity % | Number |
| Longest shared run | Number |
| Similarity flag | Select: OK, Review, Too close, Not checked |
| Feedback | Text |
| DNA version | Text |
| Voice guide version | Text |

- [ ] Scripts created
- [ ] Set `notion-pages/Short script template.md` as its default template (••• → Templates → New → paste → set as default)

## 5. Content Calendar → Content Plan (rename only in phase 0)

- [ ] R database: `Content Calendar` → `Content Plan`
- [ ] + `Idea` (Relation → Idea Bank, two-way; the other side is `Plan item`), + `Approved script` (Relation → Scripts)
- [ ] Leave everything else as is. The rest of the plan changes come in phase 3

## 6. Formulas (paste into each formula property)

Raw Content:

```
Days live
max(dateBetween(prop("Metrics captured at"), prop("Published"), "hours") / 24, 0.5)

Outlier
if(empty(prop("Views")), 0, round(prop("Views") / max(prop("Creator").map(current.prop("Baseline views")).first(), 1) * 100) / 100)

Velocity ratio
if(empty(prop("Views")), 0, round((prop("Views") / prop("Days live")) / max(prop("Creator").map(current.prop("Baseline velocity")).first(), 1) * 100) / 100)

Engagement %
if(empty(prop("Views")) or prop("Views") == 0, 0, round((if(empty(prop("Likes")), 0, prop("Likes")) + 2 * if(empty(prop("Comments")), 0, prop("Comments")) + 3 * if(empty(prop("Shares")), 0, prop("Shares"))) / prop("Views") * 10000) / 100)

Trend score
round(100 * (0.35 * min(prop("Outlier") / 4, 1) + 0.25 * min(prop("Velocity ratio") / 4, 1) + 0.20 * min((prop("Engagement %") / max(prop("Creator").map(current.prop("Baseline engagement %")).first(), 0.1)) / 3, 1) + 0.20 * min(if(empty(prop("Recurrence")), 0, prop("Recurrence")) / 5, 1)))
```

The weights (0.35 / 0.25 / 0.20 / 0.20) and caps (4×, 4×, 3×, 5 creators) are the Engine Settings defaults. Notion formulas can't read another page, so if you change them in Settings, edit this formula too.

Idea Bank:

```
Review rank
round(0.4 * if(empty(prop("Trend score")), 0, prop("Trend score")) + 0.6 * if(empty(prop("Fit score")), 0, prop("Fit score")) * 10)

Is approved
includes(["Approved", "Scripting", "Scripted", "In Production", "Published"], prop("Status"))
```

Content Creators:

```
Hit rate
if(prop("Ideas found") == 0, 0, round(prop("Ideas approved") / prop("Ideas found") * 100))
```

If a formula shows an error, the usual cause is a property name that doesn't match exactly, including capitals.

## 7. New pages

- [ ] Import `notion-pages/Engine Settings.md` into the Content Engine page
- [ ] Import `notion-pages/Brand Voice & Style Guide.md`, then reconcile it with your edited `Aliyan_AI_Content_DNA.md` (section 8 of the kit DNA moves here)
- [ ] Import `notion-pages/Idea page template.md` and set it as the Idea Bank default template

## 8. Views (manual: the Notion API can't create views)

| Database | View | Type | Filter / sort / group |
| --- | --- | --- | --- |
| Idea Bank | **Review Queue** | Table | Status is New or Shortlisted · sort Review rank ↓ · show Idea, Review rank, Trend score, Fit score, Pillar, Suggested hook, Possible duplicate, Status |
| Idea Bank | Possible duplicates | Table | Possible duplicate is checked |
| Idea Bank | Approved, to script | Table | Status is Approved |
| Idea Bank | Pipeline | Board | Group by Status |
| Content Creators | Active | Table | State is Active · sort Priority |
| Content Creators | Needs Review | Table | State is Suggested, or Baseline views is empty |
| Raw Content | Failed fetches | Table | Fetch status is Failed, Private or Unsupported |
| Scripts | Needs my review | Table | Status is Draft or Revised · sort Created ↓ |
| Scripts | By idea | Table | Group by Idea |

## Done test for phase 0

- [ ] All old rows are still there with their data
- [ ] Review Queue sorts by Review rank without errors
- [ ] A test Scripts row can link to an idea, and the idea shows it under Scripts
- [ ] Every formula column shows a number (0 is fine) rather than an error
