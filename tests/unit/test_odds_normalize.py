from edgelab.ingest.odds_api import normalize_odds_json

SAMPLE = [{
    "id": "abc", "sport_key": "americanfootball_nfl", "commence_time": "2026-10-11T17:00:00Z",
    "home_team": "Green Bay Packers", "away_team": "Chicago Bears",
    "bookmakers": [{
        "key": "draftkings", "title": "DraftKings", "last_update": "2026-10-08T12:00:00Z",
        "markets": [
            {"key": "h2h", "last_update": "2026-10-08T12:00:00Z", "outcomes": [
                {"name": "Green Bay Packers", "price": 114}, {"name": "Chicago Bears", "price": -135}]},
            {"key": "spreads", "last_update": "2026-10-08T12:00:00Z", "outcomes": [
                {"name": "Green Bay Packers", "price": -110, "point": 2.5}, {"name": "Chicago Bears", "price": -110, "point": -2.5}]},
            {"key": "totals", "last_update": "2026-10-08T12:00:00Z", "outcomes": [
                {"name": "Over", "price": -110, "point": 45.5}, {"name": "Under", "price": -110, "point": 45.5}]},
        ],
    }],
}]


def test_normalize_rows_and_points():
    df = normalize_odds_json(SAMPLE, "2026-10-08T12:00:05+00:00", "snap1")
    assert df.height == 6
    spreads = df.filter(df["market"] == "spreads")
    assert set(spreads["outcome_point"].to_list()) == {2.5, -2.5}
    assert df.filter(df["market"] == "h2h")["outcome_point"].is_null().all()
    assert (df["snapshot_id"] == "snap1").all()


def test_normalize_empty():
    assert normalize_odds_json([], "2026-10-08T12:00:05+00:00", "s").height == 0
