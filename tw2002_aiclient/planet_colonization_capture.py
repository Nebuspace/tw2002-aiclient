"""Planet colonization production LIVE-DATA analysis (pure, no socket I/O).

Canon: ``canon/strategy/planet-colonization.md`` Verification / hypothesis
sections (~lines 151–175). That doc flags every production number — stored-cargo
bonus, compounding rate, buy-production threshold, plague band, GF-growth curve
— as **UNCONFIRMED HYPOTHESIS with no implementing module**. The world model
today surfaces planets only as topology landmarks; nothing turns *repeated*
planet-screen readings over *time* into measured estimates.

This module is that missing analysis step, and nothing more:

- **Pure functions over caller-supplied observations.** No socket, no
  live-send, no auto-visiting a planet, no scheduling. A future capture loop
  (out of this module's scope) collects :class:`PlanetObservation` rows from
  repeated real visits and feeds them here.
- **Never fabricates a "real" number.** Every result carries
  ``tag="observed_estimate"`` and a ``sample_count`` / ``evidence`` trail so
  a caller can see exactly how thin (or synthetic) the backing data is. This
  module does not itself claim ``verified_vs_live=True`` — that flip is a
  live-prove decision made by whoever owns the capture loop.
- **Compounding needs an untouched window.** Stored-stock growth can reflect
  compounding *or* operator withdrawals / credit-bought production — pairs
  marked ``withdrawn_since_prior=True`` or ``production_bought_since_prior=True``
  on the later observation are excluded (``None`` = unknown, also excluded).
- **Plague band needs plague events.** Only observations with an explicit
  ``plague_loss_pct`` contribute; absent events yield no estimate (never a
  fabricated 1–99 band).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

__all__ = [
    "PlanetObservation",
    "PlanetIdentity",
    "StoredCargoBonusEstimate",
    "CompoundingRateEstimate",
    "BuyProductionThresholdEstimate",
    "PlagueBandEstimate",
    "GfGrowthEstimate",
    "PlanetColonizationReport",
    "estimate_stored_cargo_bonus",
    "estimate_compounding_rate",
    "estimate_buy_production_threshold",
    "estimate_plague_band",
    "estimate_gf_growth_curve",
    "analyze_planet_history",
    "OBSERVATIONS_FILENAME",
    "default_observations_path",
    "observation_to_dict",
    "observation_from_dict",
    "load_observations",
    "append_observations",
    "observations_from_planet_record",
    "observations_from_planet_dir",
]

OBSERVATIONS_FILENAME = "planet_colonization_observations.jsonl"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_STATE_DIR = _PROJECT_ROOT / "state"


@dataclass(frozen=True)
class PlanetObservation:
    """One observed reading of a single planet at a single visit.

    ``sector_id``/``planet_id`` together identify the physical planet. Most
    observations will key purely on ``sector_id`` with ``planet_id=None``.

    Production-related fields are optional — populated only when the capture
    loop actually read them from a planet screen. ``withdrawn_since_prior`` and
    ``production_bought_since_prior`` are operator-ledger facts between
    consecutive visits (``None`` = unknown).
    """

    sector_id: int
    timestamp: datetime
    planet_id: str | None = None
    planet_name: str | None = None
    stored_credits: float | None = None
    stored_cargo_units: int | None = None
    daily_production: float | None = None
    gf_count: int | None = None
    buy_production_price: float | None = None
    plague_loss_pct: float | None = None
    withdrawn_since_prior: bool | None = None
    production_bought_since_prior: bool | None = None


@dataclass(frozen=True)
class PlanetIdentity:
    sector_id: int
    planet_id: str | None


@dataclass(frozen=True)
class StoredCargoBonusEstimate:
    """Linear fit ``daily_production = intercept + bonus_per_unit * stored_cargo``.

    Canon hypothesis: bonus_per_unit ≈ 0.1 (one-tenth of stored cargo added to
    the daily production rate). ``sample_count`` is priced rows used."""

    identity: PlanetIdentity
    bonus_per_unit: float
    intercept: float
    sample_count: int
    evidence: tuple[tuple[int, float], ...]  # (stored_cargo_units, daily_production)
    tag: str = "observed_estimate"
    verified_vs_live: bool = False


@dataclass(frozen=True)
class CompoundingRateEstimate:
    """Average fractional growth per day of ``stored_cargo_units`` over
    trade-free pairs where stock rose."""

    identity: PlanetIdentity
    fraction_per_day: float
    sample_count: int
    evidence: tuple[tuple[datetime, datetime, float], ...]  # (t0, t1, fraction_per_day)
    tag: str = "observed_estimate"
    verified_vs_live: bool = False


@dataclass(frozen=True)
class BuyProductionThresholdEstimate:
    """Summary of observed ``buy_production_price`` readings.

    Canon hypothesis: worthwhile below ~9 credits/unit — this reports what was
    actually observed, not a confirmed threshold."""

    identity: PlanetIdentity
    median_price: float
    min_price: float
    max_price: float
    sample_count: int
    evidence: tuple[float, ...]
    tag: str = "observed_estimate"
    verified_vs_live: bool = False


@dataclass(frozen=True)
class PlagueBandEstimate:
    """Min/max of observed ``plague_loss_pct`` values."""

    identity: PlanetIdentity
    min_loss_pct: float
    max_loss_pct: float
    sample_count: int
    evidence: tuple[float, ...]
    tag: str = "observed_estimate"
    verified_vs_live: bool = False


@dataclass(frozen=True)
class GfGrowthEstimate:
    """Linear fit of observed GF/min against ``stored_credits`` at watch time.

    Canon hypothesis: ~1 GF/min at 100k credits scaling toward ~7 GF/min near
    1M — fit is over passive watch pairs the caller supplies."""

    identity: PlanetIdentity
    gf_per_min_at_zero_credits: float  # intercept
    gf_per_min_per_credit: float  # slope
    sample_count: int
    evidence: tuple[tuple[float, float], ...]  # (stored_credits, gf_per_min)
    tag: str = "observed_estimate"
    verified_vs_live: bool = False


@dataclass(frozen=True)
class PlanetColonizationReport:
    stored_cargo_bonus: dict[PlanetIdentity, StoredCargoBonusEstimate] = field(
        default_factory=dict
    )
    compounding: dict[PlanetIdentity, CompoundingRateEstimate] = field(default_factory=dict)
    buy_production: dict[PlanetIdentity, BuyProductionThresholdEstimate] = field(
        default_factory=dict
    )
    plague_band: dict[PlanetIdentity, PlagueBandEstimate] = field(default_factory=dict)
    gf_growth: dict[PlanetIdentity, GfGrowthEstimate] = field(default_factory=dict)


def _identity(obs: PlanetObservation) -> PlanetIdentity:
    return PlanetIdentity(sector_id=obs.sector_id, planet_id=obs.planet_id)


def _group(observations: Sequence[PlanetObservation]) -> dict[PlanetIdentity, list[PlanetObservation]]:
    grouped: dict[PlanetIdentity, list[PlanetObservation]] = {}
    for obs in observations:
        grouped.setdefault(_identity(obs), []).append(obs)
    for rows in grouped.values():
        rows.sort(key=lambda o: o.timestamp)
    return grouped


def _linear_fit(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float] | None:
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return None
    cov_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = cov_xy / var_x
    intercept = mean_y - slope * mean_x
    return slope, intercept


def estimate_stored_cargo_bonus(
    observations: Sequence[PlanetObservation],
) -> dict[PlanetIdentity, StoredCargoBonusEstimate]:
    """Per planet: fit daily production against stored cargo units.

    Identities with fewer than two rows bearing both fields, or with no
    spread in cargo levels, are omitted."""

    results: dict[PlanetIdentity, StoredCargoBonusEstimate] = {}
    for identity, rows in _group(observations).items():
        paired = [
            (int(o.stored_cargo_units), float(o.daily_production))
            for o in rows
            if o.stored_cargo_units is not None and o.daily_production is not None
        ]
        if len(paired) < 2:
            continue
        xs = [float(cargo) for cargo, _ in paired]
        ys = [prod for _, prod in paired]
        fit = _linear_fit(xs, ys)
        if fit is None:
            continue
        slope, intercept = fit
        results[identity] = StoredCargoBonusEstimate(
            identity=identity,
            bonus_per_unit=slope,
            intercept=intercept,
            sample_count=len(paired),
            evidence=tuple(paired),
        )
    return results


def estimate_compounding_rate(
    observations: Sequence[PlanetObservation],
) -> dict[PlanetIdentity, CompoundingRateEstimate]:
    """Per planet: average fractional stored-cargo growth per day over pairs
    explicitly marked untouched on the later row."""

    results: dict[PlanetIdentity, CompoundingRateEstimate] = {}
    for identity, rows in _group(observations).items():
        pair_rates: list[tuple[datetime, datetime, float]] = []
        for prior, current in zip(rows, rows[1:]):
            if current.withdrawn_since_prior is not False:
                continue
            if current.production_bought_since_prior is not False:
                continue
            if prior.stored_cargo_units is None or current.stored_cargo_units is None:
                continue
            if prior.stored_cargo_units <= 0:
                continue
            elapsed_days = (current.timestamp - prior.timestamp).total_seconds() / 86400.0
            if elapsed_days <= 0:
                continue
            stock_delta = current.stored_cargo_units - prior.stored_cargo_units
            if stock_delta <= 0:
                continue
            fraction_per_day = (stock_delta / prior.stored_cargo_units) / elapsed_days
            pair_rates.append((prior.timestamp, current.timestamp, fraction_per_day))
        if not pair_rates:
            continue
        avg_rate = sum(rate for _, _, rate in pair_rates) / len(pair_rates)
        results[identity] = CompoundingRateEstimate(
            identity=identity,
            fraction_per_day=avg_rate,
            sample_count=len(pair_rates),
            evidence=tuple(pair_rates),
        )
    return results


def estimate_buy_production_threshold(
    observations: Sequence[PlanetObservation],
) -> dict[PlanetIdentity, BuyProductionThresholdEstimate]:
    """Per planet: median/min/max of observed buy-production prices."""

    results: dict[PlanetIdentity, BuyProductionThresholdEstimate] = {}
    for identity, rows in _group(observations).items():
        prices = sorted(float(o.buy_production_price) for o in rows if o.buy_production_price is not None)
        if not prices:
            continue
        n = len(prices)
        mid = n // 2
        median = prices[mid] if n % 2 else (prices[mid - 1] + prices[mid]) / 2.0
        results[identity] = BuyProductionThresholdEstimate(
            identity=identity,
            median_price=median,
            min_price=prices[0],
            max_price=prices[-1],
            sample_count=n,
            evidence=tuple(prices),
        )
    return results


def estimate_plague_band(
    observations: Sequence[PlanetObservation],
) -> dict[PlanetIdentity, PlagueBandEstimate]:
    """Per planet: min/max plague loss pct from explicit event observations."""

    results: dict[PlanetIdentity, PlagueBandEstimate] = {}
    for identity, rows in _group(observations).items():
        losses = sorted(float(o.plague_loss_pct) for o in rows if o.plague_loss_pct is not None)
        if not losses:
            continue
        results[identity] = PlagueBandEstimate(
            identity=identity,
            min_loss_pct=losses[0],
            max_loss_pct=losses[-1],
            sample_count=len(losses),
            evidence=tuple(losses),
        )
    return results


def estimate_gf_growth_curve(
    observations: Sequence[PlanetObservation],
) -> dict[PlanetIdentity, GfGrowthEstimate]:
    """Per planet: linear fit of GF/min against stored credits from passive
    watch pairs (later row ``withdrawn_since_prior=False``)."""

    results: dict[PlanetIdentity, GfGrowthEstimate] = {}
    for identity, rows in _group(observations).items():
        rate_points: list[tuple[float, float]] = []
        for prior, current in zip(rows, rows[1:]):
            if current.withdrawn_since_prior is not False:
                continue
            if prior.gf_count is None or current.gf_count is None:
                continue
            if current.stored_credits is None:
                continue
            elapsed_min = (current.timestamp - prior.timestamp).total_seconds() / 60.0
            if elapsed_min <= 0:
                continue
            gf_delta = current.gf_count - prior.gf_count
            if gf_delta <= 0:
                continue
            gf_per_min = gf_delta / elapsed_min
            rate_points.append((float(current.stored_credits), gf_per_min))
        if len(rate_points) < 2:
            continue
        xs = [credits for credits, _ in rate_points]
        ys = [rate for _, rate in rate_points]
        fit = _linear_fit(xs, ys)
        if fit is None:
            continue
        slope, intercept = fit
        results[identity] = GfGrowthEstimate(
            identity=identity,
            gf_per_min_at_zero_credits=intercept,
            gf_per_min_per_credit=slope,
            sample_count=len(rate_points),
            evidence=tuple(rate_points),
        )
    return results


def analyze_planet_history(
    observations: Sequence[PlanetObservation],
) -> PlanetColonizationReport:
    """Convenience wrapper: all five estimators over the same observation set."""

    return PlanetColonizationReport(
        stored_cargo_bonus=estimate_stored_cargo_bonus(observations),
        compounding=estimate_compounding_rate(observations),
        buy_production=estimate_buy_production_threshold(observations),
        plague_band=estimate_plague_band(observations),
        gf_growth=estimate_gf_growth_curve(observations),
    )


def default_observations_path(state_dir: Path | str | None = None) -> Path:
    if state_dir is None:
        return _STATE_DIR / OBSERVATIONS_FILENAME
    base = Path(state_dir)
    if base.name == "world":
        return base.parent / OBSERVATIONS_FILENAME
    return base / OBSERVATIONS_FILENAME


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        ts = value
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        ts = datetime.fromisoformat(text)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)


def observation_to_dict(obs: PlanetObservation) -> dict:
    return {
        "sector_id": obs.sector_id,
        "timestamp": obs.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "planet_id": obs.planet_id,
        "planet_name": obs.planet_name,
        "stored_credits": obs.stored_credits,
        "stored_cargo_units": obs.stored_cargo_units,
        "daily_production": obs.daily_production,
        "gf_count": obs.gf_count,
        "buy_production_price": obs.buy_production_price,
        "plague_loss_pct": obs.plague_loss_pct,
        "withdrawn_since_prior": obs.withdrawn_since_prior,
        "production_bought_since_prior": obs.production_bought_since_prior,
    }


def observation_from_dict(payload: dict) -> PlanetObservation | None:
    try:
        sector_id = int(payload["sector_id"])
    except (KeyError, TypeError, ValueError):
        return None
    ts = _parse_timestamp(payload.get("timestamp"))
    if ts is None:
        return None
    planet_id = payload.get("planet_id")
    if planet_id is not None:
        planet_id = str(planet_id)
    planet_name = payload.get("planet_name")
    if planet_name is not None:
        planet_name = str(planet_name)
    return PlanetObservation(
        sector_id=sector_id,
        timestamp=ts,
        planet_id=planet_id,
        planet_name=planet_name,
        stored_credits=_optional_float(payload.get("stored_credits")),
        stored_cargo_units=_optional_int(payload.get("stored_cargo_units")),
        daily_production=_optional_float(payload.get("daily_production")),
        gf_count=_optional_int(payload.get("gf_count")),
        buy_production_price=_optional_float(payload.get("buy_production_price")),
        plague_loss_pct=_optional_float(payload.get("plague_loss_pct")),
        withdrawn_since_prior=_optional_bool(payload.get("withdrawn_since_prior")),
        production_bought_since_prior=_optional_bool(payload.get("production_bought_since_prior")),
    )


def load_observations(path: Path | str) -> list[PlanetObservation]:
    p = Path(path)
    if not p.is_file():
        return []
    out: list[PlanetObservation] = []
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            obs = observation_from_dict(payload)
            if obs is not None:
                out.append(obs)
    return out


def append_observations(path: Path | str, observations: Sequence[PlanetObservation]) -> int:
    rows = list(observations)
    if not rows:
        return 0
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for obs in rows:
            fh.write(json.dumps(observation_to_dict(obs), sort_keys=True) + "\n")
    return len(rows)


def observations_from_planet_record(
    sector_id: int,
    planet_dict: dict,
    *,
    withdrawn_since_prior: bool | None = None,
    production_bought_since_prior: bool | None = None,
    timestamp: datetime | None = None,
    planet_id: str | None = None,
) -> list[PlanetObservation]:
    """One :class:`PlanetObservation` from a planet record dict (future capture)."""

    if not isinstance(planet_dict, dict):
        return []
    ts = timestamp or _parse_timestamp(planet_dict.get("last_seen_ts"))
    if ts is None:
        ts = datetime.now(timezone.utc)
    pid = planet_id if planet_id is not None else planet_dict.get("planet_id")
    if pid is not None:
        pid = str(pid)
    pname = planet_dict.get("planet_name")
    if pname is not None:
        pname = str(pname)
    return [
        PlanetObservation(
            sector_id=int(sector_id),
            timestamp=ts,
            planet_id=pid,
            planet_name=pname,
            stored_credits=_optional_float(planet_dict.get("stored_credits")),
            stored_cargo_units=_optional_int(planet_dict.get("stored_cargo_units")),
            daily_production=_optional_float(planet_dict.get("daily_production")),
            gf_count=_optional_int(planet_dict.get("gf_count")),
            buy_production_price=_optional_float(planet_dict.get("buy_production_price")),
            plague_loss_pct=_optional_float(planet_dict.get("plague_loss_pct")),
            withdrawn_since_prior=withdrawn_since_prior,
            production_bought_since_prior=production_bought_since_prior,
        )
    ]


def observations_from_planet_dir(planet_dir: Path | str) -> list[PlanetObservation]:
    """Scan ``planets/*.json`` (or flat ``*.json``) for planet records."""

    root = Path(planet_dir)
    planets_sub = root / "planets"
    if planets_sub.is_dir():
        paths = sorted(planets_sub.glob("*.json"))
    else:
        paths = sorted(root.glob("*.json"))
    out: list[PlanetObservation] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if "planet" in payload and payload["planet"] is None:
            continue
        planet = payload.get("planet")
        if isinstance(planet, dict):
            record = planet
            try:
                sector_id = int(payload.get("sector_id", path.stem))
            except (TypeError, ValueError):
                continue
        elif isinstance(payload, dict) and "planet" not in payload:
            record = payload
            try:
                sector_id = int(record.get("sector_id", path.stem))
            except (TypeError, ValueError):
                continue
        else:
            continue
        out.extend(observations_from_planet_record(sector_id, record))
    return out
