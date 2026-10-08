# NFL Edge Lab — Phase 0 Proposal (approved design, as of 2026-10-08)

Living copy: Claude doc "NFL Edge Lab — Phase 0 Proposal" in the Edge Lab project. This file is the
repository's record of the design that was approved. Changes to it go through CHANGELOG.md.

## Decisions taken (Oct 8, 2026)
- No Week 5 card. Week 5 is data collection only. **First official week: Week 6**, freeze Sat Oct 17, 20:00 ET.
- Private GitHub repo `thatguydennis/edge-lab`; lab folder on Dennis's Mac (`Claude Cowork/Projects/edge lab`).
- Odds feed: The Odds API **free tier** for 2026 weekly snapshots; paid historical backfill ($59, one month) deferred to Phase 3.
- Architecture: DuckDB + immutable Parquet snapshot lake; trimmed folder tree (section J); three version lines; seven roles as Claude Code subagents.
- Open: Dennis's sportsbooks; unit definition (proposed 1u = 1% bankroll, caps 3u/game, 10u/week, flat sizing in v0).

## A. Understanding
A persistent, audited research lab that answers, per game and per cutoff timestamp: what should the
fair spread and moneyline have been, how far was the market from it, and was the gap worth a wager —
and keeps an unalterable record so calibration, CLV and results can be judged over 2026–2029.
Scope v0.x: ATS + ML. Totals/props captured where the same feed provides them, not modeled.
Honest expectation: public-data models rarely beat the close by much; first-season success = calibration + CLV.

## B. System architecture
Sources → Ingest+snapshot (hashed, timestamped) → DuckDB + Parquet lake → Features (as-of) →
Models (M0, A, B, D) → Fair price (spread, ML, P(cover)) → Decision (BET/LEAN/PASS) → Auditor gate →
Frozen snapshot + ledgers → Results/CLV → Backtest + journal → (new model version) → Models.
Design choices: snapshot-first ingestion (nflverse rebuilds history; lines overwritten live); one
analytical store; one `predict(game_id, as_of)` path for backtest and live; three separate layers in
the model stage; the Auditor is a gate, not a reviewer; terminal first, dashboard Phase 7.

## C. Multi-agent design
Seven roles from day 1 (orchestrator, data-engineer, nfl-research, market-research, modeling,
backtesting, auditor); prediction and reporting stay with the orchestrator until v1.0. Agents are role
files launched as isolated sub-sessions; they communicate only through handoff artifacts
(`artifacts/handoffs/<TASK-ID>.md|.json`). Independence: modeling never sees sealed-season results
before freeze; the auditor never sees the producing conversation; backtesting recomputes performance
claims; odds math is implemented twice (production + auditor script).

## D. Auditor
Adversarial; scored on findings. Four audit types with checklists in `.claude/agents/auditor/`
(data, leakage, backtest, prediction). Verdicts: APPROVED / APPROVED WITH CONDITIONS / REVISION
REQUIRED / REJECTED, with severity (blocker/major/minor). A blocker cannot be downgraded by the
orchestrator. Unaudited predictions are PRELIMINARY forever.

## E. Data-source audit (summary; full reports in artifacts/handoffs/P0-DATA-001.md, P0-MKT-001.md)
1. nfl_data_py archived; nflreadpy 0.1.5 is the loader (no QBR, no team-abbr cleaning).
2. nflverse betting lines are live, overwritten, unlabeled → `line_class = last_pull`.
3. Injury files lack `date_modified` from 2025 → own daily snapshots; 2025+ injury features flagged.
4. No 2026 participation/pressure data until post-season; proxies: PFR advstats, FTN charting, pbp, NGS.
5. Depth charts: weekly format ≤2024, ESPN daily timestamped snapshots ≥2025.
6. Historical pbp rebuilt (Aug 2026) and corrected Wed–Thu → snapshot-first.
7. Officials stale for 2026 → deferred.
8. Timestamped by-book line history only from 2020 (The Odds API). Pre-2020: SBR 2007–2021 (open/close/ML, unnamed book); Covers/SOH = PFR lineage, closing spread/total only.
9. Historical betting splits effectively unavailable.
10. PFR cannot be bulk-scraped (ToS).
11. Book identities move (ESPN BET → theScore Bet 2025-12-01; Caesars = williamhill_us; Circa absent; Pinnacle delayed).
Licensing: nflverse CC BY 4.0; FTN CC-BY-SA 4.0 (attribution "FTN Data via nflverse"); packages MIT.

