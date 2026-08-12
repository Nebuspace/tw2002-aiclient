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
import random
import sys
import time
from collections import defaultdict

import pytest

import tw2002_aiclient.chains as chains_module
from tw2002_aiclient.chains import (
    CHAIN_LINKS_PREFER_SEARCH_BELOW,
    DEFAULT_MAX_SEARCH_STEPS,
    MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE,
    MIN_CHAIN_LINKS_TO_EXECUTE,
    ProfitChain,
    TradeHop,
    find_profit_chains_with_note,
    is_executable_chain,
)


def _chains(hops, **kwargs):
    chains, _note = find_profit_chains_with_note(hops, **kwargs)
    return chains


def _top_chain(hops, **kwargs):
    chains, _note = find_profit_chains_with_note(hops, **kwargs)
    return chains[0] if chains else None


def _triangle():
    return [
        TradeHop(1, 2, "Equipment", 40, 1),
        TradeHop(2, 3, "Organics", 30, 1),
        TradeHop(3, 1, "Fuel Ore", 20, 1),
    ]


def test_triangle_longest_chain():
    chain = _top_chain(_triangle())
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
    assert _top_chain(hops) is None
    assert _chains(hops) == []


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
    chain = _top_chain(hops)
    assert chain is not None
    assert len(chain.hops) == 3
    assert chain.sectors[0] == 1


def _ranked_stub(*, hops: int, cr_per_turn: float, start: int = 1) -> ProfitChain:
    """Minimal ProfitChain for ranking pins (sectors/hops shapes unused by sort)."""
    hop_tuple = tuple(
        TradeHop(start + i, start + ((i + 1) % hops), "X", 1.0, 1)
        for i in range(hops)
    )
    sectors = tuple(start + i for i in range(hops)) + (start,)
    return ProfitChain(
        sectors=sectors,
        hops=hop_tuple,
        overall_profit=cr_per_turn * hops,
        turns=hops,
        cr_per_turn=cr_per_turn,
        cr_per_execution=cr_per_turn * hops,
    )


def test_rank_chains_hop_count_first_buries_short_rich_pair():
    """Canon discovery order (#523 surface bug when reused for earn)."""
    short_rich = _ranked_stub(hops=2, cr_per_turn=3.5, start=100)
    long_thin = _ranked_stub(hops=9, cr_per_turn=1.0, start=1)
    ranked = chains_module.rank_chains([short_rich, long_thin])
    assert ranked[0] is long_thin
    assert ranked[0].cr_per_turn == 1.0
    assert len(ranked[0].hops) == 9


def test_rank_chains_by_yield_surfaces_short_rich_over_long_thin():
    """Earn / credit-doubling pin: 2-hop @ 3.5 tops 9-hop @ 1.0."""
    short_rich = _ranked_stub(hops=2, cr_per_turn=3.5, start=100)
    long_thin = _ranked_stub(hops=9, cr_per_turn=1.0, start=1)
    ranked = chains_module.rank_chains_by_yield([long_thin, short_rich])
    assert ranked[0] is short_rich
    assert ranked[0].cr_per_turn == 3.5
    assert len(ranked[0].hops) == 2
    assert ranked[1] is long_thin


def test_rank_chains_by_yield_tiebreaks_equal_yield_by_hop_count():
    a = _ranked_stub(hops=2, cr_per_turn=3.5, start=10)
    b = _ranked_stub(hops=4, cr_per_turn=3.5, start=50)
    ranked = chains_module.rank_chains_by_yield([a, b])
    assert ranked[0] is b
    assert len(ranked[0].hops) == 4


def test_tie_on_length_higher_cr_per_turn_wins():
    hops = [
        TradeHop(1, 2, "A", 10, 1),
        TradeHop(2, 1, "B", 10, 1),  # 20/2 = 10 cr/turn
        TradeHop(3, 4, "C", 40, 1),
        TradeHop(4, 3, "D", 40, 1),  # 80/2 = 40 cr/turn
    ]
    chain = _top_chain(hops)
    assert chain is not None
    assert len(chain.hops) == 2
    assert chain.cr_per_turn == 40.0
    assert set(chain.sectors[:2]) == {3, 4}


