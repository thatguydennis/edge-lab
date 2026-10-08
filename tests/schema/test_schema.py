import polars as pl

from edgelab.db import connect
from edgelab.db.load import _ensure_table, _insert, load_reference


def test_schema_creates_all_schemas_and_tables(tmp_settings):
    con = connect(tmp_settings)
    schemas = {r[0] for r in con.execute("SELECT DISTINCT table_schema FROM information_schema.tables").fetchall()}
    assert {"ref", "market", "lab"} <= schemas
    tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='lab'").fetchall()}
    assert {"predictions_official", "personal_ledger", "model_ledger", "overrides", "audit_results", "backtest_runs"} <= tables
    con.close()


def test_reference_tables(tmp_settings):
    con = connect(tmp_settings)
    load_reference(con, tmp_settings)
    assert con.execute("SELECT team FROM ref.team_aliases WHERE alias='OAK'").fetchone()[0] == "LV"
    assert con.execute("SELECT team FROM ref.team_aliases WHERE alias='STL'").fetchone()[0] == "LA"
    assert con.execute("SELECT book_id FROM ref.books WHERE odds_api_key='williamhill_us'").fetchone()[0] == "caesars"
    assert con.execute("SELECT count(*) FROM ref.books WHERE book_type='exchange'").fetchone()[0] >= 3
    con.close()


def test_schema_evolution_adds_columns(tmp_settings):
    con = connect(tmp_settings)
    df1 = pl.DataFrame({"season": [2024], "a": [1]})
    _ensure_table(con, "nfl.evo", df1)
    _insert(con, "nfl.evo", df1)
    df2 = pl.DataFrame({"season": [2025], "a": [2], "dt": ["2025-09-01"]})
    _ensure_table(con, "nfl.evo", df2)
    _insert(con, "nfl.evo", df2)
    rows = con.execute("SELECT season, a, dt FROM nfl.evo ORDER BY season").fetchall()
    assert rows == [(2024, 1, None), (2025, 2, "2025-09-01")]
    con.close()
