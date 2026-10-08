"""Re-audit checks (audit 2) on the rebuilt DB. Read-only."""
import json
from pathlib import Path

import polars as pl
import pyarrow.parquet as pq

from edgelab.db import connect

ROOT = Path("/home/claude/edge-lab")
con = connect(read_only=True)
print("TimeZone:", con.execute("SELECT current_setting('TimeZone')").fetchone())
idx = [json.loads(l) for l in (ROOT / "data/metadata/snapshots.jsonl").read_text().splitlines() if l.strip()]
by_id = {r["snapshot_id"]: r for r in idx}

print("\n== (1) injuries.date_modified raw vs loaded, every 2010-2024 snapshot ==")
tot_bad = tot = 0
for r in idx:
    if r["dataset"] != "injuries" or r["duplicate_of"] or r["season"] is None or r["season"] > 2024:
        continue
    raw = pl.read_parquet(ROOT / r["path"])
    if "date_modified" not in raw.columns:
        print(r["season"], "no date_modified upstream"); continue
    raw = raw.select("season", "week", "team", "gsis_id", "date_modified").with_columns(pl.col("season").cast(pl.Int32), pl.col("week").cast(pl.Int32)).with_columns(pl.col("date_modified").dt.convert_time_zone("UTC").dt.replace_time_zone(None).alias("raw_utc")).drop("date_modified")
    db = con.execute("SELECT season, week, team, gsis_id, date_modified AT TIME ZONE 'UTC' AS db_utc FROM nfl.injury_reports WHERE season=?", [r["season"]]).pl()
    # join on full key incl. the timestamp pairing: compare multisets per key
    j = raw.sort(["season","week","team","gsis_id","raw_utc"]).with_columns(pl.int_range(pl.len()).over(["season","week","team","gsis_id"]).alias("k")) \
        .join(db.sort(["season","week","team","gsis_id","db_utc"]).with_columns(pl.int_range(pl.len()).over(["season","week","team","gsis_id"]).alias("k")), on=["season","week","team","gsis_id","k"], how="full", coalesce=True)
    bad = j.filter((pl.col("raw_utc") != pl.col("db_utc")) | pl.col("raw_utc").is_null() != pl.col("db_utc").is_null()).height
    tot += j.height; tot_bad += bad
    if bad:
        print(r["season"], "MISMATCH rows:", bad, j.filter(pl.col("raw_utc") != pl.col("db_utc")).head(3))
print(f"rows compared {tot}, mismatches {tot_bad}, raw rows {sum(r['rows'] for r in idx if r['dataset']=='injuries' and not r['duplicate_of'] and r['season'] and r['season']<=2024)}")
print("db type:", con.execute("SELECT data_type FROM information_schema.columns WHERE table_schema='nfl' AND table_name='injury_reports' AND column_name='date_modified'").fetchone())
print("sample:", con.execute("SELECT CAST(date_modified AS VARCHAR) FROM nfl.injury_reports WHERE season=2024 AND gsis_id='00-0039521' AND week=1").fetchall())

