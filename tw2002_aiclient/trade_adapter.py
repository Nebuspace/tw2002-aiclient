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
stock) -- it does NOT specify the interpolation shape, a ceiling
multiplier, or buy≠sell at the same pct. This module supplies those as
its OWN additional, equally unverified modeling choices: linear
interpolation from `floor` at `pct == 100` (fully stocked -- cheapest)
up to `floor * ceiling_multiplier` at `pct == 0` (nearly empty --
priciest), then a posture spread (`buy_sell_spread_of_floor`): the mid-
curve estimate is shifted down for a port `selling` row (player cost)
and up for a port `buying` row (player revenue) by ``floor * spread``.
Without that spread, Gather docks that stamp every row at `pct=100`
produce `margin == 0` forever and `chains.find_profit_chains` stays
empty. Every number here is a `TradeAdapterConfig` field, never a
hardcoded constant, so it can be corrected the moment live data
contradicts it.

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

Class-derived posture path (WO-CHAIN-DETECT-WIRE, DECISIONS.md "Pending
-- chain floors + class-derived posture"): the commodity/pct path above
requires a docked commerce-report `commodities` list this tree has no
producer for yet (see the module docstring's own note). `explore.py`'s
E2 flyby gate DOES persist a port's `class` letter-triple from a plain
sector-status line, turn-free, well before any commerce report exists.
`build_candidate_pairs` reads THAT signal instead and emits `CandidatePair`
-- a pair loop candidate carrying NO margin field at all (not `None`, not
`0.0` -- the field does not exist, so a caller cannot accidentally read a
guessed number out of it). This is a deliberately narrower shape than
`chains.TradeHop`, which canon (`trade-loops.md`) defines as a
*positive-margin* edge; a `CandidatePair` is never fed into `chains.py`'s
cycle search (which requires `margin`), and this module makes no attempt
to bridge the two.

Class-observation age caveat: the world-model schema (`world_model.py`)
stores exactly ONE `last_seen_ts` per port record, not one per sub-field.
A port visited again for an unrelated reason (e.g. `write_port_only`'s
docked-commerce write) re-stamps that single timestamp even though `class`
itself was NOT re-observed on that visit (`_merge_port`'s nested merge
preserves the old `class` value untouched). `CandidatePair.observed_age_s`
therefore reads as a proxy that can UNDERSTATE how old a class reading
truly is; it can never overstate it. Growing a dedicated per-sub-field
timestamp is a world_model schema change this WO does not make.
"""

from __future__ import annotations

import datetime
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional, Sequence

from tw2002_aiclient import world_model
from tw2002_aiclient.chains import TradeHop
from tw2002_aiclient.explore import known_graph
from tw2002_aiclient.formations import route_hazard_for_hop
from tw2002_aiclient.port_economics import (
    hypothesized_buy_sell_spread_of_floor,
    hypothesized_ceiling_multiplier,
    hypothesized_floor_prices,
)

# Pricing knobs — authored as HypothesisParam in port_economics (PWO-100).
# Re-exported here so existing TradeAdapterConfig / trade_driver call sites
# keep working; do not re-introduce silent floor/ceiling/spread literals.
DEFAULT_FLOOR_PRICES: Mapping[str, float] = hypothesized_floor_prices()
DEFAULT_CEILING_MULTIPLIER = hypothesized_ceiling_multiplier()
DEFAULT_BUY_SELL_SPREAD_OF_FLOOR = hypothesized_buy_sell_spread_of_floor()
DEFAULT_MAX_AGE_S = 3600.0  # drop a port reading older than this as stale (1h)
# Bounded edge-list ceiling (not a target truncation size). Live witness
# 2026-08-07 (WO-FIX-TRADE-ADAPTER-HOP-CAP-FOR-CHAIN-ARM): after #510 let
# explore fully map an academy-scale world (~70 commodity ports), priced
# candidates reached 1554 from 4992 compatible pairs. The prior ceiling of
# 500 returned a margin-ranked prefix with *no* closed cycle, so
# ``tw chains`` / ``trade_chain.start`` reported ``chain_discovery_partial``
# despite thousands of cycles existing once the full candidate set was
# searched. 5000 ≈ 3× that observed candidate count — headroom for denser
# maps without unbounded O(ports²) emission. Finder cost stays separately
# bounded by ``chains.DEFAULT_MAX_SEARCH_STEPS`` / daemon 500k deepen.
DEFAULT_MAX_HOPS = 5000
# Bounds expensive *route-search* work in build_trade_hops (one BFS per
# source sector). Caps OUTPUT separately via max_hops; this caps WORK
# before the full candidate list is routed (WO-CHAIN-WORK-BOUND).
DEFAULT_MAX_ROUTE_SEARCHES = 10_000
DEFAULT_AMOUNT_FLOOR = 1  # discovery-quality volume gate -- see TradeAdapterConfig.amount_floor

# Class-derived posture path (see module docstring). A class triple is
# STRUCTURAL -- it doesn't drift the way a commodity's `amount`/`pct` does
# absent port destruction -- so it gets its own, much longer, staleness
# ceiling rather than reusing DEFAULT_MAX_AGE_S (1h): "explore tonight, open
# the view tomorrow, get empty" would be wrong for data that doesn't decay
# on that timescale. 30 days is a deliberately generous default, not a
# claim about how often class actually changes.
DEFAULT_CLASS_MAX_AGE_S = 30 * 24 * 3600.0
# canon/strategy/port-economics.md: "first letter = Fuel Ore, second =
# Organics, third = Equipment" -- the ONE place that ordering is encoded.
CLASS_POSITIONS: tuple[str, ...] = ("Fuel Ore", "Organics", "Equipment")


@dataclass(frozen=True)
class TradeAdapterConfig:
    """Every pricing/staleness/bound knob this module uses -- all
    overridable, none hardcoded (port-economics.md's own "encode as
    configurable parameters, never hardcoded constants, until verified"
    instruction)."""

    floor_prices: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_FLOOR_PRICES))
    ceiling_multiplier: float = DEFAULT_CEILING_MULTIPLIER
    # UNVERIFIED: fraction of floor separating selling vs buying posture
    # estimates at the same pct. See module docstring / DEFAULT_*.
    buy_sell_spread_of_floor: float = DEFAULT_BUY_SELL_SPREAD_OF_FLOOR
    max_age_s: float = DEFAULT_MAX_AGE_S
    max_hops: int = DEFAULT_MAX_HOPS
    # Non-wall-clock budget: max number of one-source BFS route searches
    # build_trade_hops may run. Cheap status/amount/price filtering runs
    # first; routing is spent in margin order. 0 = zero route searches.
    max_route_searches: int = DEFAULT_MAX_ROUTE_SEARCHES
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
        if isinstance(self.max_hops, bool) or not isinstance(self.max_hops, int):
            raise TypeError(
                f"TradeAdapterConfig.max_hops must be int, got {type(self.max_hops).__name__}"
            )
        if self.max_hops < 0:
            raise ValueError(f"TradeAdapterConfig.max_hops must be >= 0, got {self.max_hops}")
        if isinstance(self.max_route_searches, bool) or not isinstance(
            self.max_route_searches, int
        ):
            raise TypeError(
                "TradeAdapterConfig.max_route_searches must be int, "
                f"got {type(self.max_route_searches).__name__}"
            )
        if self.max_route_searches < 0:
            raise ValueError(
                "TradeAdapterConfig.max_route_searches must be >= 0, "
                f"got {self.max_route_searches}"
            )
        # Module curve: floor at pct==100 → floor*ceiling_multiplier at pct==0.
        # Sub-unity inverts that (near-empty cheaper than near-full) — reject.
        if isinstance(self.ceiling_multiplier, bool) or not isinstance(
            self.ceiling_multiplier, (int, float)
        ):
            raise TypeError(
                "TradeAdapterConfig.ceiling_multiplier must be a real number, "
                f"got {type(self.ceiling_multiplier).__name__}"
            )
        if self.ceiling_multiplier < 1.0:
            raise ValueError(
                "TradeAdapterConfig.ceiling_multiplier must be >= 1.0, "
                f"got {self.ceiling_multiplier}"
            )
        if isinstance(self.buy_sell_spread_of_floor, bool) or not isinstance(
            self.buy_sell_spread_of_floor, (int, float)
        ):
            raise TypeError(
                "TradeAdapterConfig.buy_sell_spread_of_floor must be a real number, "
                f"got {type(self.buy_sell_spread_of_floor).__name__}"
            )
        if self.buy_sell_spread_of_floor < 0.0 or not math.isfinite(
            float(self.buy_sell_spread_of_floor)
        ):
            raise ValueError(
                "TradeAdapterConfig.buy_sell_spread_of_floor must be >= 0 and finite, "
                f"got {self.buy_sell_spread_of_floor}"
            )
        if isinstance(self.amount_floor, bool) or not isinstance(
            self.amount_floor, (int, float)
        ):
            raise TypeError(
                "TradeAdapterConfig.amount_floor must be a real number, "
                f"got {type(self.amount_floor).__name__}"
            )
        if isinstance(self.max_age_s, bool) or not isinstance(self.max_age_s, (int, float)):
            raise TypeError(
                "TradeAdapterConfig.max_age_s must be a real number, "
                f"got {type(self.max_age_s).__name__}"
            )
        for name, floor in self.floor_prices.items():
            if isinstance(floor, bool) or not isinstance(floor, (int, float)):
                raise TypeError(
                    f"TradeAdapterConfig.floor_prices[{name!r}] must be a real number, "
                    f"got {type(floor).__name__}"
                )


@dataclass(frozen=True)
class PairLoopConfig:
    """Knobs `build_candidate_pairs` uses -- deliberately its OWN config,
    not a reuse of `TradeAdapterConfig`: the class-derived path has no
    pricing model, no amount-floor (a class triple carries no volume
    figure to gate on), and a different staleness ceiling, so bolting
    those unrelated fields onto `TradeAdapterConfig` would let a caller
    set an `amount_floor` this path silently ignores."""

    class_max_age_s: float = DEFAULT_CLASS_MAX_AGE_S

    def __post_init__(self):
        if self.class_max_age_s < 0:
            raise ValueError(
                f"PairLoopConfig.class_max_age_s must be >= 0, got {self.class_max_age_s}"
            )


@dataclass(frozen=True)
class CandidatePair:
    """A class-derived pair-loop candidate: two ports whose BUY/SELL
    letter-triple postures are mutually complementary (`sector_a`
    SELLS every commodity in `commodities_a_sells`, which `sector_b`
    BUYS; `sector_b` SELLS every commodity in `commodities_b_sells`,
    which `sector_a` BUYS), with a known route both ways on the current
    warp graph. `sector_a < sector_b` always (construction order -- see
    `build_candidate_pairs`), giving every pair a canonical identity
    with no separate normalization step.

    Both commodity fields carry the FULL compatible set, never a
    single collapsed pick (Samantha REVISE, 2026-07-28: an earlier
    draft picked one commodity per direction via `min()` -- alphabetical
    order, which the draft's own comment called "a deterministic pick,
    never a value judgement," but alphabetical order (`Equipment, Fuel
    Ore, Organics`) disagrees with canon's stated floor-price ordering
    (`port-economics.md`: `Equipment(40) > Organics(30) > Fuel
    Ore(20)`) in the middle of the range -- a value judgement the
    comment denied making. Worse, collapsing to one commodity silently
    discarded whether a pair is compatible on one commodity or three --
    real, decision-relevant information: `port-economics.md`'s
    depletion STOP-guard means a pair that can trade three commodities
    each way survives the depletion of one, the single-commodity pair
    does not. Carrying the full set dissolves the tiebreak question
    entirely -- there is nothing to rank and nothing arbitrary to
    defend -- and keeps this margin-less path free of any dependency on
    canon's `[hypothesis]`-tagged economics ordering.) Ordered by
    `CLASS_POSITIONS` (structural class-triple position order -- Fuel
    Ore, Organics, Equipment; carries no economic ranking claim) purely
    for a deterministic, testable rendering order, never as a "best
    first" claim.

    Deliberately carries NO margin field -- not `None`, not `0.0`, the
    attribute does not exist -- because a bare class letter states a
    posture, never a price; see the module docstring's pricing-model
    note. Guessing a number here must be a structural impossibility,
    not merely a documented one.
    """

    sector_a: int
    sector_b: int
    commodities_a_sells: tuple[str, ...]  # sector_a SELLS all of these; sector_b BUYS them
    commodities_b_sells: tuple[str, ...]  # sector_b SELLS all of these; sector_a BUYS them
    turns: int  # round trip: sector_a -> sector_b -> sector_a, both legs summed
    observed_age_s: float  # age (seconds) of the STALER of the two ports' class reads


@dataclass(frozen=True)
class PairBuildStats:
    """Diagnostic counts from one `build_candidate_pairs` pass. Exists so
    a caller (`chain_detect.recompute`) can classify WHY the result is
    empty without a second world-model read -- `build_candidate_pairs`
    already walks every known sector once; re-deriving the same counts
    from a fresh read would be able to drift from what the pairing loop
    actually saw."""

    known_sectors: int  # every sector this world has ever recorded, any content
    class_valid_ports: int  # ports with a syntactically valid B/S triple, any age
    fresh_class_ports: int  # subset of the above within `class_max_age_s`
    oldest_class_age_s: Optional[float]  # max age among class_valid ports that passed fail-closed `_age_s` (never future/negative)
    compatible_pairs_considered: int  # posture-compatible among the FRESH set, before routing
    routed_pairs: int  # == len(the returned pairs tuple)


def _parse_ts(ts_str) -> Optional[datetime.datetime]:
    if not ts_str:
        return None
    try:
        return datetime.datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc
        )
    except (TypeError, ValueError):
        return None


def _age_s(ts_str, *, now: datetime.datetime) -> Optional[float]:
    """Fail-closed age in seconds from a `last_seen_ts` string.

    Returns ``None`` (never a negative float) when the stamp is absent,
    unparseable, or in the future. This is the **only** place in this
    module that computes ``(now - ts).total_seconds()`` for freshness /
    age decisions — ``_is_fresh`` and every aggregator read through it
    (WO-ADAPTER-FRESHNESS-SWEEP).
    """
    ts = _parse_ts(ts_str)
    if ts is None:
        return None
    age_s = (now - ts).total_seconds()
    if age_s < 0:
        return None
    return age_s


def _is_fresh(ts_str, *, max_age_s: float, now: datetime.datetime) -> bool:
    age_s = _age_s(ts_str, now=now)
    if age_s is None:
        return False  # fail-closed: absent / unparseable / future is never fresh
    return age_s <= max_age_s


def _commodity_price(
    row: Mapping,
    floor_prices: Mapping[str, float],
    ceiling_multiplier: float,
    buy_sell_spread_of_floor: float = 0.0,
) -> Optional[float]:
    """Estimated per-unit price from a commodity row's `pct`, via the
    linear floor->ceiling curve documented in the module docstring, then
    the UNVERIFIED posture spread when ``status`` is ``selling`` /
    ``buying``. `None` (never a guessed number) when the commodity has
    no configured floor price, or the row carries no usable `pct`."""
    name = row.get("name")
    pct = row.get("pct")
    floor = floor_prices.get(name)
    if floor is None or pct is None:
        return None
    # ``bool`` is an ``int`` subclass; ``float(True) == 1.0`` would pass
    # positivity/finite checks and invent a price from a flag.
    if isinstance(pct, bool) or isinstance(floor, bool):
        return None
    if isinstance(buy_sell_spread_of_floor, bool) or not isinstance(
        buy_sell_spread_of_floor, (int, float)
    ):
        return None
    try:
        pct_f = float(pct)
        floor_f = float(floor)
        spread_f = float(buy_sell_spread_of_floor)
    except (TypeError, ValueError):
        return None
    # cipher LOW/mack MEDIUM: NaN compares False against both bounds
    # below (max(0.0, min(100.0, nan)) silently becomes 100.0), and a
    # bare inf/-inf token is valid input to json.load -- a corrupted
    # sector JSON must not turn into a plausible-looking guessed price.
    if not math.isfinite(pct_f) or not math.isfinite(floor_f) or not math.isfinite(spread_f):
        return None
    if spread_f < 0.0:
        return None
    pct_clamped = max(0.0, min(100.0, pct_f))
    curve_spread = floor_f * (ceiling_multiplier - 1.0)
    mid = floor_f + curve_spread * (1.0 - pct_clamped / 100.0)
    delta = floor_f * spread_f
    status = row.get("status")
    if status == "selling":
        return mid - delta
    if status == "buying":
        return mid + delta
    return mid


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
    # ``bool`` is an ``int`` subclass; ``float(True) == 1.0`` would look
    # like a tradeable unit count.
    if isinstance(amount, bool):
        return False
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

    Expensive route search is separately bounded by
    `config.max_route_searches` (one multi-target BFS per source
    sector). Cheap status / amount / price filtering runs first;
    routing is spent in descending-margin order. When that work
    budget truncates discovery, the note says the search is
    incomplete -- absence of further hops is not established.

    Returns `(hops, note)`. `note` is `None` unless a cap truncated
    discovery or output -- this module has no logger of its own, so
    the caller/report is the channel."""
    cfg = config or TradeAdapterConfig()
    current = now() if now is not None else datetime.datetime.now(datetime.timezone.utc)

    ports = _fresh_ports(world_id, state_dir=state_dir, config=cfg, now=current)
    if len(ports) < 2:
        return (), None

    graph = known_graph(world_id, state_dir=state_dir)
    membership = _membership_index(world_id, state_dir=state_dir)
    threats_by_sector = _threats_index(world_id, state_dir=state_dir)
    commodity_maps = _commodity_maps(ports)

    # Phase 1 -- cheap filters only (no routing). Collect priced
    # compatible legs; margin is known without a path.
    priced: list[tuple[float, int, int, str]] = []
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

                frm_price = _commodity_price(
                    frm_row,
                    cfg.floor_prices,
                    cfg.ceiling_multiplier,
                    cfg.buy_sell_spread_of_floor,
                )
                to_price = _commodity_price(
                    to_row,
                    cfg.floor_prices,
                    cfg.ceiling_multiplier,
                    cfg.buy_sell_spread_of_floor,
                )
                if frm_price is None or to_price is None:
                    continue  # unpriced commodity/pct -- never a guessed margin

                priced.append((to_price - frm_price, frm, to, name))

    # Stable descending-margin order: ties keep discovery order so
    # repeated calls stay byte-identical.
    priced.sort(key=lambda row: row[0], reverse=True)

    # Phase 2 -- spend route-search budget (one BFS per source).
    paths_from: dict[int, dict[int, tuple[int, ...]]] = {}
    route_searches = 0
    route_truncated = False
    candidates: list[TradeHop] = []
    for margin, frm, to, name in priced:
        if frm not in paths_from:
            if route_searches >= cfg.max_route_searches:
                # Budget spent: skip legs that need a new source BFS, but
                # keep draining priced legs whose source was already paid.
                route_truncated = True
                continue
            paths_from[frm] = _bfs_paths_from(graph, frm)
            route_searches += 1
        path = paths_from[frm].get(to)
        if path is None:
            continue  # no known route -- fail-closed, no hop
        if _path_has_route_hazard(
            graph,
            path,
            membership=membership,
            threats_by_sector=threats_by_sector,
        ):
            continue  # shortest path is a route hazard — exclude, no detour
        turns = len(path) - 1  # path inclusive of both endpoints
        if turns <= 0:
            continue
        candidates.append(
            TradeHop(frm=frm, to=to, commodity=name, margin=margin, turns=turns)
        )

    hops = tuple(candidates[: cfg.max_hops])
    note = None
    if route_truncated:
        # Priced legs whose source was never BFS'd -- not yet searched.
        remaining = sum(1 for _m, f, _t, _n in priced if f not in paths_from)
        note = (
            f"trade_adapter: incomplete route search — "
            f"max_route_searches={cfg.max_route_searches} exhausted "
            f"({route_searches} source BFS; {len(candidates)} routed hops; "
            f"{remaining} priced candidates not searched; "
            f"absence of further hops is not established; "
            f"{considered} compatible pairs considered)"
        )
    elif len(candidates) > cfg.max_hops:
        note = (
            f"trade_adapter: capped at {cfg.max_hops} hops "
            f"({len(candidates)} candidates from {considered} compatible pairs considered)"
        )
    return hops, note


# --------------------------------------------------------------------------
# Class-derived posture path (WO-CHAIN-DETECT-WIRE) -- see module docstring.
# --------------------------------------------------------------------------


def _valid_class_triple(cls) -> bool:
    """`True` only for a genuine 3-letter buy/sell code (`state_parser`'s
    `_PORT_CLASS_RE` shape, upper-cased). A `Class 0`/StarDock flyby reads
    as present-but-classless (`class` absent or `None` on the stored
    record -- see `state_parser.read_port_from_sector_status`'s
    docstring), and a hand-corrupted or partially-written record could in
    principle carry any JSON scalar here -- never crash on either, just
    treat it as "no usable class"."""
    return isinstance(cls, str) and len(cls) == 3 and set(cls) <= {"B", "S"}


def _class_ports(
    world_id: str, *, state_dir
) -> dict[int, tuple[str, object]]:
    """sector_id -> (class_triple, raw `last_seen_ts`) for every sector
    whose port carries a syntactically valid class triple, at ANY age --
    staleness is `build_candidate_pairs`'s job, once it has every
    candidate's parsed age to classify with. Same skip-and-continue,
    isinstance/try-guarded discipline as `_fresh_ports` above: a
    malformed on-disk shape (non-dict `port`, non-numeric `sector_id`)
    is dropped, never raised."""
    recs = world_model.query(world_id, lambda s: bool(s.get("port")), state_dir=state_dir)
    ports: dict[int, tuple[str, object]] = {}
    for rec in recs:
        port = rec.get("port")
        if not isinstance(port, dict):
            continue
        cls = port.get("class")
        if not _valid_class_triple(cls):
            continue
        try:
            sector_id = int(rec["sector_id"])
        except (KeyError, TypeError, ValueError):
            continue
        ports[sector_id] = (cls, port.get("last_seen_ts"))
    return ports



def _membership_index(world_id: str, *, state_dir=None) -> dict[int, tuple[str, ...]]:
    """sector_id → formation_membership tags (empty when unset)."""
    out: dict[int, tuple[str, ...]] = {}
    for rec in world_model.all_sectors(world_id, state_dir=state_dir):
        tags = rec.get("formation_membership") or ()
        if tags:
            try:
                out[int(rec["sector_id"])] = tuple(str(t) for t in tags)
            except (KeyError, TypeError, ValueError):
                continue
    return out


def _threats_index(world_id: str, *, state_dir=None) -> dict[int, dict]:
    """sector_id → threats mapping (mines / fighters) for path exclude."""
    out: dict[int, dict] = {}
    for rec in world_model.all_sectors(world_id, state_dir=state_dir):
        threats = rec.get("threats")
        if isinstance(threats, dict):
            try:
                out[int(rec["sector_id"])] = threats
            except (KeyError, TypeError, ValueError):
                continue
    return out


def _path_has_route_hazard(
    graph: Mapping[int, Sequence[int]],
    path: Sequence[int],
    *,
    membership: Mapping[int, Sequence[str]] | None = None,
    threats_by_sector: Mapping[int, Mapping] | None = None,
) -> bool:
    """True when the planned shortest path crosses a known route hazard.

    WO-TRADE-HAZARD-PATH-EXCLUDE: exclude the hop/pair — never search an
    alternate path (canon Dual-consumer: STOP/exclude, not reroute).
    """
    for a, b in zip(path, path[1:]):
        if (
            route_hazard_for_hop(
                graph,
                a,
                b,
                membership=membership,
                threats_by_sector=threats_by_sector,
            )
            is not None
        ):
            return True
    return False


def _bfs_paths_from(
    graph: Mapping[int, Sequence[int]], start: int
) -> dict[int, tuple[int, ...]]:
    """Every sector reachable from `start` on the KNOWN (directed) warp
    graph, mapped to its shortest path -- `start` itself included, path
    tuples inclusive of both endpoints, same convention as
    `explore.path_to_sector`. Deliberately a single multi-target BFS
    rather than N calls to `explore.path_to_sector` (one per destination):
    the class-posture graph is ~58%-dense (`P(compatible) = 1-(3/4)**3`,
    unlike the sparse commodity graph three filters already cull before
    `build_trade_hops` ever routes), so routing every compatible pair via
    one BFS call apiece is an O(ports^2) BFS blowup this module must
    avoid. One BFS per source sector, memoized by the caller across every
    pair that shares that source, is O(ports) BFS total instead.

    Matches `path_to_sector`'s own reachability rule exactly (`nxt not in
    graph` is skipped, never stepped onto) so the two give identical
    answers for any `goal != start` where both are `in graph` -- pinned
    by a differential test, not merely asserted here."""
    if start not in graph:
        return {}
    paths: dict[int, tuple[int, ...]] = {start: (start,)}
    q: deque[int] = deque([start])
    while q:
        node = q.popleft()
        for nxt in graph.get(node, ()):
            if nxt in paths or nxt not in graph:
                continue
            paths[nxt] = paths[node] + (nxt,)
            q.append(nxt)
    return paths


def _observed_age_s(age_a: Optional[float], age_b: Optional[float]) -> Optional[float]:
    """The pair's reported class-observation age: the STALER (max) of the
    two ports' individually-computed ages. `None` -- never a fabricated
    or masked float -- when either input is missing or negative.

    Inputs must already be fail-closed ages from ``_age_s`` (or an
    equivalent that never yields a future/negative delta). Aggregation
    here deliberately does **not** invent ages from raw timestamps —
    that would reopen the laundering path where ``max(healthy, future)``
    looked like a normal one-hour reading (WO-ADAPTER-FRESHNESS-SWEEP /
    Samantha second-order finding on the #131 twin).

    Defense-in-depth: `build_candidate_pairs`'s `fresh` gate (via
    `_is_fresh`) should already exclude any future-stamped/corrupt-
    timestamp port, so in practice both inputs here are always real,
    non-negative floats. If that upstream gate is ever reopened by a
    future refactor, this guard is what stops a nonsense age from
    reaching a real `CandidatePair` -- and specifically stops the MASKING
    failure mode: `max(3600.0, -3600.0) == 3600.0` looks like a perfectly
    normal one-hour reading while silently hiding that the OTHER port's
    timestamp was garbage. A plausible wrong number is worse than an
    obviously wrong one -- treat EITHER input being negative as the whole
    result being unknown; never let the healthy side win `max()` and paper
    over the broken one."""
    if age_a is None or age_a < 0 or age_b is None or age_b < 0:
        return None
    return max(age_a, age_b)


def build_candidate_pairs(
    world_id: str,
    *,
    state_dir=None,
    config: Optional[PairLoopConfig] = None,
    now: Optional[Callable[[], datetime.datetime]] = None,
) -> tuple[tuple[CandidatePair, ...], PairBuildStats]:
    """Every class-derived pair-loop candidate currently discoverable
    from `world_id`'s world-model: two ports whose letter-triple
    postures are mutually complementary (set-intersection, never a
    cycle search -- see module docstring) with a known route both ways,
    built in ascending-`sector_a` order.

    Returns `(pairs, stats)` -- `stats` is unconditional (not only on
    empty) so `chain_detect.recompute` can classify a typed empty reason
    without a second world-model read. `pairs` is empty exactly when
    `stats.routed_pairs == 0`; every other `stats` field still describes
    what WAS found, so a caller can tell "never explored this world"
    from "explored plenty, nothing pairs up" from "pairs up, but no known
    route yet"."""
    cfg = config or PairLoopConfig()
    current = now() if now is not None else datetime.datetime.now(datetime.timezone.utc)

    # WO-WORLD-STATS-REFRESH-EVENTS B: count directory entries, do not
    # deep-copy every sector file. Deliberate behaviour change vs
    # `len(all_sectors(...))`: a corrupt JSON sibling that makes
    # `all_sectors` raise still contributes to this count (filename
    # stem is enough), and an unreadable sectors dir reports 0 here
    # rather than raising — `PairBuildStats.known_sectors` is an int.
    # `_class_ports` may still raise via `query`/`all_sectors`; that is
    # a separate path.
    count = world_model.known_sector_count(world_id, state_dir=state_dir)
    known_sectors = 0 if count is None else count
    raw_ports = _class_ports(world_id, state_dir=state_dir)

    # Ages are ONLY fail-closed `_age_s` results (None = absent / bad /
    # future). Never store a raw negative ``(now - ts)`` here — that value
    # must not participate in ``max``/pair aggregation (WO-ADAPTER-
    # FRESHNESS-SWEEP Accept: no age-aggregation laundering).
    ages: dict[int, Optional[float]] = {}
    fresh: dict[int, str] = {}
    for sid, (cls, ts_raw) in raw_ports.items():
        age = _age_s(ts_raw, now=current)
        ages[sid] = age
        if _is_fresh(ts_raw, max_age_s=cfg.class_max_age_s, now=current):
            fresh[sid] = cls

    # Aggregate only ages that already passed fail-closed parse (`_age_s`
    # returned a real non-negative float). Future stamps are ``None`` in
    # `ages` and cannot launder into ``oldest_class_age_s``.
    oldest_age = max((a for a in ages.values() if a is not None), default=None)

    if len(fresh) < 2:
        return (), PairBuildStats(
            known_sectors=known_sectors,
            class_valid_ports=len(raw_ports),
            fresh_class_ports=len(fresh),
            oldest_class_age_s=oldest_age,
            compatible_pairs_considered=0,
            routed_pairs=0,
        )

    graph = known_graph(world_id, state_dir=state_dir)
    membership = _membership_index(world_id, state_dir=state_dir)
    threats_by_sector = _threats_index(world_id, state_dir=state_dir)
    path_cache: dict[int, dict[int, tuple[int, ...]]] = {}

    def _paths_from(sector: int) -> dict[int, tuple[int, ...]]:
        if sector not in path_cache:
            path_cache[sector] = _bfs_paths_from(graph, sector)
        return path_cache[sector]

    sectors = sorted(fresh.keys())
    pairs: list[CandidatePair] = []
    considered = 0
    for i, sector_a in enumerate(sectors):
        cls_a = fresh[sector_a]
        sells_a = {name for name, letter in zip(CLASS_POSITIONS, cls_a) if letter == "S"}
        buys_a = {name for name, letter in zip(CLASS_POSITIONS, cls_a) if letter == "B"}
        for sector_b in sectors[i + 1 :]:
            cls_b = fresh[sector_b]
            sells_b = {name for name, letter in zip(CLASS_POSITIONS, cls_b) if letter == "S"}
            buys_b = {name for name, letter in zip(CLASS_POSITIONS, cls_b) if letter == "B"}

            # Perspective rule (canon, never inverted): sector_a SELLS what
            # sector_b BUYS, and independently sector_b SELLS what sector_a
            # BUYS. Two ports both selling (or both buying) the same
            # commodity are NOT a compatible pair on that leg -- fail-closed,
            # same invariant `build_trade_hops` already documents above.
            a_to_b = sells_a & buys_b
            b_to_a = sells_b & buys_a
            if not a_to_b or not b_to_a:
                continue
            considered += 1

            path_ab = _paths_from(sector_a).get(sector_b)
            path_ba = _paths_from(sector_b).get(sector_a)
            if path_ab is None or path_ba is None:
                continue  # compatible posture, no known route -- fail-closed, no pair
            if _path_has_route_hazard(
                graph,
                path_ab,
                membership=membership,
                threats_by_sector=threats_by_sector,
            ) or _path_has_route_hazard(
                graph,
                path_ba,
                membership=membership,
                threats_by_sector=threats_by_sector,
            ):
                continue  # shortest path is a route hazard — exclude, no detour
            turns = (len(path_ab) - 1) + (len(path_ba) - 1)
            if turns <= 0:
                continue

            # More than one commodity can qualify each direction (a port
            # selling several things the other buys) -- REVISE: carry the
            # FULL set, never collapse to one (see CandidatePair's own
            # docstring for why a single-pick tiebreak was wrong on two
            # counts). `CLASS_POSITIONS` order is structural, not economic,
            # and used only so the tuple has a deterministic, testable
            # order.
            commodities_a_sells = tuple(name for name in CLASS_POSITIONS if name in a_to_b)
            commodities_b_sells = tuple(name for name in CLASS_POSITIONS if name in b_to_a)
            # Both ages SHOULD always be real, non-negative floats here:
            # sector_a/sector_b are drawn from `sectors` = sorted(fresh.keys()),
            # and `fresh` only ever gains a key when `_is_fresh` returned
            # True (age in [0, max_age_s]) above. `_observed_age_s` is
            # nonetheless a defended, never-fabricate/never-mask helper --
            # see its own docstring -- so if that upstream invariant is ever
            # broken by a future refactor, this is what stops a nonsense
            # age from reaching a real `CandidatePair`, rather than
            # re-opening the exact masking failure Samantha found (REVISE,
            # 2026-07-28).
            observed_age_s = _observed_age_s(ages[sector_a], ages[sector_b])
            if observed_age_s is None:
                continue  # defense-in-depth -- see _observed_age_s's own docstring

            pairs.append(
                CandidatePair(
                    sector_a=sector_a,
                    sector_b=sector_b,
                    commodities_a_sells=commodities_a_sells,
                    commodities_b_sells=commodities_b_sells,
                    turns=turns,
                    observed_age_s=observed_age_s,
                )
            )

    stats = PairBuildStats(
        known_sectors=known_sectors,
        class_valid_ports=len(raw_ports),
        fresh_class_ports=len(fresh),
        oldest_class_age_s=oldest_age,
        compatible_pairs_considered=considered,
        routed_pairs=len(pairs),
    )
    return tuple(pairs), stats
