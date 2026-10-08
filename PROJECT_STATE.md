# PROJECT_STATE.md — read this first in every session

Updated: 2026-10-08 14:10 UTC by the Orchestrator (session 1).

## Versions
- code: **v0.1** (data foundation) — complete, audited (APPROVED WITH CONDITIONS), tagged v0.1
- model: none
- agents: **a0.1**
- Phase: **1 complete → 2 — features + baselines** (see ROADMAP.md)

## Decisions on record
- 2026-10-08 Dennis: no Week 5 card. Week 5 = data collection. **First official week = Week 6** (freeze Sat Oct 17, 20:00 ET).
- 2026-10-08 Dennis: private GitHub repo `thatguydennis/edge-lab`; lab folder on his Mac: `~/Claude Cowork/Projects/edge lab`.
- 2026-10-08: The Odds API on the **free tier** (key in `.env`); paid historical backfill deferred to Phase 3.
- 2026-10-08: DuckDB + Parquet snapshot lake; snapshots are the system of record; the two irreplaceable
  snapshot sets (daily injuries, odds feed) are committed to git, everything else is rebuildable.

## Completed (this session)
- Phase 0 proposal (Claude doc + docs/PHASE0_PROPOSAL.md), research handoffs P0-DATA-001, P0-MKT-001.
- Repo scaffold, CLAUDE.md, roles in `.claude/agents/`, auditor checklists, handoff schema, config registries,
  leakage register.
- `edgelab ingest nflverse` — snapshot-first downloader (sha256, meta, dedup with "checked" records).
- `edgelab ingest daily` — live-season injuries / depth charts / rosters / schedules.
- `edgelab ingest odds` — The Odds API snapshotter (tested normalizer; live call blocked by sandbox allowlist, see blockers).
- `edgelab db load` — DuckDB schema (ref/nfl/market/lab) + loaders with snapshot_id; nflverse lines into
  `market.historical_lines` as `last_pull`; odds loader with team/book/game_id resolution.
- `edgelab quality` — 18 checks, report to reports/quality/, recorded in lab.data_quality_runs.
- `src/edgelab/pricing/odds.py` — conversions, vig removal (multiplicative, power), EV, CLV; 13 unit tests.
- Backfill 2010–2026 loaded: 152 snapshots, 781,492 plays, 7,548 games, 87,205 injury rows, 330,582 snap counts, etc.
  DQ: 16 pass / 2 warn / 0 critical (warn: 2017_04_CHI_GB missing moneyline; 7,342 untimestamped 2025+ injury rows).
- Tests: 30 passing; ruff clean.

## Also completed
- v0.1 pushed to GitHub; repo cloned to the Mac at `~/Claude Cowork/Projects/edge lab/repo`, env installed, lake + DB rebuilt there (identical).
- Data audit P1-DATA-001: audit 1 REVISION REQUIRED (blocker B1 timestamps; majors M1–M4) → all fixed → audit 2 APPROVED WITH CONDITIONS.
  Verdicts in artifacts/audit/; recorded in lab.audit_results.

## In progress / next
1. Daily snapshot job (`edgelab ingest daily` + `edgelab ingest odds`): must run from a native Mac terminal (odds host blocked in sandboxes). Decide: Claude Code on the Mac or a launchd schedule.
2. Phase 2: `features/asof.py` (quarantine enforced in code, string event-times parsed as UTC), leakage tests, team strength, rest, QB starter, M0/A/B/D, pricing distribution, decision layer → leakage audit.
3. Deferred from audit 2 (C3, C4): rosters_weekly status precedence + DQ; docs/DATA_DICTIONARY.md with type-drift notes; in-table `untimestamped` flag.
4. Phase 3: SBR parser (2010–2021), nfldata closing_lines.csv, discrepancy study, walk-forward harness, sealed-season run → backtest audit.
5. Week 6 freeze Sat Oct 17 20:00 ET only if 2–4 are audited.

## Blockers / limitations
- **`api.the-odds-api.com` is blocked** by the network allowlist in both the cloud workspace and the Mac's
  isolated workspace (HTTP 403 from proxy). Odds snapshots must run from a native terminal on the Mac
  (Claude Code) or after the host is allow-listed. The key itself is valid (verified via a fetch tool).
- No in-season participation/pressure data for 2026 (upstream).
- Officials data stale for 2026 (upstream) — disabled in config.

## Known data facts to remember
- nflverse `spread_line` is positive when home is favored; `market.historical_lines.spread_home = -spread_line`.
- 2026 schedule has 8 neutral-site games (see P0-DATA-001); week 5 byes: CAR, KC.
- Depth charts ≤2024 → `nfl.depth_charts_weekly`; ≥2025 → `nfl.depth_chart_snapshots` (column `dt`).
- Injury rows carry `observed_at` (our retrieval); `date_modified` only ≤2024 (TIMESTAMPTZ, UTC).
- `nfl.games.kickoff_utc` is derived (gameday + gametime in America/New_York → UTC); `gametime` is Eastern wall-clock.
- `market.historical_lines.line_class`: `last_pull` = completed game (≈close, book unknown); `live` = pre-kickoff observation from a tracked schedule_lines snapshot. Never `close` from nflverse.
- Two machines, one git-tracked index: the lake is per machine and rebuildable; only injuries, schedule_lines and odds snapshots are committed.

## Open owner questions
- Which sportsbooks Dennis bets at (config/books.yaml → bettable_books).
- Unit definition (config/settings.yaml → sizing.unit_definition).
