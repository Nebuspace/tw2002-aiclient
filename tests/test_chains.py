"""Longest-profit-chain algorithm tests (synthetic graphs).

Ported onto `tw2002_aiclient.chains` (ADR-001: one import tree, `twclient`
is gone). `format_coach_callout`/`chain_as_library_row` are NOT ported --
the archive marks both PARKED with no production caller
(`tw2002_aiclient/cockpit/chains.py::compose_chain_lines` already owns
chain rendering in the reborn tree; porting a second formatter would
compete with it) -- so the two archive tests exercising only those
functions are dropped, not carried forward.
"""

import ast
import inspect

import tw2002_aiclient.chains as chains_module
from tw2002_aiclient.chains import (
    CHAIN_LINKS_PREFER_SEARCH_BELOW,
    MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE,
    MIN_CHAIN_LINKS_TO_EXECUTE,
    ProfitChain,
    TradeHop,
    find_profit_chains,
    is_executable_chain,
    longest_profit_chain,
)


def _triangle():
    return [
        TradeHop(1, 2, "Equipment", 40, 1),
        TradeHop(2, 3, "Organics", 30, 1),
        TradeHop(3, 1, "Fuel Ore", 20, 1),
    ]


def test_triangle_longest_chain():
    chain = longest_profit_chain(_triangle())
    assert chain is not None
    assert len(chain.hops) == 3
    assert chain.overall_profit == 90
    assert chain.turns == 3
    assert chain.cr_per_turn == 30.0
    # Normalized so min sector (1) is first.
    assert chain.sectors == (1, 2, 3, 1)


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
        # Short rich pair: 2 hops, 100 cr, 2 turns -> 50 cr/turn
        TradeHop(10, 11, "A", 50, 1),
        TradeHop(11, 10, "B", 50, 1),
        # Longer thinner triangle: 3 hops, 30 cr, 3 turns -> 10 cr/turn
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


def test_no_cycle_yields_no_chain():
    # A straight line with no warp back to the start -- never a closed cycle.
    hops = [
        TradeHop(1, 2, "A", 10, 1),
        TradeHop(2, 3, "B", 10, 1),
    ]
    assert longest_profit_chain(hops) is None
    assert find_profit_chains(hops) == []


def test_rotation_dedups_the_same_cycle_regardless_of_start_node():
    # The same 3-cycle discovered from every possible starting node still
    # normalizes to ONE chain, not three duplicates.
    hops = [
        TradeHop(5, 6, "A", 10, 1),
        TradeHop(6, 7, "B", 10, 1),
        TradeHop(7, 5, "C", 10, 1),
    ]
    chains = find_profit_chains(hops)
    assert len(chains) == 1
    assert chains[0].sectors == (5, 6, 7, 5)


def test_max_hops_bounds_the_search():
    # A 4-cycle exists, but max_hops=3 must never surface it.
    hops = [
        TradeHop(1, 2, "A", 10, 1),
        TradeHop(2, 3, "B", 10, 1),
        TradeHop(3, 4, "C", 10, 1),
        TradeHop(4, 1, "D", 10, 1),
    ]
    assert find_profit_chains(hops, max_hops=3) == []
    chain = longest_profit_chain(hops, max_hops=4)
    assert chain is not None
    assert len(chain.hops) == 4


# -- chain execute-floor thresholds (canon/strategy/trade-loops.md) --------


def test_chain_link_threshold_constants_match_canon():
    assert MIN_CHAIN_LINKS_TO_EXECUTE == 2
    assert CHAIN_LINKS_PREFER_SEARCH_BELOW == MIN_CHAIN_LINKS_TO_EXECUTE
    assert MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE == 4


def _hop():
    return TradeHop(1, 2, "Equipment", 10, 1)


def _chain(n_hops):
    hops = tuple(_hop() for _ in range(n_hops))
    return ProfitChain(
        sectors=tuple(range(n_hops + 1)),
        hops=hops,
        overall_profit=10.0 * n_hops,
        turns=n_hops,
        cr_per_turn=10.0,
        cr_per_execution=10.0 * n_hops,
    )


def test_is_executable_chain_true_at_the_two_link_floor():
    assert is_executable_chain(_chain(2)) is True


def test_is_executable_chain_false_below_the_floor():
    assert is_executable_chain(_chain(1)) is False
    assert is_executable_chain(_chain(0)) is False


def test_is_executable_chain_true_above_the_floor():
    assert is_executable_chain(_chain(4)) is True


def test_min_chain_links_to_execute_has_exactly_one_pure_consumer():
    """Pins the WO's "no picker, no EV scorer, no which-loop-to-run
    function" constraint structurally. Counted via `ast.Name` nodes (not
    a text/docstring count, which would conflate prose mentions with
    real references): the assignment target itself, the
    `CHAIN_LINKS_PREFER_SEARCH_BELOW` alias's RHS, and the one Load
    inside `is_executable_chain` -- exactly 3 code references. A new
    consumer (a picker, a ranker) would add a 4th and fail this."""
    tree = ast.parse(inspect.getsource(chains_module))
    refs = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "MIN_CHAIN_LINKS_TO_EXECUTE"]
    assert len(refs) == 3
