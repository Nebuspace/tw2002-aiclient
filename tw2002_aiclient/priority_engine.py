"""Priority engine — RT travel cost + stay-vs-leave (strategic ranker only).

Canon: ``canon/engine/priority-engine.md``. Pure logic — emits ordering
inputs for FOCUS; never sends, never arms, never invents hop counts.

Ported kernel from the archived ``twclient/priority_engine.py`` RT /
stay-vs-leave primitives (WO-PRIORITY-ENGINE-KERNEL). Chain-link floors
live in ``chains.py``; this module does not re-export EXECUTE surfaces.
"""

from __future__ import annotations

__all__ = [
    "hops_of_path",
    "travel_cost_rt_turns",
    "compute_return_path",
    "stay_vs_leave_upgrade",
    "upgrade_gate_while_chaining",
]

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
