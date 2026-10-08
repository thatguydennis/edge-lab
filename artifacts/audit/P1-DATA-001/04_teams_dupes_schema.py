"""Team code resolution, duplicates, schema drift across seasons, timezone handling, quarantine coverage."""
import re
from pathlib import Path

import yaml

from edgelab.db import connect

con = connect(read_only=True)
ROOT = Path("/home/claude/edge-lab")

print("== team codes in nfl.games not in ref.team_aliases ==")
print(con.execute("""SELECT t, count(*) FROM (SELECT home_team t FROM nfl.games UNION ALL SELECT away_team FROM nfl.games) x
   WHERE t NOT IN (SELECT alias FROM ref.team_aliases) GROUP BY 1""").fetchall())
print("distinct codes in games:", con.execute("SELECT count(DISTINCT t) FROM (SELECT home_team t FROM nfl.games UNION SELECT away_team FROM nfl.games)").fetchone())
print("codes by season range:")
print(con.execute("""SELECT t, min(season), max(season), count(*) FROM (SELECT home_team t, season FROM nfl.games UNION ALL SELECT away_team, season FROM nfl.games) x
   WHERE t IN ('OAK','LV','SD','LAC','STL','LA','LAR','WAS','WSH','JAC','JAX') GROUP BY 1 ORDER BY 1""").pl())
print("canonical of those:", con.execute("SELECT alias, team, franchise_id FROM ref.team_aliases WHERE alias IN ('OAK','LV','SD','LAC','STL','LA','LAR','WAS','WFT','JAC','JAX') ORDER BY 1").fetchall())
print("ref.team_aliases: alias count, distinct canonical, canonical not self-aliased:",
      con.execute("SELECT count(*), count(DISTINCT team) FROM ref.team_aliases").fetchone(),
      con.execute("SELECT DISTINCT team FROM ref.team_aliases WHERE team NOT IN (SELECT alias FROM ref.team_aliases)").fetchall())
print("ref.teams abbrs not in aliases:", con.execute("SELECT team_abbr FROM ref.teams WHERE team_abbr NOT IN (SELECT alias FROM ref.team_aliases)").fetchall())

print("\n== team codes in other tables not in aliases ==")
for t, col in [("nfl.plays", "posteam"), ("nfl.plays", "home_team"), ("nfl.plays", "away_team"), ("nfl.team_week_stats", "team"), ("nfl.team_week_stats", "opponent_team"),
               ("nfl.player_week_stats", "team"), ("nfl.rosters_weekly", "team"), ("nfl.injury_reports", "team"), ("nfl.snap_counts", "team"),
               ("nfl.depth_charts_weekly", "club_code"), ("nfl.depth_chart_snapshots", "team"), ("nfl.pfr_pass_week", "team"), ("nfl.pfr_def_week", "team"),
               ("nfl.ngs_passing", "team_abbr"), ("nfl.espn_qbr_week", "team_abb"), ("nfl.ftn_charting", "nflverse_game_id")]:
    try:
        if col == "nflverse_game_id":
            continue
        r = con.execute(f"SELECT {col}, count(*) FROM {t} WHERE {col} IS NOT NULL AND {col} NOT IN (SELECT alias FROM ref.team_aliases) GROUP BY 1 ORDER BY 2 DESC LIMIT 12").fetchall()
        print(f"{t}.{col}: {r}")
    except Exception as e:  # noqa
        print(f"{t}.{col}: ERR {str(e)[:120]}")

