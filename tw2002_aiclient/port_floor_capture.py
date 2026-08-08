"""Port floor-price / regrowth-rate LIVE-DATA analysis (pure, no socket I/O).

Canon: ``canon/strategy/port-economics.md`` "Floor-price model (hypothesis)"
and "Route-longevity & depletion predictor" sections. That doc flags every
concrete floor/regrowth number as an **UNCONFIRMED HYPOTHESIS with zero code
backing** — the client observes only ``{name, status, amount, pct}`` per
commodity (``state_parser.parse_state`` / ``read_port_commerce_report``) plus
an occasional per-unit ``final_price`` from a completed haggle
(``session/haggle.py``'s ``final_price``). Nothing today turns *repeated*
observations of the *same* port over *time* into a measured estimate.

This module is that missing analysis step, and nothing more:

- **Pure functions over caller-supplied observations.** No socket, no
  live-send, no auto-visiting a port, no scheduling. A future capture loop
  (out of this module's scope) collects :class:`PortObservation` rows from
  repeated real visits and feeds them here.
- **Never fabricates a "real" number.** Every result carries
  ``tag="observed_estimate"`` and a ``sample_count`` / ``evidence`` trail so
  a caller can see exactly how thin (or synthetic) the backing data is. This
  module does not itself claim ``verified_vs_live=True`` for
  ``port_economics.py``'s hypothesis params — that flip is a live-prove
  decision made by whoever owns the capture loop, not by this analysis code.
- **Regrowth needs a trade-free window.** Amount/pct can rise either because
  the port is regrowing stock *or* because someone else traded against it in
  the sink direction — this module cannot distinguish the two from the
  numbers alone. It only computes a regrowth rate over an observation pair
  the caller explicitly marks ``traded_since_prior=False`` (the operator's
  own ledger knows whether *they* traded; a third-party trade on the same
  port is an unavoidable, documented residual noise source in the estimate).
- **Floor price needs a price observation.** ``amount``/``pct`` alone say
  nothing about credits/unit — only a haggle's ``final_price`` (or an
  equivalent future price-quote reader) does. This module fits price against
  ``pct`` and reports the fit's value at ``pct=100`` (canon's "the price a
  commodity's value decays toward as a port's stock fills") as the floor
  estimate; it never fabricates a price when none was observed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

__all__ = [
    "PortObservation",
    "PortIdentity",
    "RegrowthEstimate",
    "FloorPriceEstimate",
    "PortEconomicsReport",
    "analyze_port_history",
]


@dataclass(frozen=True)
class PortObservation:
    """One observed reading of a single commodity at a single port-visit.

    ``sector_id``/``port_id`` together identify the physical port; TW2002
    ports are conventionally addressed by their sector (``port_id`` is an
    optional secondary label for servers/tools that assign one — most
    observations will leave it ``None`` and key purely on ``sector_id``).

    ``price_per_unit`` is optional: it is only ever populated when a haggle
    round actually completed on this commodity at this visit
    (``haggle.py``'s ``final_price``); most visits will leave it ``None``.

    ``traded_since_prior`` is the operator's own ledger fact — whether *this*
    operator bought/sold this commodity at this port between the prior
    observation and this one. ``None`` means unknown; unknown pairs are
    excluded from the regrowth estimate rather than guessed.
    """

    sector_id: int
    commodity: str
    status: str
    amount: int
    pct: int
    timestamp: datetime
    port_id: str | None = None
    price_per_unit: float | None = None
    traded_since_prior: bool | None = None


@dataclass(frozen=True)
class PortIdentity:
    sector_id: int
    port_id: str | None
    commodity: str


@dataclass(frozen=True)
class RegrowthEstimate:
    """Observed pct-of-max recovered per real-time day, averaged over the
    trade-free pairs found. ``sample_count`` is the number of *pairs* (not
    observations) that contributed."""

    identity: PortIdentity
    pct_per_day: float
    sample_count: int
    evidence: tuple[tuple[datetime, datetime, float], ...]  # (t0, t1, pct_per_day) per pair
    tag: str = "observed_estimate"
    verified_vs_live: bool = False


@dataclass(frozen=True)
class FloorPriceEstimate:
    """Linear fit of ``price_per_unit`` against ``pct`` (0-100), evaluated at
    ``pct=100`` — canon's "the price a commodity's value decays toward as a
    port's stock fills". ``sample_count`` is the number of priced
    observations the fit used (minimum 2, distinct ``pct`` values required)."""

    identity: PortIdentity
    floor_price: float
    slope: float
    sample_count: int
    evidence: tuple[tuple[int, float], ...]  # (pct, price_per_unit) inputs to the fit
    tag: str = "observed_estimate"
    verified_vs_live: bool = False


@dataclass(frozen=True)
class PortEconomicsReport:
    regrowth: dict[PortIdentity, RegrowthEstimate] = field(default_factory=dict)
    floor_price: dict[PortIdentity, FloorPriceEstimate] = field(default_factory=dict)


def _identity(obs: PortObservation) -> PortIdentity:
    return PortIdentity(sector_id=obs.sector_id, port_id=obs.port_id, commodity=obs.commodity)


def _group(observations: Sequence[PortObservation]) -> dict[PortIdentity, list[PortObservation]]:
    grouped: dict[PortIdentity, list[PortObservation]] = {}
    for obs in observations:
        grouped.setdefault(_identity(obs), []).append(obs)
    for rows in grouped.values():
        rows.sort(key=lambda o: o.timestamp)
    return grouped


def estimate_regrowth_rate(
    observations: Sequence[PortObservation],
) -> dict[PortIdentity, RegrowthEstimate]:
    """Per (sector, port, commodity): average pct-of-max recovered per day,
    over consecutive-visit pairs explicitly marked ``traded_since_prior=False``
    on the later observation, where ``pct`` rose. Identities with zero
    qualifying pairs are omitted (never a fabricated zero)."""

    results: dict[PortIdentity, RegrowthEstimate] = {}
    for identity, rows in _group(observations).items():
        pair_rates: list[tuple[datetime, datetime, float]] = []
        for prior, current in zip(rows, rows[1:]):
            if current.traded_since_prior is not False:
                continue
            elapsed_days = (current.timestamp - prior.timestamp).total_seconds() / 86400.0
            if elapsed_days <= 0:
                continue
            pct_delta = current.pct - prior.pct
            if pct_delta <= 0:
                continue
            pair_rates.append((prior.timestamp, current.timestamp, pct_delta / elapsed_days))
        if not pair_rates:
            continue
        avg_rate = sum(rate for _, _, rate in pair_rates) / len(pair_rates)
        results[identity] = RegrowthEstimate(
            identity=identity,
            pct_per_day=avg_rate,
            sample_count=len(pair_rates),
            evidence=tuple(pair_rates),
        )
    return results


def _linear_fit(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float] | None:
    """Least-squares ``y = slope*x + intercept``. ``None`` if xs has no
    spread (a vertical/degenerate fit can't be evaluated)."""

    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return None
    cov_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = cov_xy / var_x
    intercept = mean_y - slope * mean_x
    return slope, intercept


def estimate_floor_price(
    observations: Sequence[PortObservation],
) -> dict[PortIdentity, FloorPriceEstimate]:
    """Per (sector, port, commodity): linear fit of observed
    ``price_per_unit`` against ``pct``, evaluated at ``pct=100``. Identities
    with fewer than two distinctly-priced, distinctly-``pct`` observations
    are omitted (never a fabricated floor from a single reading)."""

    results: dict[PortIdentity, FloorPriceEstimate] = {}
    for identity, rows in _group(observations).items():
        priced = [o for o in rows if o.price_per_unit is not None]
        if len(priced) < 2:
            continue
        xs = [float(o.pct) for o in priced]
        ys = [float(o.price_per_unit) for o in priced]
        fit = _linear_fit(xs, ys)
        if fit is None:
            continue
        slope, intercept = fit
        floor = slope * 100.0 + intercept
        results[identity] = FloorPriceEstimate(
            identity=identity,
            floor_price=floor,
            slope=slope,
            sample_count=len(priced),
            evidence=tuple((o.pct, float(o.price_per_unit)) for o in priced),  # type: ignore[arg-type]
        )
    return results


def analyze_port_history(observations: Sequence[PortObservation]) -> PortEconomicsReport:
    """Convenience wrapper: both estimates in one report over the same
    observation set."""

    return PortEconomicsReport(
        regrowth=estimate_regrowth_rate(observations),
        floor_price=estimate_floor_price(observations),
    )
