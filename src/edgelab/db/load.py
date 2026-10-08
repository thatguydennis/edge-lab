"""Load snapshots into DuckDB. Every row gets `snapshot_id`; loads are recorded in lab.load_runs.

Strategies
- replace_season: per-season datasets (pbp, stats, rosters, ...) — delete that season, insert from the
  latest snapshot of that season.
- replace_all: single-file datasets (schedules, players, ngs, qbr) — rebuild from the latest snapshot.
- append_snapshot: datasets we snapshot daily to recover timestamps (injuries) — every snapshot's rows
  are appended with observed_at = retrieval time; a snapshot is loaded at most once.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone

import duckdb
import polars as pl

from edgelab import CODE_VERSION
from edgelab.config import Settings, get_settings
from edgelab.ingest.snapshots import SnapshotMeta, SnapshotStore

log = logging.getLogger(__name__)

# dataset name (config/sources.yaml) -> (table, strategy)
TABLE_MAP: dict[str, tuple[str, str]] = {
    "schedules": ("nfl.games", "replace_all"),
    "pbp": ("nfl.plays", "replace_season"),
    "stats_team_week": ("nfl.team_week_stats", "replace_season"),
    "stats_player_week": ("nfl.player_week_stats", "replace_season"),
    "injuries": ("nfl.injury_reports", "append_snapshot"),
    "depth_charts": ("nfl.depth_charts", "replace_season"),  # split by format at load time
    "rosters_weekly": ("nfl.rosters_weekly", "replace_season"),
    "players": ("ref.players", "replace_all"),
    "snap_counts": ("nfl.snap_counts", "replace_season"),
    "pfr_advstats_week_pass": ("nfl.pfr_pass_week", "replace_season"),
    "pfr_advstats_week_def": ("nfl.pfr_def_week", "replace_season"),
    "ftn_charting": ("nfl.ftn_charting", "replace_season"),
    "ngs_passing": ("nfl.ngs_passing", "replace_all"),
    "espn_qbr_week": ("nfl.espn_qbr_week", "replace_all"),
    "participation": ("nfl.participation", "replace_season"),
    "teams": ("ref.teams", "replace_all"),
}

# Curated play-by-play columns (the full 372-column file stays in the snapshot lake).
PBP_COLUMNS = [
    "play_id", "game_id", "old_game_id", "home_team", "away_team", "season_type", "week", "season",
    "posteam", "posteam_type", "defteam", "side_of_field", "yardline_100", "game_date",
    "quarter_seconds_remaining", "half_seconds_remaining", "game_seconds_remaining", "game_half",
    "qtr", "down", "goal_to_go", "ydstogo", "ydsnet", "desc", "play_type", "yards_gained", "shotgun",
    "no_huddle", "qb_dropback", "qb_kneel", "qb_spike", "qb_scramble", "pass_length", "pass_location",
    "air_yards", "yards_after_catch", "run_location", "run_gap", "field_goal_result", "kick_distance",
    "extra_point_result", "two_point_conv_result", "home_timeouts_remaining", "away_timeouts_remaining",
    "timeout", "timeout_team", "td_team", "posteam_score", "defteam_score", "score_differential",
    "posteam_score_post", "defteam_score_post", "score_differential_post", "ep", "epa", "total_home_epa",
    "total_away_epa", "air_epa", "yac_epa", "comp_air_epa", "comp_yac_epa", "qb_epa", "xyac_epa", "wp",
    "def_wp", "home_wp", "away_wp", "wpa", "vegas_wpa", "vegas_home_wpa", "vegas_wp", "vegas_home_wp",
    "punt_blocked", "first_down_rush", "first_down_pass", "first_down_penalty", "third_down_converted",
    "third_down_failed", "fourth_down_converted", "fourth_down_failed", "incomplete_pass", "touchback",
    "interception", "punt_inside_twenty", "fumble_forced", "fumble_not_forced", "fumble_out_of_bounds",
    "solo_tackle", "safety", "penalty", "tackled_for_loss", "fumble_lost", "qb_hit", "rush_attempt",
    "pass_attempt", "sack", "touchdown", "pass_touchdown", "rush_touchdown", "return_touchdown",
    "extra_point_attempt", "two_point_attempt", "field_goal_attempt", "kickoff_attempt", "punt_attempt",
    "fumble", "complete_pass", "passer_player_id", "passer_player_name", "receiver_player_id",
    "receiver_player_name", "rusher_player_id", "rusher_player_name", "penalty_team", "penalty_player_id",
    "penalty_yards", "penalty_type", "series", "series_success", "series_result", "drive",
    "fixed_drive", "fixed_drive_result", "drive_play_count", "drive_time_of_possession",
    "drive_first_downs", "drive_inside20", "drive_ended_with_score", "drive_start_yard_line",
    "drive_end_yard_line", "drive_start_transition", "drive_end_transition", "start_time", "time_of_day",
    "stadium", "weather", "roof", "surface", "temp", "wind", "home_coach", "away_coach", "stadium_id",
    "game_stadium", "aborted_play", "success", "passer", "rusher", "receiver", "pass", "rush", "first_down",
    "special", "play", "passer_id", "rusher_id", "receiver_id", "name", "id", "cp", "cpoe", "xpass",
    "pass_oe", "spread_line", "total_line", "result", "total", "div_game", "play_deleted",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _qualified(table: str) -> tuple[str, str]:
    schema, name = table.split(".", 1)
    return schema, name


def _table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    schema, name = _qualified(table)
    row = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema=? AND table_name=?", [schema, name]
    ).fetchone()
    return bool(row and row[0])


def _table_columns(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    schema, name = _qualified(table)
    rows = con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema=? AND table_name=? ORDER BY ordinal_position",
        [schema, name],
    ).fetchall()
    return [r[0] for r in rows]


def _duck_type(dtype: pl.DataType) -> str:
    if dtype in (pl.Int8, pl.Int16, pl.Int32):
        return "INTEGER"
    if dtype == pl.Int64 or dtype in (pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64):
        return "BIGINT"
    if dtype in (pl.Float32, pl.Float64):
        return "DOUBLE"
    if dtype == pl.Boolean:
        return "BOOLEAN"
    if dtype == pl.Date:
        return "DATE"
    if isinstance(dtype, pl.Datetime):
        return "TIMESTAMP"
    return "VARCHAR"


def _ensure_table(con: duckdb.DuckDBPyConnection, table: str, df: pl.DataFrame) -> None:
    """Create the table from the frame's schema, or add any new columns (upstream schema evolution)."""
    if not _table_exists(con, table):
        con.register("_df_schema", df.head(0).to_arrow())
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM _df_schema")
        con.unregister("_df_schema")
        return
    existing = set(_table_columns(con, table))
    for col, dtype in zip(df.columns, df.dtypes, strict=True):
        if col not in existing:
            con.execute(f'ALTER TABLE {table} ADD COLUMN "{col}" {_duck_type(dtype)}')
            log.info("schema evolution: %s + %s", table, col)


