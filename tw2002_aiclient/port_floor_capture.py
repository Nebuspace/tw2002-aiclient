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

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

__all__ = [
    "PortObservation",
    "PortIdentity",
    "RegrowthEstimate",
    "FloorPriceEstimate",
    "PortEconomicsReport",
    "analyze_port_history",
    "OBSERVATIONS_FILENAME",
    "default_observations_path",
    "observation_to_dict",
    "observation_from_dict",
    "load_observations",
    "append_observations",
    "observations_from_port_record",
    "observations_from_world_dir",
    "record_port_write",
]

# Sibling of ``state/world/`` when using the default layout; under a
# world_model ``state_dir`` override it lives inside that world-parent dir.
OBSERVATIONS_FILENAME = "port_floor_observations.jsonl"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_STATE_DIR = _PROJECT_ROOT / "state"


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


def default_observations_path(state_dir: Path | str | None = None) -> Path:
    """JSONL store path. ``state_dir`` matches ``world_model``'s override:
    the parent of per-world dirs (default ``state/world`` → store at
    ``state/port_floor_observations.jsonl``; test tmp world-parent →
    ``<tmp>/port_floor_observations.jsonl``)."""

    if state_dir is None:
        return _STATE_DIR / OBSERVATIONS_FILENAME
    base = Path(state_dir)
    # Default WORLD_DIR is ``state/world`` — keep the store next to ``world/``.
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


def observation_to_dict(obs: PortObservation) -> dict:
    return {
        "sector_id": obs.sector_id,
        "commodity": obs.commodity,
        "status": obs.status,
        "amount": obs.amount,
        "pct": obs.pct,
        "timestamp": obs.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "port_id": obs.port_id,
        "price_per_unit": obs.price_per_unit,
        "traded_since_prior": obs.traded_since_prior,
    }


def observation_from_dict(payload: dict) -> PortObservation | None:
    try:
        sector_id = int(payload["sector_id"])
        commodity = str(payload["commodity"])
        status = str(payload["status"])
        amount = int(payload["amount"])
        pct = int(payload["pct"])
    except (KeyError, TypeError, ValueError):
        return None
    ts = _parse_timestamp(payload.get("timestamp"))
    if ts is None:
        return None
    price = payload.get("price_per_unit")
    if price is not None:
        try:
            price = float(price)
        except (TypeError, ValueError):
            price = None
    traded = payload.get("traded_since_prior", None)
    if traded is not None:
        traded = bool(traded)
    port_id = payload.get("port_id")
    if port_id is not None:
        port_id = str(port_id)
    return PortObservation(
        sector_id=sector_id,
        commodity=commodity,
        status=status,
        amount=amount,
        pct=pct,
        timestamp=ts,
        port_id=port_id,
        price_per_unit=price,
        traded_since_prior=traded,
    )


def load_observations(path: Path | str) -> list[PortObservation]:
    p = Path(path)
    if not p.is_file():
        return []
    out: list[PortObservation] = []
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


def append_observations(path: Path | str, observations: Sequence[PortObservation]) -> int:
    """Append observations as JSONL. Returns count written. Creates parents."""

    rows = list(observations)
    if not rows:
        return 0
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for obs in rows:
            fh.write(json.dumps(observation_to_dict(obs), sort_keys=True) + "\n")
    return len(rows)


def observations_from_port_record(
    sector_id: int,
    port_dict: dict,
    *,
    traded_since_prior: bool | None = None,
    timestamp: datetime | None = None,
    port_id: str | None = None,
) -> list[PortObservation]:
    """One :class:`PortObservation` per commodity row with amount+pct."""

    ts = timestamp or _parse_timestamp(port_dict.get("last_seen_ts"))
    if ts is None:
        ts = datetime.now(timezone.utc)
    commodities = port_dict.get("commodities") or []
    out: list[PortObservation] = []
    if not isinstance(commodities, list):
        return out
    for row in commodities:
        if not isinstance(row, dict):
            continue
        try:
            name = str(row["name"])
            status = str(row["status"])
            amount = int(row["amount"])
            pct = int(row["pct"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append(
            PortObservation(
                sector_id=int(sector_id),
                commodity=name,
                status=status,
                amount=amount,
                pct=pct,
                timestamp=ts,
                port_id=port_id,
                traded_since_prior=traded_since_prior,
            )
        )
    return out


def observations_from_world_dir(world_dir: Path | str) -> list[PortObservation]:
    """Scan a world directory's ``sectors/*.json`` (or flat ``*.json``)."""

    root = Path(world_dir)
    sectors_dir = root / "sectors"
    if sectors_dir.is_dir():
        paths = sorted(sectors_dir.glob("*.json"))
    else:
        paths = sorted(root.glob("*.json"))
    out: list[PortObservation] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        port = payload.get("port")
        if not isinstance(port, dict):
            continue
        try:
            sector_id = int(payload.get("sector_id", path.stem))
        except (TypeError, ValueError):
            continue
        out.extend(observations_from_port_record(sector_id, port))
    return out


def record_port_write(
    sector_id: int,
    port_dict: dict,
    *,
    state_dir: Path | str | None = None,
    traded_since_prior: bool | None = None,
) -> int:
    """Best-effort append for world_model write hooks. Never raises."""

    try:
        if not isinstance(port_dict, dict):
            return 0
        commodities = port_dict.get("commodities") or []
        if not commodities:
            return 0
        obs = observations_from_port_record(
            sector_id,
            port_dict,
            traded_since_prior=traded_since_prior,
        )
        if not obs:
            return 0
        return append_observations(default_observations_path(state_dir), obs)
    except Exception:
        return 0
