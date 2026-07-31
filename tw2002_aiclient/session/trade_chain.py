"""Daemon-owned one-pass runner for an exactly approved profit chain."""

from __future__ import annotations

import datetime
import threading
from dataclasses import dataclass, replace
from typing import Optional

from .. import chain_search
from ..trade_chain_plan import plan_from_chain, resolve_exact_chain
from ..trade_driver import ChainRunResult, run_chain
from .control_lock import ControlModeConflict
from .state_parser import OUTCOME_READ

ARGS_TRADE_CHAIN_START = frozenset(
    {"world_id", "fingerprint", "cash_floor", "turn_reserve"}
)
DEFAULT_CASH_FLOOR = 1_000
DEFAULT_TURN_RESERVE = 10
DEFAULT_STATE_STALE_MS = 60_000
STOP_JOIN_TIMEOUT_S = 5.0
OUTCOME_COMPLETED = "completed"
OUTCOME_HALTED = "halted"
OUTCOME_CRASHED = "crashed"


class TradeChainRefused(Exception):
    pass


def discovery_blocks_start(discovered) -> bool:
    """True when chain discovery must not arm a trade start.

    Same condition ``TradeRunner.start`` uses for ``chain_discovery_partial``
    (WO-TRADE-PARTIAL-BACKOFF): a truncated search is incomplete even when
    it returned some cycles — absence of better cycles is not established.
    Shared so the App-armed auto-fire preflight cannot drift from the runner.
    """
    return bool(getattr(discovered, "truncated", False))


@dataclass(frozen=True)
class TradeCaps:
    cash_floor: int
    turn_reserve: int
    credits_stale_ms: int = DEFAULT_STATE_STALE_MS


@dataclass(frozen=True)
class TradeRunReport:
    world_id: str
    fingerprint: str
    route: str
    commodities: tuple[str, ...]
    cash_floor: int
    turn_reserve: int
    started_at: str
    outcome: Optional[str] = None
    reason: Optional[str] = None
    hops_completed: Optional[int] = None
    hops_total: int = 0
    sends_issued: Optional[int] = None
    credits_delta: Optional[int] = None
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

        try:
            discovered = chain_search.recompute(
                world_id.strip(), state_dir=self._state_dir
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

        stop = threading.Event()
        report = TradeRunReport(
            world_id=plan.world_id,
            fingerprint=plan.fingerprint,
            route=plan.route,
            commodities=plan.commodities,
            cash_floor=cash_floor,
            turn_reserve=turn_reserve,
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
                )
                result = run_chain(
                    self._session,
                    chain,
                    world_id=report.world_id,
                    turns_left=turns_left,
                    caps=caps,
                    should_abort=stop.is_set,
                    is_armed=lambda: (
                        not stop.is_set() and _lock_held(self._control_lock)
                    ),
                    state_dir=self._state_dir,
                    on_progress=_progress,
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
