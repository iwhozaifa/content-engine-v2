# Rolling back a schema migration

`migrate-schema` is **additive only**: it adds databases, properties, select options, Engine Settings rows and Brand Profile sections. It never removes or renames anything, and existing rows and formulas are untouched. Rolling back is therefore optional: the old engine ignores properties it doesn't know.

## Code
1. `git revert <squash commit of the phase>` on `main`, then re-tag if needed.

## Notion (only if you want the additions gone)
Compare the snapshots taken before and after the phase:

```bash
diff -r schema/snapshots/2026-10-28-pre-p1 schema/snapshots/2026-10-28-post-p1
```

| Added in P1 | How to remove |
|---|---|
| Databases Run Log, News Candidates, Weekly Plans | Content Engine page → ••• on the database → Delete (restorable from Trash for 30 days). Remove the `[databases.<key>]` block from `config/notion_ids.toml` |
| Properties listed in the post-p1 snapshot but not in pre-p1 | Database → property header → Delete property. Relations: deleting one side removes the synced side too |
| New select options (e.g. Content Plan Status "Topic Locked") | Property → Edit property → remove the option (rows using it lose the value) |
| Engine Settings "Engine v3 settings" table | Delete the heading and table on the Engine Settings page |
| Brand Profile "Topics to avoid", "Example good ideas", "Example bad ideas" | Delete the sections on the DNA page |

The engine never deletes Notion content itself; these steps are done by hand.
