"""Bounded-repeat wrapper around ``trade_driver.run_chain``.

One arm of ``run_chain`` is one pass by design (ADR-003). This module
re-arms that one-pass driver up to a pass-count ceiling, re-checking the
X5 stop-loss floor and profit-target halt before every re-arm. Whichever
of (pass-count, floor, profit_target) trips first stops the loop.

Guard shape mirrors ``stardock_hold_driver`` / ``run_chain``: REQUIRED
fail-closed ``should_abort`` / ``is_armed`` predicates checked at every
boundary. Callers that want multi-pass must gate sacrificial profiles
themselves (``TradeChainRunner.start`` refuses otherwise).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .loops.player import _check_floor, _check_profit_target
from .trade_driver import ChainRunResult, run_chain

DEFAULT_MAX_PASSES = 10
PASSES_HARD_CEILING = 50
DEFAULT_CREDITS_STALE_MS = 60_000

STOP_PASS_COUNT = "pass_count_ceiling"
STOP_ABORTED = "aborted"


@dataclass(frozen=True)
class BoundedRepeatResult:
    """Aggregate outcome of zero or more ``run_chain`` passes."""

    completed: bool
    passes_completed: int
    hops_completed: int
    steps: int
    credits_delta: Optional[int]
    stop_reason: str
    pass_stop_reasons: tuple[str, ...] = field(default_factory=tuple)


def _session_credits_snapshot(session: object):
    probe = getattr(session, "credits_snapshot", None)
    if not callable(probe):
        return None
    try:
        return probe()
    except Exception:  # noqa: BLE001
        return None


def _session_profit_snapshot(session: object):
    probe = getattr(session, "profit_snapshot", None)
    if not callable(probe):
        return None
    try:
        return probe()
    except Exception:  # noqa: BLE001
        return None


def _pre_pass_halt(
    session: object,
    *,
    cash_floor: int,
    profit_target: Optional[int],
    credits_stale_ms: int,
) -> Optional[str]:
    """Fail-closed floor + profit-target gate before (re-)arming a pass.

    Reuses the exact PR #555 / X5 decision functions so unit behavior
    stays identical to the intra-chain rails.
    """
    floor_halt = _check_floor(
        _session_credits_snapshot(session), cash_floor, credits_stale_ms
    )
    if floor_halt is not None:
        return floor_halt
    profit_halt = _check_profit_target(
        _session_profit_snapshot(session), profit_target, credits_stale_ms
    )
    if profit_halt is not None:
        return profit_halt
    return None


def clamp_pass_count(pass_count: int) -> int:
    """Refuse non-positive; clamp to the hard ceiling (never unbounded)."""
    if isinstance(pass_count, bool) or not isinstance(pass_count, int):
        raise ValueError("invalid_pass_count")
    if pass_count <= 0:
        raise ValueError("invalid_pass_count")
    return min(pass_count, PASSES_HARD_CEILING)


def run_bounded_repeat(
    session,
    chain,
    *,
    world_id: Optional[str],
    turns_left_fn: Callable[[], Optional[int]],
    caps,
    should_abort: Callable[[], bool],
    is_armed: Callable[[], bool],
    max_passes: int = DEFAULT_MAX_PASSES,
    state_dir=None,
    config=None,
    on_progress: Optional[Callable[[dict], None]] = None,
    run_chain_fn=run_chain,
    credits_stale_ms: int = DEFAULT_CREDITS_STALE_MS,
) -> BoundedRepeatResult:
    """Re-arm ``run_chain`` up to ``max_passes``, stopping on first bound.

    Before the first pass and before every re-arm: abort/arm gates, then
    X5 floor, then profit-target. A non-completed chain pass ends the
    loop immediately (no silent retry).
    """
    try:
        ceiling = clamp_pass_count(max_passes)
    except ValueError:
        return BoundedRepeatResult(
            completed=False,
            passes_completed=0,
            hops_completed=0,
            steps=0,
            credits_delta=None,
            stop_reason="invalid_pass_count",
        )

    cash_floor = int(getattr(caps, "cash_floor", 0) or 0)
    profit_target = getattr(caps, "profit_target", None)
    passes_completed = 0
    hops_completed = 0
    steps = 0
    credits_delta: Optional[int] = 0
    saw_credit = False
    pass_reasons: list[str] = []

    while passes_completed < ceiling:
        if should_abort() or not is_armed():
            return BoundedRepeatResult(
                completed=False,
                passes_completed=passes_completed,
                hops_completed=hops_completed,
                steps=steps,
                credits_delta=credits_delta if saw_credit else None,
                stop_reason=STOP_ABORTED,
                pass_stop_reasons=tuple(pass_reasons),
            )

        # Floor + profit-target are per-re-arm conditions (ADR-003 item 8).
        # The first arm relies on run_chain's own intra-pass rails so a
        # one-pass start does not demand a pre-observed credits snapshot.
        if passes_completed > 0:
            pre = _pre_pass_halt(
                session,
                cash_floor=cash_floor,
                profit_target=profit_target,
                credits_stale_ms=credits_stale_ms,
            )
            if pre is not None:
                return BoundedRepeatResult(
                    completed=False,
                    passes_completed=passes_completed,
                    hops_completed=hops_completed,
                    steps=steps,
                    credits_delta=credits_delta if saw_credit else None,
                    stop_reason=pre,
                    pass_stop_reasons=tuple(pass_reasons),
                )

        turns_left = turns_left_fn()
        result = run_chain_fn(
            session,
            chain,
            world_id=world_id,
            turns_left=turns_left,
            caps=caps,
            should_abort=should_abort,
            is_armed=is_armed,
            state_dir=state_dir,
            config=config,
            on_progress=on_progress,
        )
        if not isinstance(result, ChainRunResult):
            return BoundedRepeatResult(
                completed=False,
                passes_completed=passes_completed,
                hops_completed=hops_completed,
                steps=steps,
                credits_delta=credits_delta if saw_credit else None,
                stop_reason="driver_error",
                pass_stop_reasons=tuple(pass_reasons),
            )

        pass_reasons.append(result.stop_reason)
        hops_completed += int(result.hops_completed or 0)
        steps += int(result.steps or 0)
        if result.credits_delta is not None:
            saw_credit = True
            credits_delta = (credits_delta or 0) + int(result.credits_delta)

        if not result.completed:
            return BoundedRepeatResult(
                completed=False,
                passes_completed=passes_completed,
                hops_completed=hops_completed,
                steps=steps,
                credits_delta=credits_delta if saw_credit else None,
                stop_reason=result.stop_reason,
                pass_stop_reasons=tuple(pass_reasons),
            )

        passes_completed += 1

        # Bound trip: pass-count ceiling reached after a successful pass.
        if passes_completed >= ceiling:
            # Preserve ADR-003 one-pass wire reason when ceiling is 1.
            reason = STOP_PASS_COUNT if ceiling > 1 else "completed"
            return BoundedRepeatResult(
                completed=True,
                passes_completed=passes_completed,
                hops_completed=hops_completed,
                steps=steps,
                credits_delta=credits_delta if saw_credit else None,
                stop_reason=reason,
                pass_stop_reasons=tuple(pass_reasons),
            )

        # Re-arm path: floor / profit checked at top of next loop iteration.

    return BoundedRepeatResult(
        completed=True,
        passes_completed=passes_completed,
        hops_completed=hops_completed,
        steps=steps,
        credits_delta=credits_delta if saw_credit else None,
        stop_reason=STOP_PASS_COUNT,
        pass_stop_reasons=tuple(pass_reasons),
    )
