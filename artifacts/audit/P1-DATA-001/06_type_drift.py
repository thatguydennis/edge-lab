"""Compare raw parquet column types (every loaded snapshot) with the DuckDB column types.
Flags tz-aware timestamps stored as naive TIMESTAMP (values shifted by session TimeZone) and other lossy casts."""
import json
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from edgelab.db import connect

ROOT = Path("/home/claude/edge-lab")
con = connect(read_only=True)
idx = {r["snapshot_id"]: r for r in (json.loads(l) for l in (ROOT / "data/metadata/snapshots.jsonl").read_text().splitlines() if l.strip())}

loads = con.execute("SELECT table_name, season, snapshot_id FROM lab.load_runs ORDER BY loaded_at").fetchall()
db_types = {}
for (t,) in con.execute("SELECT DISTINCT table_name FROM lab.load_runs").fetchall():
    s, n = t.split(".")
    db_types[t] = dict(con.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema=? AND table_name=?", [s, n]).fetchall())

issues = defaultdict(set)
first_seen = {}
for t, season, sid in loads:
    r = idx[sid]
    sch = pq.read_schema(ROOT / r["path"])
    for f in sch:
        if f.name not in db_types[t]:
            if t == "nfl.plays":
                continue  # curated column list
            issues[("column dropped", t, f.name)].add(season)
            continue
        dbt = db_types[t][f.name]
        at = f.type
        if pa.types.is_timestamp(at):
            if at.tz is not None and dbt == "TIMESTAMP":
                issues[("TZ-AWARE -> NAIVE TIMESTAMP (values shifted by session TimeZone)", t, f.name)].add(season)
            elif at.tz is None and dbt.startswith("TIMESTAMP WITH"):
                issues[("naive -> TIMESTAMPTZ", t, f.name)].add(season)
        elif pa.types.is_integer(at) and dbt in ("VARCHAR", "DOUBLE"):
            issues[(f"int -> {dbt}", t, f.name)].add(season)
        elif pa.types.is_floating(at) and dbt in ("VARCHAR", "INTEGER", "BIGINT"):
            issues[(f"float -> {dbt}", t, f.name)].add(season)
        elif pa.types.is_string(at) and dbt not in ("VARCHAR",):
            issues[(f"string -> {dbt}", t, f.name)].add(season)
        elif pa.types.is_boolean(at) and dbt != "BOOLEAN":
            issues[(f"bool -> {dbt}", t, f.name)].add(season)
        elif (pa.types.is_list(at) or pa.types.is_struct(at)):
            issues[(f"list/struct -> {dbt} (stringified)", t, f.name)].add(season)
        elif pa.types.is_date(at) and dbt != "DATE":
            issues[(f"date -> {dbt}", t, f.name)].add(season)
        elif pa.types.is_null(at):
            issues[(f"null-typed column -> {dbt}", t, f.name)].add(season)

for k in sorted(issues):
    s = sorted(x for x in issues[k] if x is not None)
    print(f"{k[0]:70s} {k[1]:28s} {k[2]:30s} seasons={s if len(s) < 6 else f'{s[0]}..{s[-1]} ({len(s)})'}")

# confirm the shift numerically on injuries 2024
import polars as pl  # noqa: E402
r = [v for v in idx.values() if v["dataset"] == "injuries" and v["season"] == 2024 and not v["duplicate_of"]][0]
raw = pl.read_parquet(ROOT / r["path"]).select("gsis_id", "week", "team", "date_modified").head(5)
print("\nraw injuries 2024 (UTC):")
print(raw)
rows = con.execute("SELECT gsis_id, week, team, CAST(date_modified AS VARCHAR) FROM nfl.injury_reports WHERE season=2024 AND snapshot_id=? LIMIT 5", [r["snapshot_id"]]).fetchall()
print("stored:", rows)
# shift distribution: stored - raw
con.execute("SET TimeZone='UTC'") if False else None
rawdf = pl.read_parquet(ROOT / r["path"]).select("gsis_id", "week", "team", "date_modified").with_columns(pl.col("date_modified").dt.replace_time_zone(None).alias("raw_naive_utc"))
stored = con.execute("SELECT gsis_id, week, team, date_modified AS stored FROM nfl.injury_reports WHERE season=2024").pl()
j = rawdf.join(stored, on=["gsis_id", "week", "team"], how="inner").with_columns(((pl.col("stored") - pl.col("raw_naive_utc")).dt.total_minutes()).alias("shift_min"))
print("shift minutes distribution (stored - raw UTC):", j.group_by("shift_min").len().sort("shift_min"))
