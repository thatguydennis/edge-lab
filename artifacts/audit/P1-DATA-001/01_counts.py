"""Recompute row counts / null rates claimed in the handoff. Read-only."""
from edgelab.db import connect

con = connect(read_only=True)

print("== tables ==")
for schema, name in con.execute(
    "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN ('ref','nfl','market','lab') ORDER BY 1,2"
).fetchall():
    n = con.execute(f"SELECT count(*) FROM {schema}.{name}").fetchone()[0]
    print(f"{schema}.{name:28s} {n:>12,}")

print("\n== nfl.games seasons ==")
print(con.execute("SELECT min(season), max(season), count(*), count(DISTINCT game_id) FROM nfl.games").fetchall())
print(con.execute("""SELECT season, count(*) n,
    sum(CASE WHEN spread_line IS NULL THEN 1 ELSE 0 END) null_spread,
    sum(CASE WHEN home_moneyline IS NULL THEN 1 ELSE 0 END) null_ml,
    sum(CASE WHEN total_line IS NULL THEN 1 ELSE 0 END) null_total,
    sum(CASE WHEN result IS NULL THEN 1 ELSE 0 END) null_result,
    sum(CASE WHEN home_spread_odds IS NULL THEN 1 ELSE 0 END) null_sp_odds
  FROM nfl.games WHERE season>=2008 GROUP BY 1 ORDER BY 1""").pl())

print("\n== games with null spread/ML 2010-2025 ==")
print(con.execute("""SELECT game_id, game_type, spread_line, home_moneyline, away_moneyline, total_line, result
  FROM nfl.games WHERE season BETWEEN 2010 AND 2025 AND (spread_line IS NULL OR home_moneyline IS NULL OR away_moneyline IS NULL)""").pl())

print("\n== 2026 by week ==")
print(con.execute("""SELECT week, count(*) n, sum(CASE WHEN result IS NULL THEN 1 ELSE 0 END) unplayed,
   sum(CASE WHEN spread_line IS NULL THEN 1 ELSE 0 END) null_spread, min(gameday), max(gameday)
   FROM nfl.games WHERE season=2026 GROUP BY 1 ORDER BY 1""").pl())

print("\n== plays ==")
print(con.execute("SELECT min(season), max(season), count(*), count(DISTINCT (game_id, play_id)), count(DISTINCT game_id) FROM nfl.plays").fetchall())
print(con.execute("SELECT season, count(*) n, count(DISTINCT game_id) games, count(DISTINCT snapshot_id) snaps FROM nfl.plays GROUP BY 1 ORDER BY 1").pl())
print(con.execute("SELECT week, count(*) FROM nfl.plays WHERE season=2026 GROUP BY 1 ORDER BY 1").pl())
print("null epa pct pass/run:", con.execute("SELECT round(100.0*sum(CASE WHEN epa IS NULL THEN 1 ELSE 0 END)/count(*),4) FROM nfl.plays WHERE play_type IN ('pass','run')").fetchone())

print("\n== injuries ==")
print(con.execute("SELECT count(*), min(season), max(season), count(DISTINCT snapshot_id) FROM nfl.injury_reports").fetchall())
print(con.execute("SELECT season, count(*) n, count(DISTINCT snapshot_id) snaps, sum(CASE WHEN date_modified IS NULL THEN 1 ELSE 0 END) null_dm FROM nfl.injury_reports GROUP BY 1 ORDER BY 1").pl())
print(con.execute("SELECT snapshot_id, observed_at, count(*) FROM nfl.injury_reports WHERE season>=2025 GROUP BY 1,2 ORDER BY 2").pl())

print("\n== other tables by season ==")
for t in ["nfl.team_week_stats", "nfl.player_week_stats", "nfl.rosters_weekly", "nfl.snap_counts", "nfl.pfr_pass_week",
          "nfl.pfr_def_week", "nfl.ftn_charting", "nfl.ngs_passing", "nfl.espn_qbr_week", "nfl.depth_charts_weekly",
          "nfl.depth_chart_snapshots"]:
    try:
        r = con.execute(f"SELECT min(season), max(season), count(*), count(DISTINCT season) FROM {t}").fetchone()
        print(t, r)
    except Exception as e:  # noqa
        print(t, "ERR", e)

print("\n== players ==")
print(con.execute("""SELECT count(*), round(100.0*sum(CASE WHEN pfr_id IS NULL THEN 1 ELSE 0 END)/count(*),1) pfr,
  round(100.0*sum(CASE WHEN espn_id IS NULL THEN 1 ELSE 0 END)/count(*),1) espn,
  round(100.0*sum(CASE WHEN pff_id IS NULL THEN 1 ELSE 0 END)/count(*),1) pff,
  count(*)-count(DISTINCT gsis_id) dup_gsis, sum(CASE WHEN gsis_id IS NULL THEN 1 ELSE 0 END) null_gsis FROM ref.players""").fetchall())

print("\n== market.historical_lines ==")
print(con.execute("SELECT count(*), count(DISTINCT game_id), CAST(min(observed_at) AS VARCHAR), CAST(max(observed_at) AS VARCHAR) FROM market.historical_lines").fetchall())
print(con.execute("SELECT source, book_id, line_class, count(*), sum(CASE WHEN observed_at IS NULL THEN 1 ELSE 0 END) null_obs, sum(CASE WHEN snapshot_id IS NULL THEN 1 ELSE 0 END) null_snap FROM market.historical_lines GROUP BY 1,2,3").pl())

print("\n== lab.snapshots / load_runs / dq ==")
print(con.execute("SELECT count(*), count(DISTINCT sha256) FROM lab.snapshots").fetchall())
print(con.execute("SELECT table_name, count(*), sum(rows_loaded) FROM lab.load_runs GROUP BY 1 ORDER BY 1").pl())
print(con.execute("SELECT dq_id, CAST(run_at AS VARCHAR) run_at, scope, n_checks, n_pass, n_warn, n_critical, action, report_path FROM lab.data_quality_runs ORDER BY run_at").pl())
print(con.execute("SELECT count(*) FROM lab.audit_results").fetchall())