def test_empty_hops():
    assert _top_chain([]) is None
    assert _chains([]) == []


def test_no_cycle_yields_no_chain():
    # A straight line with no warp back to the start -- never a closed cycle.
    hops = [
        TradeHop(1, 2, "A", 10, 1),
        TradeHop(2, 3, "B", 10, 1),
    ]
    assert _top_chain(hops) is None
    assert _chains(hops) == []


def test_rotation_dedups_the_same_cycle_regardless_of_start_node():
    # The same 3-cycle discovered from every possible starting node still
    # normalizes to ONE chain, not three duplicates.
    hops = [
        TradeHop(5, 6, "A", 10, 1),
        TradeHop(6, 7, "B", 10, 1),
        TradeHop(7, 5, "C", 10, 1),
    ]
    chains = _chains(hops)
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
    assert _chains(hops, max_hops=3) == []
    chain = _top_chain(hops, max_hops=4)
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


# -- search budget (WO-CHAIN-SEARCH-BUDGET) --------------------------------
#
# `find_profit_chains`'s original recursive DFS had no depth/iteration
# bound: an unbranched ring of ~999 sectors overflows Python's default
# recursion limit, and a complete K9 graph takes 6.43s for one chain
# (`trade_adapter.build_trade_hops`'s 500-edge cap does not protect the
# finder -- 500 mutually-compatible edges over ~23 sectors is already a
# complete K23). `_search_cycles` replaced the recursion with an
# explicit-stack iterative DFS bounded by `max_search_steps`, structurally
# closing off `RecursionError` rather than merely raising the ceiling.


def _ring(n):
    """Unbranched directed cycle: 0->1->2->...->(n-1)->0. No branching,
    so DFS depth (not breadth) is the only way to blow this up -- exactly
    the shape that overflowed the pre-budget recursive algorithm."""
    return [TradeHop(i, (i + 1) % n, "X", 10.0, 1) for i in range(n)]


def _complete(n):
    """Complete directed graph K_n -- every ordered pair is an edge. This
    is a breadth blowup (branching factor n-1 at every node), the shape
    `trade_adapter`'s edge-count cap does not protect against."""
    hops = []
    for i in range(n):
        for j in range(n):
            if i != j:
                hops.append(TradeHop(i, j, "X", 10.0, 1))
    return hops


def _legacy_find_profit_chains(hops, *, min_hops=2, max_hops=None):
    """Vendored, unmodified copy of the PRE-WO-CHAIN-SEARCH-BUDGET
    recursive `find_profit_chains` (git blob 2f8a505:tw2002_aiclient/
    chains.py, the seed commit this WO built on) -- the reference oracle
    for the differential-equality proof below. Do NOT "fix" or refactor
    this copy: its entire job is to disagree with the new iterative
    implementation if (and only if) the conversion introduced a
    behavioral drift, and it is expected to genuinely crash on inputs
    the new budget was built to survive (see the RecursionError tests
    below, which exercise exactly that)."""
    usable = [h for h in hops if h.margin > 0 and h.turns > 0]
    adj = defaultdict(list)
    for h in usable:
        adj[h.frm].append(h)

    found = {}

    def record(path_nodes, path_hops):
        sectors = chains_module._normalize_cycle(tuple(path_nodes + [path_nodes[0]]))
        start = sectors[0]
        rot = path_nodes.index(start)
        hops_rot = tuple(path_hops[rot:] + path_hops[:rot])
        overall = sum(h.margin for h in hops_rot)
        turns = sum(h.turns for h in hops_rot)
        chain = ProfitChain(
            sectors=sectors,
            hops=hops_rot,
            overall_profit=overall,
            turns=turns,
            cr_per_turn=(overall / turns) if turns else 0.0,
            cr_per_execution=overall,
        )
        key = sectors
        prev = found.get(key)
        if prev is None or chain.cr_per_turn > prev.cr_per_turn:
            found[key] = chain

    def dfs(start, node, path_nodes, path_hops):
        if max_hops is not None and len(path_hops) >= max_hops:
            return
        for hop in adj.get(node, ()):
            nxt = hop.to
            if nxt == start and len(path_hops) + 1 >= min_hops:
                record(path_nodes, path_hops + [hop])
                continue
            if nxt in path_nodes:
                continue
            if max_hops is not None and len(path_hops) + 1 > max_hops:
                continue
            dfs(start, nxt, path_nodes + [nxt], path_hops + [hop])

    for start in list(adj.keys()):
        dfs(start, start, [start], [])

    return chains_module.rank_chains(list(found.values()))


