Run the NFL Edge Lab daily data job and report briefly.

1. `uv run edgelab ingest daily`
2. `uv run edgelab ingest odds --label $ARGUMENTS` (use `adhoc` if no label given). If the odds host is unreachable from this environment, say so and continue.
3. `uv run edgelab db load --datasets schedules,injuries,depth_charts,rosters_weekly`
4. `uv run edgelab quality --season 2026`
5. Commit `data/metadata/snapshots.jsonl`, `data/snapshots/nflverse/injuries/`, `data/snapshots/odds_api/` and `reports/quality/` with message `data: daily snapshot <date>`.
Report: new vs unchanged snapshots, odds credits remaining, DQ action.