print("\n== duplicate keys ==")
checks = {
    "nfl.games game_id": "SELECT count(*)-count(DISTINCT game_id) FROM nfl.games",
    "nfl.plays (game_id,play_id)": "SELECT count(*)-count(DISTINCT (game_id,play_id)) FROM nfl.plays",
    "nfl.team_week_stats (season,week,team)": "SELECT count(*)-count(DISTINCT (season,week,team)) FROM nfl.team_week_stats",
    "nfl.team_week_stats (season,week,team,season_type)": "SELECT count(*)-count(DISTINCT (season,week,team,season_type)) FROM nfl.team_week_stats",
    "nfl.player_week_stats (season,week,player_id,team)": "SELECT count(*)-count(DISTINCT (season,week,player_id,team)) FROM nfl.player_week_stats",
    "nfl.player_week_stats (season,week,player_id)": "SELECT count(*)-count(DISTINCT (season,week,player_id)) FROM nfl.player_week_stats",
    "nfl.rosters_weekly (season,week,team,gsis_id)": "SELECT count(*)-count(DISTINCT (season,week,team,gsis_id)) FROM nfl.rosters_weekly",
    "nfl.snap_counts (game_id,pfr_player_id)": "SELECT count(*)-count(DISTINCT (game_id,pfr_player_id)) FROM nfl.snap_counts",
    "nfl.pfr_pass_week (game_id,pfr_player_id)": "SELECT count(*)-count(DISTINCT (game_id,pfr_player_id)) FROM nfl.pfr_pass_week",
    "nfl.pfr_def_week (game_id,pfr_player_id)": "SELECT count(*)-count(DISTINCT (game_id,pfr_player_id)) FROM nfl.pfr_def_week",
    "nfl.ftn_charting (nflverse_game_id,nflverse_play_id)": "SELECT count(*)-count(DISTINCT (nflverse_game_id,nflverse_play_id)) FROM nfl.ftn_charting",
    "nfl.ngs_passing (season,week,player_gsis_id)": "SELECT count(*)-count(DISTINCT (season,week,player_gsis_id)) FROM nfl.ngs_passing",
    "nfl.ngs_passing (season,season_type,week,player_gsis_id)": "SELECT count(*)-count(DISTINCT (season,season_type,week,player_gsis_id)) FROM nfl.ngs_passing",
    "nfl.espn_qbr_week (season,week,player_id)": "SELECT count(*)-count(DISTINCT (season,week,player_id)) FROM nfl.espn_qbr_week",
    "nfl.espn_qbr_week (season,season_type,week,player_id)": "SELECT count(*)-count(DISTINCT (season,season_type,game_week,player_id)) FROM nfl.espn_qbr_week",
    "nfl.injury_reports (snapshot,season,week,team,gsis_id)": "SELECT count(*)-count(DISTINCT (snapshot_id,season,week,team,gsis_id)) FROM nfl.injury_reports",
    "nfl.injury_reports (season,week,team,gsis_id) across snapshots": "SELECT count(*)-count(DISTINCT (season,week,team,gsis_id)) FROM nfl.injury_reports",
    "nfl.depth_charts_weekly key_pre2025": "SELECT count(*)-count(DISTINCT (season,week,club_code,depth_team,position,gsis_id)) FROM nfl.depth_charts_weekly",
    "nfl.depth_chart_snapshots key_2025plus": "SELECT count(*)-count(DISTINCT (season,dt,team,pos_slot,pos_rank,gsis_id)) FROM nfl.depth_chart_snapshots",
    "ref.players gsis_id": "SELECT count(*)-count(DISTINCT gsis_id) FROM ref.players",
    "market.historical_lines (game_id,source,book_id,line_class)": "SELECT count(*)-count(DISTINCT (game_id,source,book_id,line_class)) FROM market.historical_lines",
}
for k, q in checks.items():
    try:
        print(f"{k}: {con.execute(q).fetchone()[0]}")
    except Exception as e:  # noqa
        print(f"{k}: ERR {str(e)[:150]}")

print("\n== games whose game_id is in plays but not in games / vice versa ==")
print("plays games not in nfl.games:", con.execute("SELECT count(DISTINCT game_id) FROM nfl.plays WHERE game_id NOT IN (SELECT game_id FROM nfl.games)").fetchone())
print("completed games 2010+ without plays:", con.execute("SELECT game_id FROM nfl.games WHERE season>=2010 AND result IS NOT NULL AND game_id NOT IN (SELECT DISTINCT game_id FROM nfl.plays) LIMIT 10").fetchall())

