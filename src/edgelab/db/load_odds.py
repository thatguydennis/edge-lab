"""Load The Odds API snapshots into market.odds_snapshots, resolving teams, books and game_id."""

from __future__ import annotations

import logging
from datetime import timedelta

import duckdb
import polars as pl

from edgelab.ingest.odds_api import DATASET, SOURCE, normalize_odds_json, read_snapshot_json
from edgelab.ingest.snapshots import SnapshotMeta, SnapshotStore

log = logging.getLogger(__name__)

# Full names as The Odds API spells them → canonical code. Supplemented at runtime by ref.teams.team_name.
NAME_OVERRIDES = {
    "Washington Commanders": "WAS", "Washington Football Team": "WAS", "Washington Redskins": "WAS",
    "Los Angeles Rams": "LA", "St. Louis Rams": "LA",
    "Los Angeles Chargers": "LAC", "San Diego Chargers": "LAC",
    "Las Vegas Raiders": "LV", "Oakland Raiders": "LV",
}


def _team_name_map(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    m: dict[str, str] = dict(NAME_OVERRIDES)
    try:
        for name, abbr in con.execute("SELECT team_name, team_abbr FROM ref.teams").fetchall():
            if name and abbr:
                m.setdefault(name, abbr)
        # nickname fallback (e.g. a 2026 rebrand that keeps the nickname)
        for name, abbr in con.execute("SELECT team_nick, team_abbr FROM ref.teams").fetchall():
            if name and abbr:
                m.setdefault(name, abbr)
    except duckdb.Error:
        pass
    # map legacy abbreviations to canonical via aliases
    alias = dict(con.execute("SELECT alias, team FROM ref.team_aliases").fetchall())
    return {k: alias.get(v, v) for k, v in m.items()}


def _book_map(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    return {k: b for b, k in con.execute("SELECT book_id, odds_api_key FROM ref.books WHERE odds_api_key IS NOT NULL").fetchall()}


def _resolve_game_ids(con: duckdb.DuckDBPyConnection, df: pl.DataFrame) -> pl.DataFrame:
    """Match (home_team, away_team, kickoff date ±1 day) to nfl.games.game_id."""
    games = con.execute(
        "SELECT game_id, home_team, away_team, CAST(gameday AS DATE) AS gameday FROM nfl.games WHERE gameday IS NOT NULL"
    ).pl()
    if games.is_empty():
        return df.with_columns(pl.lit(None, dtype=pl.Utf8).alias("game_id"))
    ev = (
        df.select(["event_id", "home_team", "away_team", "commence_time"]).unique()
        .with_columns(pl.col("commence_time").str.to_datetime(time_zone="UTC").dt.convert_time_zone("America/New_York").dt.date().alias("kick_date"))
    )
    joined = ev.join(games, on=["home_team", "away_team"], how="left").with_columns(
        (pl.col("gameday") - pl.col("kick_date")).dt.total_days().abs().alias("dd")
    ).filter(pl.col("dd") <= 1).sort("dd").unique(subset=["event_id"], keep="first").select(["event_id", "game_id"])
    return df.join(joined, on="event_id", how="left")


def load_odds_snapshots(con: duckdb.DuckDBPyConnection, store: SnapshotStore) -> int:
    idx = store.index()
    if idx.is_empty():
        return 0
    q = idx.filter((pl.col("source") == SOURCE) & (pl.col("dataset") == DATASET) & pl.col("duplicate_of").is_null())
    loaded = {r[0] for r in con.execute("SELECT DISTINCT snapshot_id FROM market.odds_snapshots").fetchall()}
    names = _team_name_map(con)
    books = _book_map(con)
    total = 0
    for row in q.sort("retrieved_at").to_dicts():
        meta = SnapshotMeta(**{k: row.get(k) for k in SnapshotMeta.__dataclass_fields__})
        if meta.snapshot_id in loaded:
            continue
        payload = read_snapshot_json(store, meta)
        df = normalize_odds_json(payload, meta.retrieved_at, meta.snapshot_id)
        if df.is_empty():
            continue
        df = df.with_columns(
            pl.col("home_name").replace_strict(names, default=None).alias("home_team"),
            pl.col("away_name").replace_strict(names, default=None).alias("away_team"),
            pl.col("book_key").replace_strict(books, default=None).alias("book_id"),
        )
        df = df.with_columns(
            pl.when(pl.col("market") == "totals")
            .then(pl.col("outcome_name").str.to_lowercase())
            .when(pl.col("outcome_name") == pl.col("home_name")).then(pl.lit("home"))
            .when(pl.col("outcome_name") == pl.col("away_name")).then(pl.lit("away"))
            .otherwise(pl.lit(None))
            .alias("outcome_side")
        )
        df = _resolve_game_ids(con, df)
        df = df.with_columns(
            pl.col("observed_at").str.to_datetime(time_zone="UTC"),
            pl.col("commence_time").str.to_datetime(time_zone="UTC"),
            pl.col("book_last_update").str.to_datetime(time_zone="UTC", strict=False),
            pl.col("market_last_update").str.to_datetime(time_zone="UTC", strict=False),
            pl.lit("snapshot").alias("line_class"),
        )
        cols = ["snapshot_id", "observed_at", "event_id", "commence_time", "game_id", "home_team", "away_team",
                "home_name", "away_name", "book_id", "book_key", "book_last_update", "market", "market_last_update",
                "outcome_name", "outcome_side", "outcome_point", "outcome_price", "line_class"]
        con.register("_odds", df.select(cols).to_arrow())
        con.execute(f"INSERT INTO market.odds_snapshots ({', '.join(cols)}) SELECT {', '.join(cols)} FROM _odds")
        con.unregister("_odds")
        unmapped = df.filter(pl.col("home_team").is_null() | pl.col("away_team").is_null()).select(["home_name", "away_name"]).unique()
        if not unmapped.is_empty():
            log.warning("unmapped team names in %s: %s", meta.snapshot_id, unmapped.to_dicts())
        total += df.height
        log.info("loaded odds snapshot %s rows=%s", meta.snapshot_id, df.height)
    return total


def timedelta_days(n: int) -> timedelta:  # small helper kept for tests
    return timedelta(days=n)
