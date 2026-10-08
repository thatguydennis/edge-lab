import io

import polars as pl

from edgelab.ingest.nflverse import derive_schedule_lines
from edgelab.ingest.snapshots import SnapshotStore


def _pq(df):
    b = io.BytesIO()
    df.write_parquet(b)
    return b.getvalue()


def test_live_extract_uses_kickoff_not_calendar_date(tmp_settings):
    store = SnapshotStore(tmp_settings)
    df = pl.DataFrame({
        "game_id": ["early", "late", "nokick"],
        "season": [2026] * 3, "week": [5] * 3,
        "gameday": ["2026-10-11"] * 3, "gametime": ["13:00", "20:20", None],
        "home_team": ["A", "B", "C"], "away_team": ["X", "Y", "Z"],
        "spread_line": [3.0, -2.5, 1.0], "home_moneyline": [-150, 120, -105], "away_moneyline": [130, -140, -115],
    })
    # retrieval Sunday 18:00 UTC = 14:00 ET: the 13:00 ET game has kicked off, the 20:20 ET game has not
    sched = store.put(source="nflverse", dataset="schedules", season=None, url="u", data=_pq(df), ext="parquet",
                      retrieved_at="2026-10-11T18:00:00+00:00")
    m = derive_schedule_lines(sched, store)
    out = store.read(m)
    assert out["game_id"].to_list() == ["late"]