def _random_graph(rng, n_nodes):
    """A small, seeded, pseudo-random directed graph -- deliberately
    capped at <=7 nodes: the DENSEST possible graph in that range (K7,
    see `test_k7_completes_without_truncation` below) still finishes
    comfortably inside `DEFAULT_MAX_SEARCH_STEPS`, so every graph this
    generates is guaranteed to fall under the budget regardless of the
    edge pattern drawn."""
    commodities = ["Equipment", "Organics", "Fuel Ore"]
    hops = []
    for i in range(n_nodes):
        for j in range(n_nodes):
            if i == j:
                continue
            if rng.random() < 0.35:
                margin = rng.choice([0.0, rng.uniform(-15.0, 80.0)])
                turns = rng.choice([0, 1, 1, 2, 3])
                hops.append(TradeHop(i, j, rng.choice(commodities), margin, turns))
            if rng.random() < 0.08:
                # Occasional parallel edge on the same (i, j) pair --
                # the finder does not dedupe multi-edges.
                hops.append(
                    TradeHop(i, j, rng.choice(commodities), rng.uniform(-15.0, 80.0), rng.choice([1, 2]))
                )
    return hops


def test_k7_completes_without_truncation():
    """Establishes the differential fuzz's safety margin: K7, the
    densest possible 7-node graph, finishes well under the default
    budget with no truncation note."""
    t0 = time.perf_counter()
    chains, note = find_profit_chains_with_note(_complete(7))
    elapsed = time.perf_counter() - t0
    assert note is None
    assert len(chains) > 0
    # Generous machine canary LAST — never mask the deterministic asserts above.
    assert elapsed < 1.0


def test_differential_iterative_matches_legacy_recursive_on_small_graphs():
    """Accept #3's differential proof: 300 seeded pseudo-random small
    graphs (<=7 nodes, so none can hit the budget -- see
    `test_k7_completes_without_truncation`), each checked for EXACT
    equality (same chains, same order, same metrics) between the new
    iterative implementation and the vendored pre-change recursive
    oracle. This is strictly stronger than re-running the 13 existing
    hand-written cases: those sample 13 fixed shapes, while the
    recursion-to-iteration conversion could in principle reorder
    traversal and silently flip which of two equal-ranked chains wins a
    tie -- something only a broad, varied differential sweep can catch."""
    rng = random.Random(20260728)
    for i in range(300):
        n = rng.randint(3, 7)
        hops = _random_graph(rng, n)
        min_hops = rng.choice([2, 2, 2, 3])
        max_hops = rng.choice([None, None, None, rng.randint(2, n)])

        expected = _legacy_find_profit_chains(hops, min_hops=min_hops, max_hops=max_hops)
        actual, note = find_profit_chains_with_note(hops, min_hops=min_hops, max_hops=max_hops)

        assert note is None, (
            f"case {i} unexpectedly truncated (n={n} min_hops={min_hops} "
            f"max_hops={max_hops} note={note!r})"
        )
        assert actual == expected, (
            f"case {i} diverged from the legacy oracle (n={n} min_hops={min_hops} "
            f"max_hops={max_hops})\nhops={hops}\nexpected={expected}\nactual={actual}"
        )


