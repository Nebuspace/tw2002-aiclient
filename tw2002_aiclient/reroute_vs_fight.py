"""Reroute-vs-fight EV — pure ranking input for priority / coaching.

Canon: ``canon/strategy/toll-and-defense.md`` § Reroute-vs-fight EV.
DECISIONS: eventual ``app`` auto-fire is allowed only behind a taught/armed
rule; this module never sends, never arms, never invents hop counts, and
never overrides the fighter-toll ``force_share`` / NPC / PvP rails
(``session.fighter_toll_policy.decide_encounter``).

Compare caller-supplied extra-hop reroute cost against caller-supplied
expected fight cost. Prefer ranking a taught reroute when it looks cheaper
**and** the live auto-Attack gate would not fire. Incomplete inputs →
``preferred="unknown"`` + gated (fail-closed).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from tw2002_aiclient.session.fighter_toll_policy import (
    DEFAULT_AUTO_ATTACK_MAX_ENEMY,
    DEFAULT_FORCE_SHARE_AUTO_ATTACK,
    force_share as _force_share,
    parse_encounter,
)

__all__ = [
    "RerouteVsFightEV",
    "extra_hops",
    "reroute_turn_cost",
    "compare_reroute_vs_fight",
    "toll_ev_to_status",
    "toll_ev_for_screen",
]

Preferred = Literal["reroute", "fight", "unknown"]


@dataclass(frozen=True)
class RerouteVsFightEV:
    """Ranking-only comparison. Never an execute decision."""

    preferred: Preferred
    reroute_turns: Optional[int]
    fight_cost_turns: Optional[float]
    fight_cost_credits: Optional[float]
    force_share: Optional[float]
    below_auto_attack_gate: bool
    gated: bool
    gate_reason: Optional[str]
    rationale: str


def extra_hops(
    direct_hops: Optional[int],
    alternate_hops: Optional[int],
) -> Optional[int]:
    """Extra warps on an alternate path vs a direct path. Never invents."""
    if direct_hops is None or alternate_hops is None:
        return None
    if direct_hops < 0 or alternate_hops < 0:
        return None
    return max(0, int(alternate_hops) - int(direct_hops))


def reroute_turn_cost(
    extra: Optional[int],
    turns_per_warp: Optional[int],
) -> Optional[int]:
    """Turn cost of the extra hops. Unknown hops or warp → None."""
    if extra is None or turns_per_warp is None:
        return None
    if turns_per_warp < 1 or extra < 0:
        return None
    return int(extra) * int(turns_per_warp)


def compare_reroute_vs_fight(
    *,
    extra_hops: Optional[int] = None,
    turns_per_warp: Optional[int] = None,
    expected_fight_turns: Optional[float] = None,
    expected_fight_credits: Optional[float] = None,
    own_fighters: Optional[int] = None,
    enemy_fighters: Optional[int] = None,
    force_share_auto_attack: Optional[float] = DEFAULT_FORCE_SHARE_AUTO_ATTACK,
    winnable_enemy_band: int = DEFAULT_AUTO_ATTACK_MAX_ENEMY,
    is_pvp: bool = False,
) -> RerouteVsFightEV:
    """Rank taught reroute vs engage. Fail-closed on incomplete / PvP."""

    reroute_turns = reroute_turn_cost(extra_hops, turns_per_warp)
    fight_t = (
        float(expected_fight_turns)
        if isinstance(expected_fight_turns, (int, float))
        else None
    )
    fight_c = (
        float(expected_fight_credits)
        if isinstance(expected_fight_credits, (int, float))
        else None
    )

    if is_pvp:
        return RerouteVsFightEV(
            preferred="unknown",
            reroute_turns=reroute_turns,
            fight_cost_turns=fight_t,
            fight_cost_credits=fight_c,
            force_share=None,
            below_auto_attack_gate=True,
            gated=True,
            gate_reason="pvp_hard_stop",
            rationale="PvP — toll math does not apply; STOP for human",
        )

    share: Optional[float] = None
    below_gate = True
    if own_fighters is None or enemy_fighters is None:
        return RerouteVsFightEV(
            preferred="unknown",
            reroute_turns=reroute_turns,
            fight_cost_turns=fight_t,
            fight_cost_credits=fight_c,
            force_share=None,
            below_auto_attack_gate=True,
            gated=True,
            gate_reason="counts_incomplete",
            rationale="own/enemy fighter counts incomplete — fail-closed",
        )

    try:
        share = _force_share(int(own_fighters), int(enemy_fighters))
    except ValueError:
        return RerouteVsFightEV(
            preferred="unknown",
            reroute_turns=reroute_turns,
            fight_cost_turns=fight_t,
            fight_cost_credits=fight_c,
            force_share=None,
            below_auto_attack_gate=True,
            gated=True,
            gate_reason="force_share_undefined",
            rationale="no fighters on either side — force_share undefined",
        )

    threshold = force_share_auto_attack
    if threshold is None:
        below_gate = True
    else:
        below_gate = share < float(threshold) or int(enemy_fighters) > int(
            winnable_enemy_band
        )

    if reroute_turns is None and fight_t is None:
        return RerouteVsFightEV(
            preferred="unknown",
            reroute_turns=None,
            fight_cost_turns=None,
            fight_cost_credits=fight_c,
            force_share=share,
            below_auto_attack_gate=below_gate,
            gated=True,
            gate_reason="costs_incomplete",
            rationale="reroute hops and fight cost both unknown — fail-closed",
        )

    # Below auto-Attack: rank taught reroute above escalate when cheaper or
    # when fight cost is unknown (do not invent a fight EV).
    if below_gate:
        if reroute_turns is not None and (fight_t is None or reroute_turns < fight_t):
            return RerouteVsFightEV(
                preferred="reroute",
                reroute_turns=reroute_turns,
                fight_cost_turns=fight_t,
                fight_cost_credits=fight_c,
                force_share=share,
                below_auto_attack_gate=True,
                gated=False,
                gate_reason=None,
                rationale=(
                    f"rank taught reroute ({reroute_turns}t) above escalate "
                    f"(below auto-Attack gate; force_share={share:.2f})"
                ),
            )
        if fight_t is not None and reroute_turns is not None and fight_t <= reroute_turns:
            return RerouteVsFightEV(
                preferred="fight",
                reroute_turns=reroute_turns,
                fight_cost_turns=fight_t,
                fight_cost_credits=fight_c,
                force_share=share,
                below_auto_attack_gate=True,
                gated=True,
                gate_reason="below_auto_attack_gate",
                rationale=(
                    "fight looks cheaper in turns but auto-Attack gate not met "
                    "— ranking only; live rail still Retreat/STOP"
                ),
            )
        return RerouteVsFightEV(
            preferred="unknown",
            reroute_turns=reroute_turns,
            fight_cost_turns=fight_t,
            fight_cost_credits=fight_c,
            force_share=share,
            below_auto_attack_gate=True,
            gated=True,
            gate_reason="incomplete_below_gate",
            rationale="below auto-Attack gate but reroute cost unknown",
        )

    # At/above auto-Attack gate: still ranking only — never a send.
    if reroute_turns is not None and fight_t is not None:
        if reroute_turns < fight_t:
            preferred: Preferred = "reroute"
            rationale = (
                f"reroute cheaper ({reroute_turns}t < fight {fight_t}t) "
                f"even with force_share={share:.2f} ≥ gate"
            )
        else:
            preferred = "fight"
            rationale = (
                f"fight cheaper/equal ({fight_t}t ≤ reroute {reroute_turns}t); "
                "ranking only — app auto-fire still requires taught/armed rule"
            )
        return RerouteVsFightEV(
            preferred=preferred,
            reroute_turns=reroute_turns,
            fight_cost_turns=fight_t,
            fight_cost_credits=fight_c,
            force_share=share,
            below_auto_attack_gate=False,
            gated=False,
            gate_reason=None,
            rationale=rationale,
        )

    if fight_t is not None and reroute_turns is None:
        return RerouteVsFightEV(
            preferred="fight",
            reroute_turns=None,
            fight_cost_turns=fight_t,
            fight_cost_credits=fight_c,
            force_share=share,
            below_auto_attack_gate=False,
            gated=False,
            gate_reason=None,
            rationale="fight cost known; alternate path hops unknown — rank engage",
        )

    return RerouteVsFightEV(
        preferred="reroute",
        reroute_turns=reroute_turns,
        fight_cost_turns=None,
        fight_cost_credits=fight_c,
        force_share=share,
        below_auto_attack_gate=False,
        gated=False,
        gate_reason=None,
        rationale="reroute cost known; fight cost unknown — rank taught reroute",
    )


def toll_ev_to_status(ev: RerouteVsFightEV) -> dict:
    """Wire-shaped mapping for ``status["toll_ev"]`` (omit-until-computed)."""
    return {
        "preferred": ev.preferred,
        "reroute_turns": ev.reroute_turns,
        "fight_cost_turns": ev.fight_cost_turns,
        "fight_cost_credits": ev.fight_cost_credits,
        "force_share": ev.force_share,
        "below_auto_attack_gate": ev.below_auto_attack_gate,
        "gated": ev.gated,
        "gate_reason": ev.gate_reason,
        "rationale": ev.rationale,
    }


def toll_ev_for_screen(
    screen_text: str,
    prompt_line: str = "",
    *,
    turns_per_warp: Optional[int] = None,
    extra_hops: Optional[int] = None,
) -> Optional[dict]:
    """Compute ``status["toll_ev"]`` from a live Option? frame, or omit.

    Product wire for WO-WIRE-REROUTE-EV-TO-PRIORITY-COACH: read-only ranking
    for coach/priority display. Never sends. ``fighter_toll_policy`` must not
    import this module (decide_encounter pin stays one-way).
    """
    state = parse_encounter(screen_text or "", prompt_line or "")
    if not state.detected:
        return None
    ev = compare_reroute_vs_fight(
        extra_hops=extra_hops,
        turns_per_warp=turns_per_warp,
        own_fighters=state.yours,
        enemy_fighters=state.theirs,
        is_pvp=bool(state.is_pvp),
    )
    return toll_ev_to_status(ev)
