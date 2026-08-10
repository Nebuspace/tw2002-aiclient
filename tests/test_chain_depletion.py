"""Pins for WO-BUILD-CHAIN-DEPLETION-PREDICTOR (canon port-economics H2)."""

from __future__ import annotations

from tw2002_aiclient.chain_depletion import (
    depletion_signals,
    leg_stocks_for_hops,
    nearing_depletion,
    predict_remaining_trades,
    rank_chains_by_longevity,
    remaining_trades,
)
from tw2002_aiclient.chains import ProfitChain, TradeHop, rank_chains_by_longevity as chains_rank


def _hop(frm: int, to: int, commodity: str) -> TradeHop:
    return TradeHop(frm=frm, to=to, commodity=commodity, margin=10.0, turns=2)


def _chain(*hops: TradeHop) -> ProfitChain:
    sectors = [hops[0].frm]
    for h in hops:
        sectors.append(h.to)
    return ProfitChain(
        sectors=tuple(sectors),
        hops=hops,
        overall_profit=40.0,
        turns=8,
        cr_per_turn=5.0,
        cr_per_execution=40.0,
    )


def test_remaining_trades_canon_formula():
    # min(80, 40, 120, 60) / 20 holds = 2.0
    assert remaining_trades([80, 40, 120, 60], 20) == 2.0


def test_remaining_trades_fail_closed_on_bad_inputs():
    assert remaining_trades([], 20) is None
    assert remaining_trades([10], 0) is None
    assert remaining_trades([10], -1) is None
    assert remaining_trades([10], True) is None  # type: ignore[arg-type]
    assert remaining_trades([10, None], 5) is None  # type: ignore[list-item]
    assert remaining_trades([-1], 5) is None


def test_leg_stocks_and_predict_for_pair_loop():
    hops = (
        _hop(1, 2, "Fuel Ore"),
        _hop(2, 1, "Organics"),
    )
    ports = {
        1: {
            "Fuel Ore": {"name": "Fuel Ore", "status": "selling", "amount": 100},
            "Organics": {"name": "Organics", "status": "buying", "amount": 50},
        },
        2: {
            "Fuel Ore": {"name": "Fuel Ore", "status": "buying", "amount": 80},
            "Organics": {"name": "Organics", "status": "selling", "amount": 40},
        },
    }
    stocks = leg_stocks_for_hops(hops, ports)
    assert stocks == (100.0, 80.0, 40.0, 50.0)
    chain = _chain(*hops)
    assert predict_remaining_trades(chain, hold_count=20, ports_by_sector=ports) == 2.0


def test_leg_stocks_omit_when_amount_missing():
    hops = (_hop(1, 2, "Fuel Ore"),)
    ports = {
        1: {"Fuel Ore": {"name": "Fuel Ore", "status": "selling", "amount": 10}},
        2: {"Fuel Ore": {"name": "Fuel Ore", "status": "buying"}},  # no amount
    }
    assert leg_stocks_for_hops(hops, ports) is None


def test_nearing_depletion_and_signals():
    assert nearing_depletion(0.5) is True
    assert nearing_depletion(1.0) is False
    assert nearing_depletion(None) is False
    sig = depletion_signals(0.25)
    assert sig["nearing_depletion"] is True
    assert sig["explore_appetite_raised"] is True
    assert sig["stop_recommended"] is True
    assert sig["remaining_trades"] == 0.25
    assert depletion_signals(None)["nearing_depletion"] is False


def test_rank_chains_by_longevity_downranks_depleted():
    fresh = _chain(_hop(1, 2, "Fuel Ore"), _hop(2, 1, "Organics"))
    thin = _chain(_hop(3, 4, "Equipment"), _hop(4, 3, "Fuel Ore"))
    # Force thin to look "better" on discovery rank (same hop count; bump cr)
    thin = ProfitChain(
        sectors=thin.sectors,
        hops=thin.hops,
        overall_profit=999.0,
        turns=1,
        cr_per_turn=999.0,
        cr_per_execution=999.0,
    )
    remaining = {
        fresh.sectors: 10.0,
        thin.sectors: 0.5,
    }
    ranked = rank_chains_by_longevity([thin, fresh], remaining)
    assert ranked[0] is fresh
    assert ranked[1] is thin
    # chains.py re-export
    assert chains_rank([thin, fresh], remaining)[0] is fresh


def test_loop_depleting_coach_reads_chain_nearing_flag():
    from tw2002_aiclient.cockpit import decisions as dec

    assert dec._loop_depleting_from_intervention({"chain_nearing_depletion": True}) is True
    assert dec._loop_depleting_from_intervention({}) is False