print("\n== quarantine list vs leakage register ==")
src = yaml.safe_load((ROOT / "config/sources.yaml").read_text())
q = set(src["nflverse"]["datasets"]["schedules"]["quarantine_columns"])
gcols = [r[0] for r in con.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='nfl' AND table_name='games' ORDER BY ordinal_position").fetchall()]
print("nfl.games columns:", gcols)
reg = (ROOT / "docs/LEAKAGE_REGISTER.md").read_text()
# fields named for nfl.games in L1-L4
named = set(re.findall(r"`nfl\.games\.([a-z_*/]+)`|`([a-z_*/]+)`", reg))
flat = set()
for a, b in named:
    flat.add(a or b)
print("register tokens:", sorted(flat))
leak_cols = set()
for c in gcols:
    for tok in flat:
        pat = "^" + tok.replace("*", ".*").replace("/", "|") + "$"
        if re.match(pat, c) or (tok == "over/under_odds" and c in ("over_odds", "under_odds")) or (tok == "*_moneyline" and c.endswith("_moneyline")):
            leak_cols.add(c)
print("nfl.games columns named in register:", sorted(leak_cols))
print("quarantine list:", sorted(q))
print("register-named columns NOT in quarantine:", sorted(leak_cols - q))
print("quarantine columns not in nfl.games:", sorted(q - set(gcols)))

print("\n== timezone handling: gameday/gametime types and sample ==")
print(con.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='nfl' AND table_name='games' AND column_name IN ('gameday','gametime','weekday','game_id','season','week') ORDER BY 1").fetchall())
print(con.execute("SELECT game_id, gameday, gametime, weekday, location FROM nfl.games WHERE season=2025 AND week=1 ORDER BY gameday, gametime LIMIT 5").fetchall())
print("international 2025:", con.execute("SELECT game_id, gameday, gametime, stadium FROM nfl.games WHERE season=2025 AND location='Neutral' LIMIT 6").fetchall())
print("null gametime:", con.execute("SELECT season, count(*) FROM nfl.games WHERE gametime IS NULL GROUP BY 1").fetchall())
print("gametime distinct formats:", con.execute("SELECT length(gametime), count(*) FROM nfl.games GROUP BY 1").fetchall())
print("plays start_time/time_of_day sample:", con.execute("SELECT game_id, game_date, start_time, time_of_day FROM nfl.plays WHERE season=2025 AND week=1 AND time_of_day IS NOT NULL LIMIT 3").fetchall())
print("any TIMESTAMPTZ columns in nfl.* tables:", con.execute("SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema='nfl' AND data_type LIKE 'TIMESTAMP%'").fetchall())
print("DuckDB TimeZone setting:", con.execute("SELECT current_setting('TimeZone')").fetchone())
print("injury observed_at raw UTC:", con.execute("SELECT CAST(observed_at AT TIME ZONE 'UTC' AS VARCHAR), CAST(observed_at AS VARCHAR) FROM nfl.injury_reports WHERE season=2026 LIMIT 1").fetchone())
print("historical_lines observed_at raw UTC:", con.execute("SELECT CAST(observed_at AT TIME ZONE 'UTC' AS VARCHAR) FROM market.historical_lines LIMIT 1").fetchone())
print("injury date_modified type/sample:", con.execute("SELECT data_type FROM information_schema.columns WHERE table_schema='nfl' AND table_name='injury_reports' AND column_name='date_modified'").fetchone(),
      con.execute("SELECT CAST(date_modified AS VARCHAR) FROM nfl.injury_reports WHERE season=2024 LIMIT 2").fetchall())
print("depth_chart_snapshots dt type/sample:", con.execute("SELECT data_type FROM information_schema.columns WHERE table_schema='nfl' AND table_name='depth_chart_snapshots' AND column_name='dt'").fetchone(),
      con.execute("SELECT CAST(dt AS VARCHAR) FROM nfl.depth_chart_snapshots WHERE season=2026 ORDER BY dt DESC LIMIT 2").fetchall())

print("\n== schema drift between seasons (per-season tables): columns all-null in some seasons ==")
for t in ["nfl.plays", "nfl.team_week_stats", "nfl.player_week_stats", "nfl.rosters_weekly", "nfl.snap_counts", "nfl.injury_reports", "nfl.depth_charts_weekly", "nfl.pfr_pass_week", "nfl.pfr_def_week", "nfl.ftn_charting"]:
    cols = [r[0] for r in con.execute(f"SELECT column_name FROM information_schema.columns WHERE table_schema='{t.split('.')[0]}' AND table_name='{t.split('.')[1]}'").fetchall()]
    exprs = ", ".join(f'sum(CASE WHEN "{c}" IS NULL THEN 1 ELSE 0 END) AS "{c}"' for c in cols)
    df = con.execute(f"SELECT season, count(*) n, {exprs} FROM {t} GROUP BY season ORDER BY season").pl()
    drift = {}
    for c in cols:
        allnull = [row["season"] for row in df.iter_rows(named=True) if row[c] == row["n"]]
        if allnull and len(allnull) < df.height:
            drift[c] = allnull
    print(f"{t}: {len(cols)} cols; columns entirely null in some seasons only: {len(drift)}")
    for c, s in sorted(drift.items())[:40]:
        print(f"   {c}: all-null in {s if len(s) < 8 else str(s[:4]) + '...' + str(s[-2:])}")
