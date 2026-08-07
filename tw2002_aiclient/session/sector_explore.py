"""App-driven sector frontier exploration from ``main_command`` (WO M4).

Pure map-fill / AP-08 adjacent hops only — no invented screen classes and no
combat or trade action. An armed Gather run may answer the exact captured port
commodity quantity prompt with ``0`` (decline); every other money prompt still
halts. Surfaces ``explore_exhausted`` when the planner has no legal hop.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, replace
from typing import Optional, Set

from .. import world_model
from .. import explore as _explore
from ..explore import known_graph, map_fill_warp_target, warp_target_for_intent
from ..halt_reasons import qualify as _qualify
from ..loops.player import (
    HALT_ABORTED,
    HALT_CONFIRM_FAILED,
    HALT_CURRENT_SECTOR_UNREADABLE,
    HALT_FENCED,
    HALT_NEVER_AUTO_ACTION,
    HALT_SETTLE_FAILED,
    HALT_UNRECOGNIZED_SCREEN,
    OUTCOME_HALTED,
)
from .classify import NEVER_AUTO_ACTION_CLASSES, classify_screen, is_avoid_danger_warp
from .control_lock import ControlLock, ControlModeConflict
from . import fighter_toll_policy
from .state_parser import (
    OUTCOME_READ,
    read_current_sector,
    read_port_commodities_from_report,
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
    "DOCK_LETTER_ALLOWLIST",
    "FIGHT_FORBIDDEN_KEYS",
    "FIGHT_LETTER_ALLOWLIST",
    "HALT_FIGHT_CONFIRM_FAILED",
    "HALT_FIGHT_FORBIDDEN_KEY",
    "HALT_FIGHT_NO_KEY",
    "HALT_FIGHT_POLICY_STOP",
    "HALT_DOCK_FORBIDDEN_KEY",
    "HALT_DOCK_MENU_UNRECOGNIZED",
    "HALT_DOCK_POSITION_UNKNOWN",
    "HALT_DOCK_REPORT_UNREADABLE",
    "MOVEMENT_SCREEN_CLASS",
    "explore_run_wire",
    "observe_explore",
    "port_needs_dock",
]

MOVEMENT_SCREEN_CLASS = "main_command"
DEFAULT_MIN_DISTINCT_SECTORS = 5
DEFAULT_TURN_BUDGET = 50

SETTLE_TIMEOUT_S = 8.0
SETTLE_DEBOUNCE_MS = 350
STOP_JOIN_TIMEOUT_S = 5.0

ARGS_EXPLORE_START = frozenset(
    {"world_id", "min_sectors", "turn_budget", "intent", "dock_new_ports", "fight_tolls"}
)

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
    # WO-EXPLORE-DOCK-NEW-PORT: may this run SPEND turns docking first-sight
    # ports? Default off, and on the report for the same reason `intent` is:
    # a run that spent turns docking and one that only read free flybys are
    # not the same run, and "turns_remaining" alone cannot tell them apart.
    #
    # Off by default because this is the only thing the explore loop does that
    # costs a resource. Reading the `Ports :` flyby and ingesting a report
    # already on screen stay unconditional -- both are free. Only the P/T
    # cascade is gated, so an unarmed run still learns everything it can see.
    dock_new_ports: bool = False
    # WO-FIGHTER-TOLL-POLICY-WIRE. Off by default, and for a stronger reason
    # than `dock_new_ports`: this one puts an ATTACK on the wire. `#208` landed
    # hours earlier because a turn-spending arm defaulted on and broke the
    # ordinary run; the same mistake here would auto-fight. Nothing about the
    # Max combat GO (`force_share >= 0.90`) implies it should be ON for a run
    # the operator did not arm for combat.
    fight_tolls: bool = False
    # WO-WIRE-EXPLORE-DECISION-LINES: last planned warp hop for DECISIONS.
    # Updated when a tick chooses a target; null when unknown — never invent.
    next_sector: Optional[int] = None
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


#: Sentinel for ``_publish_progress(next_sector=…)`` — keep last published hop.
_KEEP_NEXT_SECTOR = object()


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
            # Same honesty as fight_tolls / intent: status must prove whether
            # the run was armed to spend turns docking (WO-WIRE-EXPLORE-DECISION-LINES).
            "dock_new_ports": report.dock_new_ports,
            # The single most important fact about a run that can send Attack.
            # Omitted originally, so status could not prove whether a run was
            # armed for combat (hub-banked observability gap, live #209).
            "fight_tolls": report.fight_tolls,
            # Last planned hop (int) or null — DECISIONS next-hop chrome.
            "next_sector": report.next_sector,
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


#: Screen classes that identify StarDock and carry NO sector of their own.
#: Enumerated rather than pattern-matched on a ``stardock_`` prefix: a prefix
#: rule silently adopts any future class someone adds to the classifier, and
#: adopting one wrongly writes a permanent landmark (`landmarks` unions and
#: the product has no removal path). `tests/test_landmark_attribute.py` carries
#: the tripwire that fails if the classifier grows a StarDock class this set
#: has not been taught about -- so the closed side is checked mechanically
#: rather than remembered.
#:
#: `stardock_equipment_listing` is deliberately absent: it is not a classifier
#: class at all (see `classify._BLOCK_TITLE_SPECS`' preceding comment -- its
#: inner blocks are closed but never exclusive).
STARDOCK_SCREEN_CLASSES = frozenset(
    {
        "stardock_cargo_hold_quote",
        "stardock_shipyard_listing",
    }
)


#: WO-EXPLORE-HALT-REASON-CLASS: the halt vocabulary for a screen this loop
#: RECOGNISES but is not taught to drive -- `fighter_encounter`,
#: `sector_display`, and every future class that is neither movement nor a
#: never-auto action.
#:
#: It exists because `unrecognized_screen` was being reported for screens
#: `classify` had named perfectly well. That reading is not merely imprecise,
#: it points the reader at the wrong repair: "unrecognized" invites someone
#: to go write the classifier that already exists. The live fighter cells in
#: `dock-kernel-live-20260729T0407Z` halted `unrecognized_screen` while
#: `classify` was returning `fighter_encounter` for the very same bytes --
#: the same ambiguity that cost the dock WO a full diagnosis cycle when one
#: `dock_screen_unrecognized` string stood for two different failures.
HALT_NOT_DRIVABLE = "halt_not_drivable"

#: WO-FIX-EXPLORE-SHIP-DESTRUCTION-HANG: player ship destroyed mid-explore.
#: Named (not bare halt_not_drivable:ship_destroyed) so `tw explore status`
#: surfaces a reason operators can act on, and so the mid-warp
#: `sector_display` continue cannot swallow the outcome.
HALT_SHIP_DESTROYED = "halt_ship_destroyed"

#: `classify`'s own "I could not name this" sentinel. Named here rather than
#: inlined so the gate and its pins read the SAME literal -- a drifting
#: spelling would silently route genuine unknowns down the named-class branch
#: and re-introduce the lie in the opposite direction.
CLASS_UNKNOWN = "unknown"


#: ``base:klass`` -- the reason carries the class that produced it.
#:
#: One helper for both branches so the separator cannot drift between them,
#: and so a reader parsing live evidence has a single shape to split on.
#:
#: WO-HALT-QUALIFY-CONSOLIDATE: this was an independent three-line twin of
#: `loops.player._qualify` that hardcoded `":"` while the player built its
#: separator from a constant -- they agreed by luck, not by construction, and a
#: change to one would have left the other behind. Both now call the same
#: function. Imported from `halt_reasons` and NOT from `loops.player`: this
#: module has no business depending on the loop player for string formatting,
#: which is precisely the entanglement the old duplication was avoiding.
#:
#: Bound to the local name `_qualify` deliberately -- call sites stay unchanged
#: and the AST comparison guard still sees `_qualify(<CODE>, ...)` when it
#: derives which halt codes can carry a detail.


def _gate_screen(full_text: str, prompt_line: str) -> tuple[Optional[str], str]:
    """``(halt_reason_or_None, klass)``.

    Returns the class alongside the verdict because the halt path needs it:
    a screen that stops the run is also the screen most likely to be worth
    recording something about, and re-classifying at the call site would let
    the two answers drift.

    The reason **carries the class whenever there is one** (WO-EXPLORE-HALT-
    REASON-CLASS). Three outcomes, and the distinction between the last two
    is the whole point:

      * a never-auto class  -> ``never_auto_action:<klass>``
      * any other named class -> ``halt_not_drivable:<klass>``
      * a genuine unknown  -> bare ``unrecognized_screen``

    Only the third is a claim that nothing recognised the screen, and now it
    is the only case that makes it. Halt *behaviour* is unchanged: every
    screen that stopped the run before still stops it, and `main_command`
    still passes.
    """
    klass = classify_screen(full_text, prompt_line)
    if klass == "ship_destroyed":
        return HALT_SHIP_DESTROYED, klass
    if klass in NEVER_AUTO_ACTION_CLASSES:
        return _qualify(HALT_NEVER_AUTO_ACTION, klass), klass
    if klass != MOVEMENT_SCREEN_CLASS:
        # `unknown` is checked by exact identity, not truthiness: a falsy or
        # oddly-typed class must land on the honest-unknown branch rather
        # than be pasted into a reason as `halt_not_drivable:None`.
        if isinstance(klass, str) and klass and klass != CLASS_UNKNOWN:
            return _qualify(HALT_NOT_DRIVABLE, klass), klass
        return HALT_UNRECOGNIZED_SCREEN, klass
    return None, klass


#: The only LETTERS the toll wire may send: the two Max-ratified outcomes.
#: Deliberately not `{"A", "D", "I", "R", "S"}` -- the screen offers more than
#: the policy is allowed to choose, and this set encodes the allowed subset.
FIGHT_LETTER_ALLOWLIST = frozenset({"A", "R"})

#: `P` (Pay) is enumerated as FORBIDDEN rather than merely left out of the set
#: above. Leaving it out is a fact about today's allowlist; naming it is a fact
#: about canon ("never Pay"), and it survives someone widening the allowlist
#: later without reading this comment. Same two-layer discipline as
#: `DOCK_LETTER_ALLOWLIST` -- and, as there, the danger is a one-character bug,
#: because `A` on this screen is an attack and `P` spends the player's money.
FIGHT_FORBIDDEN_KEYS = frozenset({"P"})

HALT_FIGHT_POLICY_STOP = "fight_policy_stop"
HALT_FIGHT_NO_KEY = "fight_no_key"
HALT_FIGHT_FORBIDDEN_KEY = "fight_forbidden_key"
HALT_FIGHT_CONFIRM_FAILED = "fight_confirm_failed"
HALT_FIGHT_NO_PROGRESS = "fight_no_progress"
HALT_FIGHT_CHAIN_LIMIT = "fight_chain_limit"

#: Hard ceiling on encounter interactions per encounter. The legitimate chain
#: is short -- Attack, quantity, done -- so this is generous. It exists because
#: the LIVE failure (hub run 2026-07-29T02:02Z, `gone_rogue` +
#: `microblaster_network`) was an armed run that never terminated: the server
#: stayed on the encounter screen and the loop kept going round. A budget the
#: screen cannot talk us out of is the only reliable stop, because every
#: content-based check depends on reading a screen we have just proven we do
#: not fully understand.
FIGHT_MAX_CHAIN_STEPS = 6


def _fight_key_permitted(key, reason: str) -> bool:
    """Is `key` one this module is allowed to put on the wire?

    An INDEPENDENT second layer, not a restatement of the policy's own logic.
    `fighter_toll_policy` already refuses to return `P`; this exists so that a
    future edit there cannot reach the socket without also editing here.

    Digits are admitted only when the policy's own `reason` says it decided a
    bounded quantity commit. Without that clause the allowlist would have to
    accept "any digit string", which is precisely the shape an unrelated
    quantity screen would present.
    """
    if not isinstance(key, str) or not key:
        return False
    if key.upper() in FIGHT_FORBIDDEN_KEYS:
        return False
    if key.upper() in FIGHT_LETTER_ALLOWLIST:
        return True
    return key.isdigit() and reason.startswith("qty_commit:")


def _handle_encounter(
    session,
    full_text: str,
    prompt_line: str,
    *,
    timeout_s: float,
    debounce_ms: int,
) -> Optional[tuple[Optional[str], int]]:
    """Armed toll handling. ``None`` means "not an encounter frame at all".

    Otherwise ``(halt_reason_or_None, sends_issued)``.

    The refusal ladder is ordered so that every way of NOT having a decided key
    lands on a halt before any send can be constructed:

    * ``detected=False`` -- the policy says this is not its screen. Returns
      ``None`` so the ordinary gate keeps its verdict. This is the
      ``not_encounter`` case, and it must never be read as "proceed".
    * ``halt=True`` -- PvP, unreadable counts, band exceeded. Hard stop.
    * ``key is None`` with ``halt=False`` -- checked SEPARATELY and on purpose.
      `halt=False` is the dataclass default, so a future policy branch that
      forgets to set it would otherwise fall through to a send with no key.
      No key is no send, whatever the halt flag says.
    * a key the allowlist does not admit -- stop, do not "fix" it.

    A send that cannot be positively confirmed halts too: `send_and_confirm`
    returning `confirmed=False` means the screen did not become what we
    expected, and guessing the next keystroke into a live combat screen is the
    exact failure this module exists to prevent.
    """
    decision = fighter_toll_policy.next_encounter_input(full_text, prompt_line)
    if not decision.detected:
        return None
    if decision.halt:
        return HALT_FIGHT_POLICY_STOP, 0
    if decision.key is None:
        return HALT_FIGHT_NO_KEY, 0
    if not _fight_key_permitted(decision.key, decision.reason or ""):
        return HALT_FIGHT_FORBIDDEN_KEY, 0
    _reason, _elapsed, confirmed = _settle.send_and_confirm(
        session,
        decision.key,
        enter=True,
        timeout_s=timeout_s,
        debounce_ms=debounce_ms,
    )
    if not confirmed:
        return HALT_FIGHT_CONFIRM_FAILED, 1
    return None, 1


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


#: The ONLY letters this module may ever send. `"P"` enters the port menu and
#: `"T"` chooses Trade; the captured cascade is
#: `P` -> menu -> `T` -> `<Port>` -> `Docking...` -> commerce report.
#:
#: The set is a frozenset of exactly two letters rather than a comment because
#: of what the OTHER options on that menu are: the port menu's first entry is
#: `<A> Attack this Port`. A one-character construction bug in this module is
#: therefore not a wrong-menu-item bug, it is an unattended attack on a port —
#: the precise thing `/doctrine/alignment-and-conduct.md` forbids and that
#: `fighter_toll_policy` exists to keep behind a Max-ratified gate. The archived
#: `trade_driver` enforced the same two literals at two layers for this reason;
#: this is that discipline ported, not re-invented.
DOCK_LETTER_ALLOWLIST = frozenset({"P", "T"})

# Gather is allowed to decline a captured port quantity prompt, never to answer
# an arbitrary money question.  Keep the exact commodity shape narrower than
# the classifier's intentionally broad `money_prompt` family.
_PORT_QUANTITY_PROMPT_RE = re.compile(
    r"^How\s+many\s+holds\s+of\s+(?:Fuel\s+Ore|Organics|Equipment)"
    r"(?:\s+do\s+you\s+want\s+to\s+(?:buy|sell))?"
    r"\s+\[\s*\d[\d,]*\s*\]\?\s*$",
    re.IGNORECASE,
)
_PORT_QUANTITY_OR_COMMAND_PATTERN = (
    r"(?i:(?:How\s+many\s+holds\s+of\s+(?:Fuel\s+Ore|Organics|Equipment)"
    r"(?:\s+do\s+you\s+want\s+to\s+(?:buy|sell))?"
    r"\s+\[\s*\d[\d,]*\s*\]\?"
    r"|Command\s*\[\s*TL\s*=.*\]\s*.*:\s*))$"
)
_MAX_GATHER_DECLINES = 3


def _active_input_line(session, rows) -> str:
    """Prefer the cursor-owned row; fail closed to the legacy cropped tail.

    A TWGS redraw may leave a stale ``Command`` row painted below the active
    second or third commodity prompt. The cropped tail then names the wrong
    input gate even though the cursor still sits on ``How many holds...``.
    """
    cursor_line = getattr(session, "current_cursor_line", None)
    if callable(cursor_line):
        try:
            line = cursor_line()
        except Exception:  # noqa: BLE001 - unreadable provenance halts below
            return ""
        return line.strip() if isinstance(line, str) else ""
    return rows[-1].strip() if rows else ""


def _gather_match_scope(session) -> str:
    """Use cursor provenance in production; retain old duck-test support."""
    return (
        _settle.MATCH_SCOPE_CURSOR_LINE
        if callable(getattr(session, "current_cursor_line", None))
        else _settle.MATCH_SCOPE_SCREEN
    )


#: Three reasons, one per failure site, replacing the single
#: `dock_screen_unrecognized` this module used to return from both the menu
#: check and the post-`T` ingest. That one string cost a whole diagnosis
#: cycle: #205's live halt was read as "the dock menu dialect is unknown"
#: when the menu had matched all along and the *sector attribution* was what
#: failed. A reason shared by two failures is not a diagnosis, it is a hint.
HALT_DOCK_MENU_UNRECOGNIZED = "dock_menu_unrecognized"
HALT_DOCK_REPORT_UNREADABLE = "dock_report_unreadable"
HALT_DOCK_POSITION_UNKNOWN = "dock_position_unknown"
HALT_DOCK_FORBIDDEN_KEY = "dock_forbidden_key"

#: The port menu that `P` lands on. Matched on its prompt, not on `<A> Attack
#: this Port`, so that recognizing the menu never depends on the attack option
#: being present in the render.
#:
#: Confirmed against captured wire (`logs/session-20260725T202110Z.log`): the
#: real menu is `<A> Attack this Port / <T> Trade at this Port / <Q> Quit,
#: nevermind` over the prompt `Enter your choice [T] ? `. This marker matches
#: it. It also matches other menus that end `Enter your choice: `, which is
#: tolerable only because the letters we may send are allowlisted to `{P, T}`
#: and every screen after them is re-gated.
_PORT_MENU_MARKER = "enter your choice"


def port_needs_dock(flyby, stored_port) -> bool:
    """Is this a first-sight port whose commodities we do not yet hold?

    Turn-spending is the whole cost model here, so the predicate is
    deliberately narrow — it says yes ONLY when all of:

    * the sector-status flyby positively observed a port (``observed=True``
      with a dict). ``observed=False`` means the screen said nothing about a
      port and docking on a guess would spend a turn on nothing;
    * that observation was not ``Ports : None``. A positive "no port here"
      must never produce a dock — there is nothing to dock with, and this is
      the pin the WO calls for by name;
    * the flyby carries a commodity class triple (``([BS]{3})``). Class 0
      Special / StarDock reads as *present but classless* (``port == {}``);
      docking there lands on the equipment buy-menu, not a commerce report,
      and used to halt the whole explore run as ``dock_report_unreadable``
      (WO-FIX-EXPLORE-SKIP-SPECIAL-PORTS / live-drive 2026-08-06);
    * the world model holds no non-empty ``commodities`` for the sector.

    That last clause is what stops a re-dock every hop: once a report has been
    ingested the stored list is non-empty, so the same port is never paid for
    twice within a run or across runs. An EMPTY stored list counts as absent
    rather than as "known to have nothing", because `write_port_only` writes
    ``[]`` for a report it could not read rows from and canon's schema has no
    way to say "this port genuinely trades nothing".
    """
    if flyby is None or not getattr(flyby, "observed", False):
        return False
    port = getattr(flyby, "port", None)
    if not isinstance(port, dict):
        # `observed=True, port=None` -- "Ports : None", positively no port.
        return False
    # Present-but-classless (Class 0 Special / StarDock): nothing to price.
    if not port.get("class"):
        return False
    if isinstance(stored_port, dict) and stored_port.get("commodities"):
        return False
    return True


def _stored_port(world_id: str, sector_id: int, *, state_dir) -> Optional[dict]:
    """The world model's current ``port`` sub-dict for a sector, if any."""
    try:
        record = world_model.get_sector(world_id, int(sector_id), state_dir=state_dir)
    except Exception:
        # A read failure must not be reported as "no commodities stored",
        # which would licence a turn-spending dock. Claim knowledge instead:
        # the caller treats a truthy commodities list as "already have it".
        return {"commodities": [_UNREADABLE_SENTINEL]}
    if not isinstance(record, dict):
        return None
    port = record.get("port")
    return port if isinstance(port, dict) else None


