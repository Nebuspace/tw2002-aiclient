from dataclasses import replace

from tw2002_aiclient.chains import ProfitChain, TradeHop
from tw2002_aiclient.trade_chain_plan import (
    compose_confirm_action,
    plan_from_chain,
    resolve_exact_chain,
)


def _chain(*, second_commodity="Equipment", margin=10.0):
    hops = (
        TradeHop(frm=10, to=11, commodity="Fuel Ore", margin=margin, turns=1),
        TradeHop(frm=11, to=10, commodity=second_commodity, margin=9.0, turns=1),
    )
    return ProfitChain(
        sectors=(10, 11, 10),
        hops=hops,
        overall_profit=margin + 9.0,
        turns=2,
        cr_per_turn=(margin + 9.0) / 2,
        cr_per_execution=margin + 9.0,
    )


def test_plan_names_exact_route_postures_and_stable_identity():
    first = plan_from_chain("world-a", _chain())
    second = plan_from_chain("world-a", _chain())

    assert first == second
    assert first.route == "10>11>10"
    assert first.commodity_route == "Fuel Ore>Equipment"
    assert first.start_anchor == 10
    assert len(first.fingerprint) == 64


def test_identity_changes_with_world_route_or_commodity():
    base = plan_from_chain("world-a", _chain()).fingerprint
    assert plan_from_chain("world-b", _chain()).fingerprint != base
    assert plan_from_chain("world-a", _chain(second_commodity="Organics")).fingerprint != base
    assert plan_from_chain("world-a", _chain(margin=11.0)).fingerprint != base


def test_incomplete_or_non_executable_chain_refuses():
    valid = _chain()
    assert plan_from_chain("", valid) is None
    assert plan_from_chain("world-a", object()) is None
    assert plan_from_chain("world-a", replace(valid, sectors=(10, 11, 12))) is None
    assert plan_from_chain("world-a", replace(valid, hops=valid.hops[:1])) is None
    assert plan_from_chain(
        "world-a",
        replace(
            valid,
            hops=(
                replace(valid.hops[0], commodity="Colonists"),
                valid.hops[1],
            ),
        ),
    ) is None


def test_resolve_requires_one_exact_current_match_never_substitutes():
    chain = _chain()
    other = _chain(second_commodity="Organics")
    fingerprint = plan_from_chain("world-a", chain).fingerprint

    assert resolve_exact_chain("world-a", fingerprint, [other, chain]) is chain
    assert resolve_exact_chain("world-a", fingerprint, [other]) is None
    assert resolve_exact_chain("world-a", fingerprint, [chain, chain]) is None
    assert resolve_exact_chain("world-a", "not-a-fingerprint", [chain]) is None


def test_confirm_names_one_pass_route_commodities_and_both_floors():
    plan = plan_from_chain("world-a", _chain())
    action = compose_confirm_action(plan, cash_floor=1_000, turn_reserve=10)

    assert action == (
        "Trade 10>11>10 — Fuel Ore>Equipment; one pass, "
        "2 hops, floor 1000cr, reserve 10t"
    )
    assert compose_confirm_action(plan, cash_floor=None, turn_reserve=10) is None
    assert compose_confirm_action(plan, cash_floor=1000, turn_reserve=True) is None
