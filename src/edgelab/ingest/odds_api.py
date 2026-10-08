"""The Odds API snapshotter (free tier plan; see config/sources.yaml → odds_api).

One call = one full snapshot of every upcoming NFL game at every bookmaker in the requested regions.
We store the raw JSON response as a snapshot (source=odds_api, dataset=odds_nfl) and provide a
normalizer that flattens it into one row per (event, book, market, outcome) with `observed_at`.

The free tier has no historical endpoint; missed snapshots can be backfilled later from a paid month
because the vendor records every 5 minutes regardless (P0-MKT-001).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import polars as pl

from edgelab.config import Settings, get_settings
from edgelab.ingest.snapshots import SnapshotMeta, SnapshotStore, utc_now_iso

log = logging.getLogger(__name__)

SOURCE = "odds_api"
DATASET = "odds_nfl"


class OddsApiError(RuntimeError):
    pass


def _http_date_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        return None


def fetch_odds_snapshot(
    *,
    label: str = "adhoc",
    settings: Settings | None = None,
    store: SnapshotStore | None = None,
    regions: list[str] | None = None,
    markets: list[str] | None = None,
) -> SnapshotMeta:
    settings = settings or get_settings()
    store = store or SnapshotStore(settings)
    cfg = settings.sources["odds_api"]
    key = settings.odds_api_key
    if not key:
        raise OddsApiError("ODDS_API_KEY is not set (put it in .env)")
    regions = regions or cfg["regions"]
    markets = markets or cfg["markets"]
    url = f"{cfg['base_url'].rstrip('/')}/sports/{cfg['sport_key']}/odds"
    params = {
        "regions": ",".join(regions),
        "markets": ",".join(markets),
        "oddsFormat": cfg.get("odds_format", "american"),
        "dateFormat": "iso",
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(url, params={**params, "apiKey": key})
    if resp.status_code != 200:
        raise OddsApiError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    observed_at = _http_date_to_iso(resp.headers.get("date")) or utc_now_iso()
    extra = {
        "label": label,
        "regions": regions,
        "markets": markets,
        "requests_remaining": resp.headers.get("x-requests-remaining"),
        "requests_used": resp.headers.get("x-requests-used"),
        "requests_last": resp.headers.get("x-requests-last"),
    }
    # Never store the key: the URL recorded is the key-less one.
    meta = store.put(
        source=SOURCE, dataset=DATASET, season=None, url=f"{url}?{httpx.QueryParams(params)}",
        data=resp.content, ext="json", retrieved_at=observed_at, extra=extra,
    )
    log.info("odds snapshot %s events=%s remaining=%s", meta.snapshot_id, meta.rows, extra["requests_remaining"])
    return meta


def normalize_odds_json(payload: list[dict[str, Any]], observed_at: str, snapshot_id: str) -> pl.DataFrame:
    """Flatten a /odds response into one row per (event, bookmaker, market, outcome).

    Columns: snapshot_id, observed_at, event_id, commence_time, home_name, away_name, book_key,
    book_last_update, market, market_last_update, outcome_name, outcome_point, outcome_price.
    `outcome_point` is the spread (from the named team's perspective) or the total; null for h2h.
    """
    rows: list[dict[str, Any]] = []
    for ev in payload:
        for bk in ev.get("bookmakers", []):
            for mk in bk.get("markets", []):
                for oc in mk.get("outcomes", []):
                    rows.append(
                        {
                            "snapshot_id": snapshot_id,
                            "observed_at": observed_at,
                            "event_id": ev["id"],
                            "commence_time": ev.get("commence_time"),
                            "home_name": ev.get("home_team"),
                            "away_name": ev.get("away_team"),
                            "book_key": bk.get("key"),
                            "book_last_update": bk.get("last_update"),
                            "market": mk.get("key"),
                            "market_last_update": mk.get("last_update"),
                            "outcome_name": oc.get("name"),
                            "outcome_point": oc.get("point"),
                            "outcome_price": oc.get("price"),
                        }
                    )
    if not rows:
        return pl.DataFrame(
            schema={
                "snapshot_id": pl.Utf8, "observed_at": pl.Utf8, "event_id": pl.Utf8, "commence_time": pl.Utf8,
                "home_name": pl.Utf8, "away_name": pl.Utf8, "book_key": pl.Utf8, "book_last_update": pl.Utf8,
                "market": pl.Utf8, "market_last_update": pl.Utf8, "outcome_name": pl.Utf8,
                "outcome_point": pl.Float64, "outcome_price": pl.Int64,
            }
        )
    return pl.DataFrame(rows).with_columns(
        pl.col("outcome_point").cast(pl.Float64), pl.col("outcome_price").cast(pl.Int64)
    )


def read_snapshot_json(store: SnapshotStore, meta: SnapshotMeta) -> list[dict[str, Any]]:
    data = (store.root / meta.path).read_bytes()
    return json.loads(data)