#: Never persisted, never compared against -- it exists only so a failed
#: world-model read is indistinguishable from "already known" at the ONE call
#: site that decides whether to spend a turn. Fail closed toward not spending.
_UNREADABLE_SENTINEL = {"name": "__unreadable__"}


def _ingest_docked_report(
    world_id: str,
    *,
    full_text: str,
    prompt_line: str,
    state_dir,
    sector_id: Optional[int] = None,
) -> Optional[int]:
    """Persist a docked commerce report's commodities. Returns the sector, or
    ``None`` when nothing was written.

    This is `world_model.write_port_only`'s FIRST product caller. That writer
    shipped fully tested with a docstring naming `protocol._write_world_model`
    as its caller and `state_parser.is_genuine_port_report` as its gate;
    neither symbol has ever existed, so the write path it documents was never
    wired and every commodity table the client rendered was dropped.

    A commerce report carries no ``Sector : N`` line, so the sector has to come
    from the prompt — and attributing a port to the wrong sector is
    unrecoverable, because no product path can remove it. Hence: unreadable
    position ⇒ write nothing.

    **Which prompt, though, is the thing this function got wrong.** It used to
    read the sector from ``prompt_line`` unconditionally, documented as "THIS
    screen's own trailing ship Command prompt". Captured wire
    (``logs/session-20260725T202110Z.log``) shows that prompt is only there
    when the port has nothing to trade with you::

        Commerce report for Raven: ...
         Items     Status  Trading % of max OnBoard
        Fuel Ore   Buying    2030    100%       0
        ...
        How many holds of Equipment do you want to buy [40]?   <-- no sector

    When a trade IS possible the screen ends in the trade dialogue instead, so
    ``read_current_sector`` returned ``absent`` and this wrote nothing — the
    live ``dock_screen_unrecognized`` on every armed run. Both captured
    fixtures happened to be the no-trade case, which is why a green suite sat
    on top of a path that could not work.

    So callers who already know where they are pass ``sector_id`` explicitly.
    The free-flyby caller does not pass it and keeps reading the prompt,
    because on that path ``prompt_line`` genuinely IS the ship Command prompt.
    """
    report = read_port_commodities_from_report(full_text)
    if not report.observed:
        return None
    if sector_id is None:
        sector_read = read_current_sector(prompt_line)
        if sector_read.outcome != OUTCOME_READ or sector_read.sector is None:
            return None
        sector_id = int(sector_read.sector)
    sector_id = int(sector_id)
    world_model.write_port_only(
        world_id,
        sector_id,
        {"commodities": [dict(c) for c in report.commodities]},
        state_dir=state_dir,
    )
    return sector_id


