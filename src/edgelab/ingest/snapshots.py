"""Immutable snapshot store.

Every upstream artifact is written once, byte-for-byte, under
    data/snapshots/<source>/<dataset>/<retrieved_at>_<sha8>.<ext>
with a sibling `.meta.json`, and indexed in `data/metadata/snapshots.jsonl` (committed to git).

If the newest existing snapshot of the same (source, dataset, season) has the same sha256, no new
file is written; an index row with `duplicate_of` is still appended so "we checked on this date" is
on record (this matters for daily injury / depth-chart checks).
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl

from edgelab import CODE_VERSION
from edgelab.config import Settings, get_settings

LOADER_VERSION = f"edgelab-ingest/{CODE_VERSION}"


@dataclass
class SnapshotMeta:
    snapshot_id: str
    source: str
    dataset: str
    season: int | None
    url: str
    retrieved_at: str  # ISO-8601 UTC
    last_modified: str | None  # upstream header, if any
    sha256: str
    bytes: int
    rows: int | None
    columns: int | None
    ext: str
    path: str  # relative to project root
    loader_version: str
    duplicate_of: str | None = None
    extra: dict[str, Any] | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _compact_ts(iso: str) -> str:
    return iso.replace("-", "").replace(":", "").replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _count_rows(data: bytes, ext: str) -> tuple[int | None, int | None]:
    try:
        if ext == "parquet":
            df = pl.read_parquet(io.BytesIO(data))
        elif ext in ("csv", "csv.gz"):
            df = pl.read_csv(io.BytesIO(data), infer_schema_length=10000, ignore_errors=True)
        elif ext == "json":
            obj = json.loads(data)
            return (len(obj) if isinstance(obj, list) else None), None
        else:
            return None, None
        return df.height, df.width
    except Exception:  # noqa: BLE001 - row count is informational
        return None, None


class SnapshotStore:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.root = self.settings.root
        self.dir = self.settings.snapshots_dir
        self.index_path = self.settings.metadata_dir / "snapshots.jsonl"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

    def _rel(self, path: Path) -> str:
        """Path relative to the project root when inside it (portable across machines), else absolute."""
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    # ---- index -------------------------------------------------------------------------------
    def index(self) -> pl.DataFrame:
        if not self.index_path.exists() or self.index_path.stat().st_size == 0:
            return pl.DataFrame()
        return pl.read_ndjson(self.index_path)

    def latest(self, source: str, dataset: str, season: int | None = None) -> SnapshotMeta | None:
        idx = self.index()
        if idx.is_empty():
            return None
        q = idx.filter((pl.col("source") == source) & (pl.col("dataset") == dataset))
        if season is None:
            q = q.filter(pl.col("season").is_null())
        else:
            q = q.filter(pl.col("season") == season)
        if q.is_empty():
            return None
        row = q.sort("retrieved_at").tail(1).to_dicts()[0]
        return SnapshotMeta(**{k: row.get(k) for k in SnapshotMeta.__dataclass_fields__})

    def _append_index(self, meta: SnapshotMeta) -> None:
        with self.index_path.open("a", encoding="utf-8") as fh:
            fh.write(meta.to_json() + "\n")

    # ---- write -------------------------------------------------------------------------------
    def put(
        self,
        *,
        source: str,
        dataset: str,
        season: int | None,
        url: str,
        data: bytes,
        ext: str,
        last_modified: str | None = None,
        retrieved_at: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> SnapshotMeta:
        retrieved_at = retrieved_at or utc_now_iso()
        digest = sha256_bytes(data)
        rows, cols = _count_rows(data, ext)
        prev = self.latest(source, dataset, season)
        season_tag = str(season) if season is not None else "all"
        snapshot_id = f"{source}.{dataset}.{season_tag}.{_compact_ts(retrieved_at)}.{digest[:8]}"

        if prev is not None and prev.sha256 == digest:
            prev_file = self.root / prev.path
            if not prev_file.exists():
                # Same bytes as the indexed snapshot but absent on this machine (index is shared via
                # git, the lake is per machine): materialize it at the recorded path.
                prev_file.parent.mkdir(parents=True, exist_ok=True)
                prev_file.write_bytes(data)
                meta_file = prev_file.with_name(prev_file.name + ".meta.json")
                if not meta_file.exists():
                    meta_file.write_text(prev.to_json() + "\n", encoding="utf-8")
            meta = SnapshotMeta(
                snapshot_id=snapshot_id, source=source, dataset=dataset, season=season, url=url,
                retrieved_at=retrieved_at, last_modified=last_modified, sha256=digest, bytes=len(data),
                rows=rows, columns=cols, ext=ext, path=prev.path, loader_version=LOADER_VERSION,
                duplicate_of=prev.snapshot_id, extra=extra,
            )
            self._append_index(meta)
            return meta

        subdir = self.dir / source / dataset
        subdir.mkdir(parents=True, exist_ok=True)
        fname = f"{_compact_ts(retrieved_at)}_{season_tag}_{digest[:8]}.{ext}"
        fpath = subdir / fname
        fpath.write_bytes(data)
        meta = SnapshotMeta(
            snapshot_id=snapshot_id, source=source, dataset=dataset, season=season, url=url,
            retrieved_at=retrieved_at, last_modified=last_modified, sha256=digest, bytes=len(data),
            rows=rows, columns=cols, ext=ext, path=self._rel(fpath),
            loader_version=LOADER_VERSION, duplicate_of=None, extra=extra,
        )
        (subdir / (fname + ".meta.json")).write_text(meta.to_json() + "\n", encoding="utf-8")
        self._append_index(meta)
        return meta

    # ---- read --------------------------------------------------------------------------------
    def read(self, meta: SnapshotMeta) -> pl.DataFrame:
        path = self.root / meta.path
        data = path.read_bytes()
        if sha256_bytes(data) != meta.sha256:
            raise ValueError(f"snapshot {meta.snapshot_id} failed hash verification: {path}")
        if meta.ext == "parquet":
            return pl.read_parquet(io.BytesIO(data))
        if meta.ext in ("csv", "csv.gz"):
            return pl.read_csv(io.BytesIO(data), infer_schema_length=10000, ignore_errors=True)
        raise ValueError(f"unsupported snapshot ext {meta.ext}")

    # Datasets whose snapshot files are committed to git and must therefore exist on every machine.
    TRACKED_DATASETS = ("injuries", "odds_nfl")

    def verify_all(self) -> list[str]:
        """Return a list of problems (empty = every locally present snapshot matches its sha256 and
        every git-tracked snapshot is present). Snapshots of rebuildable datasets that are absent on
        this machine are not problems (the index is shared across machines; the lake is per machine)."""
        problems: list[str] = []
        idx = self.index()
        if idx.is_empty():
            return problems
        seen: set[str] = set()
        for row in idx.filter(pl.col("duplicate_of").is_null()).to_dicts():
            if row["path"] in seen:
                continue
            seen.add(row["path"])
            p = self.root / row["path"]
            if not p.exists():
                if row["dataset"] in self.TRACKED_DATASETS:
                    problems.append(f"missing tracked file: {row['path']} ({row['snapshot_id']})")
                continue
            if sha256_bytes(p.read_bytes()) != row["sha256"]:
                problems.append(f"hash mismatch: {row['path']} ({row['snapshot_id']})")
        return problems

    def absent_locally(self) -> int:
        """Count of indexed snapshot files not present on this machine (informational)."""
        idx = self.index()
        if idx.is_empty():
            return 0
        paths = {r["path"] for r in idx.filter(pl.col("duplicate_of").is_null()).to_dicts()}
        return sum(1 for p in paths if not (self.root / p).exists())
