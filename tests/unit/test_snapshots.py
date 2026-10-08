import polars as pl

from edgelab.ingest.snapshots import SnapshotStore


def _parquet_bytes(df: pl.DataFrame) -> bytes:
    import io
    buf = io.BytesIO()
    df.write_parquet(buf)
    return buf.getvalue()


def test_put_read_dedup_and_verify(tmp_settings):
    store = SnapshotStore(tmp_settings)
    data = _parquet_bytes(pl.DataFrame({"a": [1, 2, 3]}))
    m1 = store.put(source="t", dataset="d", season=2026, url="u", data=data, ext="parquet", retrieved_at="2026-10-08T00:00:00+00:00")
    assert m1.rows == 3 and m1.duplicate_of is None
    assert (tmp_settings.root / m1.path).exists()
    m2 = store.put(source="t", dataset="d", season=2026, url="u", data=data, ext="parquet", retrieved_at="2026-10-09T00:00:00+00:00")
    assert m2.duplicate_of == m1.snapshot_id and m2.path == m1.path
    assert store.index().height == 2
    assert store.latest("t", "d", 2026).snapshot_id == m2.snapshot_id
    df = store.read(m1)
    assert df["a"].to_list() == [1, 2, 3]
    assert store.verify_all() == []
    # tamper -> verification fails
    (tmp_settings.root / m1.path).write_bytes(b"corrupt")
    assert store.verify_all()


def test_changed_content_makes_new_file(tmp_settings):
    store = SnapshotStore(tmp_settings)
    m1 = store.put(source="t", dataset="d", season=None, url="u", data=_parquet_bytes(pl.DataFrame({"a": [1]})), ext="parquet")
    m2 = store.put(source="t", dataset="d", season=None, url="u", data=_parquet_bytes(pl.DataFrame({"a": [2]})), ext="parquet")
    assert m1.path != m2.path and m2.duplicate_of is None
