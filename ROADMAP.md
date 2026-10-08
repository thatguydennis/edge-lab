# Roadmap

Dates are targets, not promises. A phase is complete only when its audit gate is APPROVED.

| Phase | Name | Target | Exit gate |
|---|---|---|---|
| 0 | Research, architecture, agent design | Oct 7–8, 2026 ✅ | Proposal approved by owner |
| 1 | Data foundation (code v0.1) | Oct 8–11 | Data audit: provenance, schema, DQ zero criticals, ID join rates |
| 2 | Database + features + baselines (v0.2–0.3) | Oct 10–13 | Leakage audit on the as-of feature builder |
| 3 | Historical lines + validation (v0.4) | Oct 12–16 | Discrepancy study recorded; sealed-season backtest reproduced by backtesting role |
| 4 | First official week — Week 6 (v0.5) | Freeze Sat Oct 17 20:00 ET | Prediction audit APPROVED; else PRELIMINARY |
| 5 | Hypothesis cycle (v0.6–0.9) | Nov 2026 – Jan 2027 | Each experiment pre-registered, audited, journaled |
| 6 | v1.0 first stable production model | After 2026 playoffs | Full backtest + live-season review |
| 7 | Dashboard | 2027 offseason | Not before model/data integrity is proven |
| 8 | Advanced modeling (C/E/F), automation | 2027 | Only if A/B/D leave edge on the table |
| 9 | Multi-season research | 2027–2029 | Large-sample evaluation |

## Phase 1 — Data foundation (now)
- [x] Repository scaffold, CLAUDE.md, roles, handoff schema
- [ ] Snapshot-first nflverse ingestion (schedules, pbp, team/player stats, injuries, depth charts, rosters, players, snap counts, PFR advstats, FTN, NGS, QBR)
- [ ] Daily injury + depth-chart snapshot job
- [ ] The Odds API snapshotter (free tier; Tue open, midweek, T-60 per kickoff slot)
- [ ] DuckDB schema (ref / nfl / market / lab) + loaders with snapshot_id
- [ ] Data-quality checks + report
- [ ] Tests: snapshot integrity, schema, odds conversions
- [ ] Data audit (auditor role)

## Phase 2 — Features + baselines
- [ ] `features/asof.py` and the leakage test suite
- [ ] Team strength (opponent-adjusted EPA, success rate, decay, prior-season shrinkage)
- [ ] Rest / schedule features; QB starter adjustment (depth chart + QB history)
- [ ] Models M0, M-market, A (ridge), B (ratings), D (market-residual)
- [ ] Pricing layer (empirical margin distribution, key numbers, vig removal, pushes) + auditor's independent odds script
- [ ] Decision layer with calibration-derived thresholds; flat sizing
- [ ] Leakage audit

## Phase 3 — Historical lines + validation
- [ ] SBR archive parser (2010–2021): open, close, ML, 2H
- [ ] nflverse last-pull lines 2010–2025 labeled `last_pull`
- [ ] Discrepancy study SBR vs nflverse (and vs Odds API when backfilled)
- [ ] Walk-forward harness; dev 2010–2021, validation 2022–2023, sealed 2024–2025
- [ ] Backtest audit; CHANGELOG entry with baseline comparison

## Deferred (documented, not forgotten)
- The Odds API historical backfill 2020–2025 (one paid month, ~$59) — Phase 3 or when CLV history is needed
- Betting splits (no historical source; live costs $229/mo) — hypothesis only
- Officials features (2026 data stale), coaching database, OL/DL matchup model, NGS features, weather beyond roof/surface
- Kelly / confidence sizing (after a season of calibration evidence)
- Dashboard, scheduled automation
