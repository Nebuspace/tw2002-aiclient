"""Route-longevity / depletion predictor (canon port-economics H2).

Formula (hypothesis — verify before trust)::

    remaining_trades ≈ min(stock across the loop's buy/sell legs) ÷ hold_count

Leg stocks are observed commodity ``amount`` fields (never invented). Hold
count comes from live ship data (Game-Data / I-info), never hardcoded.

**Depletion is a STOP-guard / ranking / explore-appetite input — never an
autonomous loop rotation.** This module is pure: no sends, no arm, no
world-model I/O in the core formula helpers.
"""

from __future__ import annotations

import math
from typing import Mapping, Optional, Sequence

__all__ = [
    "DEPLETION_THRESHOLD_TRADES",
    "remaining_trades",
    "commodity_amount",
    "leg_stocks_for_hops",
    "predict_remaining_trades",
    "nearing_depletion",
    "depletion_signals",
    "rank_chains_by_longevity",
    "chain_identity_key",
]

# Canon: "as remaining_trades falls toward zero" — STOP/rank/appetite fire
# when predicted cycles drop below one full hold-fill trip.
DEPLETION_THRESHOLD_TRADES = 1.0


def commodity_amount(row: object) -> Optional[float]:
    """Tradeable units from a port commodity row; omit-until-known."""
    if not isinstance(row, Mapping):
        return None
    raw = row.get("amount")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        return None
    return value


def remaining_trades(
    leg_stocks: Sequence[object],
    hold_count: object,
) -> Optional[float]:
    """Canon H2 predictor. Fail-closed → ``None`` when inputs are incomplete.

    ``leg_stocks`` must be a non-empty sequence of non-negative finite
    amounts. ``hold_count`` must be a positive int (ship holds). Never
    invents stock or holds.
    """
    if isinstance(hold_count, bool) or not isinstance(hold_count, int):
        return None
    if hold_count <= 0:
        return None
    if not isinstance(leg_stocks, Sequence) or isinstance(leg_stocks, (str, bytes)):
        return None
    if len(leg_stocks) == 0:
        return None
    stocks: list[float] = []
    for item in leg_stocks:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        value = float(item)
        if not math.isfinite(value) or value < 0:
            return None
        stocks.append(value)
    return min(stocks) / float(hold_count)


def leg_stocks_for_hops(
    hops: Sequence[object],
    ports_by_sector: Mapping[int, Mapping[str, object]],
) -> Optional[tuple[float, ...]]:
    """Collect buy/sell ``amount`` stocks for each hop's commodity legs.

    Per hop (player buys at ``frm`` / sells at ``to``): include the selling
    port's amount at ``frm`` and the buying port's amount at ``to``. Missing
    sector, commodity, or amount → ``None`` (fail-closed; never invent).
    """
    if not hops:
        return None
    if not isinstance(ports_by_sector, Mapping):
        return None
    stocks: list[float] = []
    for hop in hops:
        try:
            frm = int(getattr(hop, "frm"))
            to = int(getattr(hop, "to"))
            commodity = getattr(hop, "commodity")
        except (AttributeError, TypeError, ValueError):
            return None
        if not isinstance(commodity, str) or not commodity.strip():
            return None
        frm_map = ports_by_sector.get(frm)
        to_map = ports_by_sector.get(to)
        if not isinstance(frm_map, Mapping) or not isinstance(to_map, Mapping):
            return None
        sell_amt = commodity_amount(frm_map.get(commodity))
        buy_amt = commodity_amount(to_map.get(commodity))
        if sell_amt is None or buy_amt is None:
            return None
        stocks.append(sell_amt)
        stocks.append(buy_amt)
    return tuple(stocks)


def predict_remaining_trades(
    chain: object,
    *,
    hold_count: object,
    ports_by_sector: Mapping[int, Mapping[str, object]],
) -> Optional[float]:
    """``remaining_trades`` for a ``ProfitChain``-like object (has ``.hops``)."""
    hops = getattr(chain, "hops", None)
    if hops is None:
        return None
    stocks = leg_stocks_for_hops(hops, ports_by_sector)
    if stocks is None:
        return None
    return remaining_trades(stocks, hold_count)


def nearing_depletion(
    remaining: object,
    *,
    threshold: float = DEPLETION_THRESHOLD_TRADES,
) -> bool:
    """True when a known prediction falls below the depletion threshold."""
    if isinstance(remaining, bool) or not isinstance(remaining, (int, float)):
        return False
    value = float(remaining)
    if not math.isfinite(value):
        return False
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        return False
    return value < float(threshold)


