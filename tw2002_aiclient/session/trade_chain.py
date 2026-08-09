"""Daemon-owned one-pass runner for an exactly approved profit chain."""

from __future__ import annotations

import datetime
import threading
from dataclasses import dataclass, replace
from typing import Optional

from .. import chain_search
from ..explore import known_graph, path_to_sector
from ..trade_chain_plan import plan_from_chain, resolve_exact_chain
from ..bounded_repeat_trade_chain_driver import (
    DEFAULT_MAX_PASSES,
    clamp_pass_count,
    run_bounded_repeat,
)
from ..trade_driver import ChainRunResult, run_chain
from .control_lock import ControlModeConflict
from .credentials import is_crawl_sacrificial
from .state_parser import OUTCOME_READ

ARGS_TRADE_CHAIN_START = frozenset(
    {
        "world_id",
        "fingerprint",
        "cash_floor",
        "turn_reserve",
        "profit_target",
        "pass_count",
    }
)
DEFAULT_CASH_FLOOR = 1_000
DEFAULT_TURN_RESERVE = 10
# Re-export for CLI (bounded-repeat ceiling default).
DEFAULT_PASS_COUNT = DEFAULT_MAX_PASSES
DEFAULT_STATE_STALE_MS = 60_000
STOP_JOIN_TIMEOUT_S = 5.0
OUTCOME_COMPLETED = "completed"
OUTCOME_HALTED = "halted"
OUTCOME_CRASHED = "crashed"


class TradeChainRefused(Exception):
    pass


def discovery_blocks_start(discovered) -> bool:
    """True when chain discovery must not arm a trade start.

    RESOLVED-EXPLORE-VS-TRADE-LOOP-MODES / WO-EXPLORE-TRADE-MODE-SPLIT:
    a truncated search that still returned cycles may arm an **exact**
    fingerprint present in that partial list (absence of a *better* cycle
    is not established — the selected cycle still is). Block only when
    truncated **and** empty, or when truncated with no usable chain list.
    """
    if not bool(getattr(discovered, "truncated", False)):
        return False
    found = getattr(discovered, "chains", None)
    return not isinstance(found, (tuple, list)) or len(found) == 0


def refuse_if_start_anchor_unreachable(
    session,
    world_id: str,
    start_anchor: int,
    *,
    state_dir=None,
) -> None:
    """Fail closed before arm when known position cannot directed-reach the
    chain start_anchor (WO-FIX-CHAIN-ARM-START-ANCHOR-REACHABLE).

    Skips when position memory is absent — the driver still halts on
    ``start_anchor_unknown`` / mismatch after arm. Gates only the live
    directed-sink case: known sector, no outbound path to the anchor.
    Travel-to-anchor when a path *does* exist remains a follow-on.
    """
    probe = getattr(session, "last_known_sector", None)
    if not callable(probe):
        return
    current = probe()
    if current is None or isinstance(current, bool) or not isinstance(current, int):
        return
    if current == start_anchor:
        return
    graph = known_graph(world_id, state_dir=state_dir)
    if path_to_sector(graph, current, start_anchor) is not None:
        return
    raise TradeChainRefused(
        f"start_anchor_unreachable:{current}:{start_anchor}"
    )


@dataclass(frozen=True)
class TradeCaps:
    cash_floor: int
    turn_reserve: int
    credits_stale_ms: int = DEFAULT_STATE_STALE_MS
    # ADDITIONAL stop, mirroring cash_floor's exact fail-closed shape with
    # the direction inverted (WO-BUILD-PROFIT-TARGET-HALT). `None` (the
    # default) means no target was requested and the check never fires.
    profit_target: Optional[int] = None


@dataclass(frozen=True)
class TradeRunReport:
    world_id: str
    fingerprint: str
    route: str
    commodities: tuple[str, ...]
    cash_floor: int
    turn_reserve: int
    started_at: str
    profit_target: Optional[int] = None
    pass_count: int = 1
    outcome: Optional[str] = None
    reason: Optional[str] = None
    hops_completed: Optional[int] = None
    hops_total: int = 0
    sends_issued: Optional[int] = None
    credits_delta: Optional[int] = None
    passes_completed: Optional[int] = None
    stop_requested: bool = False
    error: Optional[str] = None
    finished_at: Optional[str] = None


@dataclass(frozen=True)
class TradeSnapshot:
    running: bool
    report: Optional[TradeRunReport] = None


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _lock_held(control_lock) -> bool:
    try:
        return bool(control_lock.is_auto_loop_held())
    except Exception:  # noqa: BLE001
        return False


def run_wire(snapshot: TradeSnapshot) -> dict:
    report = snapshot.report
    wire: dict = {"running": bool(snapshot.running)}
    if report is None:
        return wire
    row = {
        "world_id": report.world_id,
        "fingerprint": report.fingerprint,
        "route": report.route,
        "commodities": list(report.commodities),
        "cash_floor": report.cash_floor,
        "turn_reserve": report.turn_reserve,
        "profit_target": report.profit_target,
        "pass_count": report.pass_count,
        "started_at": report.started_at,
        "hops_total": report.hops_total,
        "stop_requested": report.stop_requested,
    }
    for key in (
        "outcome",
        "reason",
        "hops_completed",
        "sends_issued",
        "credits_delta",
        "passes_completed",
        "error",
        "finished_at",
    ):
        value = getattr(report, key)
        if value is not None:
            row[key] = value
    wire["run"] = row
    return wire


