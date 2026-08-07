"""WO-FIX-EXPLORE-NO-DEFENSIVE-POSTURE-BEFORE-UNCHARTED — pre-explore policy.

Pure decision: whether map-fill explore should detour to a known fighter
dealer (StarDock landmark) before committing to uncharted warps.

Does **not** send keystrokes or spend credits. Explore wires the verdict:
seek the dealer within a turn-budget ceiling, then halt with a named reason
so a human-approved (or follow-up taught) purchase can happen. Unreachable /
scarce / unknown inputs degrade to today's explore (no new stall hunting a
dealer that may not exist).

Policy numbers (judgment, documented — escalate only if Max wants different
defaults):

* ``FIGHTER_FLOOR`` — 20 aboard before uncharted map-fill. Aligns with
  archive ``EconCaps.keep_min_defense_fighters``; stock start is often ~6.
* ``CREDIT_FRACTION_CEILING`` — spend at most 10% of known credits on the
  defensive stack (100k start → ≤10k; a 14-fighter top-up at 100 cr is ~1.4k).
* ``FIGHTER_UNIT_PRICE_DEFAULT`` — 100 cr/fighter Class-0 / StarDock placeholder
  until introspected (same as archived ``FIGHTER_UNIT_PRICE_CLASS0``).
* ``DEALER_DETOUR_TURN_CEILING`` — 20 turns one-way budget for the detour.
* ``CASH_FLOOR_AFTER`` — leave ≥10_000 credits after the planned spend
  (archive ``EconCaps.cash_floor``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from tw2002_aiclient.explore import (
    find_landmark_sectors,
    known_graph,
    path_to_sector,
)
from tw2002_aiclient.priority_engine import hops_of_path
from tw2002_aiclient.world_model import STARDOCK_LANDMARK

__all__ = [
    "FIGHTER_FLOOR",
    "CREDIT_FRACTION_CEILING",
    "FIGHTER_UNIT_PRICE_DEFAULT",
    "DEALER_DETOUR_TURN_CEILING",
    "CASH_FLOOR_AFTER",
    "HALT_DEFENSIVE_POSTURE",
    "DefensivePostureDecision",
    "hops_to_stardock",
    "decide_defensive_posture",
]

#: Minimum fighters aboard before uncharted map-fill is allowed to proceed
#: without a dealer detour. See module docstring.
FIGHTER_FLOOR: int = 20

#: Max fraction of known credits that may be committed to the stack.
CREDIT_FRACTION_CEILING: float = 0.10

#: Placeholder unit price until a live Class-0 / dock quote is captured.
FIGHTER_UNIT_PRICE_DEFAULT: int = 100

#: One-way turn budget for routing to a known StarDock before giving up.
DEALER_DETOUR_TURN_CEILING: int = 20

#: Credits that must remain after the planned purchase.
CASH_FLOOR_AFTER: int = 10_000

#: Explore halt reason when the dealer is reached (or already underfoot)
#: while still under the fighter floor — purchase is human-gated / follow-up.
HALT_DEFENSIVE_POSTURE = "halt_defensive_posture"


@dataclass(frozen=True)
class DefensivePostureDecision:
    """Verdict for the explore pre-uncharted gate."""

    action: str
    """``seek_dealer`` | ``already_sufficient`` | ``skip_*``."""

    reason: str
    qty: int = 0
    """Recommended fighters to buy (0 when not seeking)."""

    hops_to_dealer: Optional[int] = None
    stack_cost: Optional[int] = None


def hops_to_stardock(
    world_id: str,
    current_sector: Optional[int],
    *,
    state_dir=None,
    graph: Optional[Mapping[int, Sequence[int]]] = None,
) -> Optional[int]:
    """Shortest known-graph hops to a StarDock landmark, or None if unknown.

    ``0`` means the current sector *is* a StarDock sector (or path is
    trivial). ``None`` means no landmark, no current sector, or no path.
    """
    if current_sector is None:
        return None
    docks = find_landmark_sectors(
        world_id, STARDOCK_LANDMARK, state_dir=state_dir
    )
    if not docks:
        return None
    g = graph if graph is not None else known_graph(world_id, state_dir=state_dir)
    best: Optional[int] = None
    for dock in docks:
        path = path_to_sector(g, int(current_sector), int(dock))
        hops = hops_of_path(path)
        if hops is None:
            continue
        if best is None or hops < best:
            best = hops
    return best


def decide_defensive_posture(
    *,
    fighters_aboard: Optional[int],
    credits: Optional[int],
    hops_to_dealer: Optional[int],
    turns_remaining: int,
    fighter_floor: int = FIGHTER_FLOOR,
    credit_fraction_ceiling: float = CREDIT_FRACTION_CEILING,
    unit_price: int = FIGHTER_UNIT_PRICE_DEFAULT,
    detour_turn_ceiling: int = DEALER_DETOUR_TURN_CEILING,
    cash_floor_after: int = CASH_FLOOR_AFTER,
) -> DefensivePostureDecision:
    """Buy-vs-skip for the explore defensive-posture gate (pure)."""
    floor = max(0, int(fighter_floor))
    price = max(1, int(unit_price))
    detour_cap = max(0, int(detour_turn_ceiling))
    cash_floor = max(0, int(cash_floor_after))
    frac = float(credit_fraction_ceiling)
    if frac < 0:
        frac = 0.0

    if fighters_aboard is None:
        return DefensivePostureDecision(
            action="skip_unknown_fighters",
            reason="fighters never observed — fail-closed, explore as today",
        )
    fighters = max(0, int(fighters_aboard))
    if fighters >= floor:
        return DefensivePostureDecision(
            action="already_sufficient",
            reason=f"fighters {fighters} >= floor {floor}",
            hops_to_dealer=hops_to_dealer,
        )

    if credits is None:
        return DefensivePostureDecision(
            action="skip_unknown_credits",
            reason="credits unknown — cannot size a defensive buy",
            hops_to_dealer=hops_to_dealer,
        )
    credits_i = max(0, int(credits))

    if hops_to_dealer is None:
        return DefensivePostureDecision(
            action="skip_unreachable",
            reason="no known StarDock path — explore as today (no dealer hunt)",
        )

    hops = max(0, int(hops_to_dealer))
    # Rough turn cost: 1 turn/warp placeholder (hull warp cost not wired here).
    if hops > detour_cap:
        return DefensivePostureDecision(
            action="skip_scarce_turns",
            reason=(
                f"dealer {hops} hops > detour ceiling {detour_cap} — "
                "explore as today"
            ),
            hops_to_dealer=hops,
        )
    if int(turns_remaining) < hops:
        return DefensivePostureDecision(
            action="skip_scarce_turns",
            reason=(
                f"turns_remaining {turns_remaining} < hops_to_dealer {hops} — "
                "explore as today"
            ),
            hops_to_dealer=hops,
        )

    need = floor - fighters
    budget = min(
        int(credits_i * frac),
        max(0, credits_i - cash_floor),
    )
    max_by_budget = budget // price
    qty = min(need, max_by_budget)
    if qty < 1:
        return DefensivePostureDecision(
            action="skip_cannot_afford",
            reason=(
                f"need {need} fighters to floor {floor} but budget "
                f"{budget} cr @ {price}/ea buys 0 after cash floor"
            ),
            hops_to_dealer=hops,
            stack_cost=0,
        )

    cost = qty * price
    return DefensivePostureDecision(
        action="seek_dealer",
        reason=(
            f"fighters {fighters} < floor {floor}; buy {qty} (~{cost} cr) "
            f"via StarDock ({hops} hops)"
        ),
        qty=qty,
        hops_to_dealer=hops,
        stack_cost=cost,
    )
