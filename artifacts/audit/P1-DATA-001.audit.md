# Audit — P1-DATA-001 (data foundation, code v0.1)

Auditor: auditor (agents a0.1), adversarial data audit per `.claude/agents/auditor/checklists/data.md`.
Audited: 2026-10-08. Working tree clean at start and end (`git status`: only `artifacts/audit/` untracked).
No project file was modified; `lab.audit_results` not written (no `edgelab audit record` command exists and the DB was opened read-only) — this file is the record.

## 1. What was reviewed

- Repository `/home/claude/edge-lab` at commit `353addd994064fbb2f555e21dbdf8201e8afa26c` (handoff commit; code identical to `e5adeda` named in the handoff).
- Handoff `artifacts/handoffs/P1-DATA-001.md` + `.json`; `config/sources.yaml`, `config/settings.yaml`, `docs/LEAKAGE_REGISTER.md`, `src/edgelab/{db/load.py,db/schema.sql,db/__init__.py,ingest/snapshots.py,ingest/nflverse.py,quality/checks.py,cli.py}`, `reports/quality/dq_20261008T131611Z.md`, `tests/`.
- Snapshot index `data/metadata/snapshots.jsonl` (153 rows, 152 unique ids, 145 primary snapshots) and every primary snapshot file under `data/snapshots/` (all 145 hashed, not just a sample); DuckDB `data/db/edgelab.duckdb` opened read-only.
- Scratch scripts and outputs: `artifacts/audit/P1-DATA-001/01_counts.py … 09_tz_repro.out`.

## 2. What passed (recomputed, not re-read)

| Check | Result |
|---|---|
| Snapshot integrity | All 145 primary files exist; sha256 recomputed for all 145 = index = `.meta.json`; byte sizes match; 12-file random sample listed in `02_snapshots.out`. All index rows carry `url`, `retrieved_at` (UTC, `+00:00`), `loader_version`, `sha256`, `last_modified` (server sent it for every asset). Every `snapshot_id` stamped on DB rows exists in the index; every loaded snapshot is the latest for its (dataset, season). |
| Row counts | nfl.games 7,548 (1999–2026, 7,548 distinct game_id); nfl.plays 781,492 (2010–2026; 2026 = 11,155 rows / 64 games, weeks 1–4); injury_reports 87,205 (17 snapshots); team_week_stats 8,854; player_week_stats 291,636; rosters_weekly 669,986; snap_counts 330,582; pfr_pass 5,574; pfr_def 64,155; ftn 196,044; ngs 6,100; qbr 10,836; depth_charts_weekly 552,514; depth_chart_snapshots 1,174,266; ref.players 24,844; market.historical_lines 7,369 — all match the handoff. |
| Null rates | 2010–2025: spread_line 0 null, total_line 0 null, moneyline null in exactly 1 game (2017_04_CHI_GB); 2026 lines populated weeks 1–6, null weeks 7–18 (179 games). EPA null on pass/run plays 0.0005 %. ref.players pfr_id 8.7 % / espn_id 33.3 % / pff_id 53.2 % null, 0 duplicate gsis_id — matches P0-DATA-001. |
| Sign convention | `result = home_score − away_score` for all 4,427 completed 2010–2026 games (0 mismatches); `total = home+away` 0 mismatches. `spread_line > 0` ⇒ home favored: corr(spread_line, result) = +0.43; when home is favored the home team wins SU 67.2 %, when away is favored the away team wins 64.4 %; moneyline favorite agrees with spread favorite in 3,440/3,440 games with |spread| ≥ 3. `market.historical_lines.spread_home = −spread_line` for all 4,427 rows; favorite-by-`spread_home` SU rate 62–71 % every season 2010–2026; home cover rate 49.2 % (push 2.6 %); odds/total/ML columns copied without error. pbp `spread_line`/`result` agree with the schedule for all 4,427 games. |
| Team codes | All 35 codes in nfl.games (and posteam/home/away in plays, team in every other table, club_code in depth charts) resolve through `ref.team_aliases`; OAK→LV, SD→LAC, STL→LA continuity correct (OAK 1999–2019 / LV 2020–; SD –2016 / LAC 2017–; STL –2015 / LA 2016–). |
| Duplicates | nfl.games game_id 0; nfl.plays (game_id, play_id) 0; team_week_stats 0; player_week_stats (season, week, player_id, team) 0; snap_counts, pfr_*, ftn, ngs 0; market.historical_lines 0. |
| Market provenance | 7,369 rows, all source=nflverse, book_id=nflverse, line_class=last_pull, observed_at set (2026-10-08 13:12:57 UTC), snapshot_id set; no `close` label anywhere. |
| Quarantine of post-game columns | referee, temp, wind, result, total, overtime, scores, home/away_qb_id/name are in `quarantine_columns` (see M1 for what is missing). 2026 unplayed games: referee/temp/wind null, but home_qb_id populated for all 15 week-5 games — confirms L4 (projected starter overwritten later). |
| 2025+ injuries | All 7,342 rows carry `observed_at` from our own snapshots (2026-10-08 13:12–13:13 UTC); 2026 first daily snapshot = 1,274 rows (weeks 1–5). |
| `edgelab quality` | Reproduced via `run_checks()` on a read-only connection (the CLI would write a report + DB rows): 19 checks, 0 CRITICAL, 2 WARN (same two as the handoff). |
| Tests / lint | `uv run pytest -q`: 32 passed. `uv run ruff check src tests`: clean. |
| Player-ID joins | player_week_stats→rosters (gsis, 2024) 0.12 % unmatched; snap_counts pfr_player_id→ref.players 0.16 %; espn_qbr player_id→espn_id 0.0 %; injuries gsis→ref.players 0.0 %. |
| Licensing | nflverse CC BY 4.0, FTN CC-BY-SA with attribution string, PFR usage terms recorded in `config/sources.yaml`. |
| Other sanity | Moneylines never both positive, |ML| ≥ 100 always, implied hold 0.98–1.05 (one upstream oddity, see m9); spread range −18..+27, totals 28.5–63.5; weekday matches gameday for all rows; plays exist for no unplayed game; every completed 2010+ game has plays. |

