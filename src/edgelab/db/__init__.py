"""DuckDB connection helpers."""

from __future__ import annotations

from pathlib import Path

import duckdb

from edgelab.config import Settings, get_settings

SCHEMA_SQL = Path(__file__).with_name("schema.sql")


def connect(settings: Settings | None = None, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    settings = settings or get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.db_path), read_only=read_only)
    if not read_only:
        con.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
    return con
