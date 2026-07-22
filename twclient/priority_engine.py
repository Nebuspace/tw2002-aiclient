"""Priority engine — rank competing TW2002 client objectives.

Design brief: ``priority_engine.md`` (repo root of tw2002-aiclient).

This module is the **driver** for "what should we focus on now?" It sits
above the per-kind scorers in ``autopilot.py`` and adds Max's missing
piece: **round-trip execution cost** before abandoning in-progress work
(e.g. leave a trade chain for StarDock, buy a ship, come back).

Pure logic — no daemon I/O. Autopilot may call ``recommend()`` / wire
``rank_action_priorities()`` into ``select()``; spectate can render the
ranked list later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence

from .explore import path_to_sector


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


def recommend_actions(
    *,
    # Chain (interrupted work)
    chain_cr_per_turn: Optional[float] = None,
    chain_cycle_turns: Optional[int] = None,
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
) -> PriorityRecommendation:
    """Rank ``run_chain`` / ``upgrade`` / ``explore`` with RT-aware upgrade gating.

    Callers supply already-parsed economics (from autopilot / world snapshot).
    Unknowns fail-closed — never guess StarDock distance or return path.
    """
    scores: list[PriorityScore] = []
    notes: list[str] = []
    stay_vs_leave: Optional[str] = None

    productive: Optional[int] = None
    if turns_left is not None:
        productive = max(0, turns_left - max(0, turn_reserve))

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
    else:
        scores.append(
            PriorityScore(
                kind="run_chain",
                ev_per_turn=float(chain_cr_per_turn),
                gated=False,
                rationale=(
                    f"trade chain {chain_cr_per_turn:.1f} cr/turn"
                    + ("" if at_chain_start else " (not at cycle start — navigate first)")
                ),
                weight=40,
            )
        )

    # --- upgrade (RT-aware) ---
    chain_active = chain_cr_per_turn is not None and chain_cr_per_turn > 0
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

    return PriorityRecommendation(
        ranked=ranked,
        focus=focus,
        stay_vs_leave=stay_vs_leave,
        notes=tuple(notes),
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
                rationale="RT incomplete (Max pre-flight)",
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
