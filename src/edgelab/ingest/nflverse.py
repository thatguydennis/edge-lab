"""Snapshot-first download of nflverse-data release assets and nfldata raw CSVs.

We deliberately do not call nflreadpy here: it caches in memory and returns frames, which would
hide the exact upstream bytes. We fetch the release asset itself, hash it, store it, and only then
read it. (nflreadpy remains available for exploration and as a cross-check.)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from typing import Any

import httpx

from edgelab.config import Settings, get_settings
from edgelab.ingest.snapshots import SnapshotMeta, SnapshotStore, utc_now_iso

log = logging.getLogger(__name__)

NFLVERSE_SOURCE = "nflverse"
NFLDATA_SOURCE = "nfldata"


def _client(settings: Settings) -> httpx.Client:
    ua = settings.sources["nflverse"].get("user_agent", "nfl-edge-lab/0.1")
    return httpx.Client(
        headers={"User-Agent": ua, "Accept": "*/*"},
        follow_redirects=True,
        timeout=httpx.Timeout(120.0, connect=30.0),
    )


def _get_with_retry(client: httpx.Client, url: str, retries: int = 3) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            resp = client.get(url)
            if resp.status_code == 404:
                return resp
            resp.raise_for_status()
            return resp
        except (httpx.HTTPError, httpx.TransportError) as exc:  # noqa: PERF203
            last = exc
            sleep = 2 ** attempt
            log.warning("GET %s failed (%s); retry in %ss", url, exc, sleep)
            time.sleep(sleep)
    assert last is not None
    raise last


def dataset_spec(settings: Settings, name: str) -> dict[str, Any]:
    datasets = settings.sources["nflverse"]["datasets"]
    if name not in datasets:
        raise KeyError(f"dataset {name!r} is not registered in config/sources.yaml")
    spec = dict(datasets[name])
    if spec.get("enabled", True) is False:
        raise ValueError(f"dataset {name!r} is disabled in config/sources.yaml ({spec.get('notes', '')})")
    return spec


def asset_url(settings: Settings, name: str, season: int | None) -> str:
    spec = dataset_spec(settings, name)
    base = settings.sources["nflverse"]["base_url"].rstrip("/")
    fname = spec["file"].format(season=season) if spec.get("per_season") else spec["file"]
    return f"{base}/{spec['tag']}/{fname}"


def fetch_nflverse(
    name: str,
    seasons: Iterable[int] | None = None,
    *,
    settings: Settings | None = None,
    store: SnapshotStore | None = None,
) -> list[SnapshotMeta]:
    """Download one dataset (all seasons given, or the single file) into the snapshot store."""
    settings = settings or get_settings()
    store = store or SnapshotStore(settings)
    spec = dataset_spec(settings, name)
    per_season = bool(spec.get("per_season"))
    targets: list[int | None] = list(seasons) if per_season else [None]
    if per_season and not targets:
        raise ValueError(f"{name} is per-season; pass seasons")

    out: list[SnapshotMeta] = []
    with _client(settings) as client:
        for season in targets:
            url = asset_url(settings, name, season)
            resp = _get_with_retry(client, url)
            if resp.status_code == 404:
                log.warning("not available upstream: %s", url)
                continue
            retrieved_at = utc_now_iso()
            ext = "parquet" if url.endswith(".parquet") else ("csv.gz" if url.endswith(".csv.gz") else "csv")
            meta = store.put(
                source=NFLVERSE_SOURCE,
                dataset=name,
                season=season,
                url=url,
                data=resp.content,
                ext=ext,
                last_modified=resp.headers.get("last-modified"),
                retrieved_at=retrieved_at,
                extra={"etag": resp.headers.get("etag"), "content_length": resp.headers.get("content-length")},
            )
            log.info(
                "%s %s season=%s rows=%s %s",
                "UNCHANGED" if meta.duplicate_of else "SNAPSHOT",
                name, season, meta.rows, meta.snapshot_id,
            )
            out.append(meta)
            if name == "schedules" and not meta.duplicate_of:
                out.append(derive_schedule_lines(meta, store))
    return out


LINE_COLUMNS = [
    "game_id", "season", "week", "gameday", "gametime", "home_team", "away_team",
    "spread_line", "home_spread_odds", "away_spread_odds", "total_line", "over_odds", "under_odds",
    "home_moneyline", "away_moneyline", "home_qb_name", "away_qb_name",
]


def derive_schedule_lines(sched: SnapshotMeta, store: SnapshotStore) -> SnapshotMeta:
    """Compact, git-tracked extract of the live line values for games not yet played at retrieval time.

    The full schedules snapshot is rebuildable except for these values, which upstream overwrites
    continuously (audit P1-DATA-001 M3). ~30 rows per snapshot.
    """
    import io

    import polars as pl

    df = store.read(sched)
    today = sched.retrieved_at[:10]
    live = df.filter(
        (pl.col("spread_line").is_not_null() | pl.col("home_moneyline").is_not_null())
        & (pl.col("gameday") >= today)
    ).select([c for c in LINE_COLUMNS if c in df.columns])
    buf = io.BytesIO()
    live.write_parquet(buf)
    return store.put(
        source=NFLVERSE_SOURCE, dataset="schedule_lines", season=None, url=sched.url + "#lines",
        data=buf.getvalue(), ext="parquet", last_modified=sched.last_modified, retrieved_at=sched.retrieved_at,
        extra={"derived_from": sched.snapshot_id},
    )


def fetch_nfldata_csv(name: str, *, settings: Settings | None = None, store: SnapshotStore | None = None) -> SnapshotMeta:
    """Raw CSVs from the nfldata repo (closing_lines, initial_lines, ...)."""
    settings = settings or get_settings()
    store = store or SnapshotStore(settings)
    cfg = settings.sources["nfldata_raw"]
    spec = cfg["datasets"][name]
    url = f"{cfg['base_url'].rstrip('/')}/{spec['file']}"
    with _client(settings) as client:
        resp = _get_with_retry(client, url)
        resp.raise_for_status()
        return store.put(
            source=NFLDATA_SOURCE,
            dataset=name,
            season=None,
            url=url,
            data=resp.content,
            ext="csv",
            last_modified=resp.headers.get("last-modified"),
            extra={"line_class": spec.get("line_class"), "book": spec.get("book"), "seasons": spec.get("seasons")},
        )


def parse_seasons(expr: str) -> list[int]:
    """'2010-2026' -> [2010..2026]; '2024,2026' -> [2024, 2026]; '2026' -> [2026]."""
    out: list[int] = []
    for part in expr.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return sorted(set(out))
