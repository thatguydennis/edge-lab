"""Odds conversions, vig removal and expected value.

Conventions
- American odds: +150 means win 150 on 100; -150 means risk 150 to win 100.
- `implied_prob` is the book's price including vig; `fair_prob` has the vig removed.
- Two vig-removal methods are provided (multiplicative normalization, power/Shin-like). The method
  used is always recorded with a prediction. The auditor keeps an independent implementation.
- EV is per 1 unit staked.

Worked examples (used in tests):
  -110 -> implied 0.5238 ; +150 -> 0.4000 ; -150 -> 0.6000
  two-way -110/-110 -> multiplicative fair 0.5/0.5 (overround 4.76%)
  p=0.41 -> fair American ≈ +144 ; p=0.59 -> ≈ -144
  EV at +190 with p=0.41: 0.41*1.90 - 0.59 = +0.189 per unit
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def american_to_decimal(odds: int | float) -> float:
    odds = float(odds)
    if odds == 0:
        raise ValueError("American odds cannot be 0")
    return 1.0 + (odds / 100.0 if odds > 0 else 100.0 / abs(odds))


def decimal_to_american(dec: float) -> int:
    if dec <= 1.0:
        raise ValueError("decimal odds must exceed 1.0")
    if dec >= 2.0:
        return int(round((dec - 1.0) * 100.0))
    return int(round(-100.0 / (dec - 1.0)))


def american_to_implied(odds: int | float) -> float:
    """Book implied probability (includes vig)."""
    odds = float(odds)
    if odds == 0:
        raise ValueError("American odds cannot be 0")
    return 100.0 / (odds + 100.0) if odds > 0 else abs(odds) / (abs(odds) + 100.0)


def prob_to_american(p: float) -> int:
    """Fair American odds for probability p (no vig)."""
    if not 0.0 < p < 1.0:
        raise ValueError("probability must be in (0, 1)")
    return decimal_to_american(1.0 / p)


def overround(*prices: int | float) -> float:
    """Sum of implied probabilities minus 1 (e.g. 0.0476 for -110/-110)."""
    return sum(american_to_implied(x) for x in prices) - 1.0


def remove_vig_multiplicative(*prices: int | float) -> tuple[float, ...]:
    imps = [american_to_implied(x) for x in prices]
    s = sum(imps)
    return tuple(x / s for x in imps)


def remove_vig_power(*prices: int | float, tol: float = 1e-10, max_iter: int = 200) -> tuple[float, ...]:
    """Power method: find k such that sum(p_i ** k) = 1, fair_i = p_i ** k.

    Puts more of the vig on the longshot than multiplicative normalization does (favourite–longshot bias).
    """
    imps = [american_to_implied(x) for x in prices]
    lo, hi = 0.5, 3.0
    for _ in range(max_iter):
        k = (lo + hi) / 2.0
        s = sum(p ** k for p in imps)
        if abs(s - 1.0) < tol:
            break
        if s > 1.0:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2.0
    return tuple(p ** k for p in imps)


def ev_per_unit(p_win: float, odds: int | float, p_push: float = 0.0) -> float:
    """Expected profit per 1 unit staked at American `odds` with win probability `p_win`.

    p_push is returned stake (0 profit). Loss probability = 1 - p_win - p_push.
    """
    if p_win < 0 or p_push < 0 or p_win + p_push > 1.0 + 1e-12:
        raise ValueError("invalid probabilities")
    profit_if_win = american_to_decimal(odds) - 1.0
    p_loss = 1.0 - p_win - p_push
    return p_win * profit_if_win - p_loss


def breakeven_prob(odds: int | float) -> float:
    """Win probability at which EV = 0 (ignoring pushes). Same as implied probability."""
    return american_to_implied(odds)


@dataclass(frozen=True)
class TwoWayFair:
    p_a: float
    p_b: float
    method: str
    overround: float


def fair_two_way(price_a: int | float, price_b: int | float, method: str = "multiplicative") -> TwoWayFair:
    if method == "multiplicative":
        pa, pb = remove_vig_multiplicative(price_a, price_b)
    elif method == "power":
        pa, pb = remove_vig_power(price_a, price_b)
    else:
        raise ValueError(f"unknown method {method!r}")
    return TwoWayFair(pa, pb, method, overround(price_a, price_b))


def kelly_fraction(p_win: float, odds: int | float) -> float:
    """Full Kelly fraction for a simple bet (reference only; v0 uses flat sizing)."""
    b = american_to_decimal(odds) - 1.0
    q = 1.0 - p_win
    f = (b * p_win - q) / b
    return max(0.0, f)


def clv_cents(bet_price: int | float, close_price: int | float) -> float:
    """CLV in probability points: implied(close) - implied(bet), for the side bet. Positive = beat the close."""
    return (american_to_implied(close_price) - american_to_implied(bet_price)) * 100.0


def _isclose(a: float, b: float, tol: float = 1e-9) -> bool:
    return math.isclose(a, b, abs_tol=tol)
