import math

import pytest

from edgelab.pricing.odds import (
    american_to_decimal,
    american_to_implied,
    breakeven_prob,
    clv_cents,
    decimal_to_american,
    ev_per_unit,
    fair_two_way,
    kelly_fraction,
    overround,
    prob_to_american,
    remove_vig_multiplicative,
    remove_vig_power,
)


@pytest.mark.parametrize("odds,dec", [(-110, 1.9090909), (+150, 2.5), (-150, 1.6666667), (+100, 2.0), (-100, 2.0)])
def test_american_to_decimal(odds, dec):
    assert math.isclose(american_to_decimal(odds), dec, rel_tol=1e-6)


@pytest.mark.parametrize("odds,p", [(-110, 0.5238095), (+150, 0.4), (-150, 0.6), (+100, 0.5), (+190, 0.3448276)])
def test_american_to_implied(odds, p):
    assert math.isclose(american_to_implied(odds), p, rel_tol=1e-6)


def test_roundtrip_decimal_american():
    for odds in (-110, -105, +105, +150, -300, +1200):
        assert decimal_to_american(american_to_decimal(odds)) == odds


def test_prob_to_american_examples():
    assert prob_to_american(0.41) == 144
    assert prob_to_american(0.59) == -144
    assert prob_to_american(0.5) == 100


def test_zero_odds_rejected():
    with pytest.raises(ValueError):
        american_to_implied(0)


def test_overround_standard_juice():
    assert math.isclose(overround(-110, -110), 0.047619, rel_tol=1e-4)


def test_multiplicative_symmetric():
    a, b = remove_vig_multiplicative(-110, -110)
    assert math.isclose(a, 0.5) and math.isclose(b, 0.5)


def test_power_sums_to_one_and_penalizes_longshot_more():
    a, b = remove_vig_power(-300, +240)
    assert math.isclose(a + b, 1.0, abs_tol=1e-8)
    ma, mb = remove_vig_multiplicative(-300, +240)
    # power method gives the favourite a higher fair probability than multiplicative
    assert a > ma and b < mb


def test_fair_two_way_records_method():
    f = fair_two_way(-120, +100, method="power")
    assert f.method == "power" and math.isclose(f.p_a + f.p_b, 1.0, abs_tol=1e-8)


def test_ev_charter_example():
    # NE 41% to win at +190 -> positive theoretical value
    assert math.isclose(ev_per_unit(0.41, 190), 0.189, abs_tol=1e-6)
    assert ev_per_unit(breakeven_prob(190), 190) == pytest.approx(0.0, abs=1e-9)


def test_ev_with_push():
    # 50% win, 10% push, 40% loss at -110
    assert math.isclose(ev_per_unit(0.5, -110, p_push=0.1), 0.5 * (100 / 110) - 0.4, rel_tol=1e-9)


def test_kelly_zero_when_no_edge():
    assert kelly_fraction(0.5, +100) == 0.0
    assert kelly_fraction(0.6, +100) == pytest.approx(0.2)


def test_clv_cents_sign():
    # bet NE +190, closed +160 -> beat the close
    assert clv_cents(190, 160) > 0
    assert clv_cents(160, 190) < 0