def depletion_signals(remaining: object) -> dict:
    """Status-shaped signals: STOP recommend, explore appetite, down-rank.

    Unknown ``remaining`` → all False / omit-friendly defaults (never invent
    a depletion crisis from absence).
    """
    near = nearing_depletion(remaining)
    out = {
        "nearing_depletion": near,
        "explore_appetite_raised": near,
        "stop_recommended": near,
    }
    if isinstance(remaining, bool) or not isinstance(remaining, (int, float)):
        return out
    value = float(remaining)
    if math.isfinite(value):
        out["remaining_trades"] = value
    return out


def chain_identity_key(chain: object) -> Optional[tuple]:
    """Stable key for ranking maps: closed sector cycle when present."""
    sectors = getattr(chain, "sectors", None)
    if isinstance(sectors, Sequence) and not isinstance(sectors, (str, bytes)):
        try:
            return tuple(int(s) for s in sectors)
        except (TypeError, ValueError):
            pass
    hops = getattr(chain, "hops", None)
    if not hops:
        return None
    try:
        return tuple((int(h.frm), int(h.to), str(h.commodity)) for h in hops)
    except (AttributeError, TypeError, ValueError):
        return None


def rank_chains_by_longevity(
    chains: Sequence[object],
    remaining_by_key: Mapping[object, object],
    *,
    base_rank: str = "discovery",
) -> list:
    """Down-rank chains nearing depletion; unknowns keep base order.

    Known remaining sorts descending (more trades left first). Chains with
    unknown remaining sort after known-fresh ones but before known-depleted
    ones only when their remaining is known-low — unknowns keep relative
    ``base_rank`` order among themselves and are not treated as depleted.

    ``base_rank``: ``\"discovery\"`` → hop-count then cr/turn;
    ``\"yield\"`` → cr/turn then hop-count.
    """
    items = [c for c in chains]
    if base_rank == "yield":
        items.sort(
            key=lambda c: (
                float(getattr(c, "cr_per_turn", 0.0) or 0.0),
                len(getattr(c, "hops", ()) or ()),
            ),
            reverse=True,
        )
    else:
        items.sort(
            key=lambda c: (
                len(getattr(c, "hops", ()) or ()),
                float(getattr(c, "cr_per_turn", 0.0) or 0.0),
            ),
            reverse=True,
        )

    def _sort_key(c: object, index: int) -> tuple:
        key = chain_identity_key(c)
        rem = remaining_by_key.get(key) if key is not None else None
        if key is not None and key not in remaining_by_key:
            # Also allow ProfitChain object identity keys callers may use.
            rem = remaining_by_key.get(c, rem)
        if isinstance(rem, bool) or not isinstance(rem, (int, float)):
            # Unknown: preserve base order via index; longevity tier = mid.
            return (1, 0.0, index)
        value = float(rem)
        if not math.isfinite(value):
            return (1, 0.0, index)
        if nearing_depletion(value):
            # Depleted / near: last tier, lower remaining later.
            return (2, -value, index)
        # Fresh known: first tier, more remaining first.
        return (0, -value, index)

    indexed = list(enumerate(items))
    indexed.sort(key=lambda pair: _sort_key(pair[1], pair[0]))
    return [c for _, c in indexed]


def ports_commodity_maps_from_records(
    records: Sequence[object],
) -> dict[int, dict[str, Mapping]]:
    """Build ``sector_id -> {commodity_name: row}`` from world-model-like recs.

    Never raises; skips malformed rows. Used by status/update callers that
    already hold query results.
    """
    out: dict[int, dict[str, Mapping]] = {}
    for rec in records:
        if not isinstance(rec, Mapping):
            continue
        port = rec.get("port")
        if not isinstance(port, Mapping):
            continue
        commodities = port.get("commodities")
        if not isinstance(commodities, list) or not commodities:
            continue
        try:
            sid = int(rec["sector_id"])
        except (KeyError, TypeError, ValueError):
            continue
        by_name: dict[str, Mapping] = {}
        for row in commodities:
            if not isinstance(row, Mapping):
                continue
            name = row.get("name")
            if not isinstance(name, str):
                continue
            by_name[name] = row
        if by_name:
            out[sid] = by_name
    return out