def _insert(con: duckdb.DuckDBPyConnection, table: str, df: pl.DataFrame) -> int:
    cols = _table_columns(con, table)
    # align: missing columns become NULL, extra columns were added by _ensure_table
    missing = [c for c in cols if c not in df.columns]
    if missing:
        df = df.with_columns([pl.lit(None).alias(c) for c in missing])
    df = df.select(cols)
    con.register("_df_insert", df.to_arrow())
    quoted = ", ".join(f'"{c}"' for c in cols)
    con.execute(f"INSERT INTO {table} ({quoted}) SELECT {quoted} FROM _df_insert")
    con.unregister("_df_insert")
    return df.height


def _record_load(con: duckdb.DuckDBPyConnection, table: str, season: int | None, meta: SnapshotMeta, rows: int) -> None:
    con.execute(
        "INSERT INTO lab.load_runs (load_id, table_name, season, snapshot_id, rows_loaded, loaded_at, code_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [str(uuid.uuid4()), table, season, meta.snapshot_id, rows, _utc_now(), CODE_VERSION],
    )


def _already_loaded(con: duckdb.DuckDBPyConnection, table: str, snapshot_id: str) -> bool:
    row = con.execute(
        "SELECT count(*) FROM lab.load_runs WHERE table_name=? AND snapshot_id=?", [table, snapshot_id]
    ).fetchone()
    return bool(row and row[0])


def _prepare(df: pl.DataFrame, meta: SnapshotMeta, dataset: str) -> pl.DataFrame:
    if dataset == "pbp":
        keep = [c for c in PBP_COLUMNS if c in df.columns]
        df = df.select(keep)
    df = df.with_columns(pl.lit(meta.snapshot_id).alias("snapshot_id"))
    if meta.season is not None and "season" not in df.columns:
        df = df.with_columns(pl.lit(meta.season).cast(pl.Int32).alias("season"))
    # Normalize problematic dtypes for DuckDB arrow ingestion
    casts = []
    for col, dtype in zip(df.columns, df.dtypes, strict=True):
        if dtype == pl.Null:
            casts.append(pl.col(col).cast(pl.Utf8))
        elif isinstance(dtype, (pl.List, pl.Struct)):
            casts.append(pl.col(col).cast(pl.Utf8, strict=False))
    if casts:
        df = df.with_columns(casts)
    return df


