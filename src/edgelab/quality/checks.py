"""Data-quality checks.

Each check returns a Finding(check_id, severity, message, value). Severities: PASS, WARN, CRITICAL.
The report is written to reports/quality/<timestamp>.md and recorded in lab.data_quality_runs.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from edgelab.config import Settings, get_settings
from edgelab.ingest.snapshots import SnapshotStore


@dataclass
class Finding:
    check_id: str
    severity: str  # PASS | WARN | CRITICAL
    message: str
    value: str = ""


def _one(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None):
    row = con.execute(sql, params or []).fetchone()
    return row[0] if row else None


def _has(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    schema, name = table.split(".", 1)
    return bool(_one(con, "SELECT count(*) FROM information_schema.tables WHERE table_schema=? AND table_name=?", [schema, name]))


def run_checks(con: duckdb.DuckDBPyConnection, store: SnapshotStore, season: int | None = None) -> list[Finding]:
    f: list[Finding] = []

    # --- snapshot integrity ---------------------------------------------------------------
    problems = store.verify_all()
    f.append(Finding("snap.integrity", "CRITICAL" if problems else "PASS",
                     "all local snapshot files match recorded sha256; tracked snapshots present" if not problems else "; ".join(problems[:5]),
                     str(len(problems))))
    absent = store.absent_locally()
    f.append(Finding("snap.absent_locally", "PASS", "indexed snapshots not on this machine (rebuildable; run edgelab ingest)", str(absent)))

    if not _has(con, "nfl.games"):
        f.append(Finding("games.exists", "CRITICAL", "nfl.games not loaded"))
        return f

    # --- games ----------------------------------------------------------------------------
    dup = _one(con, "SELECT count(*) - count(DISTINCT game_id) FROM nfl.games")
    f.append(Finding("games.duplicate_ids", "CRITICAL" if dup else "PASS", "duplicate game_id rows", str(dup)))

    bad_dates = _one(con, "SELECT count(*) FROM nfl.games WHERE TRY_CAST(gameday AS DATE) IS NULL")
    f.append(Finding("games.invalid_dates", "CRITICAL" if bad_dates else "PASS", "rows with unparsable gameday", str(bad_dates)))

    impossible = _one(con, """SELECT count(*) FROM nfl.games
        WHERE (home_score IS NOT NULL AND (home_score < 0 OR home_score > 100))
           OR (away_score IS NOT NULL AND (away_score < 0 OR away_score > 100))""")
    f.append(Finding("games.impossible_scores", "CRITICAL" if impossible else "PASS", "scores outside 0..100", str(impossible)))

    inconsistent = _one(con, """SELECT count(*) FROM nfl.games
        WHERE home_score IS NOT NULL AND away_score IS NOT NULL AND result IS NOT NULL
          AND result <> home_score - away_score""")
    f.append(Finding("games.result_consistency", "CRITICAL" if inconsistent else "PASS", "result != home_score - away_score", str(inconsistent)))

    orphan_teams = _one(con, """SELECT count(*) FROM (
        SELECT home_team AS t FROM nfl.games UNION SELECT away_team FROM nfl.games) x
        WHERE t NOT IN (SELECT alias FROM ref.team_aliases)""")
    f.append(Finding("games.orphan_team_codes", "CRITICAL" if orphan_teams else "PASS", "team codes not in ref.team_aliases", str(orphan_teams)))

    # betting coverage (expected ~0% null from 2010 for regular season)
    where_season = "AND season = ?" if season else ""
    params = [season] if season else []
    null_lines = _one(con, f"""SELECT count(*) FROM nfl.games
        WHERE season >= 2010 AND game_type = 'REG' AND gameday <= strftime(current_date, '%Y-%m-%d')
          AND (spread_line IS NULL OR home_moneyline IS NULL) {where_season}""", params)
    f.append(Finding("games.missing_lines_played", "WARN" if null_lines else "PASS",
                     "played REG games since 2010 missing spread or moneyline (nflverse last_pull)", str(null_lines)))

    # schedule-vs-pbp coverage for the live season
    live = season or _one(con, "SELECT max(season) FROM nfl.games")
    if _has(con, "nfl.plays"):
        played = _one(con, "SELECT count(*) FROM nfl.games WHERE season=? AND result IS NOT NULL", [live])
        with_pbp = _one(con, "SELECT count(DISTINCT game_id) FROM nfl.plays WHERE season=?", [live])
        f.append(Finding("pbp.coverage_live_season", "WARN" if (played or 0) > (with_pbp or 0) else "PASS",
                         f"season {live}: games with result={played}, games with pbp={with_pbp}", str((played or 0) - (with_pbp or 0))))
        dup_plays = _one(con, "SELECT count(*) - count(DISTINCT (game_id, play_id)) FROM nfl.plays")
        f.append(Finding("pbp.duplicate_plays", "CRITICAL" if dup_plays else "PASS", "duplicate (game_id, play_id)", str(dup_plays)))
        null_epa = _one(con, "SELECT round(100.0*sum(CASE WHEN epa IS NULL THEN 1 ELSE 0 END)/count(*),2) FROM nfl.plays WHERE play_type IN ('pass','run')")
        f.append(Finding("pbp.null_epa_pct", "WARN" if (null_epa or 0) > 2 else "PASS", "% pass/run plays with null EPA", str(null_epa)))
    else:
        f.append(Finding("pbp.exists", "WARN", "nfl.plays not loaded"))

    # injuries: timestamp availability
    if _has(con, "nfl.injury_reports"):
        cols = [r[0] for r in con.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='nfl' AND table_name='injury_reports'").fetchall()]
        if "date_modified" in cols:
            untimestamped = _one(con, "SELECT count(*) FROM nfl.injury_reports WHERE season >= 2025 AND date_modified IS NULL")
            f.append(Finding("injuries.untimestamped_2025plus", "WARN" if untimestamped else "PASS",
                             "2025+ injury rows without upstream date_modified (as-of only via our observed_at)", str(untimestamped)))
        n_snaps = _one(con, "SELECT count(DISTINCT snapshot_id) FROM nfl.injury_reports WHERE season = ?", [live])
        f.append(Finding("injuries.daily_snapshots_live", "PASS" if (n_snaps or 0) >= 1 else "WARN",
                         f"distinct injury snapshots loaded for season {live}", str(n_snaps)))
    else:
        f.append(Finding("injuries.exists", "WARN", "nfl.injury_reports not loaded"))

    # players crosswalk
    if _has(con, "ref.players"):
        pfr_null = _one(con, "SELECT round(100.0*sum(CASE WHEN pfr_id IS NULL THEN 1 ELSE 0 END)/count(*),1) FROM ref.players")
        f.append(Finding("players.pfr_id_null_pct", "PASS" if (pfr_null or 0) < 15 else "WARN", "% players without pfr_id", str(pfr_null)))
        dup_gsis = _one(con, "SELECT count(*) - count(DISTINCT gsis_id) FROM ref.players WHERE gsis_id IS NOT NULL")
        f.append(Finding("players.duplicate_gsis", "CRITICAL" if dup_gsis else "PASS", "duplicate gsis_id", str(dup_gsis)))

    # market provenance
    if _has(con, "market.historical_lines"):
        bad = _one(con, "SELECT count(*) FROM market.historical_lines WHERE source IS NULL OR book_id IS NULL OR line_class IS NULL OR snapshot_id IS NULL")
        f.append(Finding("market.provenance", "CRITICAL" if bad else "PASS", "line rows missing source/book/line_class/snapshot", str(bad)))
        mislabeled = _one(con, "SELECT count(*) FROM market.historical_lines WHERE source='nflverse' AND line_class <> 'last_pull'")
        f.append(Finding("market.nflverse_line_class", "CRITICAL" if mislabeled else "PASS", "nflverse lines must be last_pull", str(mislabeled)))
    if _has(con, "market.odds_snapshots"):
        unmapped = _one(con, "SELECT count(DISTINCT event_id) FROM market.odds_snapshots WHERE game_id IS NULL")
        f.append(Finding("odds.unmapped_events", "WARN" if unmapped else "PASS", "odds events not matched to a game_id", str(unmapped)))
        unknown_books = _one(con, "SELECT count(DISTINCT book_key) FROM market.odds_snapshots WHERE book_id IS NULL")
        f.append(Finding("odds.unknown_books", "WARN" if unknown_books else "PASS", "feed book keys not in ref.books", str(unknown_books)))
    return f


def write_report(findings: list[Finding], con: duckdb.DuckDBPyConnection, settings: Settings | None = None, scope: str = "all") -> tuple[Path, str]:
    settings = settings or get_settings()
    n_pass = sum(1 for x in findings if x.severity == "PASS")
    n_warn = sum(1 for x in findings if x.severity == "WARN")
    n_crit = sum(1 for x in findings if x.severity == "CRITICAL")
    action = "stop" if n_crit else ("continue_with_warning" if n_warn else "continue")
    ts = datetime.now(timezone.utc).replace(microsecond=0)
    out_dir = settings.root / "reports" / "quality"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"dq_{ts.strftime('%Y%m%dT%H%M%SZ')}.md"
    lines = [
        "# DATA QUALITY CHECK", "", f"Run: {ts.isoformat()}  Scope: {scope}", "",
        f"Checks: {len(findings)}  Pass: {n_pass}  Warnings: {n_warn}  Critical: {n_crit}", "",
        f"Action: {action.replace('_', ' ')}", "", "| Check | Severity | Value | Message |", "|---|---|---|---|",
    ]
    lines += [f"| {x.check_id} | {x.severity} | {x.value} | {x.message} |" for x in findings]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    dq_id = str(uuid.uuid4())
    con.execute(
        "INSERT INTO lab.data_quality_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [dq_id, ts, scope, len(findings), n_pass, n_warn, n_crit, action, str(path.relative_to(settings.root))],
    )
    con.executemany(
        "INSERT INTO lab.data_quality_findings VALUES (?, ?, ?, ?, ?)",
        [[dq_id, x.check_id, x.severity, x.message, x.value] for x in findings],
    )
    return path, action
