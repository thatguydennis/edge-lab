# Changelog

Entries follow the charter template: Added / Changed / Removed / Reason / Backtest / Decision / Audit.
Version lines: `code vX.Y` (git tags), `model mX.Y` (lab.model_versions), `agents aX.Y`.

## code v0.1 — Data foundation (2026-10-08)

Added:
- Repository scaffold: pyproject (uv), CLAUDE.md, PROJECT_VISION.md, PROJECT_STATE.md, ROADMAP.md, docs/CHARTER.md, docs/PHASE0_PROPOSAL.md
- Agent roles as Claude Code subagents (`.claude/agents/`), handoff schema (`agents/handoff_schema.json`) — agents a0.1
- Phase 0 research handoffs: artifacts/handoffs/P0-DATA-001.md (nflverse inventory), P0-MKT-001.md (market sources)
- config/sources.yaml (dataset registry with tier, license, cadence, line_class), config/books.yaml (book registry with validity dates)
- Snapshot-first ingestion for nflverse release assets (sha256 + .meta.json + metadata index)
- The Odds API snapshotter (writes raw JSON + normalized Parquet with observed_at; free-tier plan)
- DuckDB schema (ref / nfl / market / lab) and loaders carrying snapshot_id
- Data-quality checks and report
- Tests: snapshot integrity, schema, odds conversions, timezones, quarantine coverage, live-line extract (36 passing)
- `edgelab audit record` to log auditor verdicts in lab.audit_results
- Git-tracked `schedule_lines` extract (live line values for unplayed games) and `kickoff_utc` on nfl.games

Changed (after audit 1, same day):
- tz-aware timestamps stored as TIMESTAMPTZ on the schema-evolution path; DuckDB session TimeZone=UTC
- quarantine list expanded to all leakage-register L1–L4 columns; tested against the register
- nflverse lines: `last_pull` only for completed games, `live` observations appended per schedule snapshot
- unique snapshot ids on same-second collisions; tables stamped with the primary snapshot id

Reason: charter Phase 1; data audit found live/unlabeled lines, untimestamped 2025+ injuries and rebuilt pbp, so snapshots are the system of record.

Decision: Week 5 is data collection only; first official week is Week 6 (owner decision, 2026-10-08).

Audit: P1-DATA-001 — audit 1 REVISION REQUIRED (blocker: injury timestamps shifted to local time), revised;
audit 2 APPROVED WITH CONDITIONS (C1 live-line kickoff filter fixed same day; C3/C4 deferred to Phase 2).
Reproduced on a second machine (identical counts and DQ).
