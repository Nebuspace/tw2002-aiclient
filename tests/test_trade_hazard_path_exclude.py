"""WO-TRADE-HAZARD-PATH-EXCLUDE — do not rank hops with hazardous shortest paths."""

from __future__ import annotations

import datetime

from tw2002_aiclient import trade_adapter, world_model

WORLD = "w-hazard-exclude"
_CLOCK = lambda: datetime.datetime(2026, 7, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _upsert(tmp_path, sector_id, *, warps=(), commodities=None):
    record = {"sector_id": sector_id, "warps": list(warps)}
    if commodities is not None:
        record["port"] = {
            "commodities": commodities,
            "last_seen_ts": world_model._now_iso(_CLOCK),
        }
    world_model.upsert_sector(WORLD, record, state_dir=tmp_path, now=_CLOCK)


def _row(name, status, pct, amount=1000):
    return {"name": name, "status": status, "amount": amount, "pct": pct}


def _upsert_class(tmp_path, sector_id, *, warps=(), klass=None):
    record = {"sector_id": sector_id, "warps": list(warps)}
    if klass is not None:
        record["port"] = {
            "class": klass,
            "last_seen_ts": world_model._now_iso(_CLOCK),
        }
    world_model.upsert_sector(WORLD, record, state_dir=tmp_path, now=_CLOCK)


def test_build_trade_hops_excludes_one_way_shortest_path(tmp_path):
    # 1 sells Equipment → 3 buys; shortest 1→2→3 crosses one-way 1→2.
    _upsert(
        tmp_path,
        1,
        warps=(2,),
        commodities=[_row("Equipment", "selling", 100)],
    )
    _upsert(tmp_path, 2, warps=(3,))
    _upsert(
        tmp_path,
        3,
        warps=(2,),
        commodities=[_row("Equipment", "buying", 0)],
    )
    hops, _note = trade_adapter.build_trade_hops(
        WORLD,
        state_dir=tmp_path,
        now=_CLOCK,
        config=trade_adapter.TradeAdapterConfig(max_hops=20, max_route_searches=20),
    )
    assert all(not (h.frm == 1 and h.to == 3) for h in hops)


def test_build_trade_hops_keeps_bidirectional_path(tmp_path):
    _upsert(
        tmp_path,
        10,
        warps=(11,),
        commodities=[_row("Equipment", "selling", 100)],
    )
    _upsert(
        tmp_path,
        11,
        warps=(10,),
        commodities=[_row("Equipment", "buying", 0)],
    )
    hops, _note = trade_adapter.build_trade_hops(
        WORLD, state_dir=tmp_path, now=_CLOCK
    )
    assert any(h.frm == 10 and h.to == 11 for h in hops)


def test_candidate_pairs_exclude_hazardous_leg(tmp_path):
    # Complementary classes, but 1→2 is one-way (no reverse).
    _upsert_class(tmp_path, 1, warps=(2,), klass="SBB")
    _upsert_class(tmp_path, 2, warps=(3,), klass="BSS")
    _upsert_class(tmp_path, 3, warps=(2,))
    pairs, _stats = trade_adapter.build_candidate_pairs(
        WORLD, state_dir=tmp_path, now=_CLOCK
    )
    assert all(not ({p.sector_a, p.sector_b} == {1, 2}) for p in pairs)
