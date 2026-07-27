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
    # Equipment floor 40: selling@pct100 -> 40.0; buying@pct0 -> 40*2=80.0 -> margin 40.0
    assert by_key[(10, 11, "Equipment")].margin == 40.0
    assert by_key[(10, 11, "Equipment")].turns == 1
    # Fuel Ore floor 20: selling@pct100 -> 20.0; buying@pct0 -> 20*2=40.0 -> margin 20.0
    assert by_key[(11, 10, "Fuel Ore")].margin == 20.0
    assert by_key[(11, 10, "Fuel Ore")].turns == 1
    assert len(hops) == 2

    chain = longest_profit_chain(hops)
    assert chain is not None
    assert chain.overall_profit == 60.0
    assert chain.turns == 2
    assert chain.cr_per_turn == 30.0
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
    # Highest-margin hop (Equipment, 40.0) is kept over the lower one (Fuel Ore, 20.0).
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
    assert hops[0].margin == 40.0


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

_ENTRY_FILES = (PKG_ROOT / "chains.py", PKG_ROOT / "trade_adapter.py")


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
    tw2002_aiclient-rooted import closure of `chains.py` and
    `trade_adapter.py` and asserts it never reaches
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
    assert seen >= {
        "tw2002_aiclient.chains",
        "tw2002_aiclient.trade_adapter",
        "tw2002_aiclient.world_model",
        "tw2002_aiclient.explore",
    }
