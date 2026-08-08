"""Priority engine — RT travel cost + stay-vs-leave (strategic ranker only).

Canon: ``canon/engine/priority-engine.md``. Pure logic — emits ordering
inputs for FOCUS; never sends, never arms, never invents hop counts.

Ported kernel from the archived ``twclient/priority_engine.py`` RT /
stay-vs-leave primitives (WO-PRIORITY-ENGINE-KERNEL) plus recommend-only
``afford_fighters`` (WO-BUILD-FIGHTER-AFFORDABILITY-DECISION-ENGINE).
Chain-link floors live in ``chains.py``; this module does not re-export
EXECUTE / purchase surfaces.
"""

from __future__ import annotations

__all__ = [
    "FIGHTER_SMALL_STACK",
    "FighterAffordability",
    "afford_fighters",
    "fighter_buy_status_label",
    "hops_of_path",
    "travel_cost_rt_turns",
    "compute_return_path",
    "stay_vs_leave_upgrade",
    "upgrade_gate_while_chaining",
]

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from tw2002_aiclient.explore import path_to_sector


def hops_of_path(path: Optional[Sequence[int]]) -> Optional[int]:
    """Inclusive sector path → warp hop count. None / empty → unknown."""
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
    """Warp turns for out + return on the current hull."""
    if turns_per_warp < 1:
        turns_per_warp = 1
    return (max(0, hops_out) + max(0, hops_return)) * turns_per_warp


def compute_return_path(
    graph: Mapping[int, Sequence[int]],
    from_sector: int,
    to_sector: int,
) -> Optional[tuple[int, ...]]:
    """Shortest known-graph path for the return leg (e.g. StarDock → chain)."""
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

    Returns ``(leave_for_upgrade, reason)``. Debit chain profit forgone
    during RT travel; credit upgrade extra cr/turn only after RT+payback.
    Leave only when that net gain is strictly positive.
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


def upgrade_gate_while_chaining(
    *,
    chain_cr_per_turn: float | None,
    upgrade_extra_cr_per_turn: float | None,
    upgrade_payback: float | None,
    hops_to_stardock: int | None,
    hops_return_to_work: int | None,
    turns_per_warp: int | None,
    productive_turns: int | None,
) -> tuple[bool, str | None, float | None, int | None]:
    """Pre-flight + stay-vs-leave for FOCUS when a chain is executable.

    Returns ``(gated, gate_reason, upgrade_ev_or_none, travel_cost_rt)``.

    Fail-closed: unknown StarDock path, unknown return path, unknown
    turns/payback/extra EV, or stay-vs-leave saying stay → gated. Distances
    are never invented.
    """
    if upgrade_extra_cr_per_turn is None or upgrade_payback is None:
        return True, "upgrade: price/payback unknown — skipped", None, None
    if hops_to_stardock is None:
        return True, "upgrade: path to StarDock unknown — skipped", None, None
    if hops_return_to_work is None:
        return (
            True,
            (
                "upgrade: return path to interrupted work unknown — "
                "need travel_cost_rt before leaving chain"
            ),
            None,
            None,
        )
    if turns_per_warp is None or turns_per_warp < 1:
        return True, "upgrade: turns_per_warp unknown — skipped", None, None
    if productive_turns is None:
        return True, "upgrade: turns_left unknown — skipped", None, None

    travel_rt = travel_cost_rt_turns(
        hops_to_stardock, hops_return_to_work, turns_per_warp
    )
    if upgrade_payback + travel_rt > productive_turns:
        return (
            True,
            (
                f"upgrade: payback {upgrade_payback:.1f}t + "
                f"RT {travel_rt}t > {productive_turns}t productive — HOLD"
            ),
            None,
            travel_rt,
        )

    if chain_cr_per_turn is None:
        # Chain active but EV unknown — fail-closed (do not invent).
        return True, "upgrade: chain cr/turn unknown — stay (fail-closed)", None, travel_rt

    leave, reason = stay_vs_leave_upgrade(
        chain_cr_per_turn=float(chain_cr_per_turn),
        upgrade_extra_cr_per_turn=float(upgrade_extra_cr_per_turn),
        travel_cost_rt=travel_rt,
        payback=float(upgrade_payback),
        productive_turns=int(productive_turns),
    )
    if not leave:
        return True, reason, None, travel_rt
    return False, reason, float(upgrade_extra_cr_per_turn), travel_rt

# ---------------------------------------------------------------------------
# Fighter affordability — recommend / display only (no purchase sends)
# ---------------------------------------------------------------------------

FIGHTER_SMALL_STACK: int = 5
"""Default desired stack size for recommendations — configurable preference,
not a measured live-server fact. Unit price is never defaulted here."""

_FIGHTER_BUY_STATUS_LABELS: dict[str, str] = {
    "buy_fighters": "can buy",
    "upgrade_holds": "holds first",
    "buy_ship": "ship later",
    "keep_trade_float": "need credits",
    "insufficient_credits": "need credits",
    "price_unknown": "price?",
}


@dataclass(frozen=True)
class FighterAffordability:
    """Affordability verdict for buying a small fighter stack at a Class-0 port.

    Spending priority (canon AP-09 / priority-engine Fighter economics):
    1. Reserve ``trade_float`` first (working capital).
    2. Holds upgrade (weight 75) when quote known + affordable.
    3. Buy fighters (weight 73) with remaining discretionary credits.
    4. Ship hull (weight 60) noted only — does not redirect this helper.

    Recommend/display only — never arms a purchase send. Class-0 / Sol is
    always reachable; location is never the gate. ``fighter_unit_price`` must
    be injected (captured or operator-supplied); tip does **not** ship a
    pretended-measured ``FIGHTER_UNIT_PRICE_CLASS0`` default.
    """

    recommendation: str
    can_afford: Optional[bool]
    fighter_stack_cost: Optional[int]
    discretionary: Optional[int]
    reason: str


def fighter_buy_status_label(recommendation: str) -> str:
    """Short GOALS detail for a ``FighterAffordability.recommendation``."""
    return _FIGHTER_BUY_STATUS_LABELS.get(recommendation, "price?")


def afford_fighters(
    *,
    credits: Optional[int],
    fighter_unit_price: Optional[int] = None,
    desired_count: int = FIGHTER_SMALL_STACK,
    hold_upgrade_quote: Optional[int] = None,
    cheapest_ship_price: Optional[int] = None,
    trade_float: Optional[int] = None,
) -> FighterAffordability:
    """Recommend the right spend given credits and competing priorities.

    All ``None`` inputs fail-closed — never invented. Unknown credits or
    unknown ``fighter_unit_price`` → ``price_unknown`` (no hypothesis default).

    ``cheapest_ship_price`` is accepted for API completeness but does not
    influence the recommendation today (ship weight 60 < fighter 73).
    """
    _ = cheapest_ship_price  # reserved; ship deferral lives elsewhere
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

    credits_i = int(credits)
    unit = int(fighter_unit_price)
    float_reserve = int(trade_float) if trade_float is not None else 0
    stack_cost = unit * desired_count
    discretionary = credits_i - float_reserve

    if discretionary < 0:
        return FighterAffordability(
            recommendation="keep_trade_float",
            can_afford=False,
            fighter_stack_cost=stack_cost,
            discretionary=discretionary,
            reason=(
                f"credits {credits_i:,}cr < trade_float {float_reserve:,}cr reserve; "
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
            f"{desired_count} fighters × {unit:,}cr = {stack_cost:,}cr; "
            f"have {discretionary:,}cr discretionary — go to Sol/Class-0 to buy"
        ),
    )