def intervention_block(snapshot: TradeSnapshot) -> Optional[dict]:
    report = snapshot.report
    if report is None or report.outcome not in (OUTCOME_HALTED, OUTCOME_CRASHED):
        return None
    reasons = [{"code": report.reason}] if report.reason else []
    return {"needs_attention": True, "reasons": reasons}


class TradeChainRunner:
    def __init__(
        self, session, control_lock, *, state_dir=None, log_error=None
    ) -> None:
        self._session = session
        self._control_lock = control_lock
        self._state_dir = state_dir
        self._log_error = log_error
        self._mutex = threading.Lock()
        self._in_flight = False
        self._thread: Optional[threading.Thread] = None
        self._stop: Optional[threading.Event] = None
        self._report: Optional[TradeRunReport] = None

    def snapshot(self) -> TradeSnapshot:
        with self._mutex:
            return TradeSnapshot(
                running=bool(self._in_flight),
                report=self._report,
            )

    def start(
        self,
        world_id: str,
        fingerprint: str,
        *,
        cash_floor: int = DEFAULT_CASH_FLOOR,
        turn_reserve: int = DEFAULT_TURN_RESERVE,
        profit_target: Optional[int] = None,
        pass_count: Optional[int] = None,
    ) -> TradeSnapshot:
        if not isinstance(world_id, str) or not world_id.strip():
            raise TradeChainRefused("invalid_world_id")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise TradeChainRefused("invalid_fingerprint")
        if (
            isinstance(cash_floor, bool)
            or not isinstance(cash_floor, int)
            or cash_floor < 0
        ):
            raise TradeChainRefused("invalid_cash_floor")
        if (
            isinstance(turn_reserve, bool)
            or not isinstance(turn_reserve, int)
            or turn_reserve < 0
        ):
            raise TradeChainRefused("invalid_turn_reserve")
        if profit_target is not None and (
            isinstance(profit_target, bool) or not isinstance(profit_target, int)
        ):
            raise TradeChainRefused("invalid_profit_target")
        effective_passes = 1
        if pass_count is not None:
            try:
                effective_passes = clamp_pass_count(pass_count)
            except ValueError:
                raise TradeChainRefused("invalid_pass_count") from None
        # Bounded-repeat (pass_count > 1) is sacrificial-only — never arm on
        # a real player account (Max GO 2026-08-09 for this capability).
        if effective_passes > 1:
            profile = getattr(self._session, "auto_login_profile", None)
            if not isinstance(profile, str) or not profile or not is_crawl_sacrificial(
                profile
            ):
                raise TradeChainRefused("bounded_repeat_requires_sacrificial")

        try:
            # Map growth made the default 100k DFS budget return 0 cycles while
            # still truncated (live Cartogra 2026-08-01) — soft partial gate
            # then still blocked every start. Prefer a deeper search here so an
            # exact L-armed fingerprint can resolve.
            discovered = chain_search.recompute(
                world_id.strip(),
                state_dir=self._state_dir,
                max_search_steps=500_000,
            )
        except Exception as exc:  # noqa: BLE001
            raise TradeChainRefused(
                f"chain_discovery_failed:{type(exc).__name__}"
            ) from None
        if discovery_blocks_start(discovered):
            raise TradeChainRefused("chain_discovery_partial")
        chain = resolve_exact_chain(
            world_id.strip(), fingerprint, discovered.chains
        )
        if chain is None:
            raise TradeChainRefused("chain_identity_stale")
        plan = plan_from_chain(world_id.strip(), chain)
        if plan is None:
            raise TradeChainRefused("chain_plan_invalid")
        refuse_if_start_anchor_unreachable(
            self._session,
            plan.world_id,
            plan.start_anchor,
            state_dir=self._state_dir,
        )

        stop = threading.Event()
        report = TradeRunReport(
            world_id=plan.world_id,
            fingerprint=plan.fingerprint,
            route=plan.route,
            commodities=plan.commodities,
            cash_floor=cash_floor,
            turn_reserve=turn_reserve,
            profit_target=profit_target,
            pass_count=effective_passes,
            started_at=_utc_now(),
            hops_total=plan.hops,
        )
        with self._mutex:
            if self._in_flight:
                raise TradeChainRefused("already_running")
            outstanding = self._control_lock.outstanding_auto_loop_generations()
            if outstanding:
                raise TradeChainRefused("another_app_run_winding_down")
            try:
                generation = self._control_lock.enter_auto_loop()
            except ControlModeConflict as exc:
                raise TradeChainRefused(str(exc)) from None
            thread = threading.Thread(
                target=self._run,
                args=(chain, stop, report, generation),
                name="tw-trade-chain",
                daemon=True,
            )
            self._in_flight = True
            self._stop = stop
            self._thread = thread
            self._report = report
            try:
                thread.start()
            except Exception:
                self._control_lock.leave_auto_loop(generation)
                self._in_flight = False
                self._stop = None
                self._thread = None
                self._report = replace(
                    report,
                    outcome=OUTCOME_CRASHED,
                    reason="thread_start_failed",
                    finished_at=_utc_now(),
                )
                raise TradeChainRefused("thread_start_failed") from None
        return self.snapshot()

    def stop(self, join_timeout: float = STOP_JOIN_TIMEOUT_S) -> TradeSnapshot:
        with self._mutex:
            stop = self._stop
            thread = self._thread
            if self._report is not None and self._in_flight:
                self._report = replace(self._report, stop_requested=True)
        if stop is not None:
            stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(join_timeout)
            if thread.is_alive():
                conn = getattr(self._session, "conn", None)
                if conn is not None and hasattr(conn, "force_unblock_sends"):
                    conn.force_unblock_sends()
                thread.join(min(join_timeout, 1.0))
        return self.snapshot()

    def _turns_left(self) -> Optional[int]:
        if not hasattr(self._session, "turns_snapshot"):
            return None
        snapshot = self._session.turns_snapshot()
        if getattr(snapshot, "outcome", None) != OUTCOME_READ:
            return None
        age_s = getattr(snapshot, "age_s", None)
        turns = getattr(snapshot, "turns", None)
        if (
            age_s is None
            or age_s * 1000 > DEFAULT_STATE_STALE_MS
            or isinstance(turns, bool)
            or not isinstance(turns, int)
        ):
            return None
        return turns

    def _run(
        self,
        chain,
        stop: threading.Event,
        report: TradeRunReport,
        generation: int,
    ) -> None:
        result: Optional[ChainRunResult] = None
        error: Optional[str] = None

        def _progress(event: object) -> None:
            if not isinstance(event, dict):
                return
            hop_index = event.get("hop_index")
            hops_total = event.get("hops_total")
            steps = event.get("steps")
            done = event.get("done")
            if (
                isinstance(hop_index, bool)
                or not isinstance(hop_index, int)
                or isinstance(hops_total, bool)
                or not isinstance(hops_total, int)
                or isinstance(steps, bool)
                or not isinstance(steps, int)
                or not isinstance(done, bool)
            ):
                return
            completed = hop_index if done else hop_index + 1
            with self._mutex:
                current = self._report
                if (
                    not self._in_flight
                    or current is None
                    or current.started_at != report.started_at
                ):
                    return
                self._report = replace(
                    current,
                    hops_completed=max(0, min(hops_total, completed)),
                    sends_issued=max(0, steps),
                )

        try:
            turns_left = self._turns_left()
            if turns_left is None:
                result = ChainRunResult(
                    completed=False,
                    hops_completed=0,
                    steps=0,
                    credits_delta=None,
                    stop_reason="turns_unknown",
                )
            else:
                caps = TradeCaps(
                    cash_floor=report.cash_floor,
                    turn_reserve=report.turn_reserve,
                    profit_target=report.profit_target,
                )
                bounded = run_bounded_repeat(
                    self._session,
                    chain,
                    world_id=report.world_id,
                    turns_left_fn=self._turns_left,
                    caps=caps,
                    should_abort=stop.is_set,
                    is_armed=lambda: (
                        not stop.is_set() and _lock_held(self._control_lock)
                    ),
                    max_passes=report.pass_count,
                    state_dir=self._state_dir,
                    on_progress=_progress,
                    run_chain_fn=run_chain,
                    credits_stale_ms=DEFAULT_STATE_STALE_MS,
                )
                # Adapt aggregate into ChainRunResult shape for existing finish path.
                result = ChainRunResult(
                    completed=bounded.completed,
                    hops_completed=bounded.hops_completed,
                    steps=bounded.steps,
                    credits_delta=bounded.credits_delta,
                    stop_reason=bounded.stop_reason,
                )
                # Stash passes_completed on the report via closure after finish.
                report = replace(
                    report, passes_completed=bounded.passes_completed
                )
        except Exception as exc:  # noqa: BLE001
            error = type(exc).__name__
            if self._log_error is not None:
                try:
                    self._log_error(exc)
                except Exception:  # noqa: BLE001
                    pass
        finally:
            self._control_lock.leave_auto_loop(generation)
            with self._mutex:
                if result is None:
                    finished = replace(
                        report,
                        outcome=OUTCOME_CRASHED,
                        reason="driver_error",
                        error=error or "unknown",
                        finished_at=_utc_now(),
                        stop_requested=stop.is_set(),
                    )
                else:
                    finished = replace(
                        report,
                        outcome=(
                            OUTCOME_COMPLETED
                            if result.completed
                            else OUTCOME_HALTED
                        ),
                        reason=result.stop_reason,
                        hops_completed=result.hops_completed,
                        sends_issued=result.steps,
                        credits_delta=result.credits_delta,
                        finished_at=_utc_now(),
                        stop_requested=stop.is_set(),
                    )
                self._report = finished
                self._in_flight = False
                self._thread = None
                self._stop = None
