# NFL Edge Lab

A multi-season NFL ATS / moneyline research system: snapshot-first data, as-of features, audited predictions.

- Start here: `CLAUDE.md` → `PROJECT_STATE.md` → `docs/PHASE0_PROPOSAL.md`
- Charter: `docs/CHARTER.md`
- Roles (Claude Code subagents): `.claude/agents/`

## Setup
```bash
uv sync --extra dev
cp .env.example .env            # add ODDS_API_KEY
uv run edgelab ingest nflverse --seasons 2010-2026
uv run edgelab db load --seasons 2010-2026
uv run edgelab quality
uv run edgelab status
```

## Daily (in-season)
```bash
uv run edgelab ingest daily     # injuries, depth charts, rosters, schedules (live season)
uv run edgelab ingest odds --label midweek
uv run edgelab db load --datasets injuries,depth_charts,rosters_weekly,schedules
```

## Tests
```bash
uv run pytest && uv run ruff check src tests
```
