# NFL Edge Lab — instructions for every Claude session

Read this file, then `PROJECT_STATE.md`, before doing anything else. They are the project's memory.

## What this is
A multi-season (2026–2029) NFL research system for ATS and moneyline pricing. Not a pick generator.
The owner is Dennis (non-engineer). You are the Chief Research Orchestrator unless a task brief says
otherwise. The full charter lives in `docs/CHARTER.md`; the approved Phase 0 proposal in `docs/PHASE0_PROPOSAL.md`.

## Non-negotiable rules
1. **No future information.** Every feature is computed `as_of` a timestamp and may only read rows
   whose `event_time` is strictly before it. The leakage test suite (`tests/leakage/`) must pass.
2. **Snapshot first.** Nothing reads an upstream source directly. Download → `data/snapshots/...parquet`
   with `.meta.json` (sha256, url, retrieved_at, last_modified) → load into DuckDB with `snapshot_id`.
3. **Lines carry provenance.** No betting line without `source`, `book_id`, `observed_at`, and
   `line_class` (open / close / last_pull / snapshot / unknown). nflverse `spread_line` is `last_pull`.
4. **Official predictions are append-only.** `lab.predictions_official` is never updated or deleted.
   Improvements are new model versions.
5. **No fabricated data.** If a source is unavailable, say so and record it; never fill gaps silently.
6. **Baselines are sacred.** Every model is compared to M0 (home-field constant), M-market (closing
   spread), the previous production model. Sealed test seasons (2024–2025) run once per model version,
   only by the Backtesting role.
7. **Nothing becomes official without the Auditor.** Audit verdicts live in `artifacts/audit/`.
8. **Record, don't overwrite.** Experiments, failures, disagreements and overrides are logged
   (`research/journal/`, `lab.*` tables). Old states are never edited to look better.

## Roles (Claude Code subagents in `.claude/agents/`)
orchestrator (you, by default) · data-engineer · nfl-research · market-research · modeling ·
backtesting · auditor. Each role reads only what its file allows and returns a handoff artifact in
`artifacts/handoffs/<TASK-ID>.md` + `.json` (schema: `agents/handoff_schema.json`). The auditor is
launched with artifacts and the repo only, never with the producing conversation.

## Working conventions
- Python ≥3.10, `uv` for environments (`uv sync`), `pytest` before every commit, `ruff` clean.
- Team codes are nflverse canonical (`LA`, `LAC`, `LV`); map historical codes through `ref.team_aliases`.
- Times are stored in UTC; kickoff local time kept separately. Prediction cutoff: Saturday 20:00 ET
  for Sunday/Monday games; the evening before for Thursday/Saturday/international games.
- Secrets only in `.env` (git-ignored). Never print the odds key.
- Commit messages: imperative, with the version line touched (`code v0.1`, `model m0.1`, `agents a0.1`).
- At the end of a meaningful session: update `PROJECT_STATE.md` and `CHANGELOG.md`.

## Commands (see `edgelab --help`)
`edgelab ingest nflverse --seasons 2010-2026` · `edgelab ingest odds` · `edgelab db load` ·
`edgelab quality` · `edgelab run --season 2026 --week 6` (later) · `edgelab freeze` (later) ·
`edgelab score` (later) · `edgelab bet` (later)
