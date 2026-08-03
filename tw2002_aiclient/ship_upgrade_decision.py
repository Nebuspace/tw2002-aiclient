"""Ship-upgrade DECISION engine (PWO-107 Option A / TW-30) — pure logic, no I/O.

Encodes the five §24 live-play learnings so the trainer never recommends
capacity that cannot amortize in the remaining turn budget. Inputs are
mockable stand-ins for introspected game_data (PWO-092 residual).

Recommend-only: this module never sends a purchase keystroke. Purchase
adapter + armconfirm (Option B) stay HELD pending a fresh GO.
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


def compose_upgrade_decision_lines(
    decision: UpgradeDecision,
    *,
    width: int = 40,
) -> list[str]:
    """Human-facing recommend-only callout lines for DECISIONS / coach.

    Never invents purchase commands — rationale text only. Never raises.
    """
    try:
        width = max(8, int(width))
    except (TypeError, ValueError):
        width = 40
    if not isinstance(decision, UpgradeDecision):
        return []
    if decision.recommend and decision.ship is not None:
        title = f"Upgrade: {decision.ship.name}"
    else:
        title = "Upgrade: HOLD"
    rationale = (decision.rationale or "").strip() or "no rationale"
    lines = [title[:width], f" {rationale}"[:width]]
    return lines


def upgrade_decision_from_status(status: object) -> Optional[UpgradeDecision]:
    """Build an :class:`UpgradeDecision` from a status dict, or ``None``.

    Accepts either a precomputed ``status["upgrade_decision"]`` mapping
    (recommend / rationale / optional ship fields) **or** structured
    ``upgrade_catalog`` + ``upgrade_player`` + ``upgrade_loop`` inputs for
    :func:`choose_upgrade`. Fail-closed: incomplete/hostile input → ``None``.
    Never raises.
    """
    if not isinstance(status, dict):
        return None
    try:
        pre = status.get("upgrade_decision")
        if isinstance(pre, UpgradeDecision):
            return pre
        if isinstance(pre, dict):
            recommend = pre.get("recommend") is True
            rationale = pre.get("rationale") if isinstance(pre.get("rationale"), str) else ""
            ship = None
            ship_raw = pre.get("ship")
            if isinstance(ship_raw, ShipSpec):
                ship = ship_raw
            elif isinstance(ship_raw, dict) and isinstance(ship_raw.get("name"), str):
                ship = ShipSpec(
                    name=str(ship_raw.get("name") or ""),
                    cost=int(ship_raw.get("cost") or 0),
                    holds=int(ship_raw.get("holds") or 0),
                    turns_per_warp=int(ship_raw.get("turns_per_warp") or 1),
                    fighters=int(ship_raw.get("fighters") or 0),
                    shields=int(ship_raw.get("shields") or 0),
                    alignment_req=int(ship_raw.get("alignment_req") or 0),
                    commissioned=ship_raw.get("commissioned", True) is True,
                )
            pb = pre.get("projected_payback")
            if pb is not None and not isinstance(pb, (int, float)):
                pb = None
            flags = pre.get("flags")
            flag_t = tuple(flags) if isinstance(flags, (list, tuple)) else ()
            return UpgradeDecision(
                recommend=recommend,
                ship=ship,
                rationale=rationale or ("recommend" if recommend else "HOLD"),
                projected_payback=float(pb) if isinstance(pb, (int, float)) else None,
                flags=tuple(str(f) for f in flag_t),
            )

        catalog_raw = status.get("upgrade_catalog")
        player_raw = status.get("upgrade_player")
        loop_raw = status.get("upgrade_loop")
        if not isinstance(catalog_raw, (list, tuple)):
            return None
        if not isinstance(player_raw, dict) or not isinstance(loop_raw, dict):
            return None
        catalog: list[ShipSpec] = []
        for item in catalog_raw:
            if isinstance(item, ShipSpec):
                catalog.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                catalog.append(
                    ShipSpec(
                        name=str(item.get("name") or ""),
                        cost=int(item.get("cost") or 0),
                        holds=int(item.get("holds") or 0),
                        turns_per_warp=int(item.get("turns_per_warp") or 1),
                        fighters=int(item.get("fighters") or 0),
                        shields=int(item.get("shields") or 0),
                        alignment_req=int(item.get("alignment_req") or 0),
                        commissioned=item.get("commissioned", True) is True,
                    )
                )
        if not catalog:
            return None
        state = PlayerState(
            turns_left=int(player_raw.get("turns_left") or 0),
            current_holds=int(player_raw.get("current_holds") or 0),
            turn_reserve=int(player_raw.get("turn_reserve") or 0),
            hostile_or_pvp=player_raw.get("hostile_or_pvp") is True,
            current_fighters=int(player_raw.get("current_fighters") or 0),
            current_shields=int(player_raw.get("current_shields") or 0),
        )
        loop = LoopEconomics(
            margin_per_hold=int(loop_raw.get("margin_per_hold") or 0),
            turns_per_cycle=int(loop_raw.get("turns_per_cycle") or 1),
            stock_capacity=int(loop_raw.get("stock_capacity") or 0),
            needs_chains_above=(
                int(loop_raw["needs_chains_above"])
                if isinstance(loop_raw.get("needs_chains_above"), int)
                else None
            ),
        )
        cost_per_hold = status.get("upgrade_cost_per_hold", 0)
        if not isinstance(cost_per_hold, int) or isinstance(cost_per_hold, bool):
            cost_per_hold = 0
        return choose_upgrade(catalog, state, loop, cost_per_hold=cost_per_hold)
    except Exception:  # noqa: BLE001 -- fail-closed
        return None

