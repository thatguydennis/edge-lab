from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_leakage_register_lists_known_fields():
    text = (ROOT / "docs" / "LEAKAGE_REGISTER.md").read_text()
    for field in ("spread_line", "referee", "date_modified", "result", "home_qb"):
        assert field in text
