import re
from pathlib import Path

from edgelab.config import get_settings

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = [
    "spread_line", "total_line", "home_moneyline", "away_moneyline", "home_spread_odds", "away_spread_odds",
    "over_odds", "under_odds", "referee", "temp", "wind", "roof", "result", "total", "overtime", "home_score",
    "away_score", "home_qb_id", "home_qb_name", "away_qb_id", "away_qb_name",
]


def test_quarantine_covers_register_l1_to_l4(tmp_settings):
    q = set(get_settings().sources["nflverse"]["datasets"]["schedules"]["quarantine_columns"])
    missing = [c for c in REQUIRED if c not in q]
    assert not missing, f"quarantine list missing {missing}"
    # every nfl.games.<col> mentioned in register rows L1-L4 must be quarantined
    text = (ROOT / "docs" / "LEAKAGE_REGISTER.md").read_text()
    for line in text.splitlines():
        if re.match(r"\| L[1-4] \|", line):
            for col in re.findall(r"`nfl\.games\.([a-z_]+)`", line):
                assert col in q, col
