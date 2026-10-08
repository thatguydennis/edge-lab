# Data audit checklist
Run before any model trains on a new source or snapshot set.
- [ ] Every snapshot named in the handoff exists, sha256 matches `.meta.json` and `data/metadata/snapshots.<machine>.jsonl`
- [ ] `.meta.json` has url, retrieved_at (UTC), loader_version; upstream last_modified recorded when the server sent it
- [ ] Table schemas match `src/edgelab/db/schema.sql`; no silent column drops or type changes vs the registered dictionary
- [ ] `edgelab quality` report: zero CRITICAL; every WARNING acknowledged in the handoff
- [ ] Duplicate games / plays / player-week rows: none
- [ ] Team codes resolve through `ref.team_aliases` (no orphan codes); franchise continuity across OAK→LV, SD→LAC, STL→LA
- [ ] Player ID join rates reported (gsis↔pfr, gsis↔espn) and plausible vs P0-DATA-001
- [ ] Every row in `market.*` has source, book_id, observed_at, line_class; no `close` label without documented source
- [ ] Post-game schedule columns (referee, temp, wind, result, actual QB) are in the quarantine list
- [ ] 2025+ injury rows carry `observed_at` from our own snapshots or are flagged `untimestamped`
- [ ] Coverage by season table included (first/last season, row counts, null rates on key columns)
- [ ] Licensing/attribution recorded in config/sources.yaml for each dataset