print("\n== (1b) naive TIMESTAMP columns anywhere in nfl/market/lab ==")
print(con.execute("SELECT table_schema, table_name, column_name FROM information_schema.columns WHERE table_schema IN ('nfl','market','lab') AND data_type='TIMESTAMP'").fetchall())
print("TIMESTAMPTZ columns:", con.execute("SELECT table_schema||'.'||table_name||'.'||column_name FROM information_schema.columns WHERE table_schema IN ('nfl','market') AND data_type LIKE 'TIMESTAMP WITH%'").fetchall())
# ftn date_pulled, injuries observed_at, lines observed_at raw vs loaded
print("ftn date_pulled sample raw/db:")
r = [v for v in idx if v["dataset"]=="ftn_charting" and v["season"]==2025 and not v["duplicate_of"]][0]
print(pl.read_parquet(ROOT / r["path"]).select("date_pulled").head(1), con.execute("SELECT CAST(date_pulled AS VARCHAR) FROM nfl.ftn_charting WHERE season=2025 LIMIT 1").fetchone())
print("string-typed event-time columns (not covered by the DQ check):", con.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema='nfl' AND data_type='VARCHAR' AND (column_name IN ('dt','gameday','gametime','game_date','time_of_day','start_time'))").fetchall())

print("\n== (3) rosters key with status unique? ==")
print("dupes (season,week,team,gsis_id,status):", con.execute("SELECT count(*)-count(DISTINCT (season,week,team,gsis_id,status)) FROM nfl.rosters_weekly WHERE gsis_id IS NOT NULL").fetchone())
print("player-weeks 2010-2015 with >1 status and none ACT:", con.execute("""SELECT count(*) FROM (SELECT season,week,team,gsis_id FROM nfl.rosters_weekly WHERE gsis_id IS NOT NULL GROUP BY 1,2,3,4 HAVING count(*)>1 AND sum(CASE WHEN status='ACT' THEN 1 ELSE 0 END)=0)""").fetchone())
print("status combos in dup groups:", con.execute("""SELECT string_agg(status, '+' ORDER BY status) s, count(*) FROM nfl.rosters_weekly WHERE gsis_id IS NOT NULL GROUP BY season,week,team,gsis_id HAVING count(*)>1 QUALIFY true""").pl().group_by("s").agg(pl.col("count").sum()).sort("count", descending=True).head(8) if False else con.execute("""SELECT s, count(*) FROM (SELECT string_agg(status, '+' ORDER BY status) s FROM nfl.rosters_weekly WHERE gsis_id IS NOT NULL GROUP BY season,week,team,gsis_id HAVING count(*)>1) GROUP BY 1 ORDER BY 2 DESC LIMIT 8""").fetchall())

print("\n== (4) schedule-line persistence ==")
print(con.execute("SELECT line_class, count(*), count(DISTINCT game_id), count(DISTINCT snapshot_id), CAST(min(observed_at) AS VARCHAR), CAST(max(observed_at) AS VARCHAR) FROM market.historical_lines GROUP BY 1").fetchall())
print("dupes per (game_id, snapshot_id):", con.execute("SELECT count(*)-count(DISTINCT (game_id, snapshot_id)) FROM market.historical_lines").fetchone())
print("dupes per (game_id, snapshot_id, line_class):", con.execute("SELECT count(*)-count(DISTINCT (game_id, snapshot_id, line_class)) FROM market.historical_lines").fetchone())
print("live rows by snapshot_id:", con.execute("SELECT snapshot_id, count(*), CAST(min(observed_at) AS VARCHAR) FROM market.historical_lines WHERE line_class='live' GROUP BY 1").fetchall())
print("live rows for completed games:", con.execute("SELECT count(*) FROM market.historical_lines h JOIN nfl.games g USING(game_id) WHERE h.line_class='live' AND g.result IS NOT NULL").fetchone())
print("last_pull rows for unplayed games:", con.execute("SELECT count(*) FROM market.historical_lines h JOIN nfl.games g USING(game_id) WHERE h.line_class='last_pull' AND g.result IS NULL").fetchone())
print("live rows observed after kickoff:", con.execute("SELECT count(*) FROM market.historical_lines h JOIN nfl.games g USING(game_id) WHERE h.line_class='live' AND h.observed_at >= g.kickoff_utc").fetchone())
print("live snapshot ids in index?", [s for (s,) in con.execute("SELECT DISTINCT snapshot_id FROM market.historical_lines WHERE line_class='live'").fetchall() if s not in by_id])
# raw extract vs loaded
r = [v for v in idx if v["dataset"]=="schedule_lines"]
print("schedule_lines index rows:", [(v["snapshot_id"], v["rows"], v["extra"]) for v in r])
raw = pl.read_parquet(ROOT / r[0]["path"])
print("raw extract columns:", raw.columns, "rows:", raw.height)
db = con.execute("SELECT game_id, spread_home, ml_home, ml_away, total FROM market.historical_lines WHERE line_class='live' AND snapshot_id=?", [r[0]["snapshot_id"]]).pl()
j = raw.join(db, on="game_id", how="inner")
print("raw-vs-loaded live mismatches:", j.filter((pl.col("spread_home") != -pl.col("spread_line")) | (pl.col("ml_home") != pl.col("home_moneyline")) | (pl.col("total") != pl.col("total_line"))).height, "joined", j.height)
# does the schedules snapshot the extract derives from match nfl.games snapshot?
print("nfl.games snapshot_id:", con.execute("SELECT DISTINCT snapshot_id FROM nfl.games").fetchall(), "derived_from:", r[0]["extra"])
print("games with lines but result null (should equal live distinct game_ids):", con.execute("SELECT count(*) FROM nfl.games WHERE result IS NULL AND (spread_line IS NOT NULL OR home_moneyline IS NOT NULL)").fetchone())
print("week5/6 line values changed between the 13:08 and 13:41 schedule snapshots?")
s1 = pl.read_parquet(ROOT / by_id["nflverse.schedules.all.20261008T130804+0000.58fc64e7"]["path"]).filter(pl.col("season")==2026, pl.col("week").is_in([5,6])).select("game_id","spread_line","home_moneyline","total_line")
s2 = pl.read_parquet(ROOT / by_id["nflverse.schedules.all.20261008T134122+0000.c8ea28b2"]["path"]).filter(pl.col("season")==2026, pl.col("week").is_in([5,6])).select("game_id","spread_line","home_moneyline","total_line")
print(s1.join(s2, on="game_id", suffix="_b").filter((pl.col("spread_line")!=pl.col("spread_line_b"))|(pl.col("home_moneyline")!=pl.col("home_moneyline_b"))|(pl.col("total_line")!=pl.col("total_line_b"))))

print("\n== (5) kickoff_utc samples ==")
print("type:", con.execute("SELECT data_type FROM information_schema.columns WHERE table_schema='nfl' AND table_name='games' AND column_name='kickoff_utc'").fetchone())
for gid in ["2026_05_PHI_JAX", "2026_05_TB_DAL", "2026_05_CHI_GB", "2025_01_KC_LAC", "2025_04_MIN_PIT", "2024_18_DET_SF", "2023_12_CHI_MIN", "2010_01_MIN_NO", "2025_22_KC_PHI"]:
    print(con.execute("SELECT game_id, gameday, gametime, weekday, CAST(kickoff_utc AS VARCHAR), CAST(kickoff_utc AT TIME ZONE 'America/New_York' AS VARCHAR) FROM nfl.games WHERE game_id=?", [gid]).fetchall())
print("Monday night sample:", con.execute("SELECT game_id, gameday, gametime, CAST(kickoff_utc AS VARCHAR) FROM nfl.games WHERE season=2025 AND weekday='Monday' ORDER BY gameday LIMIT 2").fetchall())
print("null gametime rows:", con.execute("SELECT count(*), sum(CASE WHEN kickoff_utc IS NULL THEN 1 ELSE 0 END) FROM nfl.games WHERE gametime IS NULL").fetchone())
print("gametime set but kickoff_utc null:", con.execute("SELECT count(*) FROM nfl.games WHERE gametime IS NOT NULL AND kickoff_utc IS NULL").fetchone())
print("kickoff_utc date != gameday (ET) for any game? (should be 0 when converted back):", con.execute("SELECT count(*) FROM nfl.games WHERE kickoff_utc IS NOT NULL AND CAST(kickoff_utc AT TIME ZONE 'America/New_York' AS DATE) <> CAST(gameday AS DATE)").fetchone())
print("ET wall-clock round trip != gametime:", con.execute("SELECT count(*) FROM nfl.games WHERE kickoff_utc IS NOT NULL AND strftime(kickoff_utc AT TIME ZONE 'America/New_York', '%H:%M') <> gametime").fetchone())
print("DST check: Nov games 13:00 ET -> 18:00 UTC; Sep games 13:00 ET -> 17:00 UTC:", con.execute("SELECT substr(gameday,6,2) m, strftime(kickoff_utc, '%H:%M') FROM nfl.games WHERE season=2024 AND gametime='13:00' GROUP BY 1,2 ORDER BY 1").fetchall())
print("pbp time_of_day vs kickoff_utc (first play within 0-60 min after kickoff) 2025:", con.execute("""SELECT count(*), sum(CASE WHEN d BETWEEN 0 AND 60 THEN 1 ELSE 0 END) FROM (SELECT g.game_id, date_diff('minute', g.kickoff_utc, min(TRY_CAST(p.time_of_day AS TIMESTAMPTZ))) d FROM nfl.plays p JOIN nfl.games g USING(game_id) WHERE p.season=2025 AND p.time_of_day IS NOT NULL GROUP BY 1, g.kickoff_utc)""").fetchone())

print("\n== minors ==")
print("snapshot ids on rows are primary (not duplicate_of rows):", con.execute("SELECT count(*) FROM lab.snapshots WHERE duplicate_of IS NOT NULL AND snapshot_id IN (SELECT snapshot_id FROM nfl.games UNION SELECT snapshot_id FROM ref.players UNION SELECT snapshot_id FROM ref.teams UNION SELECT snapshot_id FROM nfl.rosters_weekly UNION SELECT snapshot_id FROM nfl.depth_chart_snapshots)").fetchone())
print("load_runs snapshot ids that are duplicate rows:", con.execute("SELECT count(*) FROM lab.load_runs l JOIN lab.snapshots s USING(snapshot_id) WHERE s.duplicate_of IS NOT NULL").fetchone())
print("audit_results:", con.execute("SELECT task_id, audit_type, verdict, blockers, majors, minors, reaudit, commit, report_path FROM lab.audit_results").fetchall())
print("dq runs:", con.execute("SELECT CAST(run_at AS VARCHAR), n_checks, n_warn, n_critical, action FROM lab.data_quality_runs ORDER BY run_at").fetchall())
print("snap_counts seasons:", con.execute("SELECT min(season), count(DISTINCT season) FROM nfl.snap_counts").fetchone(), "load_runs 2012:", con.execute("SELECT count(*) FROM lab.load_runs WHERE table_name='nfl.snap_counts' AND season=2012").fetchone())
print("games rows / plays rows unchanged:", con.execute("SELECT (SELECT count(*) FROM nfl.games), (SELECT count(*) FROM nfl.plays), (SELECT count(*) FROM nfl.injury_reports)").fetchone())
print("games 2026 snapshot now 13:41 — week 5 lines still present/ unplayed:", con.execute("SELECT count(*), sum(CASE WHEN spread_line IS NULL THEN 1 ELSE 0 END) FROM nfl.games WHERE season=2026 AND week IN (5,6)").fetchone())
