"""Drill into duplicate-key findings."""
from edgelab.db import connect

con = connect(read_only=True)

print("== rosters_weekly dupes on (season,week,team,gsis_id) ==")
print("null gsis_id rows:", con.execute("SELECT count(*) FROM nfl.rosters_weekly WHERE gsis_id IS NULL").fetchone())
print("dupes with non-null gsis:", con.execute("""SELECT count(*) FROM (SELECT season,week,team,gsis_id, count(*) c FROM nfl.rosters_weekly WHERE gsis_id IS NOT NULL GROUP BY 1,2,3,4 HAVING c>1)""").fetchone())
print("exact full-row duplicates (all cols):", con.execute("""SELECT count(*) - (SELECT count(*) FROM (SELECT DISTINCT * FROM nfl.rosters_weekly)) FROM nfl.rosters_weekly""").fetchone())
print(con.execute("""SELECT season, count(*) FROM (SELECT season,week,team,gsis_id, count(*) c FROM nfl.rosters_weekly WHERE gsis_id IS NOT NULL GROUP BY 1,2,3,4 HAVING c>1) GROUP BY 1 ORDER BY 1""").fetchall())
print(con.execute("""SELECT season,week,team,gsis_id,full_name,position,status,game_type FROM nfl.rosters_weekly WHERE (season,week,team,gsis_id) IN
   (SELECT (season,week,team,gsis_id) FROM nfl.rosters_weekly WHERE gsis_id IS NOT NULL GROUP BY 1 HAVING count(*)>1) ORDER BY 1,2,3,4 LIMIT 8""").fetchall())
print("dupes on (season,week,team,gsis_id,game_type):", con.execute("SELECT count(*)-count(DISTINCT (season,week,team,gsis_id,game_type)) FROM nfl.rosters_weekly WHERE gsis_id IS NOT NULL").fetchone())

print("\n== injury_reports dupes ==")
print(con.execute("""SELECT snapshot_id, season, week, team, gsis_id, full_name, report_status, practice_status, CAST(date_modified AS VARCHAR) FROM nfl.injury_reports WHERE (snapshot_id,season,week,team,gsis_id) IN
   (SELECT (snapshot_id,season,week,team,gsis_id) FROM nfl.injury_reports GROUP BY 1 HAVING count(*)>1) ORDER BY 2,3""").fetchall())
print("null gsis_id in injuries:", con.execute("SELECT count(*) FROM nfl.injury_reports WHERE gsis_id IS NULL").fetchone())

print("\n== depth_charts_weekly dupes ==")
cols = [r[0] for r in con.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='nfl' AND table_name='depth_charts_weekly' ORDER BY ordinal_position").fetchall()]
print("columns:", cols)
print("exact full-row duplicates:", con.execute("SELECT count(*) - (SELECT count(*) FROM (SELECT DISTINCT * FROM nfl.depth_charts_weekly)) FROM nfl.depth_charts_weekly").fetchone())
print("dupes on key + game_type + formation + depth_position:", con.execute("SELECT count(*)-count(DISTINCT (season,week,game_type,club_code,formation,depth_team,position,depth_position,gsis_id)) FROM nfl.depth_charts_weekly").fetchone())
print("null gsis_id:", con.execute("SELECT count(*) FROM nfl.depth_charts_weekly WHERE gsis_id IS NULL").fetchone())
print(con.execute("""SELECT season,week,game_type,club_code,formation,depth_team,position,depth_position,gsis_id,full_name FROM nfl.depth_charts_weekly WHERE (season,week,club_code,depth_team,position,gsis_id) IN
   (SELECT (season,week,club_code,depth_team,position,gsis_id) FROM nfl.depth_charts_weekly WHERE gsis_id IS NOT NULL GROUP BY 1 HAVING count(*)>1) ORDER BY 1,2,4,9 LIMIT 6""").fetchall())

print("\n== depth_chart_snapshots dupes ==")
cols = [r[0] for r in con.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='nfl' AND table_name='depth_chart_snapshots' ORDER BY ordinal_position").fetchall()]
print("columns:", cols)
print("exact full-row duplicates:", con.execute("SELECT count(*) - (SELECT count(*) FROM (SELECT DISTINCT * FROM nfl.depth_chart_snapshots)) FROM nfl.depth_chart_snapshots").fetchone())
print("null gsis_id:", con.execute("SELECT count(*) FROM nfl.depth_chart_snapshots WHERE gsis_id IS NULL").fetchone())
print("dupes among non-null gsis:", con.execute("SELECT count(*)-count(DISTINCT (season,dt,team,pos_slot,pos_rank,gsis_id)) FROM nfl.depth_chart_snapshots WHERE gsis_id IS NOT NULL").fetchone())
print("distinct dt per season:", con.execute("SELECT season, count(DISTINCT dt), min(dt), max(dt) FROM nfl.depth_chart_snapshots GROUP BY 1").fetchall())
print("dt format lengths:", con.execute("SELECT length(dt), count(*) FROM nfl.depth_chart_snapshots GROUP BY 1").fetchall())

print("\n== snap_counts 2012 ==")
print(con.execute("SELECT season, count(*) FROM nfl.snap_counts WHERE season <= 2013 GROUP BY 1").fetchall())
print(con.execute("SELECT * FROM lab.load_runs WHERE table_name='nfl.snap_counts' AND season=2012").fetchall())

print("\n== injuries 2010 null date_modified ==")
print(con.execute("SELECT week, count(*) FROM nfl.injury_reports WHERE season=2010 AND date_modified IS NULL GROUP BY 1 ORDER BY 1").fetchall())

print("\n== injuries: duplicate (season,week,team,gsis_id) across different snapshots? (append strategy) ==")
print(con.execute("SELECT season, count(DISTINCT snapshot_id) FROM nfl.injury_reports GROUP BY 1 HAVING count(DISTINCT snapshot_id)>1").fetchall())

print("\n== espn_qbr_week columns ==")
print([r[0] for r in con.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='nfl' AND table_name='espn_qbr_week' ORDER BY ordinal_position").fetchall()])
