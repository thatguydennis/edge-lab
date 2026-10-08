"""Test the spread sign convention and result consistency on completed games. Read-only."""
from edgelab.db import connect

con = connect(read_only=True)

print("== result == home_score - away_score (2010-2026 completed) ==")
print(con.execute("""SELECT count(*) n,
    sum(CASE WHEN result = home_score - away_score THEN 1 ELSE 0 END) ok,
    sum(CASE WHEN result <> home_score - away_score THEN 1 ELSE 0 END) bad,
    sum(CASE WHEN total <> home_score + away_score THEN 1 ELSE 0 END) bad_total
  FROM nfl.games WHERE season BETWEEN 2010 AND 2026 AND home_score IS NOT NULL AND away_score IS NOT NULL""").fetchall())

print("\n== nfl.games.spread_line: does positive spread_line mean home favored? ==")
# If spread_line = expected home margin, then games with spread_line > 0 should have result > 0 more often than not,
# and corr(spread_line, result) should be strongly positive.
print(con.execute("""SELECT
    count(*) n,
    corr(spread_line, result) corr_spread_result,
    avg(CASE WHEN spread_line > 0 AND result > 0 THEN 1.0 WHEN spread_line > 0 THEN 0.0 END) p_home_wins_when_home_fav,
    avg(CASE WHEN spread_line < 0 AND result < 0 THEN 1.0 WHEN spread_line < 0 THEN 0.0 END) p_away_wins_when_away_fav,
    avg(CASE WHEN spread_line > 0 THEN 1.0 ELSE 0.0 END) share_home_fav,
    avg(spread_line) mean_spread_line, avg(result) mean_result
  FROM nfl.games WHERE season BETWEEN 2010 AND 2026 AND result IS NOT NULL AND spread_line IS NOT NULL""").pl())

print("\n== moneyline agrees with spread sign? (home favored by spread -> home_moneyline < 0) ==")
print(con.execute("""SELECT
    sum(CASE WHEN spread_line > 0 AND home_moneyline < 0 THEN 1 ELSE 0 END) agree_home_fav,
    sum(CASE WHEN spread_line > 0 AND home_moneyline > 0 THEN 1 ELSE 0 END) disagree_home_fav,
    sum(CASE WHEN spread_line < 0 AND home_moneyline > 0 THEN 1 ELSE 0 END) agree_away_fav,
    sum(CASE WHEN spread_line < 0 AND home_moneyline < 0 THEN 1 ELSE 0 END) disagree_away_fav
  FROM nfl.games WHERE season BETWEEN 2010 AND 2026 AND spread_line IS NOT NULL AND home_moneyline IS NOT NULL AND abs(spread_line) >= 3""").pl())

print("\n== market.historical_lines.spread_home = -spread_line; home covers if result + spread_home > 0 ==")
print(con.execute("""SELECT count(*) n,
    sum(CASE WHEN h.spread_home = -g.spread_line THEN 1 ELSE 0 END) sign_ok,
    sum(CASE WHEN h.spread_home + g.spread_line <> 0 THEN 1 ELSE 0 END) sign_bad,
    avg(CASE WHEN g.result + h.spread_home > 0 THEN 1.0 WHEN g.result + h.spread_home < 0 THEN 0.0 END) home_cover_rate,
    avg(CASE WHEN g.result + h.spread_home = 0 THEN 1.0 ELSE 0.0 END) push_rate,
    avg(CASE WHEN h.spread_home < 0 AND g.result > 0 THEN 1.0 WHEN h.spread_home < 0 THEN 0.0 END) fav_home_win_rate,
    avg(CASE WHEN h.spread_home > 0 AND g.result < 0 THEN 1.0 WHEN h.spread_home > 0 THEN 0.0 END) fav_away_win_rate,
    sum(CASE WHEN h.ml_home <> g.home_moneyline OR h.ml_away <> g.away_moneyline OR h.total <> g.total_line THEN 1 ELSE 0 END) other_cols_bad,
    sum(CASE WHEN h.spread_home_odds <> g.home_spread_odds OR h.spread_away_odds <> g.away_spread_odds THEN 1 ELSE 0 END) odds_bad
  FROM market.historical_lines h JOIN nfl.games g USING (game_id)
  WHERE g.season BETWEEN 2010 AND 2026 AND g.result IS NOT NULL""").pl())

print("\n== by season: favorite (by spread_home) straight-up win rate; should be ~65-70% every season ==")
print(con.execute("""SELECT g.season, count(*) n,
    round(avg(CASE WHEN h.spread_home < 0 AND g.result > 0 THEN 1.0 WHEN h.spread_home > 0 AND g.result < 0 THEN 1.0 WHEN h.spread_home = 0 THEN NULL ELSE 0.0 END),3) fav_su_rate,
    round(corr(h.spread_home, g.result),3) corr_sh_result,
    round(avg(CASE WHEN g.result + h.spread_home > 0 THEN 1.0 WHEN g.result + h.spread_home < 0 THEN 0.0 END),3) home_cover
  FROM market.historical_lines h JOIN nfl.games g USING (game_id)
  WHERE g.result IS NOT NULL AND g.season >= 2010 GROUP BY 1 ORDER BY 1""").pl())

print("\n== spot check a few famous games ==")
for gid in ["2010_01_MIN_NO", "2015_01_PIT_NE", "2019_21_KC_SF", "2024_01_BAL_KC", "2025_01_DAL_PHI"]:
    print(con.execute("SELECT game_id, home_team, away_team, spread_line, home_moneyline, away_moneyline, result, home_score, away_score FROM nfl.games WHERE game_id=?", [gid]).fetchall())

print("\n== pbp spread_line vs schedule spread_line consistency ==")
print(con.execute("""SELECT count(*) n, sum(CASE WHEN p.sl <> g.spread_line THEN 1 ELSE 0 END) diff, sum(CASE WHEN p.r <> g.result THEN 1 ELSE 0 END) diff_result
  FROM (SELECT game_id, max(spread_line) sl, max(result) r FROM nfl.plays GROUP BY 1) p JOIN nfl.games g USING (game_id)""").fetchall())
