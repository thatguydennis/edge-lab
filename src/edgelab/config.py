"""Configuration: project root discovery, settings.yaml, sources.yaml, books.yaml, .env secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def find_project_root(start: Path | None = None) -> Path:
    """Walk up from `start` (or cwd) until a directory containing pyproject.toml and config/ is found."""
    env = os.environ.get("EDGELAB_ROOT")
    if env:
        return Path(env).resolve()
    p = (start or Path.cwd()).resolve()
    for candidate in [p, *p.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "config").is_dir():
            return candidate
    # fall back to the package's grandparent (src/edgelab -> repo root)
    return Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    root: Path
    settings: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, Any] = field(default_factory=dict)
    books: dict[str, Any] = field(default_factory=dict)

    @property
    def data_dir(self) -> Path:
        return self.root / os.environ.get("EDGELAB_DATA_DIR", self.settings.get("data_dir", "data"))

    @property
    def snapshots_dir(self) -> Path:
        return self.data_dir / "snapshots"

    @property
    def metadata_dir(self) -> Path:
        return self.data_dir / "metadata"

    @property
    def db_path(self) -> Path:
        return self.root / os.environ.get("EDGELAB_DB_PATH", self.settings.get("db_path", "data/db/edgelab.duckdb"))

    @property
    def timezone(self) -> str:
        return os.environ.get("EDGELAB_TZ", self.settings.get("timezone", "America/New_York"))

    @property
    def odds_api_key(self) -> str | None:
        return os.environ.get("ODDS_API_KEY") or None


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    root = find_project_root()
    load_dotenv(root / ".env", override=False)
    cfg = root / "config"
    return Settings(
        root=root,
        settings=_load_yaml(cfg / "settings.yaml"),
        sources=_load_yaml(cfg / "sources.yaml"),
        books=_load_yaml(cfg / "books.yaml"),
    )
