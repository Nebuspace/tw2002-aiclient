"""Ship-upgrade DECISION engine (TW-30) — pure logic, no I/O.

Encodes the five §24 live-play learnings so the trainer never recommends
capacity that cannot amortize in the remaining turn budget. Wire later to
TW-27 game-data + TW-22 / pilot; today everything is mockable input.

Lane: client-side / pure-logic (impl-tw2002-logic). Zero daemon touch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence


@dataclass(frozen=True)
class ShipSpec:
    """One shipyard offering (mockable stand-in for TW-27 introspected data)."""

    name: str
    cost: int
    holds: int
    turns_per_warp: int
    fighters: int
    shields: int
    alignment_req: int = 0
    # True when the player's current alignment/rank meets alignment_req.
    commissioned: bool = True


@dataclass(frozen=True)
class LoopEconomics:
    """Per-cycle profit model for the trader's current (or planned) loop."""

    margin_per_hold: int  # credits of profit per hold filled once per cycle
    turns_per_cycle: int  # wall-turns to run one full cycle (warp+trade)
    stock_capacity: int  # max holds the loop's stock can sustain without chains
    needs_chains_above: Optional[int] = None  # if set, alias for stock_capacity


@dataclass(frozen=True)
class PlayerState:
    turns_left: int
    current_holds: int
    turn_reserve: int = 0  # keep this many turns unspent (safety / login buffer)
    hostile_or_pvp: bool = False
    current_fighters: int = 0
    current_shields: int = 0


@dataclass(frozen=True)
class UpgradeDecision:
    recommend: bool
    ship: Optional[ShipSpec]
    rationale: str
    projected_payback: Optional[float]  # turns to amortize; None if HOLD / N/A
    flags: tuple[str, ...] = field(default_factory=tuple)


def remaining_productive_turns(state: PlayerState) -> int:
    return max(0, state.turns_left - state.turn_reserve)


def holds_per_turn(ship: ShipSpec, loop: LoopEconomics) -> float:
    """Hold-throughput score: (holds × margin) / (cycle_turns × turns_per_warp).

    Shared loop cycle length; ships that burn more turns per warp rank lower
    at equal holds (Barge 6/warp vs Galleon 3/warp).
    """
    if loop.turns_per_cycle <= 0 or ship.turns_per_warp <= 0:
        return 0.0
    return (ship.holds * loop.margin_per_hold) / (
        loop.turns_per_cycle * ship.turns_per_warp
    )


def hold_fill_cost(extra_holds: int, cost_per_hold: int) -> int:
    return max(0, extra_holds) * max(0, cost_per_hold)


def payback_turns(
    ship: ShipSpec,
    state: PlayerState,
    loop: LoopEconomics,
    *,
    cost_per_hold: int = 0,
) -> Optional[float]:
    """Turns to amortize upgrade cost from the extra credits/turn."""
    extra_holds = ship.holds - state.current_holds
    if extra_holds <= 0:
        return None
    hpt_new = holds_per_turn(ship, loop)
    # Approximate current throughput with same warp as candidate for delta.
    current_as_ship = ShipSpec(
        name="current",
        cost=0,
        holds=state.current_holds,
        turns_per_warp=ship.turns_per_warp,
        fighters=state.current_fighters,
        shields=state.current_shields,
        commissioned=True,
    )
    hpt_cur = holds_per_turn(current_as_ship, loop)
    extra_cr_per_turn = hpt_new - hpt_cur
    if extra_cr_per_turn <= 0:
        return None
    total_cost = ship.cost + hold_fill_cost(extra_holds, cost_per_hold)
    return total_cost / extra_cr_per_turn


def _stock_cap(loop: LoopEconomics) -> int:
    if loop.needs_chains_above is not None:
        return loop.needs_chains_above
    return loop.stock_capacity


