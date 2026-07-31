"""Daemon-owned one-pass runner for an exactly approved StarDock hold buy."""

from __future__ import annotations

import datetime
import threading
from dataclasses import dataclass, replace
from typing import Optional

from ..stardock_hold_driver import HoldRunResult, run_hold_purchase
from ..stardock_hold_plan import StardockHoldPlan, plan_from_evidence
from .control_lock import ControlModeConflict

ARGS_STARDOCK_HOLD_START = frozenset(
    {
        "world_id",
        "fingerprint",
        "stardock_sector",
        "empty_holds",
        "hold_price",
        "credits",
        "qty",
        "cash_floor",
    }
)
DEFAULT_CASH_FLOOR = 1_000
STOP_JOIN_TIMEOUT_S = 5.0
OUTCOME_COMPLETED = "completed"
OUTCOME_HALTED = "halted"
OUTCOME_REFUSED = "refused"
OUTCOME_CRASHED = "crashed"


class StardockHoldRefused(Exception):
    pass


@dataclass(frozen=True)
class HoldRunReport:
    world_id: str
    fingerprint: str
    stardock_sector: int
    qty: int
    hold_price: int
    cash_floor: int
    started_at: str
    outcome: Optional[str] = None
    reason: Optional[str] = None
    sends_issued: Optional[int] = None
    qty_sent: Optional[int] = None
    stop_requested: bool = False
    error: Optional[str] = None
    finished_at: Optional[str] = None


@dataclass(frozen=True)
class HoldSnapshot:
    running: bool
    report: Optional[HoldRunReport] = None


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def run_wire(snapshot: HoldSnapshot) -> dict:
    report = snapshot.report
    wire: dict = {"running": bool(snapshot.running)}
    if report is None:
        return wire
    row = {
        "world_id": report.world_id,
        "fingerprint": report.fingerprint,
        "stardock_sector": report.stardock_sector,
        "qty": report.qty,
        "hold_price": report.hold_price,
        "cash_floor": report.cash_floor,
        "started_at": report.started_at,
        "stop_requested": report.stop_requested,
    }
    for key in (
        "outcome",
        "reason",
        "sends_issued",
        "qty_sent",
        "error",
        "finished_at",
    ):
        value = getattr(report, key)
        if value is not None:
            row[key] = value
    wire["run"] = row
    return wire


class StardockHoldRunner:
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
        self._report: Optional[HoldRunReport] = None

    def snapshot(self) -> HoldSnapshot:
        with self._mutex:
            return HoldSnapshot(
                running=bool(self._in_flight),
                report=self._report,
            )

    def start(
        self,
        world_id: object,
        fingerprint: object,
        *,
        stardock_sector: object,
        empty_holds: object,
        hold_price: object,
        credits: object,
        qty: object = 1,
        cash_floor: int = DEFAULT_CASH_FLOOR,
    ) -> HoldSnapshot:
        plan = plan_from_evidence(
            world_id,
            stardock_sector=stardock_sector,
            empty_holds=empty_holds,
            hold_price=hold_price,
            credits=credits,
            qty=qty,
        )
        if plan is None:
            raise StardockHoldRefused("hold_plan_invalid")
        if not isinstance(fingerprint, str) or fingerprint != plan.fingerprint:
            raise StardockHoldRefused("hold_identity_stale")
        if (
            isinstance(cash_floor, bool)
            or not isinstance(cash_floor, int)
            or cash_floor < 0
        ):
            raise StardockHoldRefused("invalid_cash_floor")
        if plan.credits < cash_floor:
            raise StardockHoldRefused("below_cash_floor")

        stop = threading.Event()
        report = HoldRunReport(
            world_id=plan.world_id,
            fingerprint=plan.fingerprint,
            stardock_sector=plan.stardock_sector,
            qty=plan.qty,
            hold_price=plan.hold_price,
            cash_floor=cash_floor,
            started_at=_utc_now(),
        )
        with self._mutex:
            if self._in_flight:
                raise StardockHoldRefused("already_running")
            outstanding = self._control_lock.outstanding_auto_loop_generations()
            if outstanding:
                raise StardockHoldRefused("another_app_run_winding_down")
            try:
                generation = self._control_lock.enter_auto_loop()
            except ControlModeConflict as exc:
                raise StardockHoldRefused(str(exc)) from None
            thread = threading.Thread(
                target=self._run,
                args=(plan, stop, report, generation),
                name="tw-stardock-hold",
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
                raise StardockHoldRefused("thread_start_failed") from None
        return self.snapshot()

    def stop(self, join_timeout: float = STOP_JOIN_TIMEOUT_S) -> HoldSnapshot:
        with self._mutex:
            stop = self._stop
            thread = self._thread
            if self._report is not None and self._in_flight:
                self._report = replace(self._report, stop_requested=True)
        if stop is not None:
            stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(join_timeout)
        return self.snapshot()

    def _run(
        self,
        plan: StardockHoldPlan,
        stop: threading.Event,
        report: HoldRunReport,
        generation: int,
    ) -> None:
        result: Optional[HoldRunResult] = None
        error: Optional[str] = None
        try:
            result = run_hold_purchase(
                self._session,
                plan,
                should_abort=stop.is_set,
                is_armed=lambda: True,
            )
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            if self._log_error is not None:
                try:
                    self._log_error(exc)
                except Exception:  # noqa: BLE001
                    pass
        with self._mutex:
            if result is None:
                self._report = replace(
                    report,
                    outcome=OUTCOME_CRASHED,
                    reason="driver_exception",
                    error=error,
                    finished_at=_utc_now(),
                )
            elif result.outcome == "completed":
                self._report = replace(
                    report,
                    outcome=OUTCOME_COMPLETED,
                    sends_issued=result.sends_issued,
                    qty_sent=result.qty_sent,
                    finished_at=_utc_now(),
                )
            elif result.outcome == "refused":
                self._report = replace(
                    report,
                    outcome=OUTCOME_REFUSED,
                    reason=result.reason,
                    sends_issued=result.sends_issued,
                    finished_at=_utc_now(),
                )
            else:
                self._report = replace(
                    report,
                    outcome=OUTCOME_HALTED,
                    reason=result.reason or "halted",
                    sends_issued=result.sends_issued,
                    finished_at=_utc_now(),
                )
            self._in_flight = False
            self._stop = None
            self._thread = None
        try:
            self._control_lock.leave_auto_loop(generation)
        except Exception:  # noqa: BLE001
            pass
