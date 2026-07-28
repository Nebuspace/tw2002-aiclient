"""trade_adapter -- world-model port records -> `chains.TradeHop`.

Pure logic: ZERO sends, ZERO execution. Reads `world_model`'s persisted
port records (canon shape `{class, commodities:[{name, status, amount,
pct}], last_seen_ts}` -- see world_model.py/state_parser.py) plus
`explore.py`'s known-warp-graph routing, and emits `chains.TradeHop`
edges so the chain-finder (`chains.find_profit_chains`/
`longest_profit_chain`) can discover real, currently-known profit loops
instead of only ever seeing an empty `hops` tuple. Wiring this output
into a live autopilot snapshot is a later WO's job, not this module's --
this file never imports session/protocol code or `adapters.py`, and
never touches the daemon-core.

Perspective landmine (pin this, never invert): a commodity row's
`status` is the PORT's own posture, not the player's. A hop buying
`commodity` at `frm` and selling it at `to` requires `frm`'s row
`status == "selling"` (the port SELLS to the player) AND `to`'s row
`status == "buying"` (the port BUYS from the player) for that SAME
commodity name. Two ports both "selling" (or both "buying") the same
commodity are NOT a compatible pair -- no hop, fail-closed.

Pricing model (see canon/strategy/port-economics.md): that doc is
explicitly UNVERIFIED against the live game, and only asserts (a) a
floor price exists per commodity and (b) a port's price sits somewhere
between that floor (near-full stock) and a higher price (near-empty
stock) -- it does NOT specify the interpolation shape or a ceiling
multiplier. This module supplies both as its OWN additional, equally
unverified modeling choice: linear interpolation from `floor` at
`pct == 100` (fully stocked -- cheapest) up to `floor * ceiling_multiplier`
at `pct == 0` (nearly empty -- priciest), applied identically regardless
of buying/selling posture -- a port's price moves toward its floor the
closer it sits to full stock, whichever direction the trade runs. Every
number here is a `TradeAdapterConfig` field, never a hardcoded constant,
so it can be corrected the moment live data contradicts it.

A future write-hook MAY someday attach a real observed unit price to a
port's commodity record (e.g. from a mid-haggle capture) -- no such
field exists in the canon port record shape today, so this module has
no read path for one; the pct-based estimate below is the only pricing
source until the schema grows one.

Amount-floor filter (hub-ruled): a leg's `amount` (the canon "Trading"
column -- tradeable units) must exceed `TradeAdapterConfig.amount_floor`
on BOTH sides, or no hop -- a selling port with (near-)zero amount has
nothing to sell, a buying port with (near-)zero amount wants nothing
bought, and either makes the loop a phantom. This is a discovery-quality
volume gate only (drops the obviously-impossible), NOT a substitute for
a future live, authoritative per-buy volume read at execution time.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional

from tw2002_aiclient import world_model
from tw2002_aiclient.chains import TradeHop
from tw2002_aiclient.explore import known_graph, path_to_sector

# port-economics.md's "Ore" is the same commodity state_parser._COMMODITIES
# spells out as "Fuel Ore" -- this maps the doc's name to the parser's.
DEFAULT_FLOOR_PRICES: Mapping[str, float] = {
    "Fuel Ore": 20.0,
    "Organics": 30.0,
    "Equipment": 40.0,
}
DEFAULT_CEILING_MULTIPLIER = 2.0  # this module's own interpolation choice -- UNVERIFIED, not from the doc
DEFAULT_MAX_AGE_S = 3600.0  # drop a port reading older than this as stale (1h)
DEFAULT_MAX_HOPS = 500  # bounded compute/output on a large known map
DEFAULT_AMOUNT_FLOOR = 1  # discovery-quality volume gate -- see TradeAdapterConfig.amount_floor


@dataclass(frozen=True)
class TradeAdapterConfig:
    """Every pricing/staleness/bound knob this module uses -- all
    overridable, none hardcoded (port-economics.md's own "encode as
    configurable parameters, never hardcoded constants, until verified"
    instruction)."""

    floor_prices: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_FLOOR_PRICES))
    ceiling_multiplier: float = DEFAULT_CEILING_MULTIPLIER
    max_age_s: float = DEFAULT_MAX_AGE_S
    max_hops: int = DEFAULT_MAX_HOPS
    # hub-ruled: discovery-quality volume gate, not a substitute for a
    # future live, authoritative per-buy volume read at execution time --
    # this only filters legs that are OBVIOUSLY impossible at discovery
    # time (a selling port with nothing to sell, a buying port that wants
    # nothing bought). Both `frm`'s selling-row amount AND `to`'s
    # buying-row amount must exceed this floor, or no hop.
    amount_floor: float = DEFAULT_AMOUNT_FLOOR

    def __post_init__(self):
        # mack LOW: a negative max_hops hits the `candidates[:max_hops]`
        # negative-slice footgun (drops the wrong end) -- fail loud at
        # construction, a config bug, not a per-tick data problem.
        if self.max_hops < 0:
            raise ValueError(f"TradeAdapterConfig.max_hops must be >= 0, got {self.max_hops}")


def _parse_ts(ts_str) -> Optional[datetime.datetime]:
    if not ts_str:
        return None
    try:
        return datetime.datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc
        )
    except (TypeError, ValueError):
        return None


def _is_fresh(ts_str, *, max_age_s: float, now: datetime.datetime) -> bool:
    ts = _parse_ts(ts_str)
    if ts is None:
        return False  # fail-closed: an absent/unparseable timestamp is never treated as fresh
    age_s = (now - ts).total_seconds()
    # Fail-closed on future stamps (clock skew / corrupt write): a negative
    # age would otherwise satisfy `<= max_age_s` and bypass the staleness gate.
    if age_s < 0:
        return False
    return age_s <= max_age_s


def _commodity_price(
    row: Mapping, floor_prices: Mapping[str, float], ceiling_multiplier: float
) -> Optional[float]:
    """Estimated per-unit price from a commodity row's `pct`, via the
    linear floor->ceiling curve documented in the module docstring.
    `None` (never a guessed number) when the commodity has no configured
    floor price, or the row carries no usable `pct`."""
    name = row.get("name")
    pct = row.get("pct")
    floor = floor_prices.get(name)
    if floor is None or pct is None:
        return None
    try:
        pct_f = float(pct)
    except (TypeError, ValueError):
        return None
    # cipher LOW/mack MEDIUM: NaN compares False against both bounds
    # below (max(0.0, min(100.0, nan)) silently becomes 100.0), and a
    # bare inf/-inf token is valid input to json.load -- a corrupted
    # sector JSON must not turn into a plausible-looking guessed price.
    if not math.isfinite(pct_f):
        return None
    pct_clamped = max(0.0, min(100.0, pct_f))
    spread = floor * (ceiling_multiplier - 1.0)
    return floor + spread * (1.0 - pct_clamped / 100.0)


def _has_tradeable_amount(row: Mapping, amount_floor: float) -> bool:
    """hub-ruled amount-floor filter: `row["amount"]` is the canon
    "Trading" column (tradeable units) -- a SELLING row with
    (near-)zero amount has nothing to sell (the player can't buy
    there), and a BUYING row with (near-)zero amount wants nothing
    bought (the player can't sell there); either makes the leg a
    phantom. Missing/non-numeric/non-finite `amount` is treated as 0
    (fail-closed, same discipline as `_commodity_price`'s pct
    handling) -- never a guessed volume."""
    amount = row.get("amount")
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(amount_f):
        return False
    return amount_f > amount_floor


def _fresh_ports(
    world_id: str, *, state_dir, config: TradeAdapterConfig, now: datetime.datetime
) -> dict[int, Mapping]:
    """sector_id -> port dict, for every sector with a non-empty,
    not-stale `commodities` reading. `world_model.query` is a good fit
    here -- it's exactly the "sectors matching a predicate" read path
    the module docstring describes, sparing a hand-rolled
    `all_sectors()` + filter loop.

    cipher: `query`'s own predicate only checks truthiness, so a
    malformed on-disk record (a `port` that isn't a dict, a
    `commodities` that isn't a list, a non-numeric `sector_id`) can
    still reach here -- every boundary below is isinstance/try-guarded
    and skip-and-continue for those shapes. **Non-integral** numeric
    `sector_id` values (e.g. ``10.9``) are different: ``int()`` would
    truncate and clobber sibling keys, so those raise ``ValueError``
    (WO-ADAPTER-SECTOR-ID-INTEGRAL) rather than silently map to ``10``.
    Other malformed shapes still fail-closed without crashing the tick."""
    recs = world_model.query(world_id, lambda s: bool(s.get("port")), state_dir=state_dir)
    ports: dict[int, Mapping] = {}
    for rec in recs:
        port = rec.get("port")
        if not isinstance(port, dict):
            continue
        commodities = port.get("commodities")
        if not isinstance(commodities, list) or not commodities:
            continue
        if not _is_fresh(port.get("last_seen_ts"), max_age_s=config.max_age_s, now=now):
            continue
        sector_id = _require_integral_sector_id(rec.get("sector_id"))
        if sector_id is None:
            continue
        ports[sector_id] = port
    return ports


def _require_integral_sector_id(raw) -> Optional[int]:
    """Parse ``sector_id`` without truncating non-integral values.

    Returns ``None`` for absent/non-numeric values (caller skips).
    Raises ``ValueError`` when the value is numeric but not integral
    (e.g. ``10.9``), because ``int(10.9) == 10`` would silently clobber.
    Integral floats like ``10.0`` are accepted as ``10``.
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        # ``bool`` is an ``int`` subclass; never treat True/False as sectors.
        return None
    if isinstance(raw, int):
        return raw
    try:
        as_float = float(raw)
    except (TypeError, ValueError):
        return None
    if not as_float.is_integer():
        raise ValueError(
            f"non-integral sector_id {raw!r} (refusing truncate-to-{int(as_float)})"
        )
    return int(as_float)


def _commodity_maps(ports: Mapping[int, Mapping]) -> dict[int, dict]:
    """sector_id -> {commodity_name: row}, precomputed ONCE per port
    (cipher MEDIUM: rebuilding this dict on every (frm, to) pair inside
    an O(ports^2) loop measured at ~3.2s for 1000 ports -- precomputing
    outside that loop is a pure perf fix, no behavior change). Also
    where the isinstance guard on individual `commodities` ROWS lives --
    a non-dict row is skipped here, once, rather than re-checked on
    every pair."""
    out: dict[int, dict] = {}
    for sid, port in ports.items():
        by_name: dict = {}
        for row in port.get("commodities", []):
            if not isinstance(row, dict):
                continue
            name = row.get("name")
            # cipher re-verify: a dict row whose `name` value is itself
            # a list/dict is unhashable -- `by_name[name] = row` would
            # raise TypeError before this guard existed. Same skip-and-
            # continue discipline as every other malformed-shape guard.
            if not isinstance(name, str):
                continue
            by_name[name] = row
        out[sid] = by_name
    return out


def build_trade_hops(
    world_id: str,
    *,
    state_dir=None,
    config: Optional[TradeAdapterConfig] = None,
    now: Optional[Callable[[], datetime.datetime]] = None,
) -> tuple[tuple[TradeHop, ...], Optional[str]]:
    """The adapter's one entry point: every direction-compatible,
    routable, priced hop currently discoverable from `world_id`'s
    world-model, ranked by margin and capped at `config.max_hops`.

    Returns `(hops, note)`. `note` is `None` unless the cap truncated
    the candidate list, in which case it names how many hops were
    dropped -- this module has no logger of its own, so the caller/
    report is the channel."""
    cfg = config or TradeAdapterConfig()
    current = now() if now is not None else datetime.datetime.now(datetime.timezone.utc)

    ports = _fresh_ports(world_id, state_dir=state_dir, config=cfg, now=current)
    if len(ports) < 2:
        return (), None

    graph = known_graph(world_id, state_dir=state_dir)
    route_cache: dict[tuple[int, int], Optional[tuple[int, ...]]] = {}

    def _route(frm: int, to: int) -> Optional[tuple[int, ...]]:
        key = (frm, to)
        if key not in route_cache:
            route_cache[key] = path_to_sector(graph, frm, to)
        return route_cache[key]

    commodity_maps = _commodity_maps(ports)

    candidates: list[TradeHop] = []
    considered = 0
    for frm, frm_by_name in commodity_maps.items():
        for to, to_by_name in commodity_maps.items():
            if frm == to:
                continue
            for name, frm_row in frm_by_name.items():
                # Perspective landmine, pinned: frm SELLS (player buys
                # here) and to BUYS (player sells there) -- never invert.
                if frm_row.get("status") != "selling":
                    continue
                to_row = to_by_name.get(name)
                if to_row is None or to_row.get("status") != "buying":
                    continue
                considered += 1

                if not _has_tradeable_amount(frm_row, cfg.amount_floor) or not _has_tradeable_amount(
                    to_row, cfg.amount_floor
                ):
                    continue  # phantom leg -- (near-)zero stock on one side, fail-closed

                path = _route(frm, to)
                if path is None:
                    continue  # no known route -- fail-closed, no hop
                turns = len(path) - 1  # path is INCLUSIVE of both endpoints -- see explore.path_to_sector
                if turns <= 0:
                    continue

                frm_price = _commodity_price(frm_row, cfg.floor_prices, cfg.ceiling_multiplier)
                to_price = _commodity_price(to_row, cfg.floor_prices, cfg.ceiling_multiplier)
                if frm_price is None or to_price is None:
                    continue  # unpriced commodity/pct -- never a guessed margin

                candidates.append(
                    TradeHop(frm=frm, to=to, commodity=name, margin=to_price - frm_price, turns=turns)
                )

    candidates.sort(key=lambda h: h.margin, reverse=True)
    hops = tuple(candidates[: cfg.max_hops])
    note = None
    if len(candidates) > cfg.max_hops:
        note = (
            f"trade_adapter: capped at {cfg.max_hops} hops "
            f"({len(candidates)} candidates from {considered} compatible pairs considered)"
        )
    return hops, note
