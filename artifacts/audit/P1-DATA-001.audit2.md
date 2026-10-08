# Audit 2 — P1-DATA-001 revision (scoped re-audit)

Auditor: auditor (agents a0.1). Audited 2026-10-08, after audit 1 (`artifacts/audit/P1-DATA-001.audit.md`, verdict REVISION REQUIRED).
No project file modified; DB opened read-only; `lab.audit_results` left to the orchestrator (`edgelab audit record`).

## 1. What was reviewed

- Repository at commit `31bc13a` (confirmed `git rev-parse --short HEAD`; working tree clean apart from my scratch files).
- Diff `353addd..31bc13a`: `src/edgelab/db/{__init__.py,load.py}`, `ingest/{nflverse.py,snapshots.py}`, `quality/checks.py`, `cli.py`, `config/sources.yaml`, `.gitignore`, `pyproject.toml`, `tests/leakage/test_quarantine.py`, `tests/schema/test_timezones.py`, the revision section of `artifacts/handoffs/P1-DATA-001.md/.json`, the new index rows (schedules 13:41:22 and derived `schedule_lines`), the git-tracked `data/snapshots/nflverse/schedule_lines/20261008T134122+0000_all_69db1aee.parquet` + `.meta.json`, reports `dq_20261008T134319Z.md` / `dq_20261008T134358Z.md`.
- Rebuilt DuckDB `data/db/edgelab.duckdb` (mtime 13:45:13 UTC).
- Scratch: `artifacts/audit/P1-DATA-001/10_reaudit.{py,out}`, `11_reaudit_tests.out`.

## 2. What passed (recomputed)

| Scope item | Result |
|---|---|
| (1) B1 timestamps | `connect()` sets `TimeZone='UTC'` (verified on the read-only connection); `_duck_type` maps tz-aware Datetime → TIMESTAMPTZ. `nfl.injury_reports.date_modified` is `TIMESTAMP WITH TIME ZONE`. Every 2010–2024 injury snapshot re-read from the lake and compared row-by-row (multiset per key) against the DB: **79,863 rows compared, 0 mismatches** (e.g. raw `2024-09-06 19:05:30 UTC` → stored `2024-09-06 19:05:30+00`). `ftn_charting.date_pulled` also round-trips. **No naive TIMESTAMP column exists anywhere in nfl/market/lab** (direct `information_schema` query, not the name-pattern DQ check). Unit test `test_tz_aware_column_roundtrips_in_utc_via_alter_path` covers the ALTER path that carried the bug. |
| (2) Quarantine | `quarantine_columns` now holds all L1 line columns (spread_line, home/away_spread_odds, total_line, over/under_odds, home/away_moneyline), L2 (referee, temp, wind, roof, stadium, stadium_id), L3 (result, total, overtime, scores), L4 (QB id/name) — the full set audit 1 listed. `tests/leakage/test_quarantine.py` asserts the hardcoded set and any `nfl.games.<col>` in register rows L1–L4; passes. |
| (3) Rosters key | `sources.yaml` documents the 2010–2015 multi-status rows, key now `[season, week, team, gsis_id, status]`, as-of rule "prefer ACT" recorded. (See C3 for what the rule does not cover.) |
| (4) Schedule-line persistence | `schedule_lines` dataset registered (derived, `tracked_in_git: true`), in `TRACKED_DATASETS`, `.gitignore` allow-listed; the 29-row extract and its `.meta.json` are in git (`git ls-files`), sha256 matches index and meta. `market.historical_lines`: 29 rows `line_class='live'` (1 snapshot, observed 13:41:22 UTC) and 7,340 `last_pull`; **0 duplicates per (game_id, snapshot_id)**; 0 live rows for completed games; 0 last_pull rows for unplayed games; 0 live rows with `observed_at >= kickoff_utc`; loaded live values equal the raw extract (spread_home = −spread_line, ML, total) for all 29; the extract's `derived_from` is the same schedules snapshot that `nfl.games` is loaded from; no line in weeks 5–6 moved between the 13:08 and 13:41 pulls. `build_historical_lines_from_games` now deletes/rebuilds only `last_pull` and only for `result IS NOT NULL`. |
| (5) kickoff_utc | `nfl.games.kickoff_utc` is TIMESTAMPTZ. 2026_05_PHI_JAX 09:30 ET → 13:30 UTC; 2026_05_TB_DAL Thu 20:15 ET → 00:15 UTC next day; 2026_05_CHI_GB 13:00 → 17:00; 2025_01_KC_LAC (São Paulo, Fri 20:00 ET) → 00:00 UTC; 2023_12_CHI_MIN Mon 20:15 → 01:15 UTC (EST); 2010_01_MIN_NO Thu 20:30 → 00:30. All 259 null-`gametime` rows (1999) have null `kickoff_utc`; 0 rows with gametime but no kickoff_utc. Round trip UTC→America/New_York reproduces `gameday` and `gametime` for all 7,289 rows; DST handled (13:00 ET → 17:00 UTC Sep/Oct, 18:00 UTC Nov–Jan). Independent cross-check: for all 285 games of 2025, the first play-by-play `time_of_day` falls 0–60 min after `kickoff_utc`. |
| (6) Quality / tests / lint | `run_checks()` on the final DB (read-only reproduction of `edgelab quality`; the CLI would write a report and DB rows): **24 checks, 0 CRITICAL, 3 WARN** (2017_04_CHI_GB moneyline; 62 null `date_modified` 2010 wk1; 7,342 untimestamped 2025+). `uv run pytest -q`: 35 passed. `uv run ruff check src tests`: clean. |
| Minors from audit 1 | m1 same-second id collision → suffix `.n` (code); m2 rows and `lab.load_runs` now stamped with the primary snapshot id (0 rows reference a `duplicate_of` entry); m3 `snap_counts.first_season: 2013`, 2012 not loaded; m4 DQ report regenerated at the revision commit (24 checks); m5 keys corrected for espn_qbr_week (`game_week`), depth_charts (adds `depth_position`, documents upstream dupes), injuries (documents dupes); m6 `injuries.null_date_modified_2010_2024` WARN check added (62). Row counts unchanged (games 7,548; plays 781,492; injuries 87,205). `lab.audit_results` carries audit 1's verdict. |

