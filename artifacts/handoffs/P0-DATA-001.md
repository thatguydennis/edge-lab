# P0-DATA-001 — nflverse Ecosystem Inventory

TASK ID: P0-DATA-001
RESPONSIBLE AGENT: Data Engineering (research sub-session), coordinated by the Chief Research Orchestrator
OBJECTIVE: Verified inventory of the nflverse ecosystem as of 2026-10-07 for NFL Edge Lab
DATA CUTOFF: 2026-10-08 02:30 UTC (latest nfldata commit observed)
METHOD: PyPI JSON + wheel source inspection; raw files from raw.githubusercontent.com; shallow clone of nfldata; direct download and inspection of live nflverse-data release Parquet files with HTTP Last-Modified headers. GitHub HTML/API was proxy-blocked, so primary artifacts were used instead.
AUDIT STATUS: NOT AUDITED (Phase 0 research; informs the proposal, not a model)
NEXT ACTION: Data Engineer builds sources.yaml and snapshot-first ingestion from this map; Auditor data audit before any model trains.

---

## 1. Executive summary

1. **nfl_data_py is dead.** GitHub archived it 2025-09-25 (read-only); README says "deprecated in favour of nflreadpy… no further maintenance." Last PyPI release 0.3.3 (2024-09-20). Use **nflreadpy**.
2. **nflreadpy current release = 0.1.5 (PyPI, 2025-11-19), Python ≥3.10, MIT, Polars-native.** GitHub `main` pyproject says 0.1.7 with an undocumented "devel" changelog adding `team_abbr_mapping()`, `team_abbr_mapping_norelocate()`, `player_name_mapping()`, and a Wednesday-after-Labor-Day season switch; no 0.1.6/0.1.7 exists on PyPI. **nflreadpy has no `load_espn_qbr`, no `clean_team_abbrs`, no `clean_player_names`** — hit the release URL directly for QBR.
3. **2026 data is flowing now** (asset `Last-Modified`, UTC): pbp 2026 → Oct 7 16:23 (weeks 1–4, 64 games, 372 cols); schedules → Oct 8 01:46; injuries 2026 → Oct 7 14:25 (through Week 5, TB/DAL only so far); depth charts → Oct 7 14:25; FTN charting → Oct 7 04:13; team/player stats → Oct 7 16:27; PFR advstats → Oct 7 11:03; snap counts → Oct 6; NGS → Oct 7; ESPN QBR → Oct 7; contracts → Oct 7; players → Oct 7.
4. **Participation (personnel/pressure/coverage) is NOT available for 2026 and will not be until after the 2026 postseason.** NFL NGS feed "died during the 2023 season"; FTN now supplies 2023, 2024, 2025 files (post-season dump, CC-BY-SA 4.0). 2016–2022 are NFL-NGS-sourced with a different (20-col) schema; 2023+ FTN (26-col). `pbp_participation_2026.parquet` returns 404.
5. **Schedules betting columns are live lines, not closing lines.** `spread_line/total_line/moneylines/odds` are already populated for Week 5 and Week 6 games and are being overwritten every ~5–30 min (diff of `games.csv` between Oct 5 and Oct 8: TB@DAL spread 10→8.5, PHI@JAX 4.5→7, HOU@TEN total 39.5→37.5). After kickoff they freeze at the last pull (≈closing). The sportsbook source is **UNVERIFIED** (not documented anywhere in nfldata; the only book-specific code in the repo is `code/draft_kings.R`).
6. **Injuries lost their timestamp.** `date_modified` exists 2009–2024 (null in 2009) but is **absent from the 2025 and 2026 files** (schema changed: `season_type` + new `game_type`). You cannot reconstruct "what was known at line time" from 2025+ injury files; you must snapshot them yourself.
7. **Depth charts changed format in 2025**: 2001–2024 = NFL Data Exchange weekly format (`season, club_code, week, depth_team, position, depth_position, formation, gsis_id, elias_id…`); 2025+ = ESPN daily snapshots (`dt` ISO timestamp, `espn_id, gsis_id, pos_grp, pos_abb, pos_slot, pos_rank`). 2026 file has 222 snapshots (Mar 22 → Oct 7). The 2025+ format is better for point-in-time features; the pre-2025 history is not comparable.
8. **nflfastR 6.0.0** (current): dropped support for 1999–2000 (files still exist, no fixes), raw pbp now from season releases in `nflverse-pbp` (`nflfastR-raw` deprecated, won't update 2026+), old `calculate_player_stats*()` defunct, added "explosive" and punting stats. **Historical pbp files were rebuilt in Aug 2026** (2020/2024/2025 parquet `Last-Modified` 13–26 Aug 2026) — model inputs are not immutable across years.
9. **Officials dataset is stale for 2026**: only 16 games (Week 1), file last modified 2026-09-02; the schedule page's automation table lists no officials workflow. Use `referee` from schedules (populated for completed 2026 games) instead.
10. **Licensing**: nflverse-data releases are **CC BY 4.0**; FTN charting + 2023+ participation are **CC-BY-SA 4.0** with required attribution "FTN Data via nflverse"; packages (nflreadpy, nflreadr, nflfastR, nflseedR, nfl4th, fastrmodels, rotc) are MIT. PFR/NGS/ESPN/OTC-derived data carry upstream ToS exposure (not re-licensed by nflverse).

## 2. Per-repo table

| Repo | Role | Status (verified) | Version / last activity | License |
|---|---|---|---|---|
| nflverse/nflverse-data | Release-asset host for all automated datasets (parquet/csv/rds/csv.gz) | Active; assets updated Oct 7–8, 2026 | `nflversedata` helper pkg 0.0.17 | CC BY 4.0 (LICENSE.md) |
| nflverse/nflreadpy | Current Python loader (Polars) | Active | PyPI 0.1.5 (2025-11-19); main=0.1.7-dev | MIT |
| nflverse/nflreadr | R loader; canonical dictionaries | Active | 1.5.1 CRAN; main 1.5.1.9002 | MIT |
| nflverse/nfl_data_py | Legacy Python loader | ARCHIVED 2025-09-25 | 0.3.3 (2024-09-20) | MIT |
| nflverse/nflfastR | pbp parser, EPA/WP models, `calculate_stats()` | Active | 6.0.0 | MIT |
| nflverse/nfldata (Lee Sharpe) | games/schedules incl. betting, trades, draft, lines CSVs | Active; `data/games.rds` auto-commits every ~5–30 min (last 2026-10-08 02:30 UTC) | 56.5k commits | No license file visible (UNVERIFIED) |
| nflverse/nflverse-pbp | GH Actions that build pbp + player/team stats → releases | Active | crons in-season (Jan,Feb,Sep–Dec) | — |
| nflverse/nflverse-pbp-internal | Internal pkg "nflverseraw": downloads raw pbp JSON → `pbp_raw` releases | Active (feeds nflfastR 6.0) | — | — |
| nflverse/nflfastR-raw | Legacy raw JSON repo | Deprecated (won't update 2026+) | — | — |
| nflverse/nflverse-rosters | Actions for rosters, weekly rosters, depth charts, injuries | Active; daily 07:07 UTC | — | — |
| nflverse/nflverse-players | Builds `players` (v2) crosswalk | Active ("updates automatically over night") | releases `players`, `players_components` | "Unknown, MIT licenses found" |
| nflverse/ngs-data | Next Gen Stats scraper | Active; cron `0 7 * 1,2,9-12 *` | — | — |
| nflverse/nflverse-ftn | FTN Data API client (charting; participation delivery) | Active; cron `0 */6 * 9-12,1-2 *` | — | MIT |
| nflverse/pfr_scrapR | PFR snap counts, advstats, draft, combine | Active; `0 */6 * 9-12,1 *` | — | — |
| nflverse/espnscrapeR-data | ESPN Total QBR CSVs (NFL+college) | Active | released to nflverse-data `espn_data` | none shown |
| nflverse/rotc | OverTheCap scraper → `contracts` | Active; cron `0 7 * * *` | 0.3.1 | MIT |
| nflverse/nflseedR | Season sim + tiebreakers/standings | Active | 2.0.2.9001 | MIT |
| nflverse/nfl4th | 4th-down decision model | Active | 1.0.7 | MIT |
| nflverse/fastrmodels | Data-only pkg: ep/wp/wp_spread/fg/cp/xyac models | Active | 2.1.0 | MIT |
| nflverse/nflverse-data-archives | Quarterly RDS snapshots of every release tag (redundancy) | Active | — | — |

## 3. Dataset-by-dataset detail

Release URL pattern (all): `https://github.com/nflverse/nflverse-data/releases/download/<tag>/<file>.{parquet|csv|rds|csv.gz}`. Direct download needs a browser-ish `User-Agent` (curl default UA got 403 from the proxy; `Mozilla/5.0` → 302 to `release-assets.githubusercontent.com`). nflreadpy caches in memory 24h by default (`cache_mode`, `cache_duration` configurable).

### 3.1 Play-by-play — `pbp/play_by_play_{season}` — `nflreadpy.load_pbp(seasons)`
- Coverage 1999–2026 (1999: 258 games, EPA 1.1% null, `spread_line` fully populated). nflfastR 6.0 no longer fixes 1999–2000.
- 2026: weeks 1–4, 64 games, 11,155 plays, 372 columns. Last-Modified 2026-10-07 16:23 UTC.
- Cadence (nflreadr schedule page): nightly after game days + some in-game runs; re-run Wed–Thu nights for stat corrections (so pbp for a given week can change for ~4 days).
- Key cols (all present in 2026): `epa, qb_epa, wpa, wp, vegas_wp, vegas_home_wp, vegas_wpa, cpoe, cp, xpass, pass_oe, success, series_success, air_yards, yards_after_catch, xyac_epa, qb_hit, sack, qb_scramble, qb_dropback, aborted_play, play_deleted, spread_line, total_line, result, total, roof, surface, temp, wind, stadium, home_coach, away_coach, div_game, passer_player_id, rusher_player_id, receiver_player_id, time_of_day, end_clock_time, drive_real_start_time` (wall-clock ISO timestamps per play). No `pressure`/`time_to_throw` in pbp (those live in participation/FTN).
- `spread_line`/`total_line` in pbp are joined from `load_schedules()` (`helper_add_game_data.R`), i.e. the same live Sharpe lines — despite the pbp dictionary text saying "closing… (Source: Pro-Football-Reference)" (stale).
- Ingest: nflreadpy is fine; for reproducibility pin downloaded files locally because historical files get rebuilt (Aug 2026 rebuild observed).

### 3.2 Schedules / games — `schedules/games` — `load_schedules(seasons=True)`
- Source: Lee Sharpe `nfldata/data/games.rds`, upserted by `release_games.yml` (`rows_upsert` by `game_id`) into nflverse-data on every push. Repo commits "Automated data update" every 5–30 min; the upstream scraper code is not in the repo (UNVERIFIED).
- Coverage 1999–2026 (7,548 rows); 2026 = 272 REG games, gameday 2026-09-09 (Wed, NE@SEA) → 2027-01-10; neutral sites: `2026_01_SF_LA` (Melbourne), `2026_03_BAL_DAL`, `2026_04_IND_WAS`, `2026_06_HOU_JAX`, `2026_07_PIT_NO`, `2026_09_CIN_ATL`, `2026_10_NE_DET`, `2026_11_MIN_SF`.
- Complete betting column list (46-col schema): `away_moneyline, home_moneyline` (American odds), `spread_line` (positive = home favored; aligns with `result` = home − away), `away_spread_odds, home_spread_odds, total_line, under_odds, over_odds`. Supporting: `result, total, overtime, away_rest, home_rest, div_game, roof, surface, temp, wind, away_qb_id, home_qb_id, away_qb_name, home_qb_name, away_coach, home_coach, referee, stadium_id, stadium`, IDs `old_game_id, gsis, nfl_detail_id, pfr, pff, espn, ftn`.
- Coverage of betting cols: `spread_line`/`total_line` 0% null 1999–2025; moneylines + spread/total odds null for 1999–2005, partial 2006–2009 (17.6%/0.4%/27.3%/5.2% null), ~0% 2010+. 2026: populated for weeks 1–6 only.
- Closing-line status: NO for upcoming games (live, overwritten); effectively last-pull-before-freeze for completed games. Dictionary wording ("was favored") does not claim closing.
- `referee`, `temp`, `wind` are back-filled after the game (null for 2026 future games) → leakage if used naively. `away_qb_name/home_qb_name` are populated pre-game (projected starters, updated).
- Other nfldata CSVs (raw.githubusercontent only, not in nflreadpy): `closing_lines.csv` (2006–2018, MONEYLINE/SPREAD/TOTAL rows with `line, odds, outcome`, 20,490 rows — a true closing-line archive, book unlabeled), `initial_lines.csv` (2021 only, sportsbook `WSGT`), `sc_lines.csv` (2013–2020 spreads), `win_totals.csv` (2003–2020), `predictions.csv` (crowd game predictions, 2026 current), `standings.csv, teams.csv, officials.csv, airports.csv, pff_pfr_map_v1.csv`.
- Team abbreviations in `games` are historical as-of-game (`OAK`, `SD`, `STL` appear; `LA`, `LAC`, `LV` for current). The 2026 `teams_colors_logos` has 36 rows incl. `LAR` alias row and legacy OAK/SD/STL; nflfastR 6.0 NEWS notes 2026 Titans and Rams rebrand updates.

### 3.3 Injuries — `injuries/injuries_{season}` — `load_injuries()`
- Coverage 2009–2026; "collected from an API for weekly injury report data" (nflreadr); cron `7 7 * 1,2,9-12 *` (daily 07:07 UTC in-season).
- 2026: 1,071 rows, weeks 1–5 (week 5 = TB/DAL only at build time). 2026 cols: `season, season_type, game_type, team, week, gsis_id, position, full_name, first_name, last_name, report_primary_injury, report_secondary_injury, report_status, practice_primary_injury, practice_secondary_injury, practice_status`.
- `date_modified` present 2010–2024 (UTC datetimes), absent 2025–2026 (dictionary still lists it — stale). Each row is the latest state for player-week; prior intra-week states are overwritten. `report_status` values: Out/Doubtful/Questionable/null.

### 3.4 Depth charts — `depth_charts/depth_charts_{season}` — `load_depth_charts()`
- 2001–2024 old schema (NFL Data Exchange, weekly); 2025+ ESPN daily snapshots with `dt` (2026: 617,763 rows, 222 snapshots Mar 22 → Oct 7 14:25 UTC), `pos_grp` ∈ {3WR 1TE, Base 4-3 D, Base 3-4 D, Special Teams}, `pos_slot/pos_rank` give OL/DL starters (LT/LG/C/RG/RT, LDE/LDT/RDT/RDE etc.). Cron daily 07:07 UTC year-round.

### 3.5 Participation — `pbp_participation/pbp_participation_{season}` — `load_participation()`
- 2016–2022 NFL NGS (20 cols; `time_to_throw/was_pressure/route` ~60% null; `defense_man_zone_type` 100% null in 2016); 2023–2025 FTN (26 cols incl. `offense_names/positions/numbers`, `defense_coverage_type`, `was_pressure` 0% null, `time_to_throw` ~57% null = non-pass plays, `ngs_air_yards` 100% null). Files for 2023/2024 published 2025-09-04; 2025 published 2026-02-10.
- Released code (0.1.5) caps at `get_current_season(roster=True) - 1` = 2025; main-branch code allows current season only when `get_current_week()==22`. No 2026 in-season personnel/pressure data. License CC-BY-SA 4.0 (2023+), attribution required.

### 3.6 FTN charting — `ftn_charting/ftn_charting_{season}` — `load_ftn_charting()`
- 2022–2026; "charted within 48 hours following each game"; nflverse pulls 4×/day. 2026: 10,829 plays weeks 1–4, `date_pulled` 2026-10-05 → 10-07.
- 29 cols incl. `n_defense_box, n_blitzers, n_pass_rushers, is_play_action, is_rpo, is_motion, is_screen_pass, is_interception_worthy, is_catchable_ball, is_drop, is_qb_fault_sack, read_thrown, qb_location, starting_hash`. Joins to pbp on `nflverse_game_id` + `nflverse_play_id`. CC-BY-SA 4.0.

### 3.7 Team & player stats — `stats_team/…`, `stats_player/…` — `load_team_stats()`, `load_player_stats()`
- Computed by `nflfastR::calculate_stats()` from pbp, same cadence as pbp; 1999+. 2026 week-level: 128 team-games / 4,449 player rows, 138/150 cols incl. `passing_epa, passing_cpoe, rushing_epa, sacks_suffered, def_sacks, def_qb_hits, def_pressures` (PFR only), explosive-play counts (`passing_20, rushing_12…`), kicking/punting. The old `player_stats/player_stats_{season}` tag no longer exists for 2025+ (404).

### 3.8 PFR advanced stats — `pfr_advstats/…` — `load_pfr_advstats(seasons, stat_type, summary_level)`
- 2018–2026, 4×/day in-season. Week-level pass (24 cols): `times_sacked, times_blitzed, times_hurried, times_hit, times_pressured, times_pressured_pct, passing_bad_throw_pct, passing_drops`; week-level def (29 cols): `def_pressures, def_sacks, def_times_blitzed, def_missed_tackles, def_passer_rating_allowed, def_adot`. Keyed by `pfr_player_id`, `pfr_game_id`, `game_id`. 2026 through week 4. Best in-season OL/DL pressure proxy available.

### 3.9 Snap counts — `snap_counts/snap_counts_{season}` — `load_snap_counts()`
- PFR, 2012–2026, 4×/day in-season. 2026 through week 4 (5,970 rows): `offense_snaps/pct, defense_snaps/pct, st_snaps/pct`, `pfr_player_id`, `game_id`.

### 3.10 Rosters — `rosters/roster_{season}` (1920+), `weekly_rosters/roster_weekly_{season}` (2002+)
- Daily 07:07 UTC. 2026 weekly: 13,028 rows through week 5, 36 cols incl. `status` (ACT/INA/RES/DEV/CUT/EXE/RET/TRD/TRT/W04), `depth_chart_position`, and IDs `gsis_id, espn_id, sportradar_id, yahoo_id, rotowire_id, pff_id, pfr_id, fantasy_data_id, sleeper_id, esb_id, smart_id`.

### 3.11 Players (v2 crosswalk) — `players/players` — `load_players()`
- 24,844 rows, 39 cols; IDs: `gsis_id` (0% null), `esb_id` (0%), `smart_id` (0%), `pfr_id` (8.7% null), `espn_id` (33%), `nfl_id` (52%), `pff_id` (53%), `otc_id` (61%); plus draft fields, `rookie_season, last_season, latest_team, status, ngs_position`. `load_ff_playerids()` (DynastyProcess) adds `mfl_id, sportradar_id, fantasypros_id, sleeper_id, yahoo_id, cbs_id, rotowire_id, ktc_id, cfbref_id, stats_id, swish_id…`.

### 3.12 Next Gen Stats — `nextgen_stats/ngs_{passing|receiving|rushing}` — `load_nextgen_stats(seasons, stat_type)`
- Single file per type, 2016–2026, nightly 07:00 UTC in-season; 2026 through week 4. Passing: `avg_time_to_throw, aggressiveness, avg_intended_air_yards, completion_percentage_above_expectation, expected_completion_percentage, avg_air_yards_to_sticks`, `player_gsis_id`. Week 0 = season aggregate.

### 3.13 ESPN QBR — `espn_data/qbr_{week|season}_level` — not in nflreadpy
- 2006–2026, week-level 10,836 rows through 2026 week 4; `qbr_total, qbr_raw, pts_added, epa_total, pass, run, sack, exp_sack, penalty, qualified`, ESPN `player_id`, `game_id` (ESPN id; join via schedules `espn`).

### 3.14 Contracts — `contracts/historical_contracts` — `load_contracts()`
- OverTheCap via `rotc`, daily 07:00 UTC; 53,169 rows; `apy, value, guaranteed, apy_cap_pct, year_signed, years, is_active, otc_id, gsis_id, draft_*`, nested histories. Current through 2026 signings.

### 3.15 Officials — `officials/officials` — `load_officials()`
- 2015–2026, one row per game per official. 2026 only week 1 (16 games); last modified 2026-09-02. Workflow/source UNVERIFIED.

### 3.16 Others
- `teams/teams_colors_logos` (36 rows incl. legacy OAK/SD/STL/LAR), `trades/trades`, `draft_picks/draft_picks` (1980+, PFR), `combine/combine` (PFR), ffverse rankings/opportunity (out of scope).
- Team-abbr mapping (nflreadpy main `datasets.py` parquet): canonical set `ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LA LAC LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS`. Relocation map: `OAK/RAI→LV`, `SD/SDG/SDC→LAC`, `STL/SL/RAM/LAR→LA`, `PHO/ARZ/CRD→ARI`, `WSH/WFT→WAS`, `JAC→JAX`, `GNB→GB`, `KAN→KC`, `NWE→NE`, `NOR→NO`, `SFO→SF`, `TAM→TB`, `BLT/RAV→BAL`, `CLV→CLE`, `HST/HTX→HOU`, `CLT→IND`, `OTI→TEN`. Schedules/pbp files themselves use as-of-game codes (OAK through 2019, SD through 2016, STL through 2015).

## 4. Gaps and risks for a betting model

1. Line provenance/timing (critical): single mutable snapshot per game; historical ≈ closing; current = "now"; no open/close pair, no timestamp, no book identity.
2. Injury-report leakage (2025+): no `date_modified`; snapshot the daily file ourselves.
3. Back-filled post-game columns in `games`: `referee`, `temp`, `wind`, `roof` (blank for some 2026 games), `away/home_qb_id/name`, `result/total`.
4. No in-season personnel/pressure/coverage data for 2026; schema break at 2023 (NGS→FTN).
5. Depth-chart schema break 2024→2025.
6. Historical pbp is rebuilt; EPA/WP/CPOE can drift between runs; nflfastR 6.0 changed `play_type` derivation.
7. 1999–2000 unsupported; consider 2001+ (2006+ for moneylines, 2010+ for full odds).
8. Officials stale for 2026.
9. Snap counts / PFR advstats lag (6-hour cron, PFR ToS exposure).
10. ID joins: `players.espn_id` 33% null, `pff_id` 53%, `otc_id` 61%; `pfr_id` 8.7% null.
11. Season-boundary logic changed (Wed after Labor Day) in nflreadr 1.5.1 / nflreadpy main; 0.1.5 still Thursday.
12. Licensing: CC-BY-SA on FTN/participation; CC BY 4.0 elsewhere.
13. Tooling: nflreadpy lacks QBR, abbreviation cleaning (on PyPI); release asset downloads need a browser UA.

UNVERIFIED: sportsbook source of nfldata lines; which workflow produces `officials`; nflverse-players v2 removed-column list; nflverse-ftn README text; nfldata license; nflreadpy docs site content (proxy-blocked; wheel/repo source used instead).

## 5. Sources (URLs actually used)

- https://pypi.org/pypi/nflreadpy/json ; https://pypi.org/simple/nflreadpy/ ; https://pypi.org/pypi/nfl_data_py/json
- nflreadpy 0.1.5 wheel source (files.pythonhosted.org)
- https://raw.githubusercontent.com/nflverse/nflreadpy/main/{CHANGELOG.md, pyproject.toml, README.md, src/nflreadpy/*.py, src/nflreadpy/data/*.parquet}
- https://github.com/nflverse/nfl_data_py ; https://raw.githubusercontent.com/nflverse/nfl_data_py/main/README.md
- https://raw.githubusercontent.com/nflverse/nflreadr/main/{NEWS.md, DESCRIPTION, R/load_*.R, data-raw/dictionary_*.csv}
- https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html ; https://nflreadr.nflverse.com/articles/dictionary_schedules.html
- https://raw.githubusercontent.com/nflverse/nflfastR/master/{NEWS.md, DESCRIPTION, R/helper_add_game_data.R}
- https://raw.githubusercontent.com/nflverse/nflverse-data/master/{README.md, DESCRIPTION, LICENSE.md} ; https://github.com/nflverse/nflverse-data/releases
- nflverse-data release assets (tags: pbp, schedules, injuries, snap_counts, depth_charts, pbp_participation, ftn_charting, stats_team, stats_player, pfr_advstats, weekly_rosters, rosters, officials, players, nextgen_stats, espn_data, contracts, teams, trades, combine, draft_picks, player_stats)
- https://github.com/nflverse/nfldata (shallow clone); raw DATASETS.md, README.md, .github/workflows/release_games.yml, code/draft_kings.R, data/{games.csv, closing_lines.csv, initial_lines.csv, sc_lines.csv, win_totals.csv, predictions.csv}
- https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/{README.md, .github/workflows/update_data.yaml}
- https://raw.githubusercontent.com/nflverse/nflverse-rosters/master/{README.md, .github/workflows/*.yaml}
- https://github.com/nflverse/nflverse-players ; https://github.com/nflverse/nflverse-ftn ; raw ftn_data_dictionary.csv, update_ftn.yaml
- https://raw.githubusercontent.com/nflverse/ngs-data/master/{README.md, .github/workflows/update_ngs.yaml}
- https://raw.githubusercontent.com/nflverse/pfr_scrapR/master/.github/workflows/*.yaml
- https://github.com/nflverse/espnscrapeR-data ; https://github.com/nflverse/rotc ; nflseedR, nfl4th, fastrmodels DESCRIPTION files
- https://raw.githubusercontent.com/nflverse/nflverse-data-archives/main/README.md ; nflfastR-raw README ; nflverse-pbp-internal README