# WO-CHAIN-K9-BUDGET-ASSERT: a wall-clock comparison is a property of the
# MACHINE, never of the algorithm, so it may only ever be a LAST, generous
# backstop -- never the assert that decides whether a test passes.
#
# Ordered FIRST (as `ring_500` and `K9` both were), it *masks*: a slow or
# loaded box reddens the test on a timing property, the correctness asserts
# below it never execute, and the failure reads as "the machine was busy".
# A genuine truncation regression is then invisible -- you retune the
# threshold and ship the bug.
#
# What IS deterministic here is the budget: whether `DEFAULT_MAX_SEARCH_STEPS`
# is exhausted depends only on the graph and the constant, and is identical on
# every machine. That is the primary claim these tests should make.
#
# pytest.ini already sets a global `timeout = 120`, so a genuine hang is a
# named failure regardless. This canary therefore carries only the "budget
# stopped bounding the search at all" signal, and can afford to be generous.
_BUDGET_CANARY_S = 10.0


def test_ring_500_truncates_with_a_budget_note():
    hops = _ring(500)
    t0 = time.perf_counter()
    chains, note = find_profit_chains_with_note(hops)
    elapsed = time.perf_counter() - t0

    # Deterministic primary asserts -- machine-independent.
    assert note is not None, "ring(500) must exhaust the search budget"
    assert str(DEFAULT_MAX_SEARCH_STEPS) in note, (
        f"the note must name the budget that fired, got: {note!r}"
    )
    assert "partial" in note, f"a truncated result must say it is partial, got: {note!r}"

    # Generous machine canary, LAST so it can never mask the above.
    assert elapsed < _BUDGET_CANARY_S, (
        f"ring(500) took {elapsed:.3f}s -- the search budget may have stopped bounding"
    )


def test_complete_k9_truncates_with_a_budget_note():
    hops = _complete(9)
    t0 = time.perf_counter()
    chains, note = find_profit_chains_with_note(hops)
    elapsed = time.perf_counter() - t0

    # Deterministic primary asserts -- machine-independent.
    assert note is not None, "complete K9 must exhaust the search budget"
    assert str(DEFAULT_MAX_SEARCH_STEPS) in note, (
        f"the note must name the budget that fired, got: {note!r}"
    )
    assert "partial" in note, f"a truncated result must say it is partial, got: {note!r}"

    # Generous machine canary, LAST so it can never mask the above.
    assert elapsed < _BUDGET_CANARY_S, (
        f"K9 took {elapsed:.3f}s -- the search budget may have stopped bounding"
    )


def test_ring_5000_and_50000_return_normally_without_recursion_error():
    # Already correctly ordered before this WO -- the two deterministic
    # asserts precede the timing one. Only the canary is widened, onto the
    # shared constant, so the whole class has one threshold to reason about.
    for n in (5000, 50000):
        t0 = time.perf_counter()
        chain = _top_chain(_ring(n))
        elapsed = time.perf_counter() - t0
        assert chain is not None, f"ring({n}) found no chain"
        assert len(chain.hops) == n
        assert elapsed < _BUDGET_CANARY_S, f"ring({n}) took {elapsed:.3f}s"


def test_ring_999_crashes_the_legacy_recursive_algorithm_but_not_the_new_one():
    """The exact repro measured for WO-CHAIN-SEARCH-BUDGET: an unbranched
    ring of 999 sectors overflows Python's DEFAULT recursion limit
    (deliberately not modified here, to match the original repro
    conditions) under the pre-change algorithm. The new iterative
    `find_profit_chains` handles the identical input normally."""
    hops = _ring(999)
    with pytest.raises(RecursionError):
        _legacy_find_profit_chains(hops)

    chain = _top_chain(hops)
    assert chain is not None
    assert len(chain.hops) == 999


def test_iterative_search_never_touches_the_python_call_stack():
    """Mutation-proof for 'RecursionError cannot escape under any
    input': shrink Python's recursion limit to just above however deep
    pytest's own ambient call stack already is, then hand both
    implementations a ring deep enough to blow well past that. The
    legacy oracle (real Python recursion) crashes immediately; the new
    `find_profit_chains` -- an explicit stack, never a Python call --
    is structurally unaffected regardless of how deep the graph is, not
    merely because today's default limit (1000) exceeds today's input
    sizes."""
    ambient_depth = len(inspect.stack())
    tight_limit = ambient_depth + 40
    hops = _ring(tight_limit + 200)
    old_limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(tight_limit)
        with pytest.raises(RecursionError):
            _legacy_find_profit_chains(hops)

        chain = _top_chain(hops)
        assert chain is not None
        assert len(chain.hops) == tight_limit + 200
    finally:
        sys.setrecursionlimit(old_limit)


