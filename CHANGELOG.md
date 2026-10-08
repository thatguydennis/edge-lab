# Changelog

Entries follow the charter template: Added / Changed / Removed / Reason / Backtest / Decision / Audit.
Version lines: `code vX.Y` (git tags), `model mX.Y` (lab.model_versions), `agents aX.Y`.

## code v0.1 — Data foundation (in progress, started 2026-10-08)

Added:
- Repository scaffold: pyproject (uv), CLAUDE.md, PROJECT_VISION.md, PROJECT_STATE.md, ROADMAP.md, docs/CHARTER.md, docs/PHASE0_PROPOSAL.md
- Agent roles as Claude Code subagents (`.claude/agents/`), handoff schema (`agents/handoff_schema.json`) — agents a0.1
- Phase 0 research handoffs: artifacts/handoffs/P0-DATA-001.md (nflverse inventory), P0-MKT-001.md (market sources)
- config/sources.yaml (dataset registry with tier, license, cadence, line_class), config/books.yaml (book registry with validity dates)
- Snapshot-first ingestion for nflverse release assets (sha256 + .meta.json + metadata index)
- The Odds API snapshotter (writes raw JSON + normalized Parquet with observed_at; free-tier plan)
- DuckDB schema (ref / nfl / market / lab) and loaders carrying snapshot_id
- Data-quality checks and report
- Tests: snapshot integrity, schema, odds conversions

Reason: charter Phase 1; data audit found live/unlabeled lines, untimestamped 2025+ injuries and rebuilt pbp, so snapshots are the system of record.

Decision: Week 5 is data collection only; first official week is Week 6 (owner decision, 2026-10-08).

Audit: pending (data audit).