## 3. What failed

### Blocker

**B1 — `nfl.injury_reports.date_modified` is silently converted from UTC to the loading machine's local wall-clock time and stored as a naive TIMESTAMP (2010–2024, ~80k rows).**
Upstream parquet type is `timestamp[us, tz=UTC]` (P0-DATA-001 §3 also records "UTC datetimes"). The table was created from the 2026 file (which has no `date_modified`), so the column was added through `_ensure_table`'s ALTER path, where `_duck_type(pl.Datetime(tz="UTC"))` returns `TIMESTAMP` (naive). DuckDB then casts the tz-aware Arrow values using the session `TimeZone` (America/New_York here): raw `2024-09-06 19:05:30 UTC` is stored as `2024-09-06 15:05:30`. Shift distribution over all 2024 rows: −240 min (EDT) for 2,867 rows, −300 min (EST) for 3,348 rows (`06_type_drift.out`). Reproduced in a scratch DuckDB: the same insert stores 15:05 in a New York session, 21:05 in a Berlin session, 19:05 in a UTC session (`09_tz_repro.out`) — so the stored values are machine-dependent and the handoff's "reproduced on a second machine: identical" cannot have compared values.
Why it blocks: `date_modified` is the as-of timestamp governed by register rule L6 (`date_modified < as_of`). A naive value 4–5 h early admits rows modified up to 5 h after the Saturday 20:00 ET cutoff; the checklist item "no silent type changes" fails; the error is invisible to every current DQ check. Compare `nfl.ftn_charting.date_pulled`, which took the CREATE path and is correctly `TIMESTAMP WITH TIME ZONE`.

### Major