def _attribute_landmark(session, world_id: str, klass: str, *, state_dir) -> Optional[int]:
    """Record StarDock in the sector we are in -- iff we still know which one.

    This is the halt path: the run stopped because the screen was not a
    movement screen, and for the StarDock classes that screen is genuinely
    informative. It states *what* is here but never *where* -- all four
    captured StarDock fixtures carry zero sector-bearing lines, while an
    ordinary docked-port screen carries one. So the sector has to come from
    `Session.last_known_sector()`, the memory built for exactly this.

    **`None` means refuse, never "attribute anyway".** The memory returns
    `None` whenever anything has happened since the last positive sector
    read, and that is not a technicality to route around: attributing to a
    stale sector writes StarDock into the WRONG one, `landmarks` unions, and
    no product path can remove it. A skipped write costs one re-read; a wrong
    write is permanent. Returns the sector written, or `None` if nothing was.

    **Landing on StarDock is itself the proof that we did not move.** Reaching
    either class requires sending -- they are menus entered by a command -- and
    every send expires the memory, so a memory-only rule would refuse in every
    real sequence. The way out is not to relax the memory but to notice that a
    warp lands on a **sector display**, while docking lands on a **StarDock
    screen**. The landing screen is an OBSERVATION that discriminates the two,
    where the outgoing command was only an inference. So when the memory is
    silent we fall back to `sector_before_last_send()` -- the raw pre-send
    carry, which is exactly the stale value the memory refuses to hand out, and
    which is safe to read HERE and only here because `klass` has already proved
    no movement occurred.

    Having proved position, we re-`note_sector()` it. That is not a trick to
    keep a stale value alive: landing on StarDock is positive evidence of where
    we are, the same category of evidence a sector display gives. It also makes
    multi-step menu navigation work without a special case -- each further send
    carries the re-established sector forward, and the moment a screen we
    cannot vouch for appears, the chain stops on its own.

    The human keystroke path never carries (`send_raw` files no memo), so
    attribution follows app-driven navigation only.
    """
    if klass not in STARDOCK_SCREEN_CLASSES:
        return None
    probe = getattr(session, "last_known_sector", None)
    if not callable(probe):
        return None
    sector = probe()
    if sector is None:
        carry = getattr(session, "sector_before_last_send", None)
        if callable(carry):
            sector = carry()
    if sector is None:
        return None
    world_model.add_landmark(
        world_id,
        sector,
        world_model.STARDOCK_LANDMARK,
        state_dir=state_dir,
    )
    note = getattr(session, "note_sector", None)
    if callable(note):
        note(sector)
    return sector


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

    def _publish_progress(
        self,
        report: ExploreReport,
        *,
        distinct_sectors: int,
        sends_issued: int,
        turns_remaining: int,
        stop_requested: bool,
        next_sector=_KEEP_NEXT_SECTOR,
    ) -> None:
        """WO-EXPLORE-STATUS-LIVE-COUNTERS: surface mid-run counters.

        ``explore_status`` reads ``self._report``. Updating it only at
        finish left operators with silent zeros while the viewport flew.
        Publish after each observed sector / hop; never overwrite a
        terminal report if the run has already finished.

        ``next_sector`` defaults to keeping the last published hop
        (WO-WIRE-EXPLORE-DECISION-LINES); pass an int or ``None`` to set.
        """
        if next_sector is _KEEP_NEXT_SECTOR:
            with self._mutex:
                cur = self._report
            next_val = cur.next_sector if cur is not None else None
        elif next_sector is None or (
            isinstance(next_sector, int) and not isinstance(next_sector, bool)
        ):
            next_val = next_sector
        else:
            next_val = None
        live = replace(
            report,
            distinct_sectors=int(distinct_sectors),
            sends_issued=int(sends_issued),
            turns_remaining=int(turns_remaining),
            stop_requested=bool(stop_requested),
            next_sector=next_val,
        )
        with self._mutex:
            if not self._in_flight:
                return
            current = self._report
            if current is not None and current.outcome is not None:
                return
            self._report = live

    def _send_dock_letter(self, letter: str) -> tuple[bool, str, str]:
        """Send ONE allowlisted dock letter. ``(confirmed, full_text, prompt)``.

        Layer 1 of the two-layer guard the archived `trade_driver` used, ported
        because the hazard is unchanged: the menu `P` opens leads with
        ``<A> Attack this Port``. Layer 2 is the shape assert below — it catches
        a bad construction from any FUTURE call site, not just a bad letter
        here, which is the failure a single check at the top would miss.
        """
        if letter not in DOCK_LETTER_ALLOWLIST:
            raise ValueError(f"{HALT_DOCK_FORBIDDEN_KEY}:{letter!r}")
        if not (isinstance(letter, str) and len(letter) == 1 and letter.isalpha()):
            raise ValueError(f"{HALT_DOCK_FORBIDDEN_KEY}:malformed")
        # `enter=False`: BOTH dock prompts are hot-key menus that act on the
        # bare keypress. Captured live wire -- `TX (1 bytes) p` returns the
        # 193-byte port menu, `TX (1 bytes) t` returns the 1024-byte `<Port>`
        # dock. So a trailing Enter is not harmless punctuation here, it is an
        # extra keystroke the NEXT prompt consumes:
        #
        #   "P\r"  ->  `P` opens the menu, `\r` accepts its `[T]` default and
        #              DOCKS us, landing on `How many holds ... [50]?`
        #   "T\r"  ->  `T` buffers at that numeric prompt, `\r` commits it,
        #              taking the default: `Agreed, 50 units.` -> `Your offer`
        #
        # That is exactly what the #211 live prove caught: the run bought a
        # quantity of Fuel Ore it was never asked to buy, one Enter short of
        # spending 924 credits. `send_and_confirm` makes `enter` explicit
        # precisely so the caller decides per prompt-shape; taking its default
        # was the bug.
        _reason, _elapsed, confirmed = _settle.send_and_confirm(
            self._session,
            letter,
            confirm_prompt=None,
            enter=False,
            timeout_s=self._timeout_s,
            debounce_ms=self._debounce_ms,
        )
        rows = self._session.render()
        return (
            confirmed,
            self._session.render_text(rows),
            _active_input_line(self._session, rows),
        )

    def _dock_and_ingest(
        self, report: ExploreReport, sector_id: Optional[int]
    ) -> tuple[Optional[str], int, int]:
        """`P` -> port menu -> `T` -> commerce report -> write.

        Returns ``(halt_reason_or_None, sends_issued, turns_spent)``.

        **Every unexpected screen halts the whole run** rather than backing out.
        The WO calls for "no silent wander", and mid-cascade is the worst place
        to improvise: we are inside a menu whose first option attacks the port,
        so a module that guesses its way out is a module that can pick a letter
        on a screen it does not recognize. A halt leaves the human on a real
        screen with the keyboard, which is the escalation canon asks for.

        There is no undock step, by design: the archived cascade records that
        navigating to the next hop's sector IS the undock, so this never sends
        one and the loop's ordinary hop resumes control.

        ``sector_id`` is where the CALLER knows we are, read from the sector
        screen's own Command prompt before any letter is sent. It is a
        parameter rather than something re-derived here because the screens
        this method produces do not carry a sector — see
        :func:`_ingest_docked_report`. ``None`` means the caller could not read
        its own position, and then this sends **nothing**: docking blind would
        spend a turn to learn a commodity table it could not safely attribute,
        and a port written into the wrong sector is unremovable.
        """
        if sector_id is None:
            return HALT_DOCK_POSITION_UNKNOWN, 0, 0
        confirmed, full_text, prompt = self._send_dock_letter("P")
        if not confirmed:
            return HALT_CONFIRM_FAILED, 1, 0
        # Matched against the live PROMPT LINE, never the whole screen.
        #
        # This is the fail-closed half of the #211 overshoot, and on its own it
        # would have stopped the trade. When `P\r` had already docked us, the
        # menu had scrolled up but its text was still ON the screen -- so a
        # `full_text` check happily confirmed "we are at the port menu" while
        # the live prompt underneath read `How many holds ... [50]?`, and the
        # cascade sent its next letter into a money prompt.
        #
        # A whole-screen check cannot tell "this menu is the live prompt" from
        # "this menu is scrollback", and those differ by exactly one turn and
        # one trade. Same idiom the rest of the module already uses: `classify`
        # matches its gate anchors against `prompt_line` only, for this reason.
        if _PORT_MENU_MARKER not in prompt.lower():
            return HALT_DOCK_MENU_UNRECOGNIZED, 1, 0
        confirmed, full_text, prompt = self._send_dock_letter("T")
        # The turn is deducted by the server at `Docking...`, so it is spent
        # from here on regardless of whether the report parses.
        if not confirmed:
            return HALT_CONFIRM_FAILED, 2, 1
        wrote = _ingest_docked_report(
            report.world_id,
            full_text=full_text,
            prompt_line=prompt,
            state_dir=self._state_dir,
            sector_id=sector_id,
        )
        if wrote is None:
            return HALT_DOCK_REPORT_UNREADABLE, 2, 1
        decline_halt, decline_sends = self._decline_gather_quantities(full_text, prompt)
        if decline_halt is not None:
            return decline_halt, 2 + decline_sends, 1
        return None, 2 + decline_sends, 1

    def _decline_gather_quantities(
        self, full_text: str, prompt: str
    ) -> tuple[Optional[str], int]:
        """Decline the bounded port quantity cascade after Gather ingestion.

        The Explore arm authorized commodity discovery, not a transaction.
        Therefore the only money-screen exception is the exact captured
        commodity quantity shape, answered with numeric ``0``.  A bank
        transfer, generic quantity, offer/haggle prompt, or fourth commodity
        remains a halt.
        """
        sends = 0
        while True:
            halt, klass = _gate_screen(full_text, prompt)
            if halt is None:
                return None, sends
            if (
                klass != "money_prompt"
                or _PORT_QUANTITY_PROMPT_RE.fullmatch(prompt) is None
                or sends >= _MAX_GATHER_DECLINES
            ):
                return halt, sends

            _reason, _elapsed, confirmed = _settle.send_and_confirm(
                self._session,
                "0",
                confirm_prompt=_PORT_QUANTITY_OR_COMMAND_PATTERN,
                enter=True,
                timeout_s=self._timeout_s,
                debounce_ms=self._debounce_ms,
                match_scope=_gather_match_scope(self._session),
            )
            sends += 1
            if not confirmed:
                return HALT_CONFIRM_FAILED, sends
            rows = self._session.render()
            full_text = self._session.render_text(rows)
            prompt = _active_input_line(self._session, rows)

    def start(
        self,
        world_id: str,
        *,
        min_sectors: int = DEFAULT_MIN_DISTINCT_SECTORS,
        turn_budget: int = DEFAULT_TURN_BUDGET,
        intent: str = _explore.INTENT_MAP_FILL,
        dock_new_ports: bool = False,
        fight_tolls: bool = False,
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
        # Refused, not coerced. `dock_new_ports="no"` is truthy in Python, and
        # coercing it would arm a turn-spending cascade from a string the
        # caller meant as a refusal.
        if not isinstance(dock_new_ports, bool):
            raise ExploreRefused("invalid_dock_new_ports")
        # Same refusal, higher stakes: a truthy string here would arm combat.
        if not isinstance(fight_tolls, bool):
            raise ExploreRefused("invalid_fight_tolls")

        stop = threading.Event()
        report = ExploreReport(
            world_id=world_id.strip(),
            started_at=_utc_now(),
            min_sectors=int(min_sectors),
            intent=intent,
            dock_new_ports=bool(dock_new_ports),
            fight_tolls=bool(fight_tolls),
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
        # Per-encounter, reset once the loop reaches an ordinary driven screen.
        fight_steps = 0
        last_fight_text: Optional[str] = None
        # WO-WARP-CONFIRM-Y: set True only after an intentional sector hop send.
        pending_intentional_hop = False
        # The sector that hop targeted -- only meaningful while the flag
        # above is True; consumed (and cleared) the moment the confirm
        # resolves either way.
        pending_hop_target: Optional[int] = None
        # REVISE (hub reject of always-Y, live #308 pre-empt): sector ids
        # declined off an avoid-list DANGER prompt THIS run. Never persisted
        # to world-model -- purely a runtime "don't immediately re-pick"
        # note for `warp_target_for_intent`'s `deny` kwarg. Grows for the
        # run's lifetime; no expiry, since a sector avoided once stays
        # avoided for the rest of this explore.
        denied_sectors: Set[int] = set()
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
                halt, klass = _gate_screen(full_text, prompt_line)
                # WO-WARP-CONFIRM-Y (REVISE, hub reject of always-Y): nested
                # like fight-toll — only converts a screen the loop was
                # already halting on, and only for a hop THIS run just sent
                # (no pending hop → fall through to ordinary halt, no blind
                # answer either way). Avoid-list DANGER body → N (decline;
                # deny-list the target so the next tick doesn't re-pick it).
                # Ordinary confirm on an intentional hop → Y, as before.
                if halt is not None and klass == "warp_confirm" and pending_intentional_hop:
                    pending_intentional_hop = False
                    declined_target = pending_hop_target
                    pending_hop_target = None
                    is_avoid = is_avoid_danger_warp(full_text)
                    answer = "N" if is_avoid else "Y"
                    _reason, _elapsed, confirmed = _settle.send_and_confirm(
                        self._session,
                        answer,
                        confirm_prompt=None,
                        enter=False,
                        timeout_s=self._timeout_s,
                        debounce_ms=self._debounce_ms,
                    )
                    sends += 1
                    self._publish_progress(
                        report,
                        distinct_sectors=len(distinct),
                        sends_issued=sends,
                        turns_remaining=turns,
                        stop_requested=stop.is_set(),
                    )
                    if not confirmed:
                        outcome = OUTCOME_HALTED
                        reason = HALT_CONFIRM_FAILED
                        break
                    if is_avoid and declined_target is not None:
                        denied_sectors.add(declined_target)
                    continue
                if halt is not None and klass == "warp_confirm":
                    # Avoid-list confirm without an App-initiated hop: do not
                    # auto-Y (Manual / unexpected). Ordinary halt stands.
                    pending_intentional_hop = False
                    pending_hop_target = None
                # WO-EXPLORE-MIDWARP-WAIT: after an intentional hop, mid-warp
                # progress bars and the arriving Sector body (before the
                # Command prompt) classify as `sector_display`. Settle's
                # debounce can fire between progress-bar frames, so gating
                # that class as halt_not_drivable killed the run on the
                # first hop (live Cartogra 2026-08-01:
                # halt_not_drivable:sector_display after one send). Wait for
                # main_command instead — only while THIS run just hopped.
                if (
                    halt is not None
                    and klass == "sector_display"
                    and pending_intentional_hop
                ):
                    continue
                # WO-FIGHTER-TOLL-POLICY-WIRE. Deliberately nested INSIDE the
                # halt branch. The toll wire can therefore only ever convert a
                # screen the loop was already going to stop on into a decided
                # action -- it can never take a screen away from the ordinary
                # movement path, and it cannot widen what the loop drives.
                #
                # It is also why `fight_tolls=False` is not merely a disabled
                # feature but a structural no-op: with the flag off this block
                # does not execute, so the disarmed loop is byte-for-byte the
                # loop that shipped before this WO.
                #
                # The qty step arrives classified `money_prompt`, which the gate
                # halts on via NEVER_AUTO_ACTION_CLASSES -- so reaching it here
                # is the only way the bounded chain step can be answered without
                # reclassifying the screen (canon DECISIONS.md A.2, and the
                # explicit Accept of this WO).
                if halt is not None and report.fight_tolls:
                    # REVISE (live #209): both guards below are new, and both
                    # are about TERMINATION rather than about combat.
                    #
                    # `fight_no_progress` -- we already acted on a screen with
                    # exactly this text and it did not change. Re-sending is
                    # both useless and unsafe: the key goes onto a live combat
                    # screen again. One repeat is enough to know.
                    #
                    # `fight_chain_limit` -- the backstop that does not read
                    # the screen at all. The live hang happened on a screen we
                    # demonstrably did not model correctly, so a stop condition
                    # that depends on understanding that screen is exactly the
                    # thing not to rely on.
                    if last_fight_text is not None and full_text == last_fight_text:
                        outcome = OUTCOME_HALTED
                        reason = HALT_FIGHT_NO_PROGRESS
                        break
                    if fight_steps >= FIGHT_MAX_CHAIN_STEPS:
                        outcome = OUTCOME_HALTED
                        reason = HALT_FIGHT_CHAIN_LIMIT
                        break
                    fight = _handle_encounter(
                        self._session,
                        full_text,
                        prompt_line,
                        timeout_s=self._timeout_s,
                        debounce_ms=self._debounce_ms,
                    )
                    if fight is not None:
                        fight_halt, fight_sends = fight
                        sends += fight_sends
                        fight_steps += 1
                        last_fight_text = full_text
                        # Publish BEFORE the `continue`. Without this the fight
                        # path skipped every `_publish_progress` call below, so
                        # `explore_status` reported `sends_issued=0` however
                        # many keys had gone out -- which is what made the live
                        # failure read as "sent nothing" instead of "sending
                        # and not clearing", and sent the diagnosis the wrong
                        # way for the first pass.
                        self._publish_progress(
                            report,
                            distinct_sectors=len(distinct),
                            sends_issued=sends,
                            turns_remaining=turns,
                            stop_requested=stop.is_set(),
                        )
                        if fight_halt is not None:
                            _attribute_landmark(
                                self._session,
                                report.world_id,
                                klass,
                                state_dir=self._state_dir,
                            )
                            outcome = OUTCOME_HALTED
                            reason = fight_halt
                            break
                        continue
                if halt is not None:
                    _attribute_landmark(
                        self._session,
                        report.world_id,
                        klass,
                        state_dir=self._state_dir,
                    )
                    outcome = OUTCOME_HALTED
                    reason = halt
                    break
                # Reached a screen the loop drives normally: the encounter (if
                # any) is behind us, so a later one in the same run gets its
                # own full budget rather than inheriting a spent one.
                fight_steps = 0
                last_fight_text = None
                pending_intentional_hop = False
                sector_read = read_current_sector(prompt_line)
                if sector_read.outcome != OUTCOME_READ or sector_read.sector is None:
                    outcome = OUTCOME_HALTED
                    # WO-EXPLORE-HALT-REASON-CLASS twin site. This is NOT an
                    # unrecognized screen and never was: `_gate_screen` has
                    # just passed it as `main_command`, so the screen was
                    # recognised -- what failed is reading a sector NUMBER out
                    # of it. Reporting `unrecognized_screen` here sent a
                    # reader hunting for a missing classifier when the actual
                    # fault is in `read_current_sector`.
                    #
                    # `HALT_CURRENT_SECTOR_UNREADABLE` is not invented for
                    # this: `loops/player.py` already defines it for exactly
                    # this failure and the STOP banner already renders it as
                    # "current sector unreadable".
                    reason = HALT_CURRENT_SECTOR_UNREADABLE
                    break
                current = int(sector_read.sector)
                # WO-LAST-KNOWN-SECTOR: the explore loop is the other place a
                # sector is positively stated, and it reads far more of them
                # than the `status` verb does. Noting here too means the
                # memory is fresh the moment a run stops -- including when it
                # stops BECAUSE the next screen was unrecognized, which is
                # exactly the StarDock case this exists for.
                _note = getattr(self._session, "note_sector", None)
                if callable(_note):
                    _note(current)
                distinct.add(current)
                _ingest_settled_sector(
                    report.world_id,
                    sector_id=current,
                    full_text=full_text,
                    state_dir=self._state_dir,
                )
                # WO-EXPLORE-DOCK-NEW-PORT. Free, and unconditional on the
                # dock trigger: a commerce report classifies as
                # `main_command` (it ends at the ship Command prompt), so it
                # already reaches this point in the loop with its commodity
                # table on screen. Before this call every one of those tables
                # was discarded -- including the report from a dock the HUMAN
                # performed, which costs the app nothing to read. Ingesting
                # here also means the turn-spending cascade below never has to
                # re-derive what is already rendered.
                _ingest_docked_report(
                    report.world_id,
                    full_text=full_text,
                    prompt_line=prompt_line,
                    state_dir=self._state_dir,
                )
                # The only turn-spending branch in this loop. Armed explicitly,
                # and re-checked against the world model AFTER the free ingest
                # above so a report already on screen is never paid for again.
                if report.dock_new_ports and turns > 0 and port_needs_dock(
                    read_port_from_sector_status(full_text),
                    _stored_port(report.world_id, current, state_dir=self._state_dir),
                ):
                    dock_halt, dock_sends, dock_turns = self._dock_and_ingest(report, current)
                    sends += dock_sends
                    turns -= dock_turns
                    self._publish_progress(
                        report,
                        distinct_sectors=len(distinct),
                        sends_issued=sends,
                        turns_remaining=turns,
                        stop_requested=stop.is_set(),
                    )
                    if dock_halt is not None:
                        outcome = OUTCOME_HALTED
                        reason = dock_halt
                        break
                self._publish_progress(
                    report,
                    distinct_sectors=len(distinct),
                    sends_issued=sends,
                    turns_remaining=turns,
                    stop_requested=stop.is_set(),
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
                    deny=frozenset(denied_sectors),
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
                    # Preserve typed route-hazard STOPs (formations → guards);
                    # do not rebadge them as explore_exhausted.
                    if exhaust.startswith("explore_exhausted") or exhaust.startswith(
                        "route_hazard:"
                    ):
                        reason = exhaust
                    else:
                        reason = f"{REASON_EXPLORE_EXHAUSTED}:{exhaust or 'no_hop'}"
                    # Honest clear: no hop chosen this tick.
                    self._publish_progress(
                        report,
                        distinct_sectors=len(distinct),
                        sends_issued=sends,
                        turns_remaining=turns,
                        stop_requested=stop.is_set(),
                        next_sector=None,
                    )
                    break
                graph = known_graph(report.world_id, state_dir=self._state_dir)
                if not _adjacent_warp_allowed(graph, current, target):
                    outcome = OUTCOME_HALTED
                    reason = f"{REASON_EXPLORE_EXHAUSTED}:non_adjacent"
                    break
                # Publish the chosen hop BEFORE the send so explore_status /
                # DECISIONS can show next →N while the warp is in flight.
                self._publish_progress(
                    report,
                    distinct_sectors=len(distinct),
                    sends_issued=sends,
                    turns_remaining=turns,
                    stop_requested=stop.is_set(),
                    next_sector=int(target),
                )
                _reason, _elapsed, _confirmed = _settle.send_and_confirm(
                    self._session,
                    str(target),
                    confirm_prompt=None,
                    enter=True,
                    timeout_s=self._timeout_s,
                    debounce_ms=self._debounce_ms,
                    # Mid-warp progress bars keep emitting bytes between
                    # "quiet" gaps — without retry, an unstable idle during
                    # the animation is confirm_failed even though the hop
                    # completes (live Cartogra 2026-08-01, after
                    # WO-EXPLORE-MIDWARP-WAIT unblocked sector_display).
                    retry_unstable_idle=True,
                )
                sends += 1
                turns -= 1
                # Mark intentional hop after every warp send. Arrival is
                # proven by the next main_command (or warp_confirm) tick —
                # not by a perfect mid-animation idle. A settle timeout /
                # unstable-idle here used to halt confirm_failed while the
                # ship was still warping (live 2026-08-01).
                pending_intentional_hop = True
                pending_hop_target = int(target)
                self._publish_progress(
                    report,
                    distinct_sectors=len(distinct),
                    sends_issued=sends,
                    turns_remaining=turns,
                    stop_requested=stop.is_set(),
                )
                # Deliberately do not halt on ``not confirmed``: the midwarp
                # ``sector_display`` continue (above) + warp_confirm branch
                # finish the hop. Hard aborts still trip ``should_abort`` /
                # settle-failed at the top of the next tick.
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