def _target_table(dataset: str, df: pl.DataFrame) -> str:
    table, _ = TABLE_MAP[dataset]
    if dataset == "depth_charts":
        return "nfl.depth_chart_snapshots" if "dt" in df.columns else "nfl.depth_charts_weekly"
    return table


def load_dataset(
    dataset: str,
    seasons: Iterable[int] | None = None,
    *,
    con: duckdb.DuckDBPyConnection,
    store: SnapshotStore,
    settings: Settings | None = None,
) -> list[tuple[str, int | None, int]]:
    """Load the latest snapshot(s) of `dataset` into its table. Returns [(table, season, rows)]."""
    settings = settings or get_settings()
    if dataset not in TABLE_MAP:
        raise KeyError(f"no table mapping for dataset {dataset!r}")
    _, strategy = TABLE_MAP[dataset]
    spec = settings.sources["nflverse"]["datasets"][dataset]
    per_season = bool(spec.get("per_season"))
    out: list[tuple[str, int | None, int]] = []

    if strategy == "append_snapshot":
        idx = store.index()
        if idx.is_empty():
            return out
        q = idx.filter((pl.col("source") == "nflverse") & (pl.col("dataset") == dataset) & pl.col("duplicate_of").is_null())
        if seasons is not None:
            q = q.filter(pl.col("season").is_in(list(seasons)))
        for row in q.sort("retrieved_at").to_dicts():
            meta = SnapshotMeta(**{k: row.get(k) for k in SnapshotMeta.__dataclass_fields__})
            table = _target_table(dataset, pl.DataFrame())
            if _already_loaded(con, table, meta.snapshot_id):
                continue
            df = _prepare(store.read(meta), meta, dataset).with_columns(
                pl.lit(meta.retrieved_at).str.to_datetime(time_zone="UTC").alias("observed_at")
            )
            _ensure_table(con, table, df)
            n = _insert(con, table, df)
            _record_load(con, table, meta.season, meta, n)
            out.append((table, meta.season, n))
        return out

    targets: list[int | None] = list(seasons) if per_season else [None]
    for season in targets:
        meta = store.latest("nflverse", dataset, season)
        if meta is None:
            log.warning("no snapshot for %s season=%s", dataset, season)
            continue
        df = _prepare(store.read(meta), meta, dataset)
        table = _target_table(dataset, df)
        if _already_loaded(con, table, meta.snapshot_id):
            log.info("already loaded %s %s", table, meta.snapshot_id)
            continue
        _ensure_table(con, table, df)
        if strategy == "replace_all":
            con.execute(f"DELETE FROM {table}")
        elif strategy == "replace_season":
            con.execute(f"DELETE FROM {table} WHERE season = ?", [season])
        n = _insert(con, table, df)
        _record_load(con, table, season, meta, n)
        out.append((table, season, n))
        log.info("loaded %s season=%s rows=%s from %s", table, season, n, meta.snapshot_id)
    return out


