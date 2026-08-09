"""Tests for ``planet_colonization_capture`` — SYNTHETIC fixtures only.

Every observation below is hand-authored, not collected from a live TWGS
session. These tests prove the analysis math is correct given known-shape
input, not that any specific production figure holds against a real server.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tw2002_aiclient.planet_colonization_capture import (
    CompoundingRateEstimate,
    GfGrowthEstimate,
    PlanetIdentity,
    PlanetObservation,
    StoredCargoBonusEstimate,
    analyze_planet_history,
    append_observations,
    estimate_buy_production_threshold,
    estimate_compounding_rate,
    estimate_gf_growth_curve,
    estimate_plague_band,
    estimate_stored_cargo_bonus,
    load_observations,
    observation_from_dict,
    observation_to_dict,
    observations_from_planet_dir,
    observations_from_planet_record,
)

T0 = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)


def _obs(**kwargs):
    base = dict(sector_id=500, timestamp=T0)
    base.update(kwargs)
    return PlanetObservation(**base)


def test_stored_cargo_bonus_linear_fit():
    # daily_production = 100 + 0.1 * stored_cargo
    obs = [
        _obs(stored_cargo_units=0, daily_production=100.0, timestamp=T0),
        _obs(stored_cargo_units=1000, daily_production=200.0, timestamp=T0 + timedelta(hours=1)),
        _obs(stored_cargo_units=5000, daily_production=600.0, timestamp=T0 + timedelta(hours=2)),
    ]
    result = estimate_stored_cargo_bonus(obs)
    identity = PlanetIdentity(sector_id=500, planet_id=None)
    assert identity in result
    est = result[identity]
    assert isinstance(est, StoredCargoBonusEstimate)
    assert est.sample_count == 3
    assert abs(est.bonus_per_unit - 0.1) < 1e-6
    assert abs(est.intercept - 100.0) < 1e-6


def test_stored_cargo_bonus_insufficient_data_omitted():
    obs = [_obs(stored_cargo_units=100, daily_production=50.0)]
    assert estimate_stored_cargo_bonus(obs) == {}


def test_stored_cargo_bonus_degenerate_fit_omitted():
    obs = [
        _obs(stored_cargo_units=1000, daily_production=200.0),
        _obs(stored_cargo_units=1000, daily_production=250.0, timestamp=T0 + timedelta(hours=1)),
    ]
    assert estimate_stored_cargo_bonus(obs) == {}


def test_compounding_rate_averages_untouched_pairs():
    obs = [
        _obs(stored_cargo_units=1000, timestamp=T0, withdrawn_since_prior=None),
        _obs(
            stored_cargo_units=1100,
            timestamp=T0 + timedelta(days=1),
            withdrawn_since_prior=False,
            production_bought_since_prior=False,
        ),
        _obs(
            stored_cargo_units=1210,
            timestamp=T0 + timedelta(days=2),
            withdrawn_since_prior=False,
            production_bought_since_prior=False,
        ),
    ]
    result = estimate_compounding_rate(obs)
    identity = PlanetIdentity(sector_id=500, planet_id=None)
    assert identity in result
    est = result[identity]
    assert isinstance(est, CompoundingRateEstimate)
    assert est.sample_count == 2
    # 10% per day compounding
    assert abs(est.fraction_per_day - 0.10) < 1e-6


def test_compounding_excludes_withdrawn_or_bought_pairs():
    obs = [
        _obs(stored_cargo_units=1000, timestamp=T0),
        _obs(
            stored_cargo_units=1100,
            timestamp=T0 + timedelta(days=1),
            withdrawn_since_prior=True,
        ),
        _obs(stored_cargo_units=1000, timestamp=T0 + timedelta(days=2)),
        _obs(
            stored_cargo_units=1100,
            timestamp=T0 + timedelta(days=3),
            production_bought_since_prior=True,
        ),
    ]
    assert estimate_compounding_rate(obs) == {}


def test_buy_production_threshold_median():
    obs = [
        _obs(buy_production_price=8.0),
        _obs(buy_production_price=9.0, timestamp=T0 + timedelta(hours=1)),
        _obs(buy_production_price=12.0, timestamp=T0 + timedelta(hours=2)),
    ]
    result = estimate_buy_production_threshold(obs)
    identity = PlanetIdentity(sector_id=500, planet_id=None)
    assert identity in result
    est = result[identity]
    assert est.median_price == 9.0
    assert est.min_price == 8.0
    assert est.max_price == 12.0
    assert est.sample_count == 3


def test_plague_band_min_max():
    obs = [
        _obs(plague_loss_pct=15.0),
        _obs(plague_loss_pct=72.5, timestamp=T0 + timedelta(days=30)),
        _obs(plague_loss_pct=3.0, timestamp=T0 + timedelta(days=60)),
    ]
    result = estimate_plague_band(obs)
    identity = PlanetIdentity(sector_id=500, planet_id=None)
    assert identity in result
    est = result[identity]
    assert est.min_loss_pct == 3.0
    assert est.max_loss_pct == 72.5
    assert est.sample_count == 3


def test_plague_band_no_events_omitted():
    assert estimate_plague_band([_obs(stored_cargo_units=100)]) == {}


def test_gf_growth_linear_fit():
    # gf_per_min = 0.000006 * stored_credits + 0.4  → ~1 at 100k, ~6.4 at 1M
    obs = [
        _obs(gf_count=1000, stored_credits=100_000.0, timestamp=T0),
        _obs(
            gf_count=1060,
            stored_credits=100_000.0,
            timestamp=T0 + timedelta(minutes=60),
            withdrawn_since_prior=False,
        ),
        _obs(gf_count=5000, stored_credits=1_000_000.0, timestamp=T0 + timedelta(hours=2)),
        _obs(
            gf_count=5420,
            stored_credits=1_000_000.0,
            timestamp=T0 + timedelta(hours=2, minutes=60),
            withdrawn_since_prior=False,
        ),
    ]
    result = estimate_gf_growth_curve(obs)
    identity = PlanetIdentity(sector_id=500, planet_id=None)
    assert identity in result
    est = result[identity]
    assert isinstance(est, GfGrowthEstimate)
    assert est.sample_count == 2
    # first pair: 60 GF / 60 min = 1.0 at 100k
    # second pair: 420 GF / 60 min = 7.0 at 1M
    assert abs(est.evidence[0][1] - 1.0) < 1e-6
    assert abs(est.evidence[1][1] - 7.0) < 1e-6


def test_gf_growth_insufficient_pairs_omitted():
    obs = [
        _obs(gf_count=1000, stored_credits=100_000.0, timestamp=T0),
        _obs(
            gf_count=1060,
            stored_credits=100_000.0,
            timestamp=T0 + timedelta(minutes=60),
            withdrawn_since_prior=False,
        ),
    ]
    assert estimate_gf_growth_curve(obs) == {}


def test_identities_segregated_by_sector_and_planet_id():
    obs = [
        _obs(sector_id=100, planet_id="a", buy_production_price=8.0),
        _obs(sector_id=100, planet_id="b", buy_production_price=10.0, timestamp=T0 + timedelta(hours=1)),
        _obs(sector_id=200, planet_id="a", buy_production_price=9.0, timestamp=T0 + timedelta(hours=2)),
    ]
    result = estimate_buy_production_threshold(obs)
    assert PlanetIdentity(sector_id=100, planet_id="a") in result
    assert PlanetIdentity(sector_id=100, planet_id="b") in result
    assert PlanetIdentity(sector_id=200, planet_id="a") in result


def test_analyze_planet_history_combines_all_estimators():
    obs = [
        _obs(
            stored_cargo_units=1000,
            daily_production=200.0,
            buy_production_price=9.0,
            plague_loss_pct=25.0,
            gf_count=1000,
            stored_credits=100_000.0,
            timestamp=T0,
        ),
        _obs(
            stored_cargo_units=2000,
            daily_production=300.0,
            buy_production_price=8.0,
            gf_count=1060,
            stored_credits=100_000.0,
            timestamp=T0 + timedelta(days=1),
            withdrawn_since_prior=False,
            production_bought_since_prior=False,
        ),
        _obs(
            stored_cargo_units=5000,
            daily_production=600.0,
            gf_count=5000,
            stored_credits=1_000_000.0,
            timestamp=T0 + timedelta(days=2),
            withdrawn_since_prior=False,
        ),
        _obs(
            stored_cargo_units=5500,
            daily_production=650.0,
            gf_count=5420,
            stored_credits=1_000_000.0,
            timestamp=T0 + timedelta(days=2, minutes=60),
            withdrawn_since_prior=False,
            production_bought_since_prior=False,
        ),
    ]
    report = analyze_planet_history(obs)
    identity = PlanetIdentity(sector_id=500, planet_id=None)
    assert identity in report.stored_cargo_bonus
    assert identity in report.compounding
    assert identity in report.buy_production
    assert identity in report.plague_band
    assert identity in report.gf_growth
    assert report.stored_cargo_bonus[identity].verified_vs_live is False
    assert report.compounding[identity].tag == "observed_estimate"


def test_no_observations_yields_empty_report():
    report = analyze_planet_history([])
    assert report.stored_cargo_bonus == {}
    assert report.compounding == {}
    assert report.buy_production == {}
    assert report.plague_band == {}
    assert report.gf_growth == {}


def test_observation_json_round_trip(tmp_path):
    obs = _obs(
        stored_cargo_units=500,
        daily_production=150.0,
        buy_production_price=9.5,
        withdrawn_since_prior=False,
    )
    path = tmp_path / "obs.jsonl"
    assert append_observations(path, [obs]) == 1
    loaded = load_observations(path)
    assert len(loaded) == 1
    assert loaded[0].sector_id == 500
    assert loaded[0].stored_cargo_units == 500
    assert loaded[0].buy_production_price == 9.5
    assert observation_from_dict(observation_to_dict(obs)) is not None


def test_observations_from_planet_record():
    planet = {
        "last_seen_ts": "2026-08-07T12:00:00Z",
        "planet_name": "TestWorld",
        "stored_credits": 100000.0,
        "stored_cargo_units": 2500,
        "daily_production": 350.0,
        "gf_count": 1200,
    }
    rows = observations_from_planet_record(42, planet)
    assert len(rows) == 1
    assert rows[0].sector_id == 42
    assert rows[0].planet_name == "TestWorld"
    assert rows[0].stored_cargo_units == 2500


def test_observations_from_planet_dir(tmp_path):
    planets = tmp_path / "planets"
    planets.mkdir()
    (planets / "99.json").write_text(
        '{"sector_id": 99, "planet": {"last_seen_ts": "2026-08-07T01:00:00Z",'
        ' "stored_cargo_units": 1000, "daily_production": 200.0}}\n',
        encoding="utf-8",
    )
    (planets / "100.json").write_text('{"sector_id": 100, "planet": null}\n', encoding="utf-8")
    rows = observations_from_planet_dir(tmp_path)
    assert len(rows) == 1
    assert rows[0].sector_id == 99
    assert rows[0].stored_cargo_units == 1000
