# P1-DATA-001 — Data foundation (code v0.1): snapshot lake, DuckDB load, data quality

TASK ID: P1-DATA-001
RESPONSIBLE AGENT: data-engineer (executed by the Orchestrator session, agents a0.1)
OBJECTIVE: Stand up the snapshot-first ingestion, the DuckDB schema and loaders, and the data-quality
layer; backfill 2010–2026 from nflverse; start the daily injury snapshots for the live season.
QUESTION / HYPOTHESIS: n/a (engineering)
INPUT DATA: nflverse-data release assets listed in config/sources.yaml (15 datasets); teams, players.
DATA CUTOFF: snapshots retrieved 2026-10-08 13:08–13:21 UTC (see data/metadata/snapshots.jsonl)
METHOD: download release asset bytes → sha256 → Parquet file + .meta.json + index row → load into DuckDB
with snapshot_id per row; replace-by-season for per-season files, replace-all for single files,
append-per-snapshot (with observed_at) for injuries. nflverse schedule lines copied into
market.historical_lines with source=nflverse, book_id=nflverse, line_class=last_pull, spread_home = −spread_line.
ASSUMPTIONS:
- nflverse `spread_line` is positive when the home team is favored (verified: aligns with `result` sign convention in the dictionary).
- The curated play-by-play column list (PBP_COLUMNS in src/edgelab/db/load.py) is sufficient for v0 features; the full file remains in the lake.
- Depth charts ≤2024 and ≥2025 are different datasets (nfl.depth_charts_weekly vs nfl.depth_chart_snapshots).
RESULTS:
- 145 unique snapshots (152 index rows incl. "checked, unchanged"), 356 MB lake; database 360 MB.
- nfl.games 7,548 (1999–2026); 2010–2025: 0% null spread, 0% null ML except one game (2017_04_CHI_GB missing moneyline); 2026: lines populated weeks 1–6.
- nfl.plays 781,492 (2010–2026; ~47–50k per season; 11,155 for 2026 weeks 1–4); null EPA on pass/run plays 0.0%.
- nfl.injury_reports 87,205 (2010–2026); 2026 first daily snapshot 1,274 rows; 2025+ rows untimestamped upstream (7,342).
- nfl.team_week_stats 8,854; player_week_stats 291,636; rosters_weekly 669,986; snap_counts 330,582 (2012–2026);
  pfr_pass_week 5,574 / pfr_def_week 64,155 (2018–2026); ftn_charting 196,044 (2022–2026); ngs_passing 6,100; espn_qbr_week 10,836;
  depth_charts_weekly 552,514 (≤2024), depth_chart_snapshots 1,174,266 (2025–2026).
- ref.players 24,844; null id rates pfr 8.7%, espn 33.3%, pff 53.2% (matches P0-DATA-001).
- market.historical_lines 7,369 rows, all line_class=last_pull.
- Data quality: 19 checks, 0 CRITICAL, 2 WARN (the two items above). Report: reports/quality/.
- Tests: 32 passing (odds math 13, snapshots 5, normalizer 2, schema 3, handoff schema 1, leakage register 1, …); ruff clean.
UNCERTAINTY: none quantified; engineering deliverable.
LIMITATIONS:
- The Odds API host is blocked by the sandbox network allowlist; odds snapshots not yet captured (normalizer tested on a fixture only).
- Officials disabled (upstream stale). Participation available only ≤2025 (not loaded yet; registered).
- Injury rows for 2025 carry no timestamp; only 2026 rows from today onward have a usable observed_at.
- nfldata closing_lines.csv (2006–2018) registered but not ingested (Phase 3).
REPRODUCIBILITY: commit e5adeda; `uv sync --extra dev && uv run edgelab ingest nflverse --seasons 2010-2026 && uv run edgelab db load --seasons 2010-2026 && uv run edgelab quality`;
Python 3.13 (cloud) / 3.10 (Mac); duckdb 1.5.6, polars 1.44.2, nflreadpy 0.1.5; no seeds involved.
Reproduced on a second machine (Dennis's Mac workspace): identical row counts and DQ result.
RECOMMENDATION: accept as the Phase 1 foundation; proceed to Phase 2 (as-of feature builder) after the data audit.
FILES / ARTIFACTS PRODUCED: src/edgelab/{config.py,cli.py,ingest/*,db/*,quality/*,pricing/odds.py}, config/*.yaml,
docs/LEAKAGE_REGISTER.md, data/metadata/snapshots.jsonl, reports/quality/dq_20261008T131611Z.md, tests/.
AUDIT STATUS: REVISION_REQUIRED (audit 1, artifacts/audit/P1-DATA-001.audit.md) → revised, re-audit requested
REVISION (2026-10-08, after audit 1):
- B1 fixed: tz-aware upstream timestamps now stored as TIMESTAMPTZ on the ALTER path; `connect()` sets TimeZone=UTC; verified 2024-09-06 19:05:30 UTC round-trips; DQ checks `time.naive_timestamp_columns`, `injuries.date_modified_tz`; unit test tests/schema/test_timezones.py.
- M1 fixed: quarantine list now covers L1–L4 (lines, roof, stadium, results, QB columns); test tests/leakage/test_quarantine.py parses the register.
- M2 documented: rosters_weekly key includes status; as-of rule "prefer ACT" recorded in config/sources.yaml.
- M3 fixed: git-tracked `schedule_lines` extract (live values for unplayed games) derived from every changed schedules snapshot and appended to market.historical_lines as line_class='live'; completed games keep 'last_pull'. 29 live rows preserved for week 5–6 today.
- M4 fixed: `nfl.games.kickoff_utc` derived from gameday+gametime (America/New_York → UTC); DQ check; unit test for London/ET/null cases.
- minors: unique snapshot ids on same-second collisions; tables stamped with the primary snapshot id; snap_counts first_season=2013; corrected keys for espn_qbr_week/depth_charts/injuries/rosters; DQ check for 2010 null date_modified (62 rows, WARN); DQ check count is now 23.
- Audit verdict recorded via `edgelab audit record` (lab.audit_results).
NEXT ACTION: auditor — scoped re-audit (timestamps raw-vs-loaded, quarantine vs L1–L4, rosters key rule, schedule-line persistence, kickoff_utc samples).