## F. Database
DuckDB single file `data/db/edgelab.duckdb` over `data/snapshots/<source>/<dataset>/<retrieved_at>_<sha>.parquet`.
Schemas: `ref` (teams, team_aliases, players, coaches, stadiums, books), `nfl` (games, plays, team/player
stats, snap_counts, injury_reports with observed_at, depth_chart_snapshots, pfr_advstats, ftn_charting,
ngs_*, participation), `market` (odds_snapshots, line_summary, historical_lines, line_discrepancies),
`lab` (model_versions, feature_definitions, feature_values, experiments, research_ideas, backtest_runs,
backtest_predictions, predictions_official [append-only], predictions_preliminary, results,
model_ledger, personal_ledger, overrides, agent_runs, agent_artifacts, audit_results,
data_quality_runs, events). Natural keys follow nflverse; every fact row carries `snapshot_id`; UTC.

## G. Model stack
Layer 1 margin: M0 naive, M-market, A ridge on opponent-adjusted EPA/success + HFA + rest + QB,
B Elo-style ratings with QB term, D market-residual; C/E/F later only if A/B/D leave something.
Layer 2 fair price: empirical key-number-aware residual distribution; vig removal (multiplicative +
power, method recorded); push handling. Layer 3 decision: edge + bootstrap confidence + data warnings;
thresholds from backtest calibration; v0 flat 0.5u BET / 0.25u LEAN max; best available price.
Metrics: Brier, log-loss, reliability, MAE/RMSE, ATS%/ML% at price, ROI, CLV.

## H. Backtesting
`predict(game_id, as_of)` is the only generator of backtest rows. Walk-forward by season, rolling
weekly refit. Dev 2010–2021; validation 2022–2023; sealed test 2024–2025 (run once per model
version by backtesting only). Weeks 1–4 reported separately. Leakage controls: event_time on every
row; documented close lines only in training; post-game schedule columns quarantined; leakage
register `docs/LEAKAGE_REGISTER.md`. Pre-registration of experiments; attempt counting; BH
adjustment; ≥150 OOS games before a situation is a feature candidate; Bayesian shrinkage beside raw
rates. Reproducibility: commit, snapshot ids, feature versions, seeds, package versions, config hash.

## I. Week plan (revised)
Week 5 (Oct 8–12): data collection only — daily injury/depth-chart snapshots, line snapshots from the
free tier, nflverse backfill 2010–2026, schema, DQ. Week 6 (freeze Oct 17): first official card,
only if data + leakage + backtest audits are APPROVED; otherwise Week 7.

## J. Project structure
See repository tree; changes from the charter: no `database/` (→ `data/db/`, `src/edgelab/db/`);
topic folders folded into pipeline stages; no model version directories (registry instead); idea
status in front matter not folders; no `results/` (tables + reports); no notebooks until needed;
`tests/leakage/` and `tests/odds/` first-class.

## K. Roadmap and versioning
Phases 0–9 as in the charter with dates revised above. Versions: `code v0.x` (git tags),
`model m<major>.<minor>` (lab.model_versions), `agents a0.x`; plus snapshot_id and feature_version
on every prediction.

## L. Risks (summary)
Line provenance; untimestamped 2025+ injuries; upstream revisions; thin edges; multiple testing;
Model D collapsing into the market; early-season instability; vendor gaps; ToS; agent overhead;
auditor drift; single-machine durability; reporting bias. Mitigations in the live doc.

## M. Improvements adopted
Definition of "the line" (Pinnacle close reference, best bettable price); unit + caps; pre-registration;
leakage register; null results mandatory; weeks 1–4 policy; exchanges as `book_type = exchange`;
line shopping in decision layer; snapshots as system of record; bankroll-independent scores;
competition exchange via frozen cards only; owner workflow (`edgelab run`, `edgelab bet`).
