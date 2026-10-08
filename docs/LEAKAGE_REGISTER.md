# Leakage register

Living list of fields and behaviours known to carry future information. The feature layer may not
read anything listed here except through the rule stated. The auditor's leakage checklist samples
against this file. Add an entry whenever a new source is ingested.

| # | Source / field | Why it leaks | Rule |
|---|---|---|---|
| L1 | `nfl.games.spread_line`, `total_line`, `*_moneyline`, `*_spread_odds`, `over/under_odds` | nflverse overwrites these continuously until kickoff; for completed games they are the last pull (≈close). No timestamp. | `line_class = last_pull`. Never used as a feature for the game itself; may serve as a close proxy in results/CLV when no documented close exists, and must be labeled as such. |
| L2 | `nfl.games.referee`, `temp`, `wind`, `roof` (partially), `stadium` (rare) | Back-filled after the game | Quarantined. Weather features only from a forecast captured before cutoff (none yet). Roof/surface from `ref.stadiums`. |
| L3 | `nfl.games.result`, `total`, `overtime`, `home_score`, `away_score` | Targets | Results layer only. |
| L4 | `nfl.games.home_qb_*`, `away_qb_*` | Updated to the actual starter | Expected starter must come from depth-chart snapshots or injury snapshots dated before cutoff. |
| L5 | `nfl.injury_reports` rows for seasons ≥ 2025 | Upstream file has no `date_modified`; a Sunday "Out" and a Wednesday "Out" look identical | Only rows from our own daily snapshots with `observed_at < as_of`. Pre-snapshot 2025 rows are `untimestamped` and excluded from features. |
| L6 | `nfl.injury_reports` rows 2010–2024 | `date_modified` is the last modification, earlier states overwritten | Use only when `date_modified < as_of`; accept that intra-week earlier states are unobservable. |
| L7 | Play-by-play files rebuilt upstream (Aug 2026) and corrected Wed–Thu | EPA/WP/CPOE values can change after the fact | Features computed from a pinned `snapshot_id`; a backtest records which. Corrections are a known, small, non-directional noise source. |
| L8 | Season-level aggregates (`stats_team_reg`, season NGS "week 0", season QBR) | Include games after `as_of` | Never used for features; weekly tables only, filtered by game date < as_of. |
| L9 | Opponent adjustment / strength of schedule | Full-season SOS uses future games | Compute from games with kickoff < as_of only. |
| L10 | Depth charts 2025+ (`dt` snapshots) | Fine-grained, but a snapshot taken on game day may reflect inactives | Use latest `dt < as_of` only. |
| L11 | Depth charts ≤ 2024 (weekly) | Week-w chart may be published after our cutoff | Use week ≤ w−1 unless the snapshot date is known to be before cutoff. |
| L12 | FTN charting, PFR advanced stats, snap counts | Published after the game they describe | Rows for games with kickoff < as_of only. |
| L13 | Participation (2016–2025) | Post-season dumps | Research/backtest only; never a live feature until an in-season source exists. |
| L14 | `ref.players.latest_team`, `status`, `last_season` | Current values, not as-of | Use weekly rosters (`nfl.rosters_weekly`) for as-of team and status. |
| L15 | Contracts (`is_active`, `apy`) | Current state | Use `year_signed`/history fields and the as-of rule if ever used. |
| L16 | The Odds API snapshots | None by construction (each has `observed_at`) | Use snapshots with `observed_at < as_of`. |
