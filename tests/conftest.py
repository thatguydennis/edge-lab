from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def tmp_settings(tmp_path, monkeypatch):
    """Settings pointing at a temporary data dir and db so tests never touch the real lake."""
    monkeypatch.setenv("EDGELAB_ROOT", str(ROOT))
    monkeypatch.setenv("EDGELAB_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("EDGELAB_DB_PATH", str(tmp_path / "data" / "db" / "test.duckdb"))
    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    from edgelab.config import get_settings
    get_settings.cache_clear()
    s = get_settings()
    yield s
    get_settings.cache_clear()
