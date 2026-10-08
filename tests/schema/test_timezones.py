from datetime import datetime, timezone

import polars as pl

from edgelab.db import connect
from edgelab.db.load import _ensure_table, _insert


def test_tz_aware_column_roundtrips_in_utc_via_alter_path(tmp_settings):
    con = connect(tmp_settings)
    base = pl.DataFrame({"season": [2024], "a": [1]})
    _ensure_table(con, "nfl.tz", base)
    _insert(con, "nfl.tz", base)
    ts = datetime(2024, 9, 6, 19, 5, 30, tzinfo=timezone.utc)
    df = pl.DataFrame({"season": [2024], "a": [2], "date_modified": [ts]}).with_columns(
        pl.col("date_modified").dt.replace_time_zone("UTC")
    )
    _ensure_table(con, "nfl.tz", df)  # ALTER path: this is where the bug lived
    _insert(con, "nfl.tz", df)
    dtype = con.execute("SELECT data_type FROM information_schema.columns WHERE table_name='tz' AND column_name='date_modified'").fetchone()[0]
    assert dtype == "TIMESTAMP WITH TIME ZONE"
    got = con.execute("SELECT epoch(date_modified) FROM nfl.tz WHERE a=2").fetchone()[0]
    assert int(got) == int(ts.timestamp())
    con.close()


def test_kickoff_utc_derivation():
    from edgelab.db.load import _prepare
    from edgelab.ingest.snapshots import SnapshotMeta
    meta = SnapshotMeta("id", "nflverse", "schedules", None, "u", "2026-10-08T00:00:00+00:00", None, "x", 1, 1, 1, "parquet", "p", "v")
    df = pl.DataFrame({
        "game_id": ["2026_05_PHI_JAX", "2026_05_BUF_LA", "2026_01_X_Y"],
        "gameday": ["2026-10-11", "2026-10-12", "2026-09-10"],
        "gametime": ["09:30", "20:15", None],
    })
    out = _prepare(df, meta, "schedules")
    k = out["kickoff_utc"].to_list()
    assert k[0].astimezone(timezone.utc).hour == 13   # 09:30 ET (EDT) -> 13:30 UTC
    assert k[1].astimezone(timezone.utc).hour == 0 and k[1].astimezone(timezone.utc).day == 13  # 20:15 ET -> 00:15 UTC next day
    assert k[2] is None