**M1 — Quarantine list does not cover the leakage register.** `config/sources.yaml` `quarantine_columns` omits `roof` and `stadium`, which L2 lists as "Quarantined" (the same file's own `notes:` line says roof is quarantined), and omits every L1 line column (`spread_line`, `total_line`, `home/away_moneyline`, `home/away_spread_odds`, `over/under_odds`), whose rule is "never used as a feature for the game itself". Nothing in code reads `quarantine_columns` yet, so the list is the only contract the Phase-2 feature builder will have. (`04_teams_dupes_schema.out`)

**M2 — `nfl.rosters_weekly` registered key (season, week, team, gsis_id) is not unique.** 9,494 duplicate rows in 2010–2015 (none later), identical except `status` (e.g. ACT vs TRD, RES vs TRD). Undocumented in the handoff and in `sources.yaml`; no DQ check; register rule L14 sends as-of team/status lookups to this table, where a 2010–2015 player-week can return two contradictory statuses. (`05_dupes_detail.out`)

**M3 — The only timestamped 2026 line observations are not preserved.** `market.historical_lines` holds 29 rows for unplayed 2026 week 5–6 games (e.g. 2026_05_TB_DAL spread_home −8.5, ML −470/+360, observed 2026-10-08 13:12:57 UTC). Because `nfl.games` is replace-all and `build_historical_lines_from_games` deletes and rebuilds, these pre-game values disappear from the DB on the next load; they survive only in this machine's schedule snapshot, and `schedules` is neither in `SnapshotStore.TRACKED_DATASETS` nor in the `.gitignore` allowlist (only injuries are). With the Odds API blocked, the daily schedule snapshots are the project's sole source of timestamped lines for the live season, and they are as lossy upstream as injuries (rule 3, L1).

**M4 — No UTC kickoff timestamp; `gametime` is Eastern wall-clock, undocumented.** `gameday`/`gametime` are VARCHAR; international games show `09:30` (London) and `20:00` (São Paulo 2025_01_KC_LAC), i.e. America/New_York time, not venue-local. CLAUDE.md's convention ("times stored in UTC; kickoff local kept separately") is not met for the system's principal `event_time`, and the dictionary does not say which zone `gametime` is in. Every as-of comparison in Phase 2 (L9, L12, the Saturday-20:00-ET cutoff) depends on this.

### Minor

- **m1** `snapshots.jsonl` has 153 rows but 152 unique `snapshot_id`: the second row is a `duplicate_of` entry whose id equals its own primary (`nflverse.schedules.all.20261008T130804+0000.58fc64e7`) — two `put()` calls within the same second produce the same id. Handoff says 152 rows. `lab.snapshots` (PK) kept one arbitrarily.
- **m2** Rows in nfl.games, ref.players, ref.teams, rosters_weekly 2026 and depth_chart_snapshots 2026 are stamped with the `snapshot_id` of a "checked, unchanged" index row, not the id of the file actually written (`store.latest()` does not filter `duplicate_of`). Resolvable via `lab.snapshots.duplicate_of`, but provenance should point at the primary.
- **m3** `snap_counts_2012.parquet` upstream is empty (0 rows, 4,561 bytes); handoff claims coverage 2012–2026, actual 2013–2026. Gap not recorded (rule 5).
- **m4** Handoff says "19 checks"; the committed report and the `lab.data_quality_runs` row show 18 (`snap.absent_locally` was added after the report was generated). The attached report does not correspond to the code at the handoff commit.
- **m5** Registered keys in `sources.yaml` are wrong or incomplete: `espn_qbr_week` has no `week` column (`game_week`/`week_num`); `depth_charts.key_pre2025` omits `game_type`/`formation`/`depth_position` (51,749 collisions on the registered key; 1,718 exact full-row duplicates upstream in `depth_charts_weekly`); `injury_reports` has 2 duplicate (snapshot, season, week, team, gsis_id) rows (2024 wk15 HOU Stover / NYJ Conklin, two states in one file).
- **m6** 62 rows of 2010 week 1 injuries have null `date_modified`; the untimestamped check only counts 2025+, and rule L6 needs these flagged too.
- **m7** Checklist item "coverage by season table (first/last season, row counts, null rates on key columns)" is not in the handoff — totals and ranges only. (Reconstructed in `01_counts.out`.)
- **m8** Rows the DQ layer calls "untimestamped" (7,342 for 2025+) carry no in-table flag; the as-of exclusion for 2025 works only because `observed_at` (2026-10-08) post-dates every 2025 game. Document this, or add the flag column L5 names.
- **m9** Type drift to record in the dictionary: rosters_weekly `draft_number`/`jersey_number` are int upstream 2016+ but stored VARCHAR (table typed from the 2010 file); `height` int→DOUBLE 2025+; `depth_chart_position`/`ngs_position` all-null 2010–2015; injuries `season_type` all-null ≤2024. One upstream moneyline pair with negative hold (2020_01_LV_CAR +134/−124). 13 games where a ±1 spread's ML favorite is the other side (pick'em noise). None affect training; all should be in the dictionary.