## 3. Remaining findings

**C1 — major (condition): the live-line extract can mislabel post-kickoff values as `live`.** `derive_schedule_lines` keeps rows with `gameday >= retrieved_at[:10]` (UTC date). A pull made after a same-day kickoff — e.g. any Sunday pull after 17:00 UTC, or a Thursday pull after 00:15 UTC Friday is already excluded only by the date rollover — would store in-progress/closed values with `line_class='live'` and `observed_at` after kickoff. Today's 29 rows are all genuinely pre-kickoff (0 rows with `observed_at >= kickoff_utc`), so no data is wrong yet, but the daily job's run time is still undecided (PROJECT_STATE), so the hole will open the first Sunday it runs late. Fix: filter on `kickoff_utc > retrieved_at` (derive it in the extract the same way as `_prepare`) and add a DQ CRITICAL check `live rows with observed_at >= kickoff_utc` (currently 0). Responsible: data-engineer, before `edgelab ingest daily` is scheduled.

**C2 — minor: the final DB state is not covered by a recorded DQ run, and the committed report disagrees with it.** `dq_20261008T134358Z.md` (and its `lab.data_quality_runs` row) reports `market.live_line_observations = 58`; the DB now holds 29 and was modified at 13:45:13 UTC, after that run, with no `lab.load_runs`, `lab.data_quality_runs` or `lab.events` entry describing the correction (evidently a manual delete of a doubled live insert). The handoff says 29. Rule 8 ("record, don't overwrite"): log the correction in `lab.events`/CHANGELOG and re-run `edgelab quality` so the recorded run matches the data. Responsible: data-engineer / orchestrator.

**C3 — minor: the rosters as-of rule is incomplete.** With the 5-column key there are still 71 exact duplicate rows, and "prefer ACT" does not resolve 1,165 player-weeks (2010–2015) whose duplicate rows contain no ACT (RES+TRC 204, CUT+TRC 194, DEV+TRD 167, CUT+TRD 141, …). State a full precedence order (or a dedup rule) and add the DQ check audit 1 asked for on the key actually used. Responsible: data-engineer (can land with the Phase-2 feature builder).

**C4 — minor: audit-1 minors m7, m8, m9 were neither addressed nor explicitly deferred** in the revision note: coverage-by-season table with null rates (checklist item), an in-table/ documented flag for "untimestamped" 2025+ injury rows (L5 wording), and the dictionary entries for the recorded type drift (rosters draft_number/jersey_number VARCHAR, height DOUBLE, 2010–2015 null depth_chart_position/ngs_position, injuries season_type, the one negative-hold ML pair). Add an explicit deferral line to the handoff or address them. Responsible: data-engineer.

**Note (no action required now):** `time.naive_timestamp_columns` is a column-name pattern check; string-typed event times (`nfl.plays.time_of_day`, `nfl.plays.game_date/start_time`, `nfl.depth_chart_snapshots.dt`, `nfl.games.gameday/gametime`) stay VARCHAR (ISO `…Z` for `dt`/`time_of_day`). That is acceptable for v0.1 but the feature layer must parse them as UTC explicitly; worth a dictionary line.

## 4. Verdict

**APPROVED WITH CONDITIONS.**

The blocker (B1) is fixed and verified against the raw lake for every 2010–2024 injury row; the four majors are fixed (M1, M3, M4) or documented (M2); the DQ layer now catches the failure class (naive timestamps, missing kickoff_utc, mislabeled nflverse lines). The data at commit `31bc13a` may be used as the Phase-1 foundation and read by the Phase-2 as-of feature builder.

Conditions: C1 must be fixed before the daily ingest job is scheduled (and in any case before any `live` row is used as a pre-game line); C2 before the next handoff; C3 and C4 may be deferred to Phase 2 with an explicit note in the handoff.

## 5. Re-audit required

**No.** C1–C4 are verifiable by the orchestrator from the diff and a `edgelab quality` run; the next data audit (first daily-job cycle or the Phase-2 leakage audit) should confirm `live rows with observed_at >= kickoff_utc = 0` and the recorded correction for C2.
