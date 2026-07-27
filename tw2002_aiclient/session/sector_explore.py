"""App-driven sector frontier exploration from ``main_command`` (WO M4).

Pure map-fill / AP-08 adjacent hops only — no invented screen classes, no
money/combat auto-action. Halts on the first unrecognized or never-auto
screen; surfaces ``explore_exhausted`` when the planner has no legal hop.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from typing import Optional, Set

from .. import world_model
from .. import explore as _explore
from ..explore import known_graph, map_fill_warp_target, warp_target_for_intent
from ..loops.player import (
    HALT_ABORTED,
    HALT_CONFIRM_FAILED,
    HALT_FENCED,
    HALT_NEVER_AUTO_ACTION,
    HALT_SETTLE_FAILED,
    HALT_UNRECOGNIZED_SCREEN,
    OUTCOME_HALTED,
)
from .classify import NEVER_AUTO_ACTION_CLASSES, classify_screen
from .control_lock import ControlLock, ControlModeConflict
from .state_parser import (
    OUTCOME_READ,
    read_current_sector,
    read_port_from_sector_status,
    read_warps_from_sector_status,
)
from . import settle as _settle

__all__ = [
    "ARGS_EXPLORE_START",
    "ExploreRefused",
    "ExploreReport",
    "ExploreRunner",
    "ExploreSnapshot",
    "DEFAULT_MIN_DISTINCT_SECTORS",
    "DEFAULT_TURN_BUDGET",
    "MOVEMENT_SCREEN_CLASS",
    "explore_run_wire",
    "observe_explore",
]

MOVEMENT_SCREEN_CLASS = "main_command"
DEFAULT_MIN_DISTINCT_SECTORS = 5
DEFAULT_TURN_BUDGET = 50

SETTLE_TIMEOUT_S = 8.0
SETTLE_DEBOUNCE_MS = 350
STOP_JOIN_TIMEOUT_S = 5.0

ARGS_EXPLORE_START = frozenset({"world_id", "min_sectors", "turn_budget", "intent"})

OUTCOME_COMPLETED = "completed"
OUTCOME_CRASHED = "crashed"
REASON_EXPLORE_EXHAUSTED = "explore_exhausted"
REASON_DRIVER_ERROR = "explore_driver_error"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ExploreRefused(Exception):
    """Start refused — message is the wire error code."""


@dataclass(frozen=True)
class ExploreReport:
    world_id: str
    started_at: str
    min_sectors: int
    # WO-EXPLORE-AUTOMATION-GATE E3: which goal this run is pursuing. On the
    # report (not just the call) because the run's outcome is only
    # interpretable against its intent -- "exhausted" means a filled frontier
    # for map-fill and an unreachable landmark for find-StarDock.
    intent: str = _explore.INTENT_MAP_FILL
    outcome: Optional[str] = None
    reason: Optional[str] = None
    distinct_sectors: int = 0
    sends_issued: int = 0
    turns_remaining: int = 0
    stop_requested: bool = False
    finished_at: Optional[str] = None
    error: Optional[str] = None

    @property
    def halted(self) -> bool:
        return self.outcome in (OUTCOME_HALTED, OUTCOME_CRASHED)


@dataclass(frozen=True)
class ExploreSnapshot:
    running: bool
    report: Optional[ExploreReport] = None


def explore_run_wire(snapshot: ExploreSnapshot) -> dict:
    report = snapshot.report
    if report is None:
        return {"running": bool(snapshot.running), "run": None}
    return {
        "running": bool(snapshot.running),
        "run": {
            "world_id": report.world_id,
            "outcome": report.outcome,
            "reason": report.reason,
            "distinct_sectors": report.distinct_sectors,
            "sends_issued": report.sends_issued,
            "turns_remaining": report.turns_remaining,
            "min_sectors": report.min_sectors,
            "intent": report.intent,
            "stop_requested": report.stop_requested,
            "started_at": report.started_at,
            "finished_at": report.finished_at,
            "error": report.error,
        },
    }


def observe_explore(runner, control_lock) -> ExploreSnapshot:
    if runner is not None:
        return runner.snapshot()
    probe = getattr(control_lock, "is_auto_loop_held", None)
    held = bool(probe()) if probe is not None else False
    return ExploreSnapshot(running=held)


def _lock_held(control_lock) -> bool:
    probe = getattr(control_lock, "is_auto_loop_held", None)
    if probe is None:
        return False
    return bool(probe())


def _gate_screen(full_text: str, prompt_line: str) -> Optional[str]:
    klass = classify_screen(full_text, prompt_line)
    if klass in NEVER_AUTO_ACTION_CLASSES:
        return HALT_NEVER_AUTO_ACTION
    if klass != MOVEMENT_SCREEN_CLASS:
        return HALT_UNRECOGNIZED_SCREEN
    return None


def _ingest_settled_sector(
    world_id: str,
    *,
    sector_id: int,
    full_text: str,
    state_dir,
) -> None:
    """Persist sector + warps + port posture from a settled main_command screen.

    WO-EXPLORE-AUTOMATION-GATE E2: the ``Ports :`` flyby is read on every hop
    because it is **turn-free** — the sector display already prints it, so
    port buy/sell posture is learned without docking or sending. That is what
    makes the world model good enough to feed chain detection off an ordinary
    map-fill run rather than a second, turn-spending pass.

    The tri-state from ``read_port_from_sector_status`` is forwarded, not
    flattened: the ``port`` key is **omitted** when nothing was observed (so
    `write_from_state` preserves a previously-learned port) and set to an
    explicit ``None`` only when the screen positively said ``Ports : None``
    (which clears a stale record). Collapsing those two would either wipe
    real port data on a warps-only render or keep asserting a port that is
    gone.
    """
    parsed: dict = {"sector": int(sector_id)}
    warps = read_warps_from_sector_status(full_text)
    if warps is not None:
        parsed["warps"] = warps
    port = read_port_from_sector_status(full_text)
    if port.observed:
        parsed["port"] = port.port
    world_model.write_from_state(world_id, parsed, state_dir=state_dir)


def _adjacent_warp_allowed(graph, current: int, target: int) -> bool:
    warps = graph.get(current)
    if not warps:
        return False
    return int(target) in warps


class ExploreRunner:
    """Background map-fill driver — one ``enter_auto_loop`` hold per run."""

    def __init__(
        self,
        session,
        control_lock: ControlLock,
        *,
        state_dir=None,
        log_error=None,
        timeout_s: float = SETTLE_TIMEOUT_S,
        debounce_ms: int = SETTLE_DEBOUNCE_MS,
    ) -> None:
        self._session = session
        self._control_lock = control_lock
        self._state_dir = state_dir
        self._log_error = log_error
        self._timeout_s = timeout_s
        self._debounce_ms = debounce_ms
        self._mutex = threading.Lock()
        self._in_flight = False
        self._stop: Optional[threading.Event] = None
        self._thread: Optional[threading.Thread] = None
        self._report: Optional[ExploreReport] = None

    def snapshot(self) -> ExploreSnapshot:
        with self._mutex:
            running = self._in_flight or _lock_held(self._control_lock)
            return ExploreSnapshot(running=running, report=self._report)

    def start(
        self,
        world_id: str,
        *,
        min_sectors: int = DEFAULT_MIN_DISTINCT_SECTORS,
        turn_budget: int = DEFAULT_TURN_BUDGET,
        intent: str = _explore.INTENT_MAP_FILL,
    ) -> ExploreSnapshot:
        if not isinstance(world_id, str) or not world_id.strip():
            raise ExploreRefused("missing_world_id")
        # `0` is legal and means "no sector cap" (E1 exhaustive: run until
        # turn budget or frontier exhaustion). Negatives and bools stay
        # refused -- a cap you cannot reach is not a cap.
        if isinstance(min_sectors, bool) or not isinstance(min_sectors, int) or min_sectors < 0:
            raise ExploreRefused("invalid_min_sectors")
        if isinstance(turn_budget, bool) or not isinstance(turn_budget, int) or turn_budget < 0:
            raise ExploreRefused("invalid_turn_budget")
        # Closed set, refused not defaulted: a run that quietly map-fills when
        # the operator confirmed "find StarDock" would have done something
        # other than what the arm gate promised.
        if intent not in _explore.INTENTS:
            raise ExploreRefused("invalid_intent")

        stop = threading.Event()
        report = ExploreReport(
            world_id=world_id.strip(),
            started_at=_utc_now(),
            min_sectors=int(min_sectors),
            intent=intent,
            turns_remaining=int(turn_budget),
        )
        with self._mutex:
            if self._in_flight:
                raise ExploreRefused("already_running")
            try:
                generation = self._control_lock.enter_auto_loop()
            except ControlModeConflict as exc:
                raise ExploreRefused(str(exc)) from None
            thread = threading.Thread(
                target=self._run,
                args=(report, stop, generation),
                name="tw-sector-explore",
                daemon=True,
            )
            self._in_flight = True
            self._stop = stop
            self._thread = thread
            self._report = report
            try:
                thread.start()
            except Exception as exc:
                self._control_lock.leave_auto_loop(generation)
                self._in_flight = False
                self._thread = None
                self._stop = None
                self._report = replace(
                    report,
                    outcome=OUTCOME_CRASHED,
                    reason=REASON_DRIVER_ERROR,
                    error=type(exc).__name__,
                    finished_at=_utc_now(),
                )
                raise ExploreRefused("thread_start_failed") from exc
        return self.snapshot()

    def stop(self, join_timeout: float = STOP_JOIN_TIMEOUT_S) -> ExploreSnapshot:
        with self._mutex:
            stop = self._stop
            thread = self._thread
        if stop is not None:
            stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(join_timeout)
        return self.snapshot()

    def _run(self, report: ExploreReport, stop: threading.Event, generation: int) -> None:
        outcome = OUTCOME_CRASHED
        reason: Optional[str] = REASON_DRIVER_ERROR
        distinct: Set[int] = set()
        sends = 0
        turns = report.turns_remaining
        try:
            while not stop.is_set():
                if getattr(self._session, "should_abort", lambda: False)():
                    outcome = OUTCOME_HALTED
                    reason = HALT_ABORTED
                    break
                if getattr(self._session, "is_driver_fenced", lambda: False)():
                    outcome = OUTCOME_HALTED
                    reason = HALT_FENCED
                    break
                reason_idle, _elapsed = _settle.wait_until_settled(
                    self._session,
                    debounce_ms=self._debounce_ms,
                    timeout_s=self._timeout_s,
                )
                if reason_idle != "idle":
                    outcome = OUTCOME_HALTED
                    reason = HALT_SETTLE_FAILED
                    break
                rows = self._session.render()
                full_text = self._session.render_text(rows)
                prompt_line = rows[-1].strip() if rows else ""
                halt = _gate_screen(full_text, prompt_line)
                if halt is not None:
                    outcome = OUTCOME_HALTED
                    reason = halt
                    break
                sector_read = read_current_sector(prompt_line)
                if sector_read.outcome != OUTCOME_READ or sector_read.sector is None:
                    outcome = OUTCOME_HALTED
                    reason = HALT_UNRECOGNIZED_SCREEN
                    break
                current = int(sector_read.sector)
                distinct.add(current)
                _ingest_settled_sector(
                    report.world_id,
                    sector_id=current,
                    full_text=full_text,
                    state_dir=self._state_dir,
                )
                # WO-EXPLORE-AUTOMATION-GATE E1/E3: the distinct-sector cap
                # is MAP-FILL's stopping rule and only map-fill's. A
                # find-StarDock run that stopped here would report
                # `completed` having never found a dock -- a run reporting
                # success for a goal it did not reach. That intent completes
                # on ARRIVAL (`IntentTick.goal_reached`) or halts honestly.
                #
                # E1 exhaustive mode: `min_sectors == 0` means "no sector
                # cap" -- run until the turn budget or the frontier is spent,
                # which is what E1 asks for and what chain detection needs to
                # be fed. A cap of 0 is expressible only deliberately;
                # negatives stay refused.
                if (
                    report.intent == _explore.INTENT_MAP_FILL
                    and report.min_sectors > 0
                    and len(distinct) >= report.min_sectors
                ):
                    outcome = OUTCOME_COMPLETED
                    reason = None
                    break
                if turns <= 0:
                    outcome = OUTCOME_HALTED
                    reason = f"{REASON_EXPLORE_EXHAUSTED}:turn_budget"
                    break
                tick = warp_target_for_intent(
                    report.intent,
                    report.world_id,
                    current_sector=current,
                    turn_budget=turns,
                    state_dir=self._state_dir,
                )
                if tick.goal_reached:
                    # find_stardock ARRIVED. A completed goal is not an
                    # exhausted frontier, and the report must not conflate
                    # them -- see `explore.IntentTick`.
                    outcome = OUTCOME_COMPLETED
                    reason = None
                    break
                target = tick.next_sector
                if target is None:
                    exhaust = tick.reason
                    outcome = OUTCOME_HALTED
                    reason = exhaust if exhaust.startswith("explore_exhausted") else (
                        f"{REASON_EXPLORE_EXHAUSTED}:{exhaust or 'no_hop'}"
                    )
                    break
                graph = known_graph(report.world_id, state_dir=self._state_dir)
                if not _adjacent_warp_allowed(graph, current, target):
                    outcome = OUTCOME_HALTED
                    reason = f"{REASON_EXPLORE_EXHAUSTED}:non_adjacent"
                    break
                _reason, _elapsed, confirmed = _settle.send_and_confirm(
                    self._session,
                    str(target),
                    confirm_prompt=None,
                    enter=True,
                    timeout_s=self._timeout_s,
                    debounce_ms=self._debounce_ms,
                )
                sends += 1
                turns -= 1
                if not confirmed:
                    outcome = OUTCOME_HALTED
                    reason = HALT_CONFIRM_FAILED
                    break
        except Exception as exc:
            outcome = OUTCOME_CRASHED
            reason = REASON_DRIVER_ERROR
            if self._log_error is not None:
                self._log_error(exc)
            finished = replace(
                report,
                outcome=outcome,
                reason=reason,
                distinct_sectors=len(distinct),
                sends_issued=sends,
                turns_remaining=turns,
                stop_requested=stop.is_set(),
                finished_at=_utc_now(),
                error=type(exc).__name__,
            )
            with self._mutex:
                self._report = finished
                self._in_flight = False
            self._control_lock.leave_auto_loop(generation)
            return

        finished = replace(
            report,
            outcome=outcome,
            reason=reason,
            distinct_sectors=len(distinct),
            sends_issued=sends,
            turns_remaining=turns,
            stop_requested=stop.is_set(),
            finished_at=_utc_now(),
        )
        with self._mutex:
            self._report = finished
            self._in_flight = False
        self._control_lock.leave_auto_loop(generation)
