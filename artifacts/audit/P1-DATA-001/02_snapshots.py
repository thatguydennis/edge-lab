"""Hash-check snapshot files against .meta.json and the index. Read-only."""
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path("/home/claude/edge-lab")
idx = [json.loads(l) for l in (ROOT / "data/metadata/snapshots.jsonl").read_text().splitlines() if l.strip()]
print("index rows:", len(idx))
print("unique snapshot_id:", len({r["snapshot_id"] for r in idx}))
print("duplicate_of rows:", sum(1 for r in idx if r.get("duplicate_of")))
print("datasets:", Counter((r["source"], r["dataset"]) for r in idx))

# required meta fields
missing = Counter()
for r in idx:
    for k in ("url", "retrieved_at", "loader_version", "sha256", "path", "bytes"):
        if not r.get(k):
            missing[k] += 1
    if not r.get("last_modified"):
        missing["last_modified"] += 1
    if not (r.get("retrieved_at") or "").endswith("+00:00"):
        missing["retrieved_at_not_utc"] += 1
print("missing fields:", dict(missing))
print("retrieved_at range:", min(r["retrieved_at"] for r in idx), max(r["retrieved_at"] for r in idx))

# every non-duplicate row: file exists? sha matches? meta.json matches index?
primary = [r for r in idx if not r.get("duplicate_of")]
print("primary snapshots:", len(primary), "unique paths:", len({r["path"] for r in primary}))
absent, mismatch, meta_missing, meta_diff = [], [], [], []
full_checked = 0
for r in primary:
    p = ROOT / r["path"]
    if not p.exists():
        absent.append(r["snapshot_id"]); continue
    m = Path(str(p) + ".meta.json")
    if not m.exists():
        meta_missing.append(r["snapshot_id"]); continue
    meta = json.loads(m.read_text())
    for k in ("snapshot_id", "sha256", "url", "retrieved_at", "bytes", "path", "loader_version"):
        if meta.get(k) != r.get(k):
            meta_diff.append((r["snapshot_id"], k, meta.get(k), r.get(k)))
    if p.stat().st_size != r["bytes"]:
        mismatch.append((r["snapshot_id"], "bytes", p.stat().st_size, r["bytes"]))
print("absent files:", len(absent), absent[:5])
print("meta.json missing:", len(meta_missing))
print("meta/index field diffs:", len(meta_diff), meta_diff[:5])
print("byte-size mismatches:", mismatch[:5])

# hash ALL primary snapshot files (356 MB, cheap enough)
bad = []
for r in primary:
    p = ROOT / r["path"]
    if not p.exists():
        continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    full_checked += 1
    if h != r["sha256"]:
        bad.append((r["snapshot_id"], h, r["sha256"]))
print(f"hashed {full_checked} files; mismatches: {len(bad)}", bad[:5])

# explicit random sample of 12, printed for the record
random.seed(20261008)
sample = random.sample(primary, 12)
for r in sample:
    p = ROOT / r["path"]
    h = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    meta = json.loads(Path(str(p) + ".meta.json").read_text()) if p.exists() else {}
    print(f"{r['snapshot_id']:60s} file={'ok' if h == r['sha256'] else 'BAD'} meta={'ok' if meta.get('sha256') == r['sha256'] else 'BAD'} lm={r.get('last_modified')}")

# duplicate_of rows: does the referenced snapshot exist and have the same sha?
by_id = {r["snapshot_id"]: r for r in idx}
dupbad = [r["snapshot_id"] for r in idx if r.get("duplicate_of") and (r["duplicate_of"] not in by_id or by_id[r["duplicate_of"]]["sha256"] != r["sha256"])]
print("duplicate_of rows pointing at missing/different sha:", dupbad)

# any snapshot_id used in the DB but not in the index?
from edgelab.db import connect  # noqa: E402
con = connect(read_only=True)
ids = set()
for t in ["nfl.games","nfl.plays","nfl.injury_reports","nfl.team_week_stats","nfl.player_week_stats","nfl.rosters_weekly",
          "nfl.snap_counts","nfl.pfr_pass_week","nfl.pfr_def_week","nfl.ftn_charting","nfl.ngs_passing","nfl.espn_qbr_week",
          "nfl.depth_charts_weekly","nfl.depth_chart_snapshots","ref.players","ref.teams","market.historical_lines"]:
    for (s,) in con.execute(f"SELECT DISTINCT snapshot_id FROM {t}").fetchall():
        ids.add(s)
print("distinct snapshot_ids in DB:", len(ids), "not in index:", [s for s in ids if s not in by_id])
print("DB snapshot ids that are duplicate_of rows (should be none):", [s for s in ids if by_id.get(s, {}).get("duplicate_of")])
# is every loaded snapshot the LATEST for its (dataset, season)?
latest = {}
for r in sorted(idx, key=lambda r: r["retrieved_at"]):
    latest[(r["source"], r["dataset"], r["season"])] = r
stale = [s for s in ids if by_id[s] is not latest[(by_id[s]["source"], by_id[s]["dataset"], by_id[s]["season"])] and not latest[(by_id[s]["source"], by_id[s]["dataset"], by_id[s]["season"])].get("duplicate_of")]
print("loaded snapshots that are not the latest primary for their key:", stale)
# which (dataset, season) in index have no rows in DB?
loaded_keys = {(by_id[s]["dataset"], by_id[s]["season"]) for s in ids}
print("indexed primary keys not loaded:", sorted({(r["dataset"], r["season"]) for r in primary} - loaded_keys))
