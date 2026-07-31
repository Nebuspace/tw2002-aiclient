"""trade_adapter tests -- synthetic world-model fixtures only, no live
daemon, no network (same tmp_path/state_dir convention as world_model's
own tests).

Ported onto `tw2002_aiclient.trade_adapter` (ADR-001: one import tree,
`twclient` is gone).
"""

import ast
import datetime
import json
from pathlib import Path
from typing import Optional

import pytest

from tw2002_aiclient import trade_adapter, world_model
from tw2002_aiclient.chains import find_profit_chains, longest_profit_chain

WORLD = "hostA__F__ALPHA"

_CLOCK = lambda: datetime.datetime(2026, 7, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _upsert(tmp_path, sector_id, *, warps=(), commodities=None, port_ts_clock=_CLOCK):
    record = {"sector_id": sector_id, "warps": list(warps)}
    if commodities is not None:
        record["port"] = {
            "commodities": commodities,
            "last_seen_ts": world_model._now_iso(port_ts_clock),
        }
    world_model.upsert_sector(WORLD, record, state_dir=tmp_path, now=port_ts_clock)


def _row(name, status, pct, amount=1000):
    return {"name": name, "status": status, "amount": amount, "pct": pct}


def _upsert_class(tmp_path, sector_id, *, warps=(), klass=None, port_ts_clock=_CLOCK):
    """Like `_upsert`, but writes the class-derived posture shape
    (`{"class": ..., "last_seen_ts": ...}`, NO `commodities`) --
    `explore.py`'s E2 flyby gate writes exactly this shape (see
    `state_parser.read_port_from_sector_status`), never a commerce
    report. `klass=None` writes a warps-only sector with no port field
    at all (mirrors a plain movement observation)."""
    record = {"sector_id": sector_id, "warps": list(warps)}
    if klass is not None:
        record["port"] = {"class": klass, "last_seen_ts": world_model._now_iso(port_ts_clock)}
    world_model.upsert_sector(WORLD, record, state_dir=tmp_path, now=port_ts_clock)


def _write_raw_sector(tmp_path, sector_id, record):
    """Writes a raw sector JSON file directly, bypassing `upsert_sector`'s
    own field-level merge entirely -- the only way to construct a
    genuinely malformed on-disk shape (a non-dict `port`, a non-list
    `commodities`, a mismatched-type `sector_id` field) for the
    fail-closed/isinstance-guard tests below. `_load_sector_file` only
    requires the top-level JSON be an object with a `sector_id` key --
    it never validates the SHAPE of any nested field, so this is a
    legitimate on-disk state, not an artificial test-only shortcut."""
    path = world_model._sector_path(WORLD, sector_id, state_dir=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f)


# -- (1) direction-compatible pair: hand-computed margins + known-best chain -


def test_direction_compatible_pair_hand_computed_margins_and_best_chain(tmp_path):
    # Sector 10 sells Equipment (cheap, full stock) and buys Fuel Ore
    # (best price, empty stock). Sector 11 is the mirror image.
    _upsert(
        tmp_path,
        10,
        warps=(11,),
        commodities=[_row("Equipment", "selling", 100), _row("Fuel Ore", "buying", 0)],
    )
    _upsert(
        tmp_path,
        11,
        warps=(10,),
        commodities=[_row("Fuel Ore", "selling", 100), _row("Equipment", "buying", 0)],
    )

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert note is None
    by_key = {(h.frm, h.to, h.commodity): h for h in hops}
    # Equipment floor 40, default spread 0.05 → delta 2:
    # selling@pct100 mid 40 → 38; buying@pct0 mid 80 → 82 → margin 44.
    assert by_key[(10, 11, "Equipment")].margin == 44.0
    assert by_key[(10, 11, "Equipment")].turns == 1
    # Fuel Ore floor 20, delta 1: selling@100 → 19; buying@0 → 41 → margin 22.
    assert by_key[(11, 10, "Fuel Ore")].margin == 22.0
    assert by_key[(11, 10, "Fuel Ore")].turns == 1
    assert len(hops) == 2

    chain = longest_profit_chain(hops)
    assert chain is not None
    assert chain.overall_profit == 66.0
    assert chain.turns == 2
    assert chain.cr_per_turn == 33.0
    assert set(chain.sectors) == {10, 11}


# -- (2) perspective landmine: both-selling (or both-buying) -> zero hops --


def test_both_ports_selling_same_commodity_yields_zero_hops(tmp_path):
    _upsert(tmp_path, 20, warps=(21,), commodities=[_row("Equipment", "selling", 100)])
    _upsert(tmp_path, 21, warps=(20,), commodities=[_row("Equipment", "selling", 50)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()
    assert note is None


def test_both_ports_buying_same_commodity_yields_zero_hops(tmp_path):
    _upsert(tmp_path, 22, warps=(23,), commodities=[_row("Organics", "buying", 100)])
    _upsert(tmp_path, 23, warps=(22,), commodities=[_row("Organics", "buying", 50)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


def test_perspective_landmine_pinned_frm_sells_to_buys_never_inverted(tmp_path):
    """DoD accept 3: explicitly pins the direction -- `frm` must be the
    SELLING sector, `to` the BUYING sector. Deliberately asymmetric (only
    one warp direction, only one commodity, only one compatible pair) so
    a status-check swap in the implementation (checking `frm` for
    "buying" and `to` for "selling") flips this from one hop to zero,
    rather than merely relabeling an existing hop -- mutate-proven to go
    RED, see report."""
    _upsert(tmp_path, 200, warps=(201,), commodities=[_row("Equipment", "selling", 100)])
    _upsert(tmp_path, 201, warps=(200,), commodities=[_row("Equipment", "buying", 0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert len(hops) == 1
    hop = hops[0]
    assert hop.frm == 200  # the SELLING sector -- player buys here
    assert hop.to == 201  # the BUYING sector -- player sells here


# -- (3) missing/unrecognized status or commodity -> fail-closed, zero hops -


def test_missing_status_field_yields_zero_hops(tmp_path):
    malformed_row = {"name": "Equipment", "amount": 500, "pct": 100}  # no "status" key at all
    _upsert(tmp_path, 30, warps=(31,), commodities=[malformed_row])
    _upsert(tmp_path, 31, warps=(30,), commodities=[_row("Equipment", "buying", 0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


def test_unrecognized_commodity_name_yields_zero_hops(tmp_path):
    """No configured floor price -> `_commodity_price` returns None ->
    never a guessed margin."""
    _upsert(tmp_path, 32, warps=(33,), commodities=[_row("Space Yeast", "selling", 100)])
    _upsert(tmp_path, 33, warps=(32,), commodities=[_row("Space Yeast", "buying", 0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


# -- no known route between two otherwise-compatible ports -> no hop -------


def test_no_known_route_yields_no_hop(tmp_path):
    _upsert(tmp_path, 40, warps=(), commodities=[_row("Equipment", "selling", 100)])
    _upsert(tmp_path, 41, warps=(), commodities=[_row("Equipment", "buying", 0)])  # no warp linking them

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


def test_route_through_unvisited_frontier_sector_yields_no_hop(tmp_path):
    """Distinct from the case above: `path_to_sector`'s BFS only steps
    into a warp target that is ITSELF a known sector (present as a key
    in the graph, i.e. previously visited/recorded) -- a warp pointing at
    an unvisited sector is a frontier edge, not a route. Sectors 150 and
    151 both warp toward 999, but 999 is never upserted here, so it is
    not in `known_graph`'s output at all. Even though the live game may
    well connect 150 to 151 through 999, this trainer has never observed
    that path, so it must not be invented -- offering a hop the ship
    can't actually fly would be worse than offering none."""
    _upsert(tmp_path, 150, warps=(999,), commodities=[_row("Equipment", "selling", 100)])
    _upsert(tmp_path, 151, warps=(999,), commodities=[_row("Equipment", "buying", 0)])
    # Sector 999 itself is deliberately never upserted -- unvisited.

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


# -- (4) multi-hop fixture: proves the len-1 off-by-one -------------------


def test_multi_hop_turns_is_path_length_minus_one(tmp_path):
    # 1 -> 2 -> 3, directed; sector 2 carries no port of its own, just
    # routes through it -- proves turns counts WARPS, not sectors-visited,
    # and pins `path_to_sector`'s "inclusive of both endpoints" contract:
    # a 3-sector path is 2 turns, not 3.
    _upsert(tmp_path, 1, warps=(2,), commodities=[_row("Equipment", "selling", 100)])
    _upsert(tmp_path, 2, warps=(3,))
    _upsert(tmp_path, 3, warps=(), commodities=[_row("Equipment", "buying", 0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert len(hops) == 1
    hop = hops[0]
    assert (hop.frm, hop.to, hop.commodity) == (1, 3, "Equipment")
    assert hop.turns == 2  # path (1, 2, 3) has 3 sectors, 2 warps -- NOT 3


# -- (5) stale-past-cutoff port reading is dropped --------------------------


def test_stale_port_reading_is_dropped(tmp_path):
    stale_clock = lambda: datetime.datetime(2026, 7, 20, 10, 0, 0, tzinfo=datetime.timezone.utc)
    later = lambda: datetime.datetime(2026, 7, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)  # +2h
    _upsert(
        tmp_path, 50, warps=(51,), commodities=[_row("Equipment", "selling", 100)], port_ts_clock=stale_clock
    )
    _upsert(
        tmp_path, 51, warps=(50,), commodities=[_row("Equipment", "buying", 0)], port_ts_clock=stale_clock
    )

    cfg = trade_adapter.TradeAdapterConfig(max_age_s=60.0)  # 1 minute -- 2h-old reading is well past it
    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, config=cfg, now=later)

    assert hops == ()


def test_fresh_port_reading_within_max_age_is_kept(tmp_path):
    """Sanity counterpart to the stale test above -- the freshness gate
    doesn't drop everything, just genuinely stale readings."""
    _upsert(tmp_path, 52, warps=(53,), commodities=[_row("Equipment", "selling", 100)])
    _upsert(tmp_path, 53, warps=(52,), commodities=[_row("Equipment", "buying", 0)])

    cfg = trade_adapter.TradeAdapterConfig(max_age_s=60.0)
    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK)

    assert len(hops) == 1


def test_future_last_seen_ts_is_rejected(tmp_path):
    """WO-ADAPTER-FRESHNESS-FUTURE-TS: a future stamp must fail-closed.
    Negative `(now - ts)` would otherwise pass `<= max_age_s`."""
    future_clock = lambda: datetime.datetime(2099, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    _upsert(
        tmp_path,
        54,
        warps=(55,),
        commodities=[_row("Equipment", "selling", 100)],
        port_ts_clock=future_clock,
    )
    _upsert(
        tmp_path,
        55,
        warps=(54,),
        commodities=[_row("Equipment", "buying", 0)],
        port_ts_clock=future_clock,
    )

    cfg = trade_adapter.TradeAdapterConfig(max_age_s=60.0)
    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK)

    assert hops == ()
    assert trade_adapter._is_fresh(
        world_model._now_iso(future_clock), max_age_s=60.0, now=_CLOCK()
    ) is False


@pytest.mark.parametrize("age_s,expected", [(-1.0, False), (0.0, True), (100.0, True), (100.1, False)])
def test_is_fresh_boundary_including_future_timestamps(age_s, expected):
    """#131 WO-ADAPTER-FRESHNESS-FUTURE-TS. Direct unit coverage of the
    predicate's exact boundary, independent of either caller -- neither
    `test_future_last_seen_ts_is_rejected` above nor
    `test_commodity_path_future_stamped_port_is_never_treated_as_fresh`
    below exercises the `<=` edge itself (`100.0` true vs `100.1` false),
    only the far future/negative case. `age_s=-1.0` (a future/clock-skewed
    timestamp) must fail closed, not satisfy `<= max_age_s` unconditionally."""
    now = _CLOCK()
    ts_str = trade_adapter.world_model._now_iso(lambda: now - datetime.timedelta(seconds=age_s))
    assert trade_adapter._is_fresh(ts_str, max_age_s=100.0, now=now) is expected


def test_commodity_path_future_stamped_port_is_never_treated_as_fresh(tmp_path):
    """Asymmetric case neither sibling test above covers: only ONE side
    of the pair (sector 60) carries a future stamp, the other (61) is
    stamped normally. Proves a single corrupt/future timestamp is enough
    to fail the WHOLE pair, not just the "both sides future" case
    `test_future_last_seen_ts_is_rejected` exercises."""
    future_clock = lambda: _CLOCK() + datetime.timedelta(hours=1)
    _upsert(
        tmp_path, 60, warps=(61,), commodities=[_row("Equipment", "selling", 100)], port_ts_clock=future_clock
    )
    _upsert(tmp_path, 61, warps=(60,), commodities=[_row("Equipment", "buying", 0)])

    cfg = trade_adapter.TradeAdapterConfig(max_age_s=3600.0 * 24)  # generous -- only the FUTURE stamp should fail
    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK)

    assert hops == ()


def test_absent_last_seen_ts_yields_no_hop(tmp_path):
    """An absent/unparseable timestamp is never treated as fresh
    (`_is_fresh`'s explicit fail-closed contract) -- a raw sector whose
    port has no `last_seen_ts` key at all must drop, not default-pass."""
    _write_raw_sector(
        tmp_path,
        98,
        {
            "sector_id": 98,
            "warps": [99],
            "port": {"commodities": [_row("Equipment", "selling", 100)]},  # no last_seen_ts
        },
    )
    _upsert(tmp_path, 99, warps=(98,), commodities=[_row("Equipment", "buying", 0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


def test_unparseable_last_seen_ts_yields_no_hop(tmp_path):
    _write_raw_sector(
        tmp_path,
        100,
        {
            "sector_id": 100,
            "warps": [101],
            "port": {
                "commodities": [_row("Equipment", "selling", 100)],
                "last_seen_ts": "not-a-timestamp",
            },
        },
    )
    _upsert(tmp_path, 101, warps=(100,), commodities=[_row("Equipment", "buying", 0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


# -- (6) hop-cap truncates + notes ------------------------------------------


def test_hop_cap_truncates_and_reports_a_note(tmp_path):
    _upsert(
        tmp_path,
        60,
        warps=(61,),
        commodities=[_row("Equipment", "selling", 100), _row("Fuel Ore", "buying", 0)],
    )
    _upsert(
        tmp_path,
        61,
        warps=(60,),
        commodities=[_row("Fuel Ore", "selling", 100), _row("Equipment", "buying", 0)],
    )

    cfg = trade_adapter.TradeAdapterConfig(max_hops=1)
    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK)

    assert len(hops) == 1
    assert note is not None
    assert "capped" in note
    # Highest-margin hop (Equipment) is kept over the lower one (Fuel Ore).
    assert hops[0].commodity == "Equipment"


# -- (7) empty/unpriced world -> [] -----------------------------------------


def test_empty_world_returns_empty_and_no_note(tmp_path):
    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()
    assert note is None


def test_single_port_world_returns_empty(tmp_path):
    _upsert(tmp_path, 70, warps=(), commodities=[_row("Equipment", "selling", 100)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


# -- chain-finder wiring stays inert on an empty hop tuple -------------------


def test_empty_hops_keeps_chain_finder_output_none():
    assert longest_profit_chain(()) is None
    assert find_profit_chains(()) == []


# -- malformed container shapes fail-closed (isinstance guards), never ------
# -- crash a per-tick caller -------------------------------------------------


def test_non_dict_port_is_skipped_not_crashed(tmp_path):
    _write_raw_sector(tmp_path, 90, {"sector_id": 90, "warps": [91], "port": "not-a-dict"})
    _upsert(tmp_path, 91, warps=(90,), commodities=[_row("Equipment", "buying", 0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


def test_non_list_commodities_is_skipped_not_crashed(tmp_path):
    _write_raw_sector(
        tmp_path,
        92,
        {
            "sector_id": 92,
            "warps": [93],
            "port": {
                "commodities": "not-a-list",
                "last_seen_ts": world_model._now_iso(_CLOCK),
            },
        },
    )
    _upsert(tmp_path, 93, warps=(92,), commodities=[_row("Equipment", "buying", 0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


def test_non_dict_commodity_row_is_skipped_but_sibling_valid_row_still_works(tmp_path):
    _write_raw_sector(
        tmp_path,
        94,
        {
            "sector_id": 94,
            "warps": [95],
            "port": {
                "commodities": ["not-a-dict-row", _row("Equipment", "selling", 100)],
                "last_seen_ts": world_model._now_iso(_CLOCK),
            },
        },
    )
    _upsert(tmp_path, 95, warps=(94,), commodities=[_row("Equipment", "buying", 0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    # The garbage row is silently skipped; the well-formed row alongside
    # it in the SAME list still produces a normal hop -- proves partial
    # tolerance, not just "doesn't crash."
    assert len(hops) == 1
    assert (hops[0].frm, hops[0].to, hops[0].commodity) == (94, 95, "Equipment")
    assert hops[0].margin == 44.0


@pytest.mark.parametrize("bad_name", [["x"], {"nested": "dict"}])
def test_unhashable_commodity_name_row_is_skipped_not_crashed(tmp_path, bad_name):
    """cipher re-verify: a dict ROW (passes the isinstance-dict guard)
    whose `name` VALUE is itself a list/dict is unhashable -- used to
    raise TypeError at `by_name[name] = row` before this guard existed."""
    _write_raw_sector(
        tmp_path,
        140,
        {
            "sector_id": 140,
            "warps": [141],
            "port": {
                "commodities": [
                    {"name": bad_name, "status": "selling", "amount": 1000, "pct": 100},
                    _row("Equipment", "selling", 100),
                ],
                "last_seen_ts": world_model._now_iso(_CLOCK),
            },
        },
    )
    _upsert(tmp_path, 141, warps=(140,), commodities=[_row("Equipment", "buying", 0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    # The unhashable-name row is silently skipped (no crash); the
    # well-formed sibling row still produces a normal hop.
    assert len(hops) == 1
    assert (hops[0].frm, hops[0].to, hops[0].commodity) == (140, 141, "Equipment")


def test_non_numeric_sector_id_field_is_skipped_not_crashed(tmp_path):
    # The FILE is validly named (86.json, via _sector_path) but the
    # record's own `sector_id` field content is corrupt -- `all_sectors`
    # parses the filename, not this field, so this reaches `_fresh_ports`
    # rather than blowing up one layer down in world_model itself.
    _write_raw_sector(
        tmp_path,
        86,
        {
            "sector_id": "not-a-number",
            "warps": [],
            "port": {
                "commodities": [_row("Equipment", "selling", 100)],
                "last_seen_ts": world_model._now_iso(_CLOCK),
            },
        },
    )
    _upsert(tmp_path, 87, warps=(86,), commodities=[_row("Equipment", "buying", 0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


def test_non_integral_sector_id_raises_rather_than_truncating(tmp_path):
    """WO-ADAPTER-SECTOR-ID-INTEGRAL: 10.9 must not silently become key 10."""
    _write_raw_sector(
        tmp_path,
        110,
        {
            "sector_id": 10.9,
            "warps": [111],
            "port": {
                "commodities": [_row("Equipment", "selling", 100)],
                "last_seen_ts": world_model._now_iso(_CLOCK),
            },
        },
    )
    _upsert(tmp_path, 111, warps=(110,), commodities=[_row("Equipment", "buying", 0)])

    with pytest.raises(ValueError, match="non-integral sector_id"):
        trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)


def test_require_integral_sector_id_accepts_integral_float_and_int():
    assert trade_adapter._require_integral_sector_id(10) == 10
    assert trade_adapter._require_integral_sector_id(10.0) == 10
    assert trade_adapter._require_integral_sector_id("10") == 10
    assert trade_adapter._require_integral_sector_id("not-a-number") is None
    with pytest.raises(ValueError, match="non-integral"):
        trade_adapter._require_integral_sector_id(10.9)


def test_integral_float_sector_id_builds_hops(tmp_path):
    """``10.0`` is integral — accepted as sector 10 and can form a hop."""
    _write_raw_sector(
        tmp_path,
        10,
        {
            "sector_id": 10.0,
            "warps": [11],
            "port": {
                "commodities": [_row("Equipment", "selling", 100)],
                "last_seen_ts": world_model._now_iso(_CLOCK),
            },
        },
    )
    _write_raw_sector(
        tmp_path,
        11,
        {
            "sector_id": 11,
            "warps": [10],
            "port": {
                "commodities": [_row("Equipment", "buying", 0)],
                "last_seen_ts": world_model._now_iso(_CLOCK),
            },
        },
    )

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert len(hops) == 1
    assert (hops[0].frm, hops[0].to, hops[0].commodity) == (10, 11, "Equipment")


# -- non-finite pct fails closed, not open -----------------------------------


@pytest.mark.parametrize("bad_pct", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_pct_yields_no_hop(tmp_path, bad_pct):
    _upsert(tmp_path, 96, warps=(97,), commodities=[_row("Equipment", "selling", bad_pct)])
    _upsert(tmp_path, 97, warps=(96,), commodities=[_row("Equipment", "buying", 0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


def test_missing_pct_yields_no_hop(tmp_path):
    malformed_row = {"name": "Equipment", "status": "selling", "amount": 1000}  # no "pct" key
    _upsert(tmp_path, 102, warps=(103,), commodities=[malformed_row])
    _upsert(tmp_path, 103, warps=(102,), commodities=[_row("Equipment", "buying", 0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


# -- max_hops validation ------------------------------------------------------


def test_max_hops_zero_returns_empty_but_notes_the_drop(tmp_path):
    _upsert(
        tmp_path,
        110,
        warps=(111,),
        commodities=[_row("Equipment", "selling", 100), _row("Fuel Ore", "buying", 0)],
    )
    _upsert(
        tmp_path,
        111,
        warps=(110,),
        commodities=[_row("Fuel Ore", "selling", 100), _row("Equipment", "buying", 0)],
    )

    cfg = trade_adapter.TradeAdapterConfig(max_hops=0)
    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK)

    assert hops == ()
    assert note is not None
    assert "capped" in note


def test_negative_max_hops_raises_at_construction():
    with pytest.raises(ValueError):
        trade_adapter.TradeAdapterConfig(max_hops=-1)


# -- max_route_searches (WO-CHAIN-WORK-BOUND) ---------------------------------


def _pair_world(tmp_path, a, b):
    """Two-port Equipment/Fuel Ore mirror used by several hop pins."""
    _upsert(
        tmp_path,
        a,
        warps=(b,),
        commodities=[_row("Equipment", "selling", 100), _row("Fuel Ore", "buying", 0)],
    )
    _upsert(
        tmp_path,
        b,
        warps=(a,),
        commodities=[_row("Fuel Ore", "selling", 100), _row("Equipment", "buying", 0)],
    )


def test_route_search_budget_bounds_bfs_calls(tmp_path, monkeypatch):
    """Spy/counter (not wall-clock): many compatible pairs, few sources —
    budget of 1 must not run more than one source BFS."""
    # Three sell-sources (10, 20, 30) each with a buyer that only that
    # source can profitably hit on Equipment — forces distinct BFS starts
    # if the budget allows, and proves pair-count growth cannot exceed
    # the configured search limit.
    for frm, to in ((10, 11), (20, 21), (30, 31)):
        _upsert(
            tmp_path,
            frm,
            warps=(to,),
            commodities=[_row("Equipment", "selling", 100, amount=1000)],
        )
        _upsert(
            tmp_path,
            to,
            warps=(frm,),
            commodities=[_row("Equipment", "buying", 0, amount=1000)],
        )

    calls = {"n": 0}
    real_bfs = trade_adapter._bfs_paths_from

    def counting_bfs(graph, start):
        calls["n"] += 1
        return real_bfs(graph, start)

    monkeypatch.setattr(trade_adapter, "_bfs_paths_from", counting_bfs)
    cfg = trade_adapter.TradeAdapterConfig(max_route_searches=1)
    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK)

    assert calls["n"] == 1
    assert note is not None
    assert "incomplete" in note
    assert "not established" in note
    assert len(hops) >= 1  # the one paid source still yields its hop


def test_route_search_within_budget_matches_legacy_and_is_deterministic(tmp_path):
    _pair_world(tmp_path, 10, 11)
    cfg = trade_adapter.TradeAdapterConfig(max_route_searches=100)
    a = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK)
    b = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK)
    default = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert a == b
    assert a == default
    assert a[1] is None  # within budget: no incomplete-search note
    assert len(a[0]) == 2


def test_max_route_searches_zero_performs_zero_bfs(tmp_path, monkeypatch):
    _pair_world(tmp_path, 10, 11)
    calls = {"n": 0}

    def counting_bfs(graph, start):
        calls["n"] += 1
        return {}

    monkeypatch.setattr(trade_adapter, "_bfs_paths_from", counting_bfs)
    cfg = trade_adapter.TradeAdapterConfig(max_route_searches=0)
    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK)

    assert calls["n"] == 0
    assert hops == ()
    assert note is not None
    assert "incomplete" in note


def test_negative_max_route_searches_raises_at_construction():
    with pytest.raises(ValueError, match="max_route_searches"):
        trade_adapter.TradeAdapterConfig(max_route_searches=-1)


def test_bool_max_route_searches_raises_at_construction():
    with pytest.raises(TypeError, match="max_route_searches"):
        trade_adapter.TradeAdapterConfig(max_route_searches=True)


def test_non_int_max_route_searches_raises_at_construction():
    with pytest.raises(TypeError, match="max_route_searches"):
        trade_adapter.TradeAdapterConfig(max_route_searches=1.5)


# -- config guards: ceiling_multiplier + bool-as-number (WO-ADAPTER-CONFIG-GUARDS-LOW)


def test_ceiling_multiplier_below_one_raises_at_construction():
    with pytest.raises(ValueError, match="ceiling_multiplier"):
        trade_adapter.TradeAdapterConfig(ceiling_multiplier=0.5)


def test_ceiling_multiplier_unity_is_accepted():
    cfg = trade_adapter.TradeAdapterConfig(ceiling_multiplier=1.0)
    assert cfg.ceiling_multiplier == 1.0


def test_bool_ceiling_multiplier_raises_at_construction():
    with pytest.raises(TypeError, match="ceiling_multiplier"):
        trade_adapter.TradeAdapterConfig(ceiling_multiplier=True)


def test_bool_pct_is_rejected_by_commodity_price():
    # float(True) == 1.0 would otherwise invent a price from a flag.
    row = {"name": "Equipment", "pct": True, "amount": 1000, "status": "selling"}
    assert trade_adapter._commodity_price(row, trade_adapter.DEFAULT_FLOOR_PRICES, 2.0) is None


def test_bool_amount_is_rejected_by_tradeable_amount():
    row = {"name": "Equipment", "pct": 50, "amount": True, "status": "selling"}
    assert trade_adapter._has_tradeable_amount(row, amount_floor=0) is False


def test_bool_amount_yields_no_hop(tmp_path):
    _upsert(
        tmp_path,
        140,
        warps=(141,),
        commodities=[_row("Equipment", "selling", 100, amount=True)],
    )
    _upsert(
        tmp_path,
        141,
        warps=(140,),
        commodities=[_row("Equipment", "buying", 0, amount=1000)],
    )

    hops, _note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


# -- amount-floor filter drops phantom legs ----------------------------------


def test_both_sides_zero_amount_yields_no_hop(tmp_path):
    _upsert(tmp_path, 120, warps=(121,), commodities=[_row("Equipment", "selling", 100, amount=0)])
    _upsert(tmp_path, 121, warps=(120,), commodities=[_row("Equipment", "buying", 0, amount=0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


def test_empty_seller_zero_amount_yields_no_hop(tmp_path):
    _upsert(tmp_path, 122, warps=(123,), commodities=[_row("Equipment", "selling", 100, amount=0)])
    _upsert(tmp_path, 123, warps=(122,), commodities=[_row("Equipment", "buying", 0, amount=1000)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


def test_empty_buyer_zero_amount_yields_no_hop(tmp_path):
    _upsert(tmp_path, 124, warps=(125,), commodities=[_row("Equipment", "selling", 100, amount=1000)])
    _upsert(tmp_path, 125, warps=(124,), commodities=[_row("Equipment", "buying", 0, amount=0)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


def test_both_sides_above_default_floor_emits_hop(tmp_path):
    _upsert(tmp_path, 126, warps=(127,), commodities=[_row("Equipment", "selling", 100, amount=1000)])
    _upsert(tmp_path, 127, warps=(126,), commodities=[_row("Equipment", "buying", 0, amount=1000)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert len(hops) == 1


def test_amount_below_configured_floor_is_dropped(tmp_path):
    # Amounts are well above the DEFAULT floor (1) but below a stricter
    # configured floor -- proves the config knob, not just the default.
    _upsert(tmp_path, 128, warps=(129,), commodities=[_row("Equipment", "selling", 100, amount=10)])
    _upsert(tmp_path, 129, warps=(128,), commodities=[_row("Equipment", "buying", 0, amount=10)])

    cfg = trade_adapter.TradeAdapterConfig(amount_floor=50)
    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK)

    assert hops == ()


def test_amount_above_configured_floor_still_emits_hop(tmp_path):
    _upsert(tmp_path, 130, warps=(131,), commodities=[_row("Equipment", "selling", 100, amount=100)])
    _upsert(tmp_path, 131, warps=(130,), commodities=[_row("Equipment", "buying", 0, amount=100)])

    cfg = trade_adapter.TradeAdapterConfig(amount_floor=50)
    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK)

    assert len(hops) == 1


@pytest.mark.parametrize("bad_amount", [None, float("nan"), "not-a-number"])
def test_missing_or_unusable_amount_yields_no_hop(tmp_path, bad_amount):
    _upsert(tmp_path, 132, warps=(133,), commodities=[_row("Equipment", "selling", 100, amount=bad_amount)])
    _upsert(tmp_path, 133, warps=(132,), commodities=[_row("Equipment", "buying", 0, amount=1000)])

    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert hops == ()


# --------------------------------------------------------------------------
# WO-CHAIN-DETECT-WIRE -- class-derived posture path (build_candidate_pairs)
# --------------------------------------------------------------------------


def test_class_pair_compatible_hand_computed(tmp_path):
    """Sector 10: SBB -- sells Fuel Ore, buys Organics+Equipment.
    Sector 11: BSS -- buys Fuel Ore, sells Organics+Equipment.
    Perspective rule pinned: 10 sells Fuel Ore which 11 buys (one
    compatible commodity); 11 sells {Organics, Equipment}, both of
    which 10 buys (two compatible commodities). REVISE (Samantha,
    2026-07-28): the full set is carried on both sides now, never
    collapsed to a single tiebroken pick -- see `CandidatePair`'s own
    docstring for why a `min()` tiebreak was wrong. One adjacent warp
    each way -> turns == 1 + 1 == 2, canon's cheapest pair-loop shape."""
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB")
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS")

    pairs, stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.sector_a == 10 and pair.sector_b == 11
    assert pair.commodities_a_sells == ("Fuel Ore",)
    assert pair.commodities_b_sells == ("Organics", "Equipment")  # CLASS_POSITIONS order, full set
    assert pair.turns == 2
    assert pair.observed_age_s == 0.0
    assert not hasattr(pair, "margin")  # structurally impossible to guess a number here
    assert stats == trade_adapter.PairBuildStats(
        known_sectors=2,
        class_valid_ports=2,
        fresh_class_ports=2,
        oldest_class_age_s=0.0,
        compatible_pairs_considered=1,
        routed_pairs=1,
    )


def test_class_pair_sector_a_always_lower_regardless_of_write_order(tmp_path):
    """Same pair as above, written in descending sector-id order --
    `CandidatePair.sector_a < sector_b` must hold by construction, not
    by luck of iteration order."""
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS")
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB")

    pairs, _stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert len(pairs) == 1
    assert pairs[0].sector_a == 10
    assert pairs[0].sector_b == 11


def test_class_pair_both_selling_same_single_commodity_not_compatible(tmp_path):
    """Canon invariant, pinned for the class path too: two ports both
    SELLING (never buying) the same single commodity are NOT a
    compatible pair on either leg -- fail-closed, no candidate.
    Perspective-rule pin: swapping the S/B interpretation anywhere in
    `build_candidate_pairs` (e.g. computing `sells & sells` instead of
    `sells & buys`) would turn a variant of this fixture green when it
    must stay red -- see report Verification for the manual mutation
    proof."""
    _upsert_class(tmp_path, 20, warps=(21,), klass="SSS")
    _upsert_class(tmp_path, 21, warps=(20,), klass="SSS")

    pairs, stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert pairs == ()
    assert stats.fresh_class_ports == 2
    assert stats.compatible_pairs_considered == 0
    assert stats.routed_pairs == 0


def test_class_pair_asymmetric_one_way_warps_sums_both_directions(tmp_path):
    """40 -> 41 -> 42 -> 40 is a one-way RING (sector 41 is a plain
    waypoint, no port). Path 40->42 is 2 hops (via 41); path 42->40 is
    1 hop (direct). `turns` must be the sum of the TWO direction-
    specific route lengths (2 + 1 == 3), never a naive doubling of one
    direction's hop count -- pins that `_bfs_paths_from` is queried
    once per source and both directions are genuinely routed."""
    _upsert_class(tmp_path, 40, warps=(41,), klass="SBB")
    _upsert_class(tmp_path, 41, warps=(42,))  # waypoint only, no port
    _upsert_class(tmp_path, 42, warps=(40,), klass="BSS")

    pairs, stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert len(pairs) == 1
    assert pairs[0].turns == 3
    assert stats.known_sectors == 3  # the waypoint counts as a known sector too
    assert stats.class_valid_ports == 2  # but never as a class-valid PORT


def test_future_stamped_port_is_never_treated_as_fresh(tmp_path):
    """#131 WO-ADAPTER-FRESHNESS-FUTURE-TS (main, `ff48656`) fixed
    `_is_fresh` to fail closed on a negative age (a future/clock-skewed
    `last_seen_ts`). `build_candidate_pairs` used to re-derive the same
    predicate inline instead of calling `_is_fresh`, and missed the fix:
    a future-stamped port's negative age satisfied the old bare
    `age <= max_age_s` check unconditionally and was treated as fresh.

    Execution proof: sector 10 is stamped ONE HOUR IN THE FUTURE relative
    to `now`; sector 11 is stamped normally and is otherwise posture-
    compatible with sector 10 and routed. Only sector 11 may count as
    fresh, so no pair can form (fewer than 2 fresh ports)."""
    future_clock = lambda: _CLOCK() + datetime.timedelta(hours=1)
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB", port_ts_clock=future_clock)
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS", port_ts_clock=_CLOCK)

    pairs, stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert stats.class_valid_ports == 2  # both are syntactically valid class triples
    assert stats.fresh_class_ports == 1  # only sector 11 -- sector 10's future stamp is NOT fresh
    assert pairs == ()


def test_oldest_class_age_excludes_a_negative_future_stamp(tmp_path):
    """Sanity, not a discriminating regression pin (a genuinely-old
    positive age is always numerically larger than any negative one, so
    plain `max()` already picks it correctly regardless of the `a >= 0`
    filter -- verified by hand, not claimed as mutation-proven). The
    actually-discriminating case, where the filter is load-bearing, is
    `test_oldest_class_age_is_none_when_every_reading_is_future_stamped`
    below (every candidate negative -> `max()` alone would pick the
    least-negative one and report it as a real "oldest reading")."""
    future_clock = lambda: _CLOCK() + datetime.timedelta(hours=1)
    old_clock = lambda: datetime.datetime(2026, 6, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB", port_ts_clock=future_clock)
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS", port_ts_clock=old_clock)

    cfg = trade_adapter.PairLoopConfig(class_max_age_s=10.0)
    pairs, stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK)

    expected_age = (_CLOCK() - old_clock()).total_seconds()
    assert stats.oldest_class_age_s == expected_age  # sector 11's genuinely-old age, never sector 10's negative one
    assert stats.oldest_class_age_s > 0


def test_oldest_class_age_is_none_when_every_reading_is_future_stamped(tmp_path):
    """No genuinely non-negative age exists at all -- `None` (honest
    unknown), never a negative number masquerading as an age."""
    future_clock = lambda: _CLOCK() + datetime.timedelta(hours=1)
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB", port_ts_clock=future_clock)
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS", port_ts_clock=future_clock)

    pairs, stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert stats.oldest_class_age_s is None


# --------------------------------------------------------------------------
# _observed_age_s -- direct unit coverage of the defense-in-depth guard
# (Samantha's second-order finding: a plausible-but-wrong number is worse
# than an obviously-wrong one; `max()` alone MASKS one negative input
# behind a healthy-looking one).
# --------------------------------------------------------------------------


def test_observed_age_s_normal_case_returns_the_staler():
    assert trade_adapter._observed_age_s(100.0, 3600.0) == 3600.0
    assert trade_adapter._observed_age_s(0.0, 0.0) == 0.0


def test_observed_age_s_is_none_when_both_are_future_stamped():
    assert trade_adapter._observed_age_s(-100.0, -50.0) is None


def test_observed_age_s_never_masks_one_future_stamp_behind_a_healthy_one():
    """The masking case, named explicitly: `max(3600.0, -3600.0)` is
    `3600.0` on its own, which reads as a perfectly normal one-hour
    figure while hiding that the OTHER input was garbage. Must be
    `None`, whichever side carries the negative value."""
    assert trade_adapter._observed_age_s(3600.0, -3600.0) is None
    assert trade_adapter._observed_age_s(-3600.0, 3600.0) is None


def test_observed_age_s_is_none_not_zero_on_a_missing_input():
    """Honest unknown, never a fabricated `0.0` -- same em-dash discipline
    as every other "never guess" guard in this module."""
    assert trade_adapter._observed_age_s(None, 100.0) is None
    assert trade_adapter._observed_age_s(100.0, None) is None
    assert trade_adapter._observed_age_s(None, None) is None


# --------------------------------------------------------------------------
# WO-ADAPTER-FRESHNESS-SWEEP -- `_age_s` owns the only `(now - ts)` site;
# aggregators never see raw negative ages.
# --------------------------------------------------------------------------


def test_age_s_fail_closed_on_future_and_unparseable():
    now = _CLOCK()
    future = world_model._now_iso(lambda: now + datetime.timedelta(hours=1))
    past = world_model._now_iso(lambda: now - datetime.timedelta(seconds=42))
    assert trade_adapter._age_s(future, now=now) is None
    assert trade_adapter._age_s(None, now=now) is None
    assert trade_adapter._age_s("not-a-ts", now=now) is None
    assert trade_adapter._age_s(past, now=now) == 42.0


def test_age_s_is_the_sole_total_seconds_freshness_site():
    """Accept #1: no remaining inline `(now - ts).total_seconds()` freshness
    decisions outside the shared helper. Every Call to `total_seconds` in
    this module must live inside `_age_s` (tests may still compute ages)."""
    src = Path(trade_adapter.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    offenders = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            func = call.func
            if isinstance(func, ast.Attribute) and func.attr == "total_seconds":
                if node.name != "_age_s":
                    offenders.append(node.name)
    assert offenders == [], f"total_seconds outside _age_s: {offenders}"


def test_one_future_stamp_never_launders_into_pair_observed_age(tmp_path):
    """CC probe shape: one future + one healthy neighbour must not yield a
    pair whose `observed_age_s` is the healthy neighbour's age (Accept #3).
    Gate drops the future port → fewer than 2 fresh → no pair at all."""
    future_clock = lambda: _CLOCK() + datetime.timedelta(hours=1)
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB", port_ts_clock=future_clock)
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS", port_ts_clock=_CLOCK)

    pairs, stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert stats.fresh_class_ports == 1
    assert pairs == ()
    # ages dict stores None for the future stamp — oldest is only the healthy side
    assert stats.oldest_class_age_s == 0.0


@pytest.mark.parametrize(
    "klass",
    [None, "", "BS", "BSSS", "BSX", "bss", 5, ["B", "S", "S"], {"letters": "BSS"}],
)
def test_invalid_class_shapes_never_crash_and_are_excluded(tmp_path, klass):
    """`_valid_class_triple` fail-closed sweep: `None` (never observed /
    Class-0-StarDock presence-without-class), wrong length, an invalid
    letter, lowercase (canon stores upper-case only -- `state_parser`
    upper-cases at the regex site, so a lowercase triple here is a
    malformed on-disk shape, never a live-parser output), and non-str
    types a corrupted JSON file could genuinely carry. None of these
    may raise, and none may count as a usable class port."""
    _write_raw_sector(
        tmp_path,
        50,
        {
            "sector_id": 50,
            "warps": [51],
            "port": {"class": klass, "last_seen_ts": world_model._now_iso(_CLOCK)},
        },
    )
    _upsert_class(tmp_path, 51, warps=(50,), klass="SBB")

    pairs, stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert pairs == ()
    assert stats.class_valid_ports == 1  # only sector 51


@pytest.mark.parametrize(
    "raw_record",
    [
        {"sector_id": 60, "warps": [61], "port": "not-a-dict"},
        {"sector_id": "not-an-int", "warps": [61], "port": {"class": "SBB"}},
        {"sector_id": 60, "warps": [61], "port": {"class": "SBB", "last_seen_ts": None}},
    ],
)
def test_malformed_on_disk_shapes_never_crash(tmp_path, raw_record):
    """`world_model.query`'s predicate only checks truthiness -- a
    malformed on-disk record (non-dict `port`, non-numeric `sector_id`,
    an unparseable `last_seen_ts`) must reach `build_candidate_pairs`
    without raising, same fail-closed discipline `_fresh_ports` already
    documents for the commodity path."""
    _write_raw_sector(tmp_path, 60, raw_record)
    _upsert_class(tmp_path, 61, warps=(60,), klass="BSS")

    pairs, _stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert pairs == ()  # sector 60 never contributes a usable class port either way


def test_reason_no_world_model(tmp_path):
    pairs, stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, now=_CLOCK)
    assert pairs == ()
    assert stats.known_sectors == 0


def test_reason_fewer_than_two_ports(tmp_path):
    _upsert_class(tmp_path, 1, warps=(2,))  # known sector, no port at all
    _upsert_class(tmp_path, 2, warps=(1,), klass="SBB")  # the only valid class port

    pairs, stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert pairs == ()
    assert stats.known_sectors == 2
    assert stats.class_valid_ports == 1


def test_reason_all_stale_carries_oldest_age(tmp_path):
    """Both ports carry a genuine, syntactically valid, MUTUALLY
    COMPATIBLE class pair -- the ONLY thing wrong is staleness against
    a deliberately short `class_max_age_s`. `oldest_class_age_s` must
    report a real, computed figure (not a placeholder), matching the
    "explore tonight, open the view tomorrow" scenario the config's
    long default guards against."""
    old_clock = lambda: datetime.datetime(2026, 6, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB", port_ts_clock=old_clock)
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS", port_ts_clock=old_clock)

    cfg = trade_adapter.PairLoopConfig(class_max_age_s=10.0)
    pairs, stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK)

    expected_age = (_CLOCK() - old_clock()).total_seconds()
    assert pairs == ()
    assert stats.class_valid_ports == 2
    assert stats.fresh_class_ports == 0
    assert stats.oldest_class_age_s == expected_age


def test_reason_no_compatible_pairs(tmp_path):
    _upsert_class(tmp_path, 20, warps=(21,), klass="SSS")
    _upsert_class(tmp_path, 21, warps=(20,), klass="SSS")

    pairs, stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert pairs == ()
    assert stats.fresh_class_ports == 2
    assert stats.compatible_pairs_considered == 0


def test_reason_compatible_but_unrouted(tmp_path):
    """Posture-compatible, but the two sectors' warp graphs never
    connect (no warps recorded either side) -- structurally compatible,
    never routable, the single most actionable empty this feature can
    surface."""
    _upsert_class(tmp_path, 30, warps=(), klass="SBB")
    _upsert_class(tmp_path, 31, warps=(), klass="BSS")

    pairs, stats = trade_adapter.build_candidate_pairs(WORLD, state_dir=tmp_path, now=_CLOCK)

    assert pairs == ()
    assert stats.compatible_pairs_considered == 1
    assert stats.routed_pairs == 0


def test_pair_loop_config_rejects_negative_class_max_age():
    with pytest.raises(ValueError):
        trade_adapter.PairLoopConfig(class_max_age_s=-1.0)


def test_bfs_paths_from_matches_path_to_sector_for_every_reachable_pair():
    """Differential proof for the O(ports) routing optimization
    (module docstring): `_bfs_paths_from`'s single multi-target BFS
    must return EXACTLY what `explore.path_to_sector`'s one-BFS-per-
    call would have, for every (start, goal) pair on a graph with a
    cycle, a branch, a disconnected component, AND a dangling warp
    (sector 1 warps to 99, which is never itself a known sector --
    `known_graph` genuinely produces this shape from a flyby that has
    seen a neighbor's warp but not yet visited it) -- swept
    exhaustively, not sampled. The dangling case is load-bearing, not
    decorative: a mutant that drops `_bfs_paths_from`'s "only step onto
    a KNOWN sector" guard passes every other case here unchanged but
    fabricates a path through sector 99 -- see report Verification."""
    from tw2002_aiclient.explore import path_to_sector

    graph = {
        1: (2, 3, 99),  # 99 is a dangling warp target -- never a key below
        2: (4,),
        3: (4, 5),
        4: (1,),
        5: (),
        6: (7,),  # disconnected component -- unreachable from 1..5
        7: (),
    }
    nodes = list(graph.keys())
    for start in nodes:
        paths = trade_adapter._bfs_paths_from(graph, start)
        assert paths[start] == (start,)
        for goal in list(nodes) + [99]:
            if goal == start:
                continue
            assert paths.get(goal) == path_to_sector(graph, start, goal), (start, goal)


def test_bfs_paths_from_unknown_start_is_empty():
    assert trade_adapter._bfs_paths_from({1: (2,), 2: (1,)}, 99) == {}


# --------------------------------------------------------------------------
# Structural pin -- DoD accept 4: neither module reaches a send path
# --------------------------------------------------------------------------

PKG_ROOT = Path(trade_adapter.__file__).resolve().parent
REPO_ROOT = PKG_ROOT.parent

_BANNED_MODULES = frozenset(
    {
        "tw2002_aiclient.session.connection",
        "tw2002_aiclient.session.protocol",
        "tw2002_aiclient.adapters",
    }
)

_ENTRY_FILES = (
    PKG_ROOT / "chains.py",
    PKG_ROOT / "trade_adapter.py",
    # WO-CHAIN-DETECT-WIRE: the class-derived pair-loop wire adds TWO more
    # pure-read entry points (`build_candidate_pairs` lives in
    # trade_adapter.py above, already covered) that must never reach a
    # send path either -- same walker, same banned set, no second copy of
    # the AST scan. `chain_detect_view.py` (the re-scoped dedicated
    # formatter, 2026-07-28) replaces the deleted `loops.list_view` bridge
    # -- it imports nothing at all, so its own closure sanity-checks to a
    # singleton set below.
    PKG_ROOT / "chain_detect.py",
    PKG_ROOT / "chain_detect_view.py",
)


def _is_banned(dotted: str) -> bool:
    return any(dotted == b or dotted.startswith(b + ".") for b in _BANNED_MODULES)


def _dotted_for_file(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT)
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _package_for_file(path: Path, dotted: str) -> str:
    """A module's `__package__`: itself if it's an `__init__.py`, else its
    dotted name with the last component dropped (Python relative-import
    semantics)."""
    if path.name == "__init__.py":
        return dotted
    return dotted.rsplit(".", 1)[0] if "." in dotted else ""


def _file_for_dotted(dotted: str) -> Optional[Path]:
    if not (dotted == "tw2002_aiclient" or dotted.startswith("tw2002_aiclient.")):
        return None
    parts = dotted.split(".")
    candidate = REPO_ROOT.joinpath(*parts).with_suffix(".py")
    if candidate.is_file():
        return candidate
    pkg_init = REPO_ROOT.joinpath(*parts, "__init__.py")
    if pkg_init.is_file():
        return pkg_init
    return None


def _scan_module(path: Path, *, seen: set, banned_hits: list, unresolved_dynamic: list) -> None:
    """Recursively walk `path`'s tw2002_aiclient-rooted import closure,
    collecting any edge into `_BANNED_MODULES` (absolute imports, resolved
    relative imports, and literal `importlib.import_module`/`__import__`
    calls) and separately flagging any dynamic-import call whose target
    isn't a string literal -- per this repo's evasion-aware scanning
    convention, an unreadable dynamic import is refused, not trusted."""
    dotted = _dotted_for_file(path)
    if dotted in seen:
        return
    seen.add(dotted)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    package = _package_for_file(path, dotted)
    targets: set = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("tw2002_aiclient"):
                    targets.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                mod = node.module or ""
                if mod == "tw2002_aiclient" or mod.startswith("tw2002_aiclient."):
                    targets.add(mod)
                    for alias in node.names:
                        targets.add(f"{mod}.{alias.name}")
            else:
                base_parts = package.split(".") if package else []
                strip = node.level - 1
                base = base_parts[: len(base_parts) - strip] if strip <= len(base_parts) else []
                prefix = ".".join(base + ([node.module] if node.module else []))
                if prefix:
                    targets.add(prefix)
                    for alias in node.names:
                        targets.add(f"{prefix}.{alias.name}")
        elif isinstance(node, ast.Call):
            fn = node.func
            is_dynamic_import = (isinstance(fn, ast.Attribute) and fn.attr == "import_module") or (
                isinstance(fn, ast.Name) and fn.id == "__import__"
            )
            if is_dynamic_import:
                if (
                    node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    literal = node.args[0].value
                    if _is_banned(literal):
                        banned_hits.append(f"{dotted}: dynamic import of {literal!r}")
                else:
                    unresolved_dynamic.append(f"{dotted}: {ast.dump(node)[:120]}")

    for t in targets:
        if _is_banned(t):
            banned_hits.append(f"{dotted} -> {t}")
        child = _file_for_dotted(t)
        if child is not None:
            _scan_module(child, seen=seen, banned_hits=banned_hits, unresolved_dynamic=unresolved_dynamic)


def test_neither_module_reaches_a_send_path():
    """DoD accept 4 -- structural, not text-grep: recursively walks the
    tw2002_aiclient-rooted import closure of `chains.py`,
    `trade_adapter.py`, and (WO-CHAIN-DETECT-WIRE) `chain_detect.py` +
    `chain_detect_view.py`, and asserts none of them ever reaches
    `session.connection`, `session.protocol`, or `adapters.py` (the
    send-capable surfaces). Also refuses (rather than silently trusting)
    any dynamic `importlib.import_module`/`__import__` call whose target
    isn't a string literal -- mutate-proven, see report."""
    seen: set = set()
    banned_hits: list = []
    unresolved_dynamic: list = []
    for entry in _ENTRY_FILES:
        _scan_module(entry, seen=seen, banned_hits=banned_hits, unresolved_dynamic=unresolved_dynamic)

    assert banned_hits == []
    assert unresolved_dynamic == []
    # Sanity the walk actually traversed the real closure -- an empty/
    # trivial `seen` would make the assertions above vacuously true.
    # `loops.list_view` is DELIBERATELY absent here (WO-CHAIN-DETECT-WIRE
    # re-scope, 2026-07-28): `chain_detect.py` no longer imports it (the
    # bridge into `format_loop_row` was deleted), and `chain_detect_view.py`
    # -- its replacement -- imports nothing at all, so it never reaches
    # this module's own closure either. A stray re-introduction of that
    # import edge is exactly what this assertion (an exact `seen` set, not
    # merely `>=` on the old members) would catch.
    assert seen >= {
        "tw2002_aiclient.chains",
        "tw2002_aiclient.trade_adapter",
        "tw2002_aiclient.world_model",
        "tw2002_aiclient.explore",
        "tw2002_aiclient.chain_detect",
        "tw2002_aiclient.chain_detect_view",
    }
    assert "tw2002_aiclient.loops.list_view" not in seen


# --------------------------------------------------------------------------
# WO-WORLD-STATS-REFRESH-EVENTS B — cheap known_sector_count at pair-build
# --------------------------------------------------------------------------


def test_candidate_pairs_known_sectors_uses_cheap_count_when_all_sectors_would_raise(
    tmp_path, monkeypatch
):
    """Corrupt sibling: `all_sectors` raises; the stats count must still land.

    Hub ruling: cheap counter wins — skip unreadable content for the *count*,
    do not raise at the `known_sectors` call site. Pairing still needs a
    loadable graph, so after proving the raise we replace `all_sectors` with
    the two good records only (isolates the count call site).
    """
    _upsert_class(tmp_path, 10, warps=(11,), klass="SBB")
    _upsert_class(tmp_path, 11, warps=(10,), klass="BSS")
    bad = world_model._sector_path(WORLD, 99, state_dir=tmp_path)
    bad.write_text("{not-json", encoding="utf-8")

    assert world_model.known_sector_count(WORLD, state_dir=tmp_path) == 3
    with pytest.raises(world_model.WorldModelError):
        world_model.all_sectors(WORLD, state_dir=tmp_path)

    good = [
        world_model.get_sector(WORLD, 10, state_dir=tmp_path),
        world_model.get_sector(WORLD, 11, state_dir=tmp_path),
    ]
    monkeypatch.setattr(
        world_model,
        "all_sectors",
        lambda wid, state_dir=None: list(good),
    )

    pairs, stats = trade_adapter.build_candidate_pairs(
        WORLD, state_dir=tmp_path, now=_CLOCK
    )
    assert stats.known_sectors == 3
    assert len(pairs) == 1


# -- WO-TRADE-ADAPTER-BUY-SELL-SPREAD -----------------------------------------


def test_default_config_exposes_buy_sell_spread_of_floor():
    cfg = trade_adapter.TradeAdapterConfig()
    assert cfg.buy_sell_spread_of_floor == trade_adapter.DEFAULT_BUY_SELL_SPREAD_OF_FLOOR
    assert cfg.buy_sell_spread_of_floor == 0.05


def test_same_pct_complementary_ports_yield_positive_margin_under_default_spread(tmp_path):
    """Accept #2 — Gather pct=100 both sides still clears margin > 0."""
    _upsert(
        tmp_path,
        300,
        warps=(301,),
        commodities=[_row("Equipment", "selling", 100)],
    )
    _upsert(
        tmp_path,
        301,
        warps=(300,),
        commodities=[_row("Equipment", "buying", 100)],
    )
    hops, note = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)
    assert note is None
    assert len(hops) == 1
    # floor 40 * 2 * 0.05 = 4.0
    assert hops[0].margin == 4.0
    assert hops[0].margin > 0


def test_zero_spread_restores_same_pct_zero_margin(tmp_path):
    """Spread=0 reproduces the pre-WO posture-blind same-pct collapse."""
    _upsert(
        tmp_path,
        302,
        warps=(303,),
        commodities=[_row("Equipment", "selling", 100)],
    )
    _upsert(
        tmp_path,
        303,
        warps=(302,),
        commodities=[_row("Equipment", "buying", 100)],
    )
    cfg = trade_adapter.TradeAdapterConfig(buy_sell_spread_of_floor=0.0)
    hops, _ = trade_adapter.build_trade_hops(
        WORLD, state_dir=tmp_path, config=cfg, now=_CLOCK
    )
    # margin == 0 is dropped by chains, but build_trade_hops still emits the leg
    assert len(hops) == 1
    assert hops[0].margin == 0.0
    assert find_profit_chains(hops) == []


def test_same_posture_still_yields_no_hop_with_spread(tmp_path):
    """Accept #3 — spread must not invent hops across mismatched postures."""
    _upsert(tmp_path, 304, warps=(305,), commodities=[_row("Equipment", "selling", 100)])
    _upsert(tmp_path, 305, warps=(304,), commodities=[_row("Equipment", "selling", 100)])
    hops, _ = trade_adapter.build_trade_hops(WORLD, state_dir=tmp_path, now=_CLOCK)
    assert hops == ()


@pytest.mark.parametrize("bad", [-0.01, float("nan"), float("inf"), True])
def test_buy_sell_spread_rejects_hostile_config(bad):
    with pytest.raises((TypeError, ValueError)):
        trade_adapter.TradeAdapterConfig(buy_sell_spread_of_floor=bad)


def test_chain_search_finds_cycle_on_same_pct_world(tmp_path):
    """Optional Accept pin — priced bubbles can light after Gather-shaped docks."""
    from tw2002_aiclient import chain_search

    _upsert(
        tmp_path,
        310,
        warps=(311,),
        commodities=[
            _row("Equipment", "selling", 100),
            _row("Fuel Ore", "buying", 100),
        ],
    )
    _upsert(
        tmp_path,
        311,
        warps=(310,),
        commodities=[
            _row("Fuel Ore", "selling", 100),
            _row("Equipment", "buying", 100),
        ],
    )
    result = chain_search.recompute(WORLD, state_dir=tmp_path, now=_CLOCK)
    assert result.chains, f"expected priced cycle, got reason={result.reason!r}"
    assert result.reason is None