# ----------------------------------------------------------------------------- reference tables
TEAM_ALIASES: list[tuple[str, str, str, str]] = [
    # alias, canonical, franchise_id, note
    ("ARI", "ARI", "cardinals", ""), ("ARZ", "ARI", "cardinals", "alt"), ("PHO", "ARI", "cardinals", "Phoenix 1988-93"), ("CRD", "ARI", "cardinals", "PFR"),
    ("ATL", "ATL", "falcons", ""),
    ("BAL", "BAL", "ravens", ""), ("BLT", "BAL", "ravens", "alt"), ("RAV", "BAL", "ravens", "PFR"),
    ("BUF", "BUF", "bills", ""),
    ("CAR", "CAR", "panthers", ""),
    ("CHI", "CHI", "bears", ""),
    ("CIN", "CIN", "bengals", ""),
    ("CLE", "CLE", "browns", ""), ("CLV", "CLE", "browns", "alt"),
    ("DAL", "DAL", "cowboys", ""),
    ("DEN", "DEN", "broncos", ""),
    ("DET", "DET", "lions", ""),
    ("GB", "GB", "packers", ""), ("GNB", "GB", "packers", "PFR"),
    ("HOU", "HOU", "texans", ""), ("HST", "HOU", "texans", "alt"), ("HTX", "HOU", "texans", "PFR"),
    ("IND", "IND", "colts", ""), ("CLT", "IND", "colts", "PFR"),
    ("JAX", "JAX", "jaguars", ""), ("JAC", "JAX", "jaguars", "alt"),
    ("KC", "KC", "chiefs", ""), ("KAN", "KC", "chiefs", "PFR"),
    ("LA", "LA", "rams", "Los Angeles Rams 2016-"), ("LAR", "LA", "rams", "alt"), ("STL", "LA", "rams", "St. Louis 1995-2015"), ("SL", "LA", "rams", "alt"), ("RAM", "LA", "rams", "PFR"),
    ("LAC", "LAC", "chargers", "Los Angeles Chargers 2017-"), ("SD", "LAC", "chargers", "San Diego -2016"), ("SDG", "LAC", "chargers", "PFR"), ("SDC", "LAC", "chargers", "alt"),
    ("LV", "LV", "raiders", "Las Vegas 2020-"), ("OAK", "LV", "raiders", "Oakland -2019"), ("RAI", "LV", "raiders", "PFR"),
    ("MIA", "MIA", "dolphins", ""),
    ("MIN", "MIN", "vikings", ""),
    ("NE", "NE", "patriots", ""), ("NWE", "NE", "patriots", "PFR"),
    ("NO", "NO", "saints", ""), ("NOR", "NO", "saints", "PFR"),
    ("NYG", "NYG", "giants", ""),
    ("NYJ", "NYJ", "jets", ""),
    ("PHI", "PHI", "eagles", ""),
    ("PIT", "PIT", "steelers", ""),
    ("SEA", "SEA", "seahawks", ""),
    ("SF", "SF", "49ers", ""), ("SFO", "SF", "49ers", "PFR"),
    ("TB", "TB", "buccaneers", ""), ("TAM", "TB", "buccaneers", "PFR"),
    ("TEN", "TEN", "titans", ""), ("OTI", "TEN", "titans", "PFR"),
    ("WAS", "WAS", "commanders", ""), ("WSH", "WAS", "commanders", "alt"), ("WFT", "WAS", "commanders", "Football Team 2020-21"),
]


def load_reference(con: duckdb.DuckDBPyConnection, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    con.execute("DELETE FROM ref.team_aliases")
    con.executemany("INSERT INTO ref.team_aliases VALUES (?, ?, ?, ?)", TEAM_ALIASES)
    con.execute("DELETE FROM ref.books")
    for b in settings.books["books"]:
        con.execute(
            "INSERT INTO ref.books VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                b["book_id"], b["display_name"], b["book_type"], (b.get("feed_keys") or {}).get("odds_api"),
                b.get("region"), b.get("valid_from"), b.get("valid_to"), b.get("notes"),
            ],
        )


def sync_snapshot_index(con: duckdb.DuckDBPyConnection, store: SnapshotStore) -> int:
    idx = store.index()
    if idx.is_empty():
        return 0
    cols = ["snapshot_id", "source", "dataset", "season", "url", "retrieved_at", "last_modified", "sha256",
            "bytes", "rows", "columns", "ext", "path", "loader_version", "duplicate_of"]
    df = idx.select([c for c in cols if c in idx.columns]).unique(subset=["snapshot_id"])
    df = df.with_columns(pl.col("retrieved_at").str.to_datetime(time_zone="UTC"))
    con.execute("DELETE FROM lab.snapshots")
    con.register("_snap", df.to_arrow())
    quoted = ", ".join(f'"{c}"' for c in df.columns)
    con.execute(f"INSERT INTO lab.snapshots ({quoted}) SELECT {quoted} FROM _snap")
    con.unregister("_snap")
    return df.height


def build_historical_lines_from_games(con: duckdb.DuckDBPyConnection) -> int:
    """nflverse schedule lines → market.historical_lines with line_class='last_pull'.

    Betting convention: spread_home is negative when home is favored. nflverse `spread_line` is
    positive when home is favored (it equals the expected home margin), so spread_home = -spread_line.
    """
    con.execute("DELETE FROM market.historical_lines WHERE source = 'nflverse'")
    con.execute(
        """
        INSERT INTO market.historical_lines
        SELECT g.game_id, 'nflverse', 'nflverse', 'last_pull',
               s.retrieved_at,
               -g.spread_line, g.home_spread_odds, g.away_spread_odds,
               g.total_line, g.over_odds, g.under_odds,
               g.home_moneyline, g.away_moneyline,
               g.snapshot_id,
               'live/overwritten upstream; ≈close only for completed games'
        FROM nfl.games g
        LEFT JOIN lab.snapshots s ON s.snapshot_id = g.snapshot_id
        WHERE g.spread_line IS NOT NULL OR g.home_moneyline IS NOT NULL
        """
    )
    return con.execute("SELECT count(*) FROM market.historical_lines WHERE source='nflverse'").fetchone()[0]