def evaluate_candidate(
    ship: ShipSpec,
    state: PlayerState,
    loop: LoopEconomics,
    *,
    cost_per_hold: int = 0,
    defense_floor_fighters: int = 1,
) -> UpgradeDecision:
    """Evaluate a single commissioned ship against the five TW-30 gates."""
    flags: list[str] = []

    if not ship.commissioned:
        return UpgradeDecision(
            recommend=False,
            ship=ship,
            rationale=f"{ship.name}: not commissioned (alignment/rank gate).",
            projected_payback=None,
            flags=("alignment_rank",),
        )

    stock = _stock_cap(loop)
    if ship.holds > stock:
        flags.append("needs_chains")
        return UpgradeDecision(
            recommend=False,
            ship=ship,
            rationale=(
                f"{ship.name}: {ship.holds} holds exceed loop stock capacity "
                f"({stock}) — needs chains (TW-21) first."
            ),
            projected_payback=None,
            flags=tuple(flags),
        )

    if state.hostile_or_pvp and ship.fighters < defense_floor_fighters:
        flags.append("defense_floor")
        return UpgradeDecision(
            recommend=False,
            ship=ship,
            rationale=(
                f"{ship.name}: fighters={ship.fighters} below defense floor "
                f"({defense_floor_fighters}) on hostile/PvP — refuse 0-fighter mug risk."
            ),
            projected_payback=None,
            flags=tuple(flags),
        )

    productive = remaining_productive_turns(state)
    pb = payback_turns(ship, state, loop, cost_per_hold=cost_per_hold)
    if pb is None:
        return UpgradeDecision(
            recommend=False,
            ship=ship,
            rationale=f"{ship.name}: no positive credit delta vs current holds.",
            projected_payback=None,
            flags=tuple(flags),
        )
    if pb > productive:
        flags.append("roi_vs_budget")
        return UpgradeDecision(
            recommend=False,
            ship=ship,
            rationale=(
                f"{ship.name}: payback {pb:.1f} turns > remaining productive "
                f"{productive} — HOLD (ROI-vs-turn-budget)."
            ),
            projected_payback=pb,
            flags=tuple(flags),
        )

    return UpgradeDecision(
        recommend=True,
        ship=ship,
        rationale=(
            f"{ship.name}: payback {pb:.1f} turns within productive {productive}; "
            f"holds/turn≈{holds_per_turn(ship, loop):.1f}."
        ),
        projected_payback=pb,
        flags=tuple(flags),
    )


def choose_upgrade(
    catalog: Sequence[ShipSpec],
    state: PlayerState,
    loop: LoopEconomics,
    *,
    cost_per_hold: int = 0,
    defense_floor_fighters: int = 1,
) -> UpgradeDecision:
    """Pick the best hold-throughput ship that passes all five gates, or HOLD."""
    eligible: list[tuple[float, UpgradeDecision]] = []
    refusals: list[UpgradeDecision] = []

    for ship in catalog:
        decision = evaluate_candidate(
            ship,
            state,
            loop,
            cost_per_hold=cost_per_hold,
            defense_floor_fighters=defense_floor_fighters,
        )
        if decision.recommend and decision.ship is not None:
            eligible.append((holds_per_turn(decision.ship, loop), decision))
        else:
            refusals.append(decision)

    if not eligible:
        # Prefer the most informative refusal (ROI gate first if present).
        for key in ("roi_vs_budget", "needs_chains", "defense_floor", "alignment_rank"):
            for r in refusals:
                if key in r.flags:
                    return UpgradeDecision(
                        recommend=False,
                        ship=None,
                        rationale=f"HOLD — {r.rationale}",
                        projected_payback=r.projected_payback,
                        flags=r.flags,
                    )
        return UpgradeDecision(
            recommend=False,
            ship=None,
            rationale="HOLD — no eligible commissioned upgrade in catalog.",
            projected_payback=None,
            flags=(),
        )

    eligible.sort(key=lambda pair: pair[0], reverse=True)
    best = eligible[0][1]
    return best