## 4. Required corrections and responsible role

| # | Correction | Role |
|---|---|---|
| B1 | In `db/load.py`, map tz-aware `pl.Datetime` to `TIMESTAMP WITH TIME ZONE` in `_duck_type` (and/or `SET TimeZone='UTC'` in `db.connect()` so no cast can depend on the host); drop and reload `nfl.injury_reports` from the existing snapshots; add a DQ CRITICAL check that no `nfl.*`/`market.*` column is a naive TIMESTAMP and that a sample of loaded timestamps equals the raw parquet values; add a unit test for the ALTER path with a tz-aware column. | data-engineer |
| M1 | Add `roof`, `stadium`, `spread_line`, `total_line`, `home_moneyline`, `away_moneyline`, `home_spread_odds`, `away_spread_odds`, `over_odds`, `under_odds` to `quarantine_columns` (lines may be carried as "quarantined: results/CLV only"); add a test asserting every nfl.games column named in L1–L4 of the register is listed. | data-engineer |
| M2 | Document the 2010–2015 multi-status rows; define a precedence/dedup rule for as-of status (or load `status` as a set), correct the registered key, add a DQ check on the key actually used. | data-engineer |
| M3 | Treat daily schedule snapshots as irreplaceable: add `schedules` to `TRACKED_DATASETS` and the `.gitignore` allowlist (≈0.5 MB/day), or append per-snapshot nflverse line observations (keyed by snapshot_id, observed_at) instead of rebuilding `market.historical_lines` from the latest schedule only. | data-engineer |
| M4 | Derive `kickoff_utc` (gameday + gametime interpreted in America/New_York) in the loader or a view, keep `gametime` as ET and say so in the dictionary; use it as the games' `event_time`. | data-engineer |
| m1–m9 | Fix snapshot_id uniqueness (sub-second or counter) and refuse a `put` with an existing id; stamp rows with the primary snapshot_id; record the 2012 snap-count gap; regenerate the DQ report at the handoff commit; correct registered keys; flag 2010 null `date_modified`; add the coverage-by-season table; record the type drift in the dictionary. | data-engineer |

## 5. Verdict

**REVISION REQUIRED.**

The lake, hashes, provenance labels, row counts, sign convention, team mapping and key uniqueness of games/plays/stats are sound and were reproduced independently. The data cannot yet be handed to a feature builder because the one upstream as-of timestamp the project has for 2010–2024 injuries (`date_modified`) was silently shifted into the loading machine's local time and stored without a zone (B1), and the quarantine contract that the feature layer will rely on is narrower than the leakage register (M1).

## 6. Re-audit required

**Yes** — scoped: after B1 and M1–M4 are addressed, re-verify (a) raw-vs-loaded timestamp equality for `nfl.injury_reports` and absence of naive TIMESTAMP columns, (b) the quarantine list against L1–L4, (c) the rosters key rule, (d) persistence of schedule snapshots, (e) `kickoff_utc` on a sample of international/Thursday/Monday games. The hash, sign-convention and duplicate checks need not be repeated unless the loader changes how rows are stamped.

---
Scratch: `artifacts/audit/P1-DATA-001/01_counts.{py,out}` (counts/nulls), `02_snapshots.{py,out}` (hashes/index), `03_sign_convention.{py,out}`, `04_teams_dupes_schema.{py,out}`, `05_dupes_detail.{py,out}`, `05b_misc.out`, `06_type_drift.{py,out}`, `07_quality.out`, `08_tests.out`, `09_tz_repro.out`.
