"""TW-21 longest-profit-chain algorithm tests (synthetic graphs)."""

from twclient.chains import (
    TradeHop,
    chain_as_library_row,
    find_profit_chains,
    format_coach_callout,
    longest_profit_chain,
)


def _triangle():
    return [
        TradeHop(1, 2, "Equipment", 40, 1),
        TradeHop(2, 3, "Organics", 30, 1),
        TradeHop(3, 1, "Fuel Ore", 20, 1),
    ]


def test_triangle_longest_and_callout():
    chain = longest_profit_chain(_triangle())
    assert chain is not None
    assert len(chain.hops) == 3
    assert chain.overall_profit == 90
    assert chain.turns == 3
    assert chain.cr_per_turn == 30.0
    # Normalized so min sector (1) is first.
    assert chain.sectors == (1, 2, 3, 1)
    text = format_coach_callout(chain)
    assert "1→2→3→1" in text
    assert "+90" in text
    assert "3 turns" in text


def test_negative_hop_breaks_triangle():
    hops = [
        TradeHop(1, 2, "Equipment", 40, 1),
        TradeHop(2, 3, "Organics", -5, 1),  # ignored
        TradeHop(3, 1, "Fuel Ore", 20, 1),
    ]
    assert longest_profit_chain(hops) is None
    assert find_profit_chains(hops) == []


def test_longer_cycle_preferred_over_shorter_higher_cprt():
    hops = [
        # Short rich pair: 2 hops, 100 cr, 2 turns → 50 cr/turn
        TradeHop(10, 11, "A", 50, 1),
        TradeHop(11, 10, "B", 50, 1),
        # Longer thinner triangle: 3 hops, 30 cr, 3 turns → 10 cr/turn
        TradeHop(1, 2, "X", 10, 1),
        TradeHop(2, 3, "Y", 10, 1),
        TradeHop(3, 1, "Z", 10, 1),
    ]
    chain = longest_profit_chain(hops)
    assert chain is not None
    assert len(chain.hops) == 3
    assert chain.sectors[0] == 1


def test_tie_on_length_higher_cr_per_turn_wins():
    hops = [
        TradeHop(1, 2, "A", 10, 1),
        TradeHop(2, 1, "B", 10, 1),  # 20/2 = 10 cr/turn
        TradeHop(3, 4, "C", 40, 1),
        TradeHop(4, 3, "D", 40, 1),  # 80/2 = 40 cr/turn
    ]
    chain = longest_profit_chain(hops)
    assert chain is not None
    assert len(chain.hops) == 2
    assert chain.cr_per_turn == 40.0
    assert set(chain.sectors[:2]) == {3, 4}


def test_empty_hops():
    assert longest_profit_chain([]) is None
    assert find_profit_chains([]) == []


def test_library_row_bridge():
    chain = longest_profit_chain(_triangle())
    assert chain is not None
    row = chain_as_library_row(chain)
    assert row["source"] == "discovered"
    assert row["steps"] == 3
    assert row["demo_profit"] == 90
    assert row["profit_per_turn"] == 30.0
    assert row["profit_per_action"] == 90