def test_max_search_steps_actually_bounds_the_search():
    """Mutation-proof that the budget genuinely stops the search, not
    just that pathological inputs happen to finish fast: ring(50) needs
    on the order of 50 DFS frame-visits to close its one cycle, so a
    budget of 5 must truncate before ever reaching the closing hop --
    if the `steps > max_search_steps` guard in `_search_cycles` were
    removed or miswired, this would instead run to completion and
    return the full 50-hop chain."""
    hops = _ring(50)
    chains, note = find_profit_chains_with_note(hops, max_search_steps=5)
    assert chains == []
    assert note is not None
    assert "exhausted at 5 DFS steps" in note


def test_default_max_search_steps_is_configurable_not_magic():
    assert DEFAULT_MAX_SEARCH_STEPS == 100_000
    # A caller-supplied budget overrides the default and is honored.
    chains, note = find_profit_chains_with_note(_ring(50), max_search_steps=1_000_000)
    assert note is None
    assert len(chains) == 1


def test_in_degree_zero_start_does_not_starve_budget_for_real_pairs():
    """Live academy regression: SSS (all-selling) ports have out-degree but
    in-degree 0. Insertion order put them first as DFS starts; the open tree
    exhausted DEFAULT_MAX_SEARCH_STEPS with 0 chains while mutual pairs
    existed elsewhere — UI fell back to a 2-port class pair.

    A cycle that starts at S must return to S, so in-degree-0 starts are
    skipped. This graph reproduces the starvation shape under a modest
    budget: without the skip, `dead` burns the budget before the pair is
    ever used as a start.
    """
    dead = 9000
    hops: list[TradeHop] = []
    leaves = list(range(100, 112))
    for leaf in leaves:
        hops.append(TradeHop(dead, leaf, "Equipment", 10, 1))
    for a in leaves:
        for b in leaves:
            if a != b:
                hops.append(TradeHop(a, b, "Organics", 1, 1))
    hops.append(TradeHop(1, 2, "Fuel Ore", 40, 1))
    hops.append(TradeHop(2, 1, "Organics", 40, 1))

    found, note = find_profit_chains_with_note(hops, max_search_steps=20_000)
    assert any(
        len(c.hops) == 2 and set(c.sectors[:2]) == {1, 2} for c in found
    ), ([(len(c.hops), c.sectors) for c in found[:5]], note)


def test_hold_scaled_cr_per_turn_multiplies_unit_by_holds():
    from tw2002_aiclient.chains import hold_scaled_cr_per_turn

    assert hold_scaled_cr_per_turn(3.5, 100) == 350.0
    assert hold_scaled_cr_per_turn(1.0, 20) == 20.0


def test_hold_scaled_cr_per_turn_fail_closed():
    from tw2002_aiclient.chains import hold_scaled_cr_per_turn

    assert hold_scaled_cr_per_turn(3.5, None) is None
    assert hold_scaled_cr_per_turn(3.5, 0) is None
    assert hold_scaled_cr_per_turn(3.5, -1) is None
    assert hold_scaled_cr_per_turn(3.5, True) is None
    assert hold_scaled_cr_per_turn(None, 10) is None
    assert hold_scaled_cr_per_turn(True, 10) is None
    assert hold_scaled_cr_per_turn(float("nan"), 10) is None


def test_hold_count_from_status_prefers_upgrade_player():
    from tw2002_aiclient.chains import hold_count_from_status

    assert hold_count_from_status(
        {"upgrade_player": {"current_holds": 55}, "current_ship": {"total_holds": 10}}
    ) == 55
    assert hold_count_from_status({"current_ship": {"total_holds": 40}}) == 40
    assert hold_count_from_status({}) is None
    assert hold_count_from_status({"upgrade_player": {"current_holds": 0}}) is None
    assert hold_count_from_status(None) is None
