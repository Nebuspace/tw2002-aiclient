"""Priority engine — rank competing TW2002 client objectives.

Design brief: ``priority_engine.md`` (repo root of tw2002-aiclient).

This module is the **driver** for "what should we focus on now?" It sits
above the per-kind scorers in ``autopilot.py`` and adds the missing
piece: **round-trip execution cost** before abandoning in-progress work
(e.g. leave a trade chain for StarDock, buy a ship, come back).

Pure logic — no daemon I/O. Autopilot may call ``recommend_actions()`` / wire
``rank_action_priorities()`` into ``select()``; spectate renders the ranked
list via ``compose_priorities_lines()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence

from .explore import path_to_sector

# ---------------------------------------------------------------------------
# Fighter affordability constants (2026-07-22)
# ---------------------------------------------------------------------------

# Unit price at Class-0 ports (e.g. Sol, sector 1 — always reachable as start).
# Source: GameBanshee / community guides.  UNVERIFIED against live game; treat as
# a configurable placeholder until confirmed by an introspected Class-0 port screen.
FIGHTER_UNIT_PRICE_CLASS0: int = 100  # cr per fighter

# Small defensive stack to evaluate ("can I buy some fighters?").
# Mirrors fighter_toll_policy.DEFAULT_FIGHTER_RESERVE — if you change the
# reserve floor there, update this too.
FIGHTER_SMALL_STACK: int = 5  # fighters

# Execute floor: grind when the best known chain has at least this many
# links (``len(ProfitChain.hops)``). Max (2026-07-22): a 2-hop chain
# (two ports back-and-forth, or three sectors / two edges) is enough to
# ungate Trade chain and prefer it over Explore. One-hop / empty stays
# discovery-only.
MIN_CHAIN_LINKS_TO_EXECUTE = 2
# Once execute is allowed, prefer *earning* over hunting a longer chain.
# Exploring remains a secondary candidate by EV.
CHAIN_LINKS_PREFER_SEARCH_BELOW = MIN_CHAIN_LINKS_TO_EXECUTE
# Ship purchase / StarDock hull upgrade waits until the best chain is at
# least this long — at 2–3 links, cash goes to fighters + holds first.
MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE = 4


@dataclass(frozen=True)
class PriorityScore:
    """One ranked focus candidate (action kind or catalog goal id)."""

    kind: str
    """``run_chain`` | ``upgrade`` | ``explore`` (Layer 2 actions today)."""

    ev_per_turn: Optional[float]
    """Comparable cr/turn when ungated; None when gated / unknown."""

    gated: bool
    gate_reason: Optional[str] = None
    travel_cost_rt: Optional[int] = None
    """Round-trip warp turns when this action is a detour from interrupted work."""

    travel_one_way: Optional[int] = None
    rationale: str = ""
    weight: int = 0
    """Catalog weight for future boolean overlay (Layer 1)."""


@dataclass(frozen=True)
class PriorityRecommendation:
    """Engine output: ordered scores + current focus."""

    ranked: tuple[PriorityScore, ...]
    focus: Optional[PriorityScore]
    """Top ungated score, or None if everything gated."""

    stay_vs_leave: Optional[str] = None
    """Human-readable stay-trading vs leave-for-upgrade verdict when both apply."""

    notes: tuple[str, ...] = field(default_factory=tuple)


def hops_of_path(path: Optional[Sequence[int]]) -> Optional[int]:
    """Inclusive sector path → warp hop count. None path → unknown."""
    if path is None:
        return None
    if len(path) == 0:
        return None
    return max(0, len(path) - 1)


def travel_cost_rt_turns(
    hops_out: int,
    hops_return: int,
    turns_per_warp: int,
) -> int:
    """Warp turns for out + return on the **current** hull."""
    if turns_per_warp < 1:
        turns_per_warp = 1
    return (max(0, hops_out) + max(0, hops_return)) * turns_per_warp


def compute_return_path(
    graph: Mapping[int, Sequence[int]],
    from_sector: int,
    to_sector: int,
) -> Optional[tuple[int, ...]]:
    """Shortest known-graph path for the return leg (e.g. StarDock → chain start)."""
    return path_to_sector(graph, from_sector, to_sector)


def stay_vs_leave_upgrade(
    *,
    chain_cr_per_turn: float,
    upgrade_extra_cr_per_turn: float,
    travel_cost_rt: int,
    payback: float,
    productive_turns: int,
) -> tuple[bool, str]:
    """Whether leaving the chain for an upgrade beats staying.

    Returns ``(leave_for_upgrade, reason)``.

    Rule (v0): debit chain profit forgone during RT travel; credit the
    upgrade's extra cr/turn only on productive turns **after** RT+payback.
    Leave only when that net gain is positive.
    """
    if productive_turns <= 0:
        return False, "no productive turns left — stay put"
    if travel_cost_rt < 0 or payback < 0:
        return False, "invalid travel/payback — stay (fail-closed)"

    remaining_after = productive_turns - travel_cost_rt - payback
    if remaining_after <= 0:
        return False, (
            f"RT {travel_cost_rt}t + payback {payback:.1f}t exhausts "
            f"{productive_turns}t productive — stay trading"
        )

    forgone = chain_cr_per_turn * travel_cost_rt
    gain = upgrade_extra_cr_per_turn * remaining_after
    if gain > forgone:
        return True, (
            f"leave for upgrade: gain {gain:.1f}cr over {remaining_after:.1f}t "
            f"> forgone {forgone:.1f}cr during {travel_cost_rt}t RT"
        )
    return False, (
        f"stay trading: forgone {forgone:.1f}cr during {travel_cost_rt}t RT "
        f">= upgrade gain {gain:.1f}cr over {remaining_after:.1f}t"
    )


def prefer_search_over_earn(
    *,
    chain_links: int,
    explore_available: bool,
    min_execute: int = MIN_CHAIN_LINKS_TO_EXECUTE,
    prefer_search_below: int = CHAIN_LINKS_PREFER_SEARCH_BELOW,
) -> tuple[bool, str]:
    """Earn-vs-search: grind the chain, or keep mapping for a longer one?

    Returns ``(prefer_explore, reason)``.

    Policy (human 2026-07-23):
    - ``links < min_execute`` → must search (execute gated separately)
    - ``links >= min_execute`` → prefer earn (fighters/holds from the
      chain we have); a longer/more profitable chain still ranks higher
      when discovered, but we do not defer grinding to hunt one
    - ``prefer_search_below`` defaults to ``min_execute`` (empty search
      band). Callers may raise it to restore a hunt-before-grind window.
    """
    if chain_links < min_execute:
        return True, (
            f"search: have {chain_links}-link chain; need ≥{min_execute} to execute"
        )
    if explore_available and chain_links < prefer_search_below:
        return True, (
            f"search: have {chain_links}-link; hunt longer before grinding "
            f"(earn preferred from {prefer_search_below}+ links)"
        )
    if not explore_available:
        return False, f"earn: {chain_links}-link chain; no frontier — grind"
    return False, (
        f"earn: {chain_links}-link chain ≥ {prefer_search_below}; "
        f"grind for fighters/holds (explore secondary)"
    )


def recommend_actions(
    *,
    # Chain (interrupted work)
    chain_cr_per_turn: Optional[float] = None,
    chain_cycle_turns: Optional[int] = None,
    chain_link_count: Optional[int] = None,
    at_chain_start: bool = False,
    # Upgrade target
    upgrade_extra_cr_per_turn: Optional[float] = None,
    upgrade_payback: Optional[float] = None,
    upgrade_ship_name: Optional[str] = None,
    # Travel
    hops_to_stardock: Optional[int] = None,
    hops_return_to_work: Optional[int] = None,
    turns_per_warp: int = 1,
    # Budget / explore
    turns_left: Optional[int] = None,
    turn_reserve: int = 0,
    explore_available: bool = False,
    explore_baseline_ev: float = 0.01,
    require_rt_when_chain_active: bool = True,
    min_chain_links_to_execute: int = MIN_CHAIN_LINKS_TO_EXECUTE,
    chain_links_prefer_search_below: int = CHAIN_LINKS_PREFER_SEARCH_BELOW,
    min_chain_links_for_ship_upgrade: int = MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE,
) -> PriorityRecommendation:
    """Rank ``run_chain`` / ``upgrade`` / ``explore`` with RT-aware upgrade gating.

    Callers supply already-parsed economics (from autopilot / world snapshot).
    Unknowns fail-closed — never guess StarDock distance or return path.

    ``chain_link_count`` is ``len(ProfitChain.hops)`` (a 3-link cycle has
    three hops). Execute requires ≥ ``min_chain_links_to_execute`` (default 3).
    Ship hull upgrades wait until ≥ ``min_chain_links_for_ship_upgrade``
    (default 4) so a 3-link chain funds fighters/holds first.
    """
    scores: list[PriorityScore] = []
    notes: list[str] = []
    stay_vs_leave: Optional[str] = None
    earn_vs_search: Optional[str] = None

    productive: Optional[int] = None
    if turns_left is not None:
        productive = max(0, turns_left - max(0, turn_reserve))

    links = chain_link_count
    if links is None and chain_cr_per_turn is not None:
        # Fail-closed on unknown length when we somehow have EV without
        # hop count — treat as too short to execute.
        links = 0

    # --- run_chain ---
    if chain_cr_per_turn is None:
        scores.append(
            PriorityScore(
                kind="run_chain",
                ev_per_turn=None,
                gated=True,
                gate_reason="run_chain: no profitable cycle",
                rationale="no chain",
                weight=40,
            )
        )
    elif turns_left is None:
        scores.append(
            PriorityScore(
                kind="run_chain",
                ev_per_turn=None,
                gated=True,
                gate_reason="run_chain: turns_left unknown",
                rationale="fail-closed turn budget",
                weight=40,
            )
        )
    elif chain_cycle_turns is not None and productive is not None and productive < chain_cycle_turns:
        scores.append(
            PriorityScore(
                kind="run_chain",
                ev_per_turn=None,
                gated=True,
                gate_reason=(
                    f"run_chain: needs {chain_cycle_turns}t > {productive}t productive"
                ),
                rationale="turn-reserve floor",
                weight=40,
            )
        )
    elif links is not None and links < min_chain_links_to_execute:
        scores.append(
            PriorityScore(
                kind="run_chain",
                ev_per_turn=None,
                gated=True,
                gate_reason=(
                    f"run_chain: need ≥{min_chain_links_to_execute}-link chain "
                    f"(have {links})"
                ),
                rationale=f"{links}-link below execute floor",
                weight=40,
            )
        )
        earn_vs_search = (
            f"search: have {links}-link chain; need ≥{min_chain_links_to_execute} to execute"
        )
    else:
        # Longer / higher-EV chains already win via chain_cr_per_turn
        # (rank_chains prefers hop count then cr/turn before we get here).
        scores.append(
            PriorityScore(
                kind="run_chain",
                ev_per_turn=float(chain_cr_per_turn),
                gated=False,
                rationale=(
                    f"trade chain {links}-link {chain_cr_per_turn:.1f} cr/turn"
                    + ("" if at_chain_start else " (not at cycle start — navigate first)")
                ),
                weight=40,
            )
        )
        if links is not None:
            prefer_search, earn_vs_search = prefer_search_over_earn(
                chain_links=links,
                explore_available=explore_available,
                min_execute=min_chain_links_to_execute,
                prefer_search_below=chain_links_prefer_search_below,
            )
            if prefer_search and explore_available:
                notes.append(earn_vs_search)

    # --- upgrade (RT-aware); ship hull deferred until chain is long enough ---
    # Only treat chain as "active interrupted work" when execute is allowed.
    chain_active = (
        chain_cr_per_turn is not None
        and chain_cr_per_turn > 0
        and links is not None
        and links >= min_chain_links_to_execute
    )
    ship_deferred = (
        links is not None
        and links < min_chain_links_for_ship_upgrade
        and chain_cr_per_turn is not None
    )
    if ship_deferred:
        upgrade_score = _UpgradeScoreBundle(
            PriorityScore(
                kind="upgrade",
                ev_per_turn=None,
                gated=True,
                gate_reason=(
                    f"upgrade: ship deferred until ≥{min_chain_links_for_ship_upgrade}-link "
                    f"chain (have {links}); earn fighters/holds on current chain first"
                ),
                rationale="ship after longer chain; holds/fighters first",
                weight=60,
            ),
            notes=(
                f"ship upgrade gated: {links}-link < {min_chain_links_for_ship_upgrade}",
            ),
        )
    else:
        upgrade_score = _score_upgrade_priority(
            upgrade_extra_cr_per_turn=upgrade_extra_cr_per_turn,
            upgrade_payback=upgrade_payback,
            upgrade_ship_name=upgrade_ship_name,
            hops_to_stardock=hops_to_stardock,
            hops_return_to_work=hops_return_to_work,
            turns_per_warp=turns_per_warp,
            productive=productive,
            chain_cr_per_turn=chain_cr_per_turn if chain_active else None,
            require_rt_when_chain_active=require_rt_when_chain_active and chain_active,
        )
    scores.append(upgrade_score.score)
    if upgrade_score.stay_vs_leave:
        stay_vs_leave = upgrade_score.stay_vs_leave
    notes.extend(upgrade_score.notes)

    # --- explore ---
    if explore_available:
        scores.append(
            PriorityScore(
                kind="explore",
                ev_per_turn=float(explore_baseline_ev),
                gated=False,
                rationale=f"explore baseline {explore_baseline_ev} cr/turn",
                weight=45,
            )
        )
    else:
        scores.append(
            PriorityScore(
                kind="explore",
                ev_per_turn=None,
                gated=True,
                gate_reason="explore: no frontier hop",
                rationale="no explore target",
                weight=45,
            )
        )

    # Rank: ungated by EV desc; gated last. Tie-break: run_chain, upgrade, explore.
    kind_order = {"run_chain": 0, "upgrade": 1, "explore": 2}

    def sort_key(s: PriorityScore):
        if s.gated or s.ev_per_turn is None:
            return (1, 0.0, kind_order.get(s.kind, 9))
        return (0, -float(s.ev_per_turn), kind_order.get(s.kind, 9))

    ranked = tuple(sorted(scores, key=sort_key))
    focus = next((s for s in ranked if not s.gated and s.ev_per_turn is not None), None)

    # If stay-vs-leave said stay, demote upgrade below chain even if raw EV higher.
    if (
        stay_vs_leave
        and stay_vs_leave.startswith("stay")
        and focus is not None
        and focus.kind == "upgrade"
    ):
        chain = next((s for s in ranked if s.kind == "run_chain" and not s.gated), None)
        if chain is not None:
            focus = chain
            notes.append("focus overridden to run_chain by stay-vs-leave")

    # Earn-vs-search: prefer explore over grinding a short-but-legal chain.
    if (
        earn_vs_search
        and earn_vs_search.startswith("search")
        and explore_available
        and focus is not None
        and focus.kind == "run_chain"
    ):
        explore = next((s for s in ranked if s.kind == "explore" and not s.gated), None)
        if explore is not None:
            focus = explore
            notes.append("focus overridden to explore by earn-vs-search")

    extra_notes = notes
    if earn_vs_search:
        extra_notes = list(notes) + [f"earn_vs_search: {earn_vs_search}"]

    return PriorityRecommendation(
        ranked=ranked,
        focus=focus,
        stay_vs_leave=stay_vs_leave,
        notes=tuple(extra_notes),
    )


@dataclass(frozen=True)
class _UpgradeScoreBundle:
    score: PriorityScore
    stay_vs_leave: Optional[str] = None
    notes: tuple[str, ...] = ()


def _score_upgrade_priority(
    *,
    upgrade_extra_cr_per_turn: Optional[float],
    upgrade_payback: Optional[float],
    upgrade_ship_name: Optional[str],
    hops_to_stardock: Optional[int],
    hops_return_to_work: Optional[int],
    turns_per_warp: int,
    productive: Optional[int],
    chain_cr_per_turn: Optional[float],
    require_rt_when_chain_active: bool,
) -> _UpgradeScoreBundle:
    name = upgrade_ship_name or "ship"

    if upgrade_extra_cr_per_turn is None or upgrade_payback is None:
        return _UpgradeScoreBundle(
            PriorityScore(
                kind="upgrade",
                ev_per_turn=None,
                gated=True,
                gate_reason="upgrade: price/payback unknown — skipped",
                rationale="no upgrade candidate",
                weight=60,
            )
        )

    if hops_to_stardock is None:
        return _UpgradeScoreBundle(
            PriorityScore(
                kind="upgrade",
                ev_per_turn=None,
                gated=True,
                gate_reason="upgrade: path to StarDock unknown — skipped",
                rationale="never guess one-way travel",
                weight=60,
            )
        )

    one_way = hops_to_stardock * max(1, turns_per_warp)

    if require_rt_when_chain_active and hops_return_to_work is None:
        return _UpgradeScoreBundle(
            PriorityScore(
                kind="upgrade",
                ev_per_turn=None,
                gated=True,
                gate_reason=(
                    "upgrade: return path to interrupted work unknown — "
                    "need travel_cost_rt before leaving chain"
                ),
                travel_one_way=one_way,
                rationale="RT incomplete (pre-flight)",
                weight=60,
            )
        )

    if hops_return_to_work is None:
        # No active chain / RT not required — one-way only (legacy autopilot shape).
        travel_rt = one_way
        notes = ("upgrade using one-way travel only (no return-to-work required)",)
    else:
        travel_rt = travel_cost_rt_turns(
            hops_to_stardock, hops_return_to_work, turns_per_warp
        )
        notes = (
            f"travel_cost_rt={travel_rt}t "
            f"(out {hops_to_stardock}h + return {hops_return_to_work}h "
            f"× {turns_per_warp}/warp)",
        )

    if productive is None:
        return _UpgradeScoreBundle(
            PriorityScore(
                kind="upgrade",
                ev_per_turn=None,
                gated=True,
                gate_reason="upgrade: turns_left unknown — skipped",
                travel_cost_rt=travel_rt,
                travel_one_way=one_way,
                rationale="fail-closed turn budget",
                weight=60,
            ),
            notes=notes,
        )

    if upgrade_payback + travel_rt > productive:
        return _UpgradeScoreBundle(
            PriorityScore(
                kind="upgrade",
                ev_per_turn=None,
                gated=True,
                gate_reason=(
                    f"upgrade: {name} payback {upgrade_payback:.1f}t + "
                    f"RT {travel_rt}t > {productive}t productive — HOLD"
                ),
                travel_cost_rt=travel_rt,
                travel_one_way=one_way,
                rationale="RT+payback exceeds budget",
                weight=60,
            ),
            notes=notes,
        )

    stay_msg: Optional[str] = None
    gated = False
    gate_reason: Optional[str] = None
    ev = float(upgrade_extra_cr_per_turn)

    if chain_cr_per_turn is not None and hops_return_to_work is not None:
        leave, stay_msg = stay_vs_leave_upgrade(
            chain_cr_per_turn=chain_cr_per_turn,
            upgrade_extra_cr_per_turn=ev,
            travel_cost_rt=travel_rt,
            payback=float(upgrade_payback),
            productive_turns=productive,
        )
        if not leave:
            gated = True
            gate_reason = stay_msg
            ev_out: Optional[float] = None
        else:
            ev_out = ev
    else:
        ev_out = ev

    return _UpgradeScoreBundle(
        PriorityScore(
            kind="upgrade",
            ev_per_turn=ev_out,
            gated=gated,
            gate_reason=gate_reason,
            travel_cost_rt=travel_rt,
            travel_one_way=one_way,
            rationale=(
                f"StarDock {name}: +{upgrade_extra_cr_per_turn:.1f} cr/turn; "
                f"payback {upgrade_payback:.1f}t; RT {travel_rt}t"
            ),
            weight=60,
        ),
        stay_vs_leave=stay_msg,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Fighter affordability
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FighterAffordability:
    """Affordability verdict for buying a small fighter stack at a Class-0 port.

    Spending priority rule:
    1. Reserve ``trade_float`` first — working capital to fill holds and run
       the trade loop; never cut into it for discretionary combat spend.
    2. Upgrade holds (catalog weight 75) when quote is known and affordable
       — hold upgrades pay back every cycle; they outrank fighter buys (73).
    3. Buy fighters (weight 73) when stack is affordable after the float.
    4. Buy ship (weight 60) — noted for completeness; lower priority;
       engine also defers hull until ≥4-link chain (see
       ``MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE``).

    Class-0 port (e.g. Sol, sector 1) is the primary source and is always
    reachable as the game start sector — **location is never the gate**.
    The gate is credits vs competing spends.

    ``fighter_unit_price=None`` means the price has not yet been captured
    from a live Class-0 port screen; use ``FIGHTER_UNIT_PRICE_CLASS0`` as
    the default placeholder until confirmed.
    """

    recommendation: str
    """One of: ``buy_fighters`` | ``upgrade_holds`` | ``buy_ship`` |
    ``keep_trade_float`` | ``insufficient_credits`` | ``price_unknown``."""

    can_afford: Optional[bool]
    """True/False when deterministic; None when a required input is unknown."""

    fighter_stack_cost: Optional[int]
    """Total cost for ``desired_count`` fighters; None when price unknown."""

    discretionary: Optional[int]
    """Credits available after reserving ``trade_float``; None when credits unknown."""

    reason: str
    """Human-readable verdict; suitable as a GOALS detail string."""


def afford_fighters(
    *,
    credits: Optional[int],
    fighter_unit_price: Optional[int] = FIGHTER_UNIT_PRICE_CLASS0,
    desired_count: int = FIGHTER_SMALL_STACK,
    hold_upgrade_quote: Optional[int] = None,
    cheapest_ship_price: Optional[int] = None,
    trade_float: Optional[int] = None,
) -> FighterAffordability:
    """Recommend the right spend given current credits and competing priorities.

    All ``None`` inputs are fail-closed — never invented.  When credits or
    ``fighter_unit_price`` is unknown, returns ``price_unknown`` rather than
    guessing a verdict.

    Rule summary:
    - ``trade_float`` is reserved first (working capital; defaults 0 when None).
    - ``hold_upgrade_quote`` known + affordable → ``upgrade_holds`` (weight 75 > 73).
    - ``credits − trade_float >= fighter_stack_cost`` → ``buy_fighters``.
    - Otherwise → ``insufficient_credits`` or ``keep_trade_float``.

    ``cheapest_ship_price`` is accepted for future expansion but does not
    influence the recommendation today (ship buy weight 60 < fighter 73).
    """
    desired_count = max(1, int(desired_count))

    if credits is None:
        return FighterAffordability(
            recommendation="price_unknown",
            can_afford=None,
            fighter_stack_cost=None,
            discretionary=None,
            reason="credits unknown — cannot evaluate fighter buy",
        )

    if fighter_unit_price is None:
        disc = int(credits) - int(trade_float or 0)
        return FighterAffordability(
            recommendation="price_unknown",
            can_afford=None,
            fighter_stack_cost=None,
            discretionary=disc,
            reason=(
                "fighter unit price not yet captured from Class-0 screen; "
                "Sol/Class-0 reachable — visit to confirm price"
            ),
        )

    credits = int(credits)
    fighter_unit_price = int(fighter_unit_price)
    float_reserve = int(trade_float) if trade_float is not None else 0
    stack_cost = fighter_unit_price * desired_count
    discretionary = credits - float_reserve

    if discretionary < 0:
        return FighterAffordability(
            recommendation="keep_trade_float",
            can_afford=False,
            fighter_stack_cost=stack_cost,
            discretionary=discretionary,
            reason=(
                f"credits {credits:,}cr < trade_float {float_reserve:,}cr reserve; "
                "preserve working capital before any combat spend"
            ),
        )

    if discretionary < stack_cost:
        shortfall = stack_cost - discretionary
        return FighterAffordability(
            recommendation="insufficient_credits",
            can_afford=False,
            fighter_stack_cost=stack_cost,
            discretionary=discretionary,
            reason=(
                f"need {stack_cost:,}cr for {desired_count} fighters; "
                f"have {discretionary:,}cr discretionary — short {shortfall:,}cr"
            ),
        )

    # Discretionary covers the fighter stack.
    # Holds upgrade (weight 75 > 73) takes priority when known + affordable.
    if hold_upgrade_quote is not None and int(hold_upgrade_quote) <= discretionary:
        return FighterAffordability(
            recommendation="upgrade_holds",
            can_afford=True,
            fighter_stack_cost=stack_cost,
            discretionary=discretionary,
            reason=(
                f"hold upgrade {int(hold_upgrade_quote):,}cr affordable and higher "
                f"priority (weight 75 > 73) — upgrade holds before fighter buy"
            ),
        )

    return FighterAffordability(
        recommendation="buy_fighters",
        can_afford=True,
        fighter_stack_cost=stack_cost,
        discretionary=discretionary,
        reason=(
            f"{desired_count} fighters × {fighter_unit_price:,}cr = {stack_cost:,}cr; "
            f"have {discretionary:,}cr discretionary — go to Sol/Class-0 to buy"
        ),
    )
