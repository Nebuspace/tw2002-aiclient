"""Tests for ``port_floor_capture`` — SYNTHETIC fixtures only.

Every observation below is hand-authored, not collected from a live TWGS
session (see the module docstring + WO for the live-prove caveat). These
tests prove the analysis math is correct given known-shape input, not that
any specific credits/day figure holds against a real server.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tw2002_aiclient.port_floor_capture import (
    FloorPriceEstimate,
    PortIdentity,
    PortObservation,
    analyze_port_history,
    estimate_floor_price,
    estimate_regrowth_rate,
)

T0 = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)


def _obs(**kwargs):
    base = dict(sector_id=100, commodity="Fuel Ore", status="selling", amount=500, pct=10, timestamp=T0)
    base.update(kwargs)
    return PortObservation(**base)


def test_regrowth_rate_averages_trade_free_pairs():
    obs = [
        _obs(pct=10, amount=500, timestamp=T0, traded_since_prior=None),
        _obs(pct=20, amount=1000, timestamp=T0 + timedelta(days=1), traded_since_prior=False),
        _obs(pct=30, amount=1500, timestamp=T0 + timedelta(days=2), traded_since_prior=False),
    ]
    result = estimate_regrowth_rate(obs)
    identity = PortIdentity(sector_id=100, port_id=None, commodity="Fuel Ore")
    assert identity in result
    est = result[identity]
    assert est.sample_count == 2
    assert abs(est.pct_per_day - 10.0) < 1e-9


def test_regrowth_excludes_pairs_with_unknown_or_true_trade_flag():
    obs = [
        _obs(pct=10, timestamp=T0, traded_since_prior=None),
        _obs(pct=50, timestamp=T0 + timedelta(days=1), traded_since_prior=True),
        _obs(pct=5, timestamp=T0 + timedelta(days=2), traded_since_prior=None),
    ]
    result = estimate_regrowth_rate(obs)
    assert result == {}


def test_regrowth_excludes_pct_decreases():
    obs = [
        _obs(pct=50, timestamp=T0, traded_since_prior=None),
        _obs(pct=30, timestamp=T0 + timedelta(days=1), traded_since_prior=False),
    ]
    result = estimate_regrowth_rate(obs)
    assert result == {}


def test_regrowth_zero_or_negative_elapsed_time_excluded():
    obs = [
        _obs(pct=10, timestamp=T0, traded_since_prior=None),
        _obs(pct=20, timestamp=T0, traded_since_prior=False),  # zero elapsed
    ]
    result = estimate_regrowth_rate(obs)
    assert result == {}


def test_floor_price_linear_fit_at_pct_100():
    # Price declines 0.1 credit per pct point: floor at pct=100 should be
    # exactly extrapolated from a perfect line.
    obs = [
        _obs(pct=10, price_per_unit=25.0, timestamp=T0),
        _obs(pct=50, price_per_unit=21.0, timestamp=T0 + timedelta(hours=1)),
        _obs(pct=90, price_per_unit=17.0, timestamp=T0 + timedelta(hours=2)),
    ]
    result = estimate_floor_price(obs)
    identity = PortIdentity(sector_id=100, port_id=None, commodity="Fuel Ore")
    assert identity in result
    est = result[identity]
    assert isinstance(est, FloorPriceEstimate)
    assert est.sample_count == 3
    # slope = -0.1 credits/pct; price = 26 - 0.1*pct, so floor at pct=100 == 16.0
    assert abs(est.floor_price - 16.0) < 1e-6
    assert abs(est.slope - (-0.1)) < 1e-6


def test_floor_price_requires_at_least_two_priced_observations():
    obs = [_obs(pct=10, price_per_unit=25.0, timestamp=T0)]
    assert estimate_floor_price(obs) == {}


def test_floor_price_ignores_unpriced_observations():
    obs = [
        _obs(pct=10, price_per_unit=None, timestamp=T0),
        _obs(pct=50, price_per_unit=None, timestamp=T0 + timedelta(hours=1)),
    ]
    assert estimate_floor_price(obs) == {}


def test_floor_price_degenerate_fit_same_pct_omitted():
    obs = [
        _obs(pct=50, price_per_unit=20.0, timestamp=T0),
        _obs(pct=50, price_per_unit=22.0, timestamp=T0 + timedelta(hours=1)),
    ]
    assert estimate_floor_price(obs) == {}


def test_identities_are_segregated_by_sector_port_and_commodity():
    obs = [
        _obs(sector_id=100, commodity="Fuel Ore", pct=10, price_per_unit=25.0, timestamp=T0),
        _obs(sector_id=100, commodity="Fuel Ore", pct=90, price_per_unit=17.0, timestamp=T0 + timedelta(hours=1)),
        _obs(sector_id=200, commodity="Fuel Ore", pct=10, price_per_unit=25.0, timestamp=T0),
        _obs(sector_id=100, commodity="Organics", pct=10, price_per_unit=30.0, timestamp=T0),
    ]
    result = estimate_floor_price(obs)
    assert PortIdentity(sector_id=100, port_id=None, commodity="Fuel Ore") in result
    # sector 200 and the Organics commodity each only have one priced row.
    assert PortIdentity(sector_id=200, port_id=None, commodity="Fuel Ore") not in result
    assert PortIdentity(sector_id=100, port_id=None, commodity="Organics") not in result


def test_port_id_distinguishes_same_sector_different_port_label():
    obs = [
        _obs(sector_id=100, port_id="alpha", pct=10, price_per_unit=25.0, timestamp=T0),
        _obs(sector_id=100, port_id="alpha", pct=90, price_per_unit=17.0, timestamp=T0 + timedelta(hours=1)),
        _obs(sector_id=100, port_id="beta", pct=10, price_per_unit=25.0, timestamp=T0),
    ]
    result = estimate_floor_price(obs)
    assert PortIdentity(sector_id=100, port_id="alpha", commodity="Fuel Ore") in result
    assert PortIdentity(sector_id=100, port_id="beta", commodity="Fuel Ore") not in result


def test_analyze_port_history_combines_both_estimates():
    obs = [
        _obs(pct=10, amount=500, price_per_unit=25.0, timestamp=T0, traded_since_prior=None),
        _obs(pct=20, amount=1000, price_per_unit=23.0, timestamp=T0 + timedelta(days=1), traded_since_prior=False),
        _obs(pct=30, amount=1500, price_per_unit=21.0, timestamp=T0 + timedelta(days=2), traded_since_prior=False),
    ]
    report = analyze_port_history(obs)
    identity = PortIdentity(sector_id=100, port_id=None, commodity="Fuel Ore")
    assert identity in report.regrowth
    assert identity in report.floor_price
    assert report.regrowth[identity].tag == "observed_estimate"
    assert report.floor_price[identity].tag == "observed_estimate"
    assert report.regrowth[identity].verified_vs_live is False
    assert report.floor_price[identity].verified_vs_live is False


def test_no_observations_yields_empty_report():
    report = analyze_port_history([])
    assert report.regrowth == {}
    assert report.floor_price == {}