def test_chain_scalars_merge_attaches_remaining_trades():
    from tw2002_aiclient.chain_status import (
        DEPLETION_STOP_RECOMMENDED_KEY,
        EXPLORE_APPETITE_RAISED_KEY,
        NEARING_DEPLETION_KEY,
        REMAINING_TRADES_KEY,
        ChainScalars,
    )

    hops = (
        _hop(1, 2, "Fuel Ore"),
        _hop(2, 1, "Organics"),
    )
    chain = _chain(*hops)
    cs = ChainScalars()
    cs._seen = True
    cs._hops = 2
    cs._unit = "hops"
    cs._best_chain = chain
    cs._ranked_chains = (chain,)
    cs._commodity_maps = {
        1: {
            "Fuel Ore": {"name": "Fuel Ore", "amount": 10},
            "Organics": {"name": "Organics", "amount": 10},
        },
        2: {
            "Fuel Ore": {"name": "Fuel Ore", "amount": 10},
            "Organics": {"name": "Organics", "amount": 10},
        },
    }
    # 10/40 = 0.25 → nearing
    status = {"current_ship": {"total_holds": 40, "ship_type": "Scout"}}
    merged = cs.merge(status)
    assert merged[REMAINING_TRADES_KEY] == 0.25
    assert merged[NEARING_DEPLETION_KEY] is True
    assert merged[EXPLORE_APPETITE_RAISED_KEY] is True
    assert merged[DEPLETION_STOP_RECOMMENDED_KEY] is True


def test_predicted_depletion_stop_reason_when_thin():
    from tw2002_aiclient.trade_driver import _predicted_depletion_stop
    from tw2002_aiclient import world_model

    class _Sess:
        last_current_ship = {"total_holds": 40, "ship_type": "Scout"}

        def current_ship_snapshot(self):
            return self.last_current_ship

    hops = (
        _hop(1, 2, "Fuel Ore"),
        _hop(2, 1, "Organics"),
    )
    chain = _chain(*hops)
    # Monkeypatch world_model.query via simple fake ports in predict path:
    # call helper with patched query returning amount=10 everywhere.
    real_query = world_model.query

    def _fake_query(world_id, pred, state_dir=None):
        return [
            {
                "sector_id": 1,
                "port": {
                    "commodities": [
                        {"name": "Fuel Ore", "status": "selling", "amount": 10},
                        {"name": "Organics", "status": "buying", "amount": 10},
                    ]
                },
            },
            {
                "sector_id": 2,
                "port": {
                    "commodities": [
                        {"name": "Fuel Ore", "status": "buying", "amount": 10},
                        {"name": "Organics", "status": "selling", "amount": 10},
                    ]
                },
            },
        ]

    world_model.query = _fake_query  # type: ignore[assignment]
    try:
        reason = _predicted_depletion_stop(
            _Sess(), chain, world_id="test-world", state_dir=None
        )
    finally:
        world_model.query = real_query  # type: ignore[assignment]
    assert reason is not None
    assert reason.startswith("depleted:predicted:")

def test_depletion_routes_via_hold_count_from_status(monkeypatch):
    """WO-BUILD-CHAIN-STATUS-HOLD-COUNT-WIRE: ChainScalars uses chains.hold_count_from_status."""
    from tw2002_aiclient import chains as chains_mod
    from tw2002_aiclient.chain_status import (
        DEPLETION_STOP_RECOMMENDED_KEY,
        EXPLORE_APPETITE_RAISED_KEY,
        NEARING_DEPLETION_KEY,
        REMAINING_TRADES_KEY,
        ChainScalars,
    )

    calls: list[object] = []
    real = chains_mod.hold_count_from_status

    def _spy(status):
        calls.append(status)
        return real(status)

    monkeypatch.setattr(chains_mod, "hold_count_from_status", _spy)

    hops = (
        _hop(1, 2, "Fuel Ore"),
        _hop(2, 1, "Organics"),
    )
    chain = _chain(*hops)
    cs = ChainScalars()
    cs._seen = True
    cs._hops = 2
    cs._unit = "hops"
    cs._best_chain = chain
    cs._ranked_chains = (chain,)
    cs._commodity_maps = {
        1: {
            "Fuel Ore": {"name": "Fuel Ore", "amount": 10},
            "Organics": {"name": "Organics", "amount": 10},
        },
        2: {
            "Fuel Ore": {"name": "Fuel Ore", "amount": 10},
            "Organics": {"name": "Organics", "amount": 10},
        },
    }
    status = {"current_ship": {"total_holds": 40, "ship_type": "Scout"}}
    merged = cs.merge(status)
    assert calls, "ChainScalars depletion must call chains.hold_count_from_status"
    # merge() may pass an enriched status mapping; hold keys must still resolve.
    assert calls[0].get("current_ship", {}).get("total_holds") == 40
    assert merged[REMAINING_TRADES_KEY] == 0.25
    assert merged[NEARING_DEPLETION_KEY] is True
    assert merged[EXPLORE_APPETITE_RAISED_KEY] is True
    assert merged[DEPLETION_STOP_RECOMMENDED_KEY] is True

