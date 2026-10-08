"""edgelab command line.

    edgelab ingest nflverse --seasons 2010-2026 [--datasets schedules,pbp,...]
    edgelab ingest daily                 # injuries + depth charts + rosters + schedules for the live season
    edgelab ingest odds [--label tue_open]
    edgelab db load --seasons 2010-2026 [--datasets ...]
    edgelab quality [--season 2026]
    edgelab status
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from edgelab import CODE_VERSION
from edgelab.config import get_settings

app = typer.Typer(help="NFL Edge Lab", no_args_is_help=True)
ingest_app = typer.Typer(help="Download upstream data into immutable snapshots")
db_app = typer.Typer(help="Load snapshots into DuckDB")
app.add_typer(ingest_app, name="ingest")
app.add_typer(db_app, name="db")
console = Console()

ALL_DATASETS = [
    "schedules", "teams", "players", "pbp", "stats_team_week", "stats_player_week", "injuries",
    "depth_charts", "rosters_weekly", "snap_counts", "pfr_advstats_week_pass", "pfr_advstats_week_def",
    "ftn_charting", "ngs_passing", "espn_qbr_week",
]
DAILY_DATASETS = ["schedules", "injuries", "depth_charts", "rosters_weekly"]  # schedules also derives schedule_lines


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def _seasons_for(dataset: str, requested: list[int]) -> list[int]:
    spec = get_settings().sources["nflverse"]["datasets"][dataset]
    lo = spec.get("supported_from", spec.get("first_season", 0))
    hi = spec.get("last_available_season", 9999)
    return [s for s in requested if lo <= s <= hi]


@ingest_app.command("nflverse")
def ingest_nflverse(
    seasons: str = typer.Option("2010-2026", help="e.g. 2010-2026 or 2024,2026"),
    datasets: str | None = typer.Option(None, help="comma-separated; default: all registered"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    from edgelab.ingest.nflverse import fetch_nflverse, parse_seasons
    from edgelab.ingest.snapshots import SnapshotStore

    _setup_logging(verbose)
    store = SnapshotStore()
    wanted = datasets.split(",") if datasets else ALL_DATASETS
    requested = parse_seasons(seasons)
    for name in wanted:
        spec = get_settings().sources["nflverse"]["datasets"][name]
        seas = _seasons_for(name, requested) if spec.get("per_season") else None
        metas = fetch_nflverse(name, seas, store=store)
        new = sum(1 for m in metas if not m.duplicate_of)
        console.print(f"[bold]{name}[/]: {len(metas)} files checked, {new} new snapshots")


@ingest_app.command("daily")
def ingest_daily(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    """The daily job: snapshot the live-season files whose upstream history is lossy (injuries, depth charts)."""
    from edgelab.ingest.nflverse import fetch_nflverse
    from edgelab.ingest.snapshots import SnapshotStore

    _setup_logging(verbose)
    live = int(get_settings().settings["seasons"]["live"])
    store = SnapshotStore()
    for name in DAILY_DATASETS:
        spec = get_settings().sources["nflverse"]["datasets"][name]
        metas = fetch_nflverse(name, [live] if spec.get("per_season") else None, store=store)
        for m in metas:
            console.print(f"{'unchanged' if m.duplicate_of else 'NEW      '} {name} rows={m.rows} {m.snapshot_id}")


@ingest_app.command("odds")
def ingest_odds(
    label: str = typer.Option("adhoc", help="tue_open | midweek | pre_kickoff | adhoc"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    from edgelab.ingest.odds_api import fetch_odds_snapshot

    _setup_logging(verbose)
    meta = fetch_odds_snapshot(label=label)
    extra = meta.extra or {}
    console.print(f"odds snapshot {meta.snapshot_id} events={meta.rows} credits remaining={extra.get('requests_remaining')}")


@db_app.command("load")
def db_load(
    seasons: str = typer.Option("2010-2026"),
    datasets: str | None = typer.Option(None),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    from edgelab.db import connect
    from edgelab.db.load import (
        build_historical_lines_from_games,
        load_dataset,
        load_reference,
        load_schedule_line_snapshots,
        sync_snapshot_index,
    )
    from edgelab.db.load_odds import load_odds_snapshots
    from edgelab.ingest.nflverse import parse_seasons
    from edgelab.ingest.snapshots import SnapshotStore

    _setup_logging(verbose)
    store = SnapshotStore()
    con = connect()
    load_reference(con)
    n = sync_snapshot_index(con, store)
    console.print(f"snapshot index synced: {n} rows")
    wanted = datasets.split(",") if datasets else ALL_DATASETS
    requested = parse_seasons(seasons)
    for name in wanted:
        spec = get_settings().sources["nflverse"]["datasets"][name]
        seas = _seasons_for(name, requested) if spec.get("per_season") else None
        res = load_dataset(name, seas, con=con, store=store)
        console.print(f"[bold]{name}[/]: " + (", ".join(f"{t}@{s}={r}" for t, s, r in res) if res else "nothing new"))
    if "schedules" in wanted:
        console.print(f"market.historical_lines (nflverse): {build_historical_lines_from_games(con)} rows")
        console.print(f"live schedule-line snapshots appended: {load_schedule_line_snapshots(con, store)} rows")
    console.print(f"odds snapshots loaded: {load_odds_snapshots(con, store)} rows")
    con.close()


@app.command("quality")
def quality(season: int | None = typer.Option(None), verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    from edgelab.db import connect
    from edgelab.ingest.snapshots import SnapshotStore
    from edgelab.quality.checks import run_checks, write_report

    _setup_logging(verbose)
    con = connect()
    findings = run_checks(con, SnapshotStore(), season)
    path, action = write_report(findings, con, scope=f"season={season}" if season else "all")
    t = Table(title="DATA QUALITY CHECK")
    for col in ("check", "severity", "value", "message"):
        t.add_column(col)
    for x in findings:
        color = {"PASS": "green", "WARN": "yellow", "CRITICAL": "red"}[x.severity]
        t.add_row(x.check_id, f"[{color}]{x.severity}[/]", x.value, x.message)
    console.print(t)
    console.print(f"Action: [bold]{action.replace('_', ' ')}[/]  report: {path}")
    con.close()
    if action == "stop":
        raise typer.Exit(code=2)


audit_app = typer.Typer(help="Audit records")
app.add_typer(audit_app, name="audit")


@audit_app.command("record")
def audit_record(
    task_id: str = typer.Argument(...),
    audit_type: str = typer.Option(..., help="data | leakage | backtest | prediction"),
    verdict: str = typer.Option(..., help="APPROVED | APPROVED_WITH_CONDITIONS | REVISION_REQUIRED | REJECTED"),
    blockers: int = typer.Option(0), majors: int = typer.Option(0), minors: int = typer.Option(0),
    reaudit: bool = typer.Option(False), report: str = typer.Option(..., help="path to the .audit.md"),
) -> None:
    """Record an auditor verdict in lab.audit_results (the auditor itself never writes to the DB)."""
    import subprocess
    import uuid

    from edgelab.db import connect

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=get_settings().root).stdout.strip()
    con = connect()
    con.execute(
        "INSERT INTO lab.audit_results (audit_id, task_id, audit_type, verdict, blockers, majors, minors, reaudit, commit, report_path) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [str(uuid.uuid4()), task_id, audit_type, verdict, blockers, majors, minors, reaudit, commit, report],
    )
    con.close()
    console.print(f"recorded {task_id} {audit_type} {verdict} @ {commit}")


@app.command("status")
def status() -> None:
    from edgelab.db import connect

    s = get_settings()
    console.print(f"edgelab code {CODE_VERSION}  root={s.root}  db={s.db_path}")
    if not s.db_path.exists():
        console.print("database not created yet")
        return
    con = connect(read_only=True)
    t = Table(title="tables")
    t.add_column("table")
    t.add_column("rows", justify="right")
    for schema, name in con.execute(
        "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN ('ref','nfl','market','lab') ORDER BY 1,2"
    ).fetchall():
        n = con.execute(f"SELECT count(*) FROM {schema}.{name}").fetchone()[0]
        t.add_row(f"{schema}.{name}", f"{n:,}")
    console.print(t)
    con.close()


if __name__ == "__main__":
    app()
