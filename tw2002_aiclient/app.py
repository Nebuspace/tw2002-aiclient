"""Curses app entry — launcher ↔ create form ↔ play shell (WO-P1-010…016)."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import replace

import curses

from tw2002_aiclient import adapters
from tw2002_aiclient import daemon_lifecycle
from tw2002_aiclient.cockpit import analyze as _analyze
from tw2002_aiclient.cockpit import assign_trigger as _assign_trigger
from tw2002_aiclient.cockpit import autoloop_controls as _autoloop_controls
from tw2002_aiclient import explore as _explore
from tw2002_aiclient import autonomy_policy as _autonomy_policy
from tw2002_aiclient import trade_chain_plan as _trade_chain_plan
from tw2002_aiclient import stardock_hold_plan as _stardock_hold_plan
from tw2002_aiclient import world_identity as _world_identity
from tw2002_aiclient.cockpit import chains as _chains
from tw2002_aiclient.cockpit import cycle_progress as _cycle_progress
from tw2002_aiclient.cockpit import draft_approve as _draft_approve
from tw2002_aiclient.cockpit import draw as _cockpit_draw
from tw2002_aiclient.cockpit import explore_flags as _explore_flags
from tw2002_aiclient.cockpit import live_refresh as _live_refresh
from tw2002_aiclient.cockpit import record_macro as _record_macro
from tw2002_aiclient.cockpit import reflex_controls as _reflex_controls
from tw2002_aiclient.cockpit import rules_library as _rules_library
from tw2002_aiclient.loops import store as _loop_store
from tw2002_aiclient.rules import store as _rule_store
from tw2002_aiclient.rules import writer as _rules_writer
from tw2002_aiclient.screens import (
    BankViewScreen,
    CreateFormScreen,
    LauncherScreen,
    MODE_KEY,
    PlayShellScreen,
    ProfileRow,
)
from tw2002_aiclient.session import cli as session_cli
from tw2002_aiclient.session import credentials, env, player_bank
from tw2002_aiclient.session.attach_client import AttachInputConn
from tw2002_aiclient.session.autoloop import CYCLES_HARD_CEILING
from tw2002_aiclient.session.trade_chain import (
    DEFAULT_CASH_FLOOR as _TRADE_CASH_FLOOR,
    DEFAULT_TURN_RESERVE as _TRADE_TURN_RESERVE,
)
from tw2002_aiclient.session.stardock_hold import (
    DEFAULT_CASH_FLOOR as _HOLD_CASH_FLOOR,
)
from tw2002_aiclient.watchfeed import WatchFeed

# Presence poll while the launcher sits idle (ms). Timeout getch wakes redraw.
_LAUNCHER_PRESENCE_POLL_MS = 2000

# WO-PLAY-EXPLORE-ARM (L3): the post-ensure explore offer.
#
# The classification the offer is gated on. Named rather than inlined so the
# gate and the pin that guards it read the SAME literal -- a drifting spelling
# would silently stop offering explore, and the failure mode is silence.
_EXPLORE_OFFER_CLASSIFICATION = "main_command"
# What the confirm line describes. `compose_arm_confirm_line` renders this as
# `Explore x5 LIVE?  y/N` -- canon's "the prompt spells out *what* runs and
# *how many cycles*".
_EXPLORE_OFFER_ACTION = "Explore"
# WO-EXPLORE-AUTOMATION-GATE E3: the second armable intent's confirm text.
# States the stopping rule ("until found") because it is NOT the ×N rule the
# map-fill prompt states, and the gate must describe the run it arms.
_EXPLORE_STARDOCK_ACTION = "Explore \u2014 find StarDock (until found)"
# Cycles shown in the prompt AND the `min_sectors` handed to the adapter. ONE
# constant feeds both, so the number the human confirms cannot drift from the
# number the run is started with -- the confirm gate's whole value is that the
# prompt is the truth about what happens next.
_EXPLORE_MIN_SECTORS = 5
# The key that RAISES the confirm gate. Deliberately not auto-raised on
# ensure: a modal gate raised unbidden consumes the operator's next
# keystroke, and measurement showed that keystroke is usually their Ctrl-A
# attach chord (33 pre-existing `_run_play` tests went red on exactly that
# swallow). Same posture the hub ruled for WO-P5-065's prompt-to-attach --
# offer, do not take. `E` is unbound everywhere else in this app; teach
# `A`/`R`/`T` stay reserved for WO-067/068/069.
_EXPLORE_OFFER_KEYS = (ord("e"), ord("E"))
# WO-STARDOCK-HOLD-UPGRADE-ARM: H offers the hold-buy confirm scaffold when
# evidence is complete; never auto-executes.
_HOLD_OFFER_KEYS = (ord("h"), ord("H"))
# `O` asks the pure policy which existing, confirm-gated path is next.
_AUTONOMY_OFFER_KEYS = (ord("o"), ord("O"))


class DeadTerminalError(Exception):
    """The controlling terminal is gone -- see ``_DeadTerminalGuard`` below.

    Raised out of every getch() loop in this module instead of ever
    returning once the terminal is confirmed gone; caught once in
    ``main()``. Propagating as a plain exception (rather than returning a
    sentinel) means it unwinds through ``_run_play``'s own ``finally``
    (control-lock release, ``WatchFeed.stop()``, terminal-mode restore)
    exactly like any other exception, and ``curses.wrapper``'s own
    ``try/finally`` (no ``except`` clause -- it always re-raises) restores
    the terminal before this propagates out of ``main()``.
    """


# WO-TUI-DEAD-TERMINAL-SPIN: `getch()` returning -1 conflates two states --
# "no key yet, my configured timeout elapsed exactly as armed" (the
# legitimate idle tick -- once a second at the play loop's own
# `stdscr.timeout(1000)`, or, per ncurses' own semantics, essentially NEVER
# in the three `timeout(-1)` (blocking) loops below, where a legitimate -1
# has no defined occurrence at all -- ncurses documents -1/ERR in blocking
# mode only as an error/EOF condition) and "the controlling terminal is
# gone -- every subsequent read() now returns EOF instantly, forever". A
# dead pty can't be told apart from an idle one by the return value alone.
# Live incident 2026-07-26: 11 orphaned `curses.wrapper(_run)` processes,
# ~1094% combined CPU, up to 22h45m.
#
# TWO signals, COMBINED so neither can misfire alone (Samantha review,
# 2026-07-26 -- an earlier version treated them as independently
# sufficient; see the combining-rule paragraph below for why that was
# wrong):
#
#   1. A FAST -1: elapsed under `_DEAD_TERMINAL_FAST_S` (10ms). A dead
#      terminal's read() returns EOF in microseconds regardless of the
#      requested timeout. The throttled play loop's own ~1000ms idle tick
#      and `_QueueStdscr`'s (`tests/test_cockpit_attach.py`) deliberate
#      ~50ms poll both clear that floor comfortably and are the genuinely
#      slow, legitimate case this guard must never trip on -- a SLOW -1
#      never counts as evidence of anything, orphaned or not (see below).
#
#      Several OTHER in-tree test doubles instead return -1 with NO delay
#      at all once their scripted key list is exhausted -- plain
#      `self._keys.pop(0) if self._keys else -1`, called back-to-back with
#      no sleep in between: `tests/test_cockpit_attach.py:170`, `tests/
#      test_cockpit_utf8_getch.py:34`, `tests/test_play_esc_daemon_
#      survival.py:105`, `tests/test_spectate_no_send.py:790` (the first
#      sits in the very same file as `_QueueStdscr` above). Those -1s DO
#      clear the fast floor and are indistinguishable, by this guard's own
#      measurement, from a dead terminal. They do not trip
#      `DeadTerminalError` today for a narrower reason than "fast enough to
#      still count as idle": every one of their scripted key lists ends in
#      an exit key (Esc / `q`) that returns control to the caller before
#      the streak reaches `_DEAD_TERMINAL_STREAK` (3). A test double that
#      scripted MORE idle redraws after its last real key than the streak
#      threshold would correctly raise -- an unbroken fast -1 stream is
#      exactly the incident shape, whether it comes from a dead terminal or
#      a test double standing in for one, and that is intended, not a gap.
#      Requiring `_DEAD_TERMINAL_STREAK` (3) consecutive fast returns
#      rather than one is what keeps a single legitimate -1 (the normal
#      idle tick, or one stray interrupted read) from ever tripping this on
#      its own -- required by this WO's own constraint.
#
#   2. `os.getppid() == 1` -- our real parent is gone and init reparented
#      us. This is the literal mechanism of the incident:
#      `start_new_session=True` (tests/pty_helpers.py) gives a pty-spawned
#      child its own session, so when whatever spawned it dies, the child
#      is simply reparented to init rather than signalled -- and the SAME
#      reparenting happens for a plain interactive session when its
#      controlling shell dies from a tty hangup (ssh drop / closed window
#      / killed tmux pane), since the shell was this process's direct
#      parent. macOS has no `PR_SET_PDEATHSIG`; polling this is the
#      portable substitute.
#
# COMBINING RULE: being orphaned lowers the required fast-streak from 3
# down to 1 -- it is NEVER sufficient by itself, and a fast streak is
# NEVER waived by itself either. An earlier version fired on
# `os.getppid() == 1` alone, independent of elapsed time -- reviewed and
# rejected: it would kill a legitimately backgrounded session whose
# terminal is still fully valid the instant its ORIGINAL parent exits
# (e.g. `sh -c './tw &'` from a non-session-leader subshell reparents to
# init immediately, but the terminal itself is untouched) -- that
# session's own perfectly normal ~1s idle tick would be misread as proof
# of a dead terminal. Requiring a FAST -1 even when orphaned closes that
# hole for free: a healthy, still-attached terminal never produces a fast
# -1, orphaned or not. A pure AND (always require the full streak
# regardless of orphan status) was ALSO considered and rejected: it would
# defeat this WO's own literal proof requirement -- closing the pty
# master alone, with the spawning process staying alive throughout (as
# `tests/test_dead_terminal_spin.py`'s own master-fd-close tests do, and
# as this WO's Proof section requires), is not "orphaned", so a pure AND
# would never fire there. The two live-incident signals (100% CPU spin ==
# fast, reparented == orphaned) already coincide by construction, so
# lowering the threshold to 1 when orphaned costs nothing against the
# actual incident while closing the false-positive gap above.
#
# An EARLIER design measured elapsed time as a FRACTION of whatever
# `stdscr.timeout(...)` was armed with, rather than this fixed floor. Two
# reasons it was rejected: it gave no signal at all for the three
# blocking-mode loops (`timeout(-1)` has no finite value to take a fraction
# of), and at the play loop's 1000ms timeout a 5% fraction (50ms) collided
# almost exactly with `_QueueStdscr`'s own legitimate 50ms tick, which is
# real wall-clock (`queue.Queue.get(timeout=0.05)`), not synthetic -- a
# flaky false-positive waiting to happen. An ABSOLUTE floor works
# uniformly across every call site below, independent of which
# `stdscr.timeout()` happens to be armed.
_DEAD_TERMINAL_STREAK = 3
_DEAD_TERMINAL_FAST_S = 0.01


class _DeadTerminalGuard:
    """One instance per getch() loop -- tracks consecutive too-fast -1s.

    See the module-level comment above for the full argument. Call
    :meth:`check` immediately after every `stdscr.getch()` via
    :func:`_guarded_getch`, never directly.
    """

    def __init__(self) -> None:
        self._streak = 0

    def check(self, key: int, elapsed_s: float) -> None:
        if key != -1:
            self._streak = 0
            return
        if elapsed_s >= _DEAD_TERMINAL_FAST_S:
            # A genuinely slow -1 is never evidence on its own, orphaned
            # or not -- see the module comment's "combining rule".
            self._streak = 0
            return
        self._streak += 1
        orphaned = os.getppid() == 1
        required = 1 if orphaned else _DEAD_TERMINAL_STREAK
        if self._streak >= required:
            detail = (
                "reparented to init"
                if orphaned
                else f"{self._streak} consecutive fast returns"
            )
            raise DeadTerminalError(
                f"getch() returned -1 in under "
                f"{_DEAD_TERMINAL_FAST_S * 1000:.0f}ms ({detail}) — "
                "controlling terminal is gone"
            )


def _guarded_getch(stdscr: curses.window, guard: _DeadTerminalGuard) -> int:
    """`stdscr.getch()`, checked for a dead controlling terminal.

    Raises `DeadTerminalError` instead of ever returning once the terminal
    is confirmed gone (see `_DeadTerminalGuard` above) -- every
    `while True: ...; getch(); if key == -1: continue` loop in this module
    calls this instead of `stdscr.getch()` directly, so the one fix lives
    in one place.
    """
    t0 = time.monotonic()
    key = stdscr.getch()
    guard.check(key, time.monotonic() - t0)
    return key


def _utf8_multibyte_len(lead: int) -> int | None:
    """Return expected byte length for a UTF-8 lead, else ``None``.

    Hub-ruled WO-AUDIT-COCKPIT-UTF8-GETCH: leads ``0xC0``–``0xF4`` start a
    multi-byte sequence that must be refused (not forwarded byte-by-byte).
    Bare ``0x80``–``0xBF`` / ``0xF5``–``0xFF`` are *not* multi-byte leads —
    those stay on the single-byte forward path (latin-1 acceptance).
    """
    if 0xC0 <= lead <= 0xDF:
        return 2
    if 0xE0 <= lead <= 0xEF:
        return 3
    if 0xF0 <= lead <= 0xF4:
        return 4
    return None


def _refuse_utf8_getch_sequence(stdscr: curses.window, lead: int) -> str:
    """Consume a multi-byte UTF-8 getch burst; return pure-ASCII status copy.

    Forwards **zero** bytes. Notice names ``U+XXXX`` only — never a glyph
    (secrets/operator doctrine: refuse notice must not echo the character).
    """
    expected = _utf8_multibyte_len(lead)
    assert expected is not None
    seq = bytearray([lead])
    while len(seq) < expected:
        nxt = stdscr.getch()
        if nxt == -1:
            break
        if 0x80 <= nxt <= 0xBF:
            seq.append(nxt)
        else:
            # Incomplete / truncated lead: the next getch already consumed a
            # real keystroke (e.g. ASCII). Push it back so the normal attach
            # key path sees it — never silent-swallow (hub REVISE @ 15:19:39Z).
            unget = getattr(stdscr, "ungetch", None)
            if callable(unget):
                unget(nxt)
            else:
                curses.ungetch(nxt)
            break
    try:
        cp = ord(bytes(seq).decode("utf-8"))
        return f"unencodable keystroke U+{cp:04X} - not sent"
    except UnicodeDecodeError:
        return "unencodable keystroke - not sent"


def _rows_from_disk() -> list[ProfileRow]:
    rows: list[ProfileRow] = []
    for summary in credentials.list_profile_summaries():
        rows.append(
            ProfileRow(
                name=str(summary["name"]),
                handle=str(summary.get("handle") or "?"),
                server=str(summary.get("server") or "?"),
                host=str(summary.get("host") or summary.get("server") or "?"),
                game_letter=str(summary.get("game_letter") or ""),
                autopilot=bool(summary.get("autopilot")),
                error=summary.get("error"),  # type: ignore[arg-type]
            )
        )
    return rows


def _load_profiles() -> list[ProfileRow]:
    """Resolve launcher rows: fixtures override disk for automated Proof.

    Env fixtures (disclose in STATUS):
    - ``TW2002_LAUNCHER_FIXTURE=broken`` — one broken row + healthy CTA
    - ``TW2002_LAUNCHER_FIXTURE=worldid`` — two same host+letter, different handle
    - ``TW2002_LAUNCHER_FIXTURE=polish`` — muted + warn + ok(autopilot) for palette Proof
    - ``TW2002_LAUNCHER_DEMO=1`` — two healthy demo rows
    - default — ``credentials.list_profile_summaries()`` (may be empty)
    """
    fixture = os.environ.get("TW2002_LAUNCHER_FIXTURE", "").strip().lower()
    if fixture == "broken":
        return [
            ProfileRow(
                name="broken-pilot",
                handle="?",
                server="?",
                host="?",
                error="missing game_letter",
            )
        ]
    if fixture == "worldid":
        # Same host + game_letter, distinct handles — proves full world tuple is shown.
        return [
            ProfileRow(
                name="pilot-one",
                handle="PilotOne",
                server="example_one",
                host="example.host",
                game_letter="A",
            ),
            ProfileRow(
                name="pilot-two",
                handle="PilotTwo",
                server="example_one",
                host="example.host",
                game_letter="A",
            ),
        ]
    if fixture == "polish":
        return [
            ProfileRow(
                name="steady",
                handle="Steady",
                server="demo",
                host="demo.example",
                game_letter="A",
            ),
            ProfileRow(
                name="broken-pilot",
                handle="?",
                server="?",
                host="?",
                error="missing game_letter",
            ),
            ProfileRow(
                name="armed-cap",
                handle="Armed",
                server="demo",
                host="demo.example",
                game_letter="B",
                autopilot=True,
            ),
        ]
    if os.environ.get("TW2002_LAUNCHER_DEMO") == "1":
        return [
            ProfileRow(
                name="alpha",
                handle="Alpha",
                server="demo-a",
                host="demo-a.example",
                game_letter="B",
            ),
            ProfileRow(
                name="bravo",
                handle="Bravo",
                server="demo-b",
                host="demo-b.example",
                game_letter="B",
            ),
        ]
    return _rows_from_disk()


def _run_create(stdscr: curses.window) -> str:
    form = CreateFormScreen(stdscr)
    guard = _DeadTerminalGuard()
    while True:
        form.draw()
        key = _guarded_getch(stdscr, guard)
        if key == -1:
            continue
        action = form.handle_key(key)
        if action in ("saved", "cancel"):
            return action


# Ctrl-] (ASCII 29, the classic telnet escape) is canon's own designated
# graceful detach key -- `spectate-and-attach.md §"Attach — the interactive driving surface"` ("The detach key
# is Ctrl-] ... deliberately not q or Ctrl-C, because those are live
# TradeWars menu commands"), mirroring the archive's own `DETACH_KEY`
# precedent (`interactive_app.py`). Wired in `_run_play` below
# (WO-P4-057) -- distinct from Esc, which stays the interim safety exit.
_DETACH_KEY = 29

# Ctrl-A (ASCII 1) is the Mode chord -- ADR-002 (Accepted 2026-07-25,
# `canon/ADR/002-mode-chord-ctrl-a.md`), implemented here per its own
# explicit call-out (WO-P5-061-ENTRY): toggles the seat between App-hold
# and Human in BOTH directions. Deliberately NOT a printable key: while
# attached, bare `M` is TradeWars' own Move command and must reach the
# game untouched -- "no single printable key may ever be Mode" (the ADR's
# own words, since every printable belongs to the game's alphabet).
# Distinct from Ctrl-] just above: Ctrl-] always lands on Spectate,
# Ctrl-A always lands on App-hold. `MODE_KEY` itself is imported from
# `screens.py` (see this module's own top import block) rather than
# redefined here -- ONE keycode, ONE definition, so this attached-branch
# intercept and `PlayShellScreen.handle_key`'s own Ctrl-A check can never
# silently drift onto different keycodes (Samantha review, WO-P5-061-
# ENTRY follow-up).

# Poll timeout for the GOALS status_provider (Mack finding, HIGH): must stay
# well under the 1 Hz refresh cadence (app.py's own stdscr.timeout(1000)) so
# a bound-but-not-accepting daemon socket can never wedge the whole play
# loop -- Esc included -- behind send_request's much longer 15.0s transport
# default, repeating every tick. An async poll (decoupling the daemon round
# trip from the redraw tick entirely) is a banked follow-on; this bound is
# the minimal fix that keeps the operator in control today.
_STATUS_POLL_TIMEOUT_S = 1.0


def _daemon_status_provider(run_dir):
    """Build the play shell's GOALS ``status_provider`` (PWO-034): a no-arg
    closure that polls the daemon's ``status`` verb and returns its dict, or
    ``None`` on any non-``ok`` response.

    Bounded and never-raising by construction -- ``session_cli.send_request``
    itself never raises for an expected transport failure (its own
    docstring: "always returns a dict") and early-returns
    ``daemon_not_running`` without ever opening a socket when
    ``run/twd.sock`` doesn't exist, so a play shell with no daemon attached
    polls this once a second at zero cost. When a socket DOES exist but
    nothing is accepting on it, the explicit ``_STATUS_POLL_TIMEOUT_S``
    bound (rather than the transport's own much longer default) is what
    keeps this poll -- and the play loop's own redraw/Esc handling around
    it -- from freezing for multiple seconds per tick. Isolation for
    automated Proof is the test's own responsibility (monkeypatch
    ``session_cli.send_request`` before driving the app, mirroring how
    every existing pty test stubs ``adapters.ensure_session`` rather than
    this module branching on a test env var).
    """

    def _poll() -> dict | None:
        resp = session_cli.send_request(
            "status", {}, timeout=_STATUS_POLL_TIMEOUT_S, run_dir=run_dir
        )
        return resp if isinstance(resp, dict) and resp.get("ok") else None

    return _poll


def _preview_relaunch_sends(run_dir) -> object:
    """Read-only preview of ``sends_issued``, taken BEFORE the relaunch
    confirm gate is raised (WO-AUTOLOOP-RELAUNCH-COCKPIT).

    The gate's label must disclose the money-path truth ahead of the
    keystroke that fires it, but that truth (``sends_already_issued``) is
    only handed back on the WIRE by `adapters.autoloop_relaunch` itself --
    and that call is the mutating one the gate exists to guard. Calling it
    just to preview its own answer would defeat the gate.

    Reads the identical underlying field instead via
    ``adapters.autoloop_status`` (not a raw ``session_cli.send_request`` --
    ``app.py`` may only request the adjudicated ``status`` verb directly;
    every other daemon verb goes through adapters). The daemon's
    ``_dispatch_autoloop_relaunch`` captures ``sends_already_issued`` from
    ``snapshot.report.sends_issued`` before re-arming, and
    ``_dispatch_autoloop_status`` echoes that same ``report.sends_issued``
    back as ``run.sends_issued``, so this is a genuine preview of the same
    daemon state, not an invented value. No new protocol surface.

    Returns the raw ``sends_issued`` value (an ``int`` or ``None``) on any
    ``ok`` response with a real run, or ``None`` -- honest unknown, never a
    guessed zero -- for a non-``ok`` response or no runner."""
    result = adapters.autoloop_status(run_dir=run_dir)
    if not result.ok or not isinstance(result.raw, dict):
        return None
    run = result.raw.get("run")
    if not isinstance(run, dict):
        return None
    return run.get("sends_issued")


def _attempt_attach(sock_path):
    """Take the Human control lock for THIS cockpit instance -- PWO-056
    (WO-P4-056). Canon `mode-line-and-teach-controls.md`'s App<->Human
    control-switch key is **Ctrl-A** (ADR-002, Accepted 2026-07-25,
    superseding an earlier `M` draft) so bare `M` stays free for
    TradeWars' own Move command while attached -- no single printable key
    may ever double as Mode. This cockpit's own standing state is
    Spectate, not App; this wires
    the spectate->Human leg only: ``control_lock.take_human()`` via
    the daemon's existing ``attach`` verb (``session/daemon.py::
    _handle_attach``), never a new lock-taking mechanism of our own.

    ALLOWLISTED SEND-CAPABLE SITE (adjudicated against ``tests/
    test_spectate_no_send.py``'s banned-symbol scanner -- see that file's
    own ``_is_allowlisted_attach_site``, mirroring WO-P4-050's
    ``_is_allowlisted_watchfeed_stop`` precedent in ``tests/
    test_play_esc_daemon_survival.py``): this is the ONE place
    ``AttachInputConn`` is ever constructed reachable from the product
    cockpit -- called only from ``_run_play`` below, only in reaction to
    the human's own Ctrl-A keypress, from either Spectate or App-hold
    (``PlayShellScreen.handle_key``'s ``"attach"`` return value), never
    automatic and never reachable from a cockpit's own read-only entry
    state -- which is App-hold, not Spectate, as of WO-ENTRY-APP-CHIP
    (this docstring previously called it "the read-only spectate
    default"; only the NAME of that state changed -- it is still equally
    read-only, and this call site is still equally unreachable from it
    without a human keypress).

    Returns ``(conn, None)`` on success -- the daemon's ``control_lock.
    mode`` is now ``MODE_HUMAN`` -- or ``(None, error)`` on ANY refusal or
    failure. ``AttachInputConn.connect()`` already surfaces both a
    daemon-side ``ControlModeConflict`` (e.g. ``"already_attached"`` --
    ``take_human()``'s only conflict code; a ``controller_busy``-shaped
    refusal is ``acquire_driver()``'s own vocabulary, a different lock
    operation this verb never calls) AND a plain transport failure (e.g.
    daemon not running -- ``"daemon_not_running"``/an ``OSError`` message)
    through the identical ``.error`` string, so this wrapper does not
    need to distinguish them further: "handled honestly" here means the
    caller always learns WHY a refusal happened, never silently treats it
    as success.
    """
    conn = AttachInputConn(sock_path)
    if conn.connect():
        return conn, None
    error = conn.error or "attach_rejected"
    conn.close()
    return None, error


def _explore_status_line_from_wire(
    raw: dict | None, *, default_min_sectors: int
) -> tuple[str | None, bool]:
    """Map an ``explore_status`` wire dict to a Play status_line.

    Returns ``(line, keep_polling)``. ``keep_polling`` is False once the run
    reaches a terminal outcome or the explorer is no longer running.
    """
    if raw is None:
        return None, False
    running = bool(raw.get("running"))
    run = raw.get("run")
    if not isinstance(run, dict):
        if running:
            return f"explore 0/{default_min_sectors}…", True
        return None, False
    distinct = run.get("distinct_sectors")
    if not isinstance(distinct, int):
        distinct = 0
    min_sectors = run.get("min_sectors")
    if not isinstance(min_sectors, int):
        min_sectors = default_min_sectors
    outcome = run.get("outcome")
    reason = run.get("reason") or run.get("error") or "unknown"
    if outcome == "completed":
        return f"explore completed ({distinct})", False
    if outcome in ("halted", "crashed"):
        return f"explore halted: {reason}", False
    if running or outcome is None:
        return f"explore {distinct}/{min_sectors}…", True
    return f"explore halted: {outcome}", False


def _poll_explore_status(play: PlayShellScreen, *, run_dir) -> bool:
    """Poll ``adapters.explore_status``; refresh the visible band and
    ``status_line``.

    Returns whether the Play loop should keep polling on idle ticks.

    WO-PLAY-OFFER-VISIBLE-ON-LIVE: the same text goes to `explore_band` as
    to `status_line`. `status_line` alone is not enough -- it renders only
    when the LOGS band has no daemon tail, which on a live session is never
    (live prove 2026-07-27). The band is the surface an operator actually
    sees mid-session; `status_line` is kept for the empty-LOGS case and for
    the existing L4 tests that assert on it.

    WO-WIRE-EXPLORE-DECISION-LINES: also refresh ``explore_decision_lines``
    for the DECISIONS pane (status overlay). Cleared on stand-down / error.
    """
    try:
        result = adapters.explore_status(run_dir=run_dir)
    except Exception:  # noqa: BLE001 — honest containment; do not drop the loop
        play.explore_decision_lines = None
        return False
    if not result.ok:
        reason = result.reason or "unknown"
        play.status_line = f"explore status unavailable — {reason}"
        # Stop claiming the band on a reading we do not have -- a stale
        # "explore 3/5…" frozen on screen would be a live-looking run that
        # is not being observed.
        play.explore_band = None
        play.explore_decision_lines = None
        return False
    line, keep_polling = _explore_status_line_from_wire(
        result.raw, default_min_sectors=_EXPLORE_MIN_SECTORS
    )
    if line is not None:
        play.status_line = line
        play.explore_band = line
    if keep_polling:
        run = result.raw.get("run") if isinstance(result.raw, dict) else None
        play.explore_decision_lines = _explore.explore_decision_lines_from_run(run)
    else:
        # Terminal outcome: leave the final reading on `status_line` and hand
        # the band back to the calm teach tokens. Clear DECISIONS overlay.
        play.explore_band = None
        play.explore_decision_lines = None
        # WO-WORLD-STATS-REFRESH-EVENTS A: explore terminal poll is a real
        # client-visible completion signal (already paid for explore_status).
        # Refresh known_sectors here — never on the draw path.
        try:
            from tw2002_aiclient import world_identity as _world_identity

            status = None
            provider = getattr(play, "status_provider", None)
            if callable(provider):
                try:
                    status = provider()
                except Exception:  # noqa: BLE001
                    status = None
            play.world_stats.refresh(
                _world_identity.world_id_from_profile(play.profile),
                status=status,
            )
        except Exception:  # noqa: BLE001 — count is best-effort; keep the loop
            pass
    return keep_polling


def _apply_autoloop_cycle_band(play: PlayShellScreen, raw: object) -> bool:
    """Set or clear ``explore_band`` from an ``autoloop_status`` wire body.

    Returns whether the run is still live (keep polling). Display-only
    (WO-AUTOLOOP-CYCLE-PROGRESS): unknown progress omits the band rather
    than inventing counts. Stand-down / finished clears the band so calm
    teach tokens return.
    """
    if not isinstance(raw, dict):
        play.explore_band = None
        return False
    if raw.get("stand_down") or not raw.get("running"):
        play.explore_band = None
        return False
    run = raw.get("run")
    if not isinstance(run, dict):
        play.explore_band = None
        return True  # running but no report yet — keep polling, omit chrome
    line = _cycle_progress.compose_cycle_progress(
        run.get("loop"),
        run.get("cycle"),
        run.get("cycles"),
        unicode_ok=_cockpit_draw.unicode_ok(),
    )
    play.explore_band = line  # None when unknown — calm hints, not a guess
    return True


def _poll_autoloop_status(play: PlayShellScreen, *, run_dir) -> bool:
    """Poll ``adapters.autoloop_status`` for cycle-progress chrome.

    Returns whether idle ticks should keep polling. Never raises into the
    play loop. Explore owns the same band when its poll is active — this
    path is only reached when explore is idle.
    """
    try:
        result = adapters.autoloop_status(run_dir=run_dir)
    except Exception:  # noqa: BLE001 — honest containment
        play.explore_band = None
        return False
    if not result.ok:
        play.explore_band = None
        return False
    return _apply_autoloop_cycle_band(play, result.raw)


def _apply_trade_chain_band(play: PlayShellScreen, raw: object) -> bool:
    if not isinstance(raw, dict):
        play.explore_band = None
        return False
    run = raw.get("run")
    if not isinstance(run, dict):
        play.explore_band = None
        return bool(raw.get("running"))
    route = run.get("route") if isinstance(run.get("route"), str) else "?"
    if raw.get("running"):
        done = run.get("hops_completed")
        total = run.get("hops_total")
        progress = (
            f"{done}/{total}" if isinstance(done, int) and isinstance(total, int)
            else f"?/{total}" if isinstance(total, int)
            else "?"
        )
        play.explore_band = f"trade {route} · hop {progress}"
        return True
    play.explore_band = None
    outcome = run.get("outcome")
    reason = run.get("reason") or "unknown"
    if outcome == "completed":
        play.status_line = f"trade completed — {route}"
    elif outcome is not None:
        play.status_line = f"trade stopped — {reason}"
    return False


def _poll_trade_chain_status(play: PlayShellScreen, *, run_dir) -> bool:
    try:
        result = adapters.trade_chain_status(run_dir=run_dir)
    except Exception:  # noqa: BLE001
        play.explore_band = None
        return False
    if not result.ok:
        play.status_line = f"trade status unavailable — {result.reason or 'unknown'}"
        play.explore_band = None
        return False
    return _apply_trade_chain_band(play, result.raw)


def _run_play(stdscr: curses.window, profile: ProfileRow) -> str:
    """Bind profile to a fresh play-shell placeholder; Esc ends the binding."""
    run_dir = env.resolve_run_dir()
    play = PlayShellScreen(stdscr, profile)
    # Producer for `status["chain_hops"]`/`["chain_unit"]` -- the fields
    # cockpit/goals.py reads and, until now, nothing wrote. Updated from the
    # chains-popup branch below, where a discovery already happens for its own
    # reasons. Applied as a WRAPPER rather than an argument to
    # `_daemon_status_provider`: the scalars are a client-side overlay on
    # whatever the status source is, not part of polling the daemon, so every
    # provider (including the scripted ones tests substitute) carries them.
    # Both overlays compose by wrapping: each adds only its own keys, each
    # declines to clobber a value the layer beneath already supplied, and each
    # maps a `None` provider to `None`, so the order is not load-bearing.
    # FOCUS wraps outermost so it sees chain + world scalars already merged.
    play.status_provider = play.focus_scalars.wrap(
        play.world_stats.wrap(
            play.chain_scalars.wrap(_daemon_status_provider(run_dir))
        )
    )
    play.status_line = "Ensuring session…"
    play.draw()  # show the ensuring state during the (blocking) wait below
    # no_auto_arm=True: ensure only reaches main_command and stops, even if
    # the profile itself enables autopilot -- no surprise auto-arm here.
    result = adapters.ensure_session(profile.name, no_auto_arm=True)
    if result.ok:
        # WO-P5-068: record the confirmed classification so T Assign-Trigger
        # can stamp it on the stub's ``when.screen`` field.  Only set on
        # a successful ensure (an ok=False result has no confirmed screen
        # class -- leaving current_classification as None lets create_stub's
        # own degradation path produce "" rather than a wrong class name).
        play.current_classification = result.classification
        play.status_line = f"session ready — {result.classification}"
        # WO-PLAY-EXPLORE-ARM (L3): the FIRST production caller of the
        # confirm-to-arm gate. Until now `begin_arm_confirm` had zero
        # production call sites by design (WO-P5-063 shipped the gate with a
        # pin asserting exactly that, so this moment would have to be
        # deliberate rather than accidental). This is that moment; the pin is
        # updated in the same change to assert THIS path, not deleted.
        #
        # Gated on the literal ready classification, not on `result.ok`
        # alone. `ok` can be true for a session that settled somewhere other
        # than the command prompt, and offering to explore from a screen the
        # daemon has not confirmed is the command prompt would arm a
        # strategic behaviour against an unknown position.
        #
        # Raising the gate arms NOTHING -- it draws the y/N line and routes
        # the next keystroke through `armconfirm.resolve_arm_confirm_key`,
        # which is default-deny. `no_auto_arm=True` above is untouched:
        # explore is a separate, human-confirmed action, not a silent
        # re-arm of Autopilot.
        explore_offered = result.classification == _EXPLORE_OFFER_CLASSIFICATION
        if explore_offered:
            # WO-EXPLORE-GATHER-VISIBLE: composed in `cockpit/explore_flags.py`
            # rather than inline here, so the operator's FIRST contact with the
            # feature is assertable without a curses harness. The line is
            # additive against the pre-WO one -- `press E` is unchanged; `D`
            # is named because it was reachable on every surface and
            # advertised on none.
            play.status_line = _explore_flags.compose_explore_offer(
                result.classification, cycles=_EXPLORE_MIN_SECTORS
            )
    else:
        explore_offered = False
        play.status_line = f"ensure failed — {result.reason}: {result.detail}"
    # ~1 Hz GOALS refresh (PWO-034): a bounded getch() timeout wakes the loop
    # even with no keypress, so the next draw() picks up a fresh
    # status_provider() snapshot. -1 (the timeout tick) is deliberately never
    # routed into handle_key -- it isn't a real key, just a redraw prompt.
    stdscr.timeout(1000)
    # WO-P4-050: the watch-stream client's lifecycle is scoped to this one
    # play-shell binding -- started right before the loop, stopped in the
    # `finally` below on every exit path (Esc/back, quit, or an exception
    # unwinding out of the loop). WO-P4-052 wires its `snapshot` as the GAME
    # viewport's `viewport_provider` (below) -- the existing 1 Hz
    # `getch`/`draw` loop below remains the SOLE redraw owner; the feed's
    # own background reader thread never wakes the UI on its own.
    feed = WatchFeed(run_dir=run_dir)
    feed.start()
    play.viewport_provider = feed.snapshot
    # PWO-056 (WO-P4-056): the attach connection, once the human's Ctrl-A
    # keypress takes the Human control lock (`_attempt_attach` above; the
    # chord moved from `M` to Ctrl-A per WO-P5-061-ENTRY, see `MODE_KEY`
    # imported above from `screens.py`, its single source of truth).
    # `None` here means spectating -- the loop below still routes every
    # key through `play.handle_key`, exactly as before this WO.
    attach_conn = None
    # WO-AUTOLOOP-RELAUNCH-COCKPIT: which pending gate a subsequent
    # "arm_confirm" belongs to. `PlayShellScreen._arm_confirm` is a single
    # slot shared by every affordance that raises it (explore, and now
    # relaunch) -- `handle_key` clears it and returns the SAME generic
    # "arm_confirm" string on `y` regardless of who raised it, so this loop
    # must remember which one it is on its own. Set right before each
    # `begin_arm_confirm` call below; cleared the instant "arm_confirm"
    # fires.
    pending_confirm_action: str | None = None
    # WO-EXPLORE-AUTOMATION-GATE E3: the intent the most recently raised `E`
    # offer was composed from, or `None` before the first press. ONE variable,
    # not two: the cycle position and "what the live prompt says" are the same
    # fact here, because `E` advances the cycle and raises the gate in the
    # same step. An earlier draft kept a separate "next" variable and a
    # comment explaining how they could differ; they could not, and mutating
    # the confirm branch to read the other one left every test green -- which
    # is how the redundancy was found. The confirm branch reads THIS, so the
    # run is always the one the visible prompt named.
    explore_intent_offered: str | None = None
    # WO-PLAY-EXPLORE-FLAGS / WO-PLAY-EXPLORE-GATHER-DEFAULT-ON: dock gather
    # defaults ON in Play (Max GO 2026-07-30); fight-tolls stays default OFF.
    # CLI/daemon library defaults remain OFF — this is the Play surface only.
    #
    # Held as real `bool` and handed to the adapter untouched -- see
    # `cockpit/explore_flags.py` on why `fight_tolls` must never be wrapped
    # in `bool(...)` anywhere on this path.
    #
    # Loop-local rather than screen state, deliberately: these feed the
    # confirm line and the adapter call, both of which live in this loop,
    # and a flag that outlived the loop would be an opt-in the operator
    # cannot see when they next arm.
    explore_dock_opt_in = True
    explore_tolls_opt_in = False
    # WO-PLAY-AUTOLOOP-START: the exact row the taught-loop confirm line was
    # composed from. Held alongside `pending_confirm_action` rather than
    # re-read at `y`, so the macro that runs is provably the macro named in
    # the prompt the operator agreed to.
    #
    # Cancelling a gate leaves `pending_confirm_action` stale (the screen
    # clears its own gate and returns None, so this loop never sees the
    # cancel). That is currently harmless only because EVERY
    # `begin_arm_confirm` call site also assigns `pending_confirm_action` --
    # an invariant nothing enforces. So the arm branch additionally requires
    # this to be non-None and clears it on every other gate raise: if that
    # invariant ever breaks, the failure is a refusal to arm rather than
    # arming yesterday's macro under someone else's prompt.
    pending_confirm_loop: dict | None = None
    pending_confirm_trade: _trade_chain_plan.TradeChainPlan | None = None
    # WO-STARDOCK-HOLD-UPGRADE-ARM: exact hold-buy scaffold held for confirm.
    pending_confirm_hold: _stardock_hold_plan.StardockHoldPlan | None = None
    # WO-PLAY-REFLEX-ARM: the exact identity (`rule_id`, `macro`, `classification`)
    # shown at preview. Held alongside `pending_confirm_action` so `y` launches
    # the claim the human saw — never a re-read of the library between prompt
    # and confirm. Cleared on every other gate raise and on the reflex arm
    # branch itself.
    pending_confirm_reflex: dict | None = None
    # WO-PLAY-EXPLORE-VISIBLE (L4): set after a successful arm start; cleared
    # when ``explore_status`` reports a terminal outcome so idle ticks do not
    # spam the daemon.
    explore_poll_active = False
    # WO-AUTOLOOP-CYCLE-PROGRESS: poll autoloop_status on idle ticks while a
    # taught run is live so the hint band can show cycle chrome. Cleared when
    # the run stands down. Explore owns the same band when its poll is active.
    autoloop_poll_active = False
    trade_poll_active = False
    # WO-CHAINS-LIVE-REFRESH: the always-on GOALS/HUD readouts used to update
    # only when the `L` modal was opened, so a whole explore run showed empty
    # chain and sector rows. Per session, so a world that outgrew the chain
    # budget last time is not held against a different profile this time.
    live = _live_refresh.LiveRefresh()
    guard = _DeadTerminalGuard()
    try:
        while True:
            play.draw()
            key = _guarded_getch(stdscr, guard)
            if key == -1:
                if explore_poll_active:
                    explore_poll_active = _poll_explore_status(play, run_dir=run_dir)
                elif trade_poll_active:
                    trade_poll_active = _poll_trade_chain_status(play, run_dir=run_dir)
                elif autoloop_poll_active:
                    autoloop_poll_active = _poll_autoloop_status(play, run_dir=run_dir)
                # The idle tick, NOT the draw path: `play.draw()` runs every
                # loop iteration, while this branch is only reached when
                # `getch` times out (~1 Hz). `LiveRefresh` throttles on top of
                # that and never raises, so a slow or broken world model
                # cannot cost the operator the loop. The PROFILE is handed
                # over unresolved on purpose -- `world_id_from_profile` raises
                # on an unusable host, and that raise belongs inside the
                # module that promises not to raise.
                live.tick(play, profile)
                continue
            if attach_conn is not None and key != 27:
                # Attached: canon mode-line-and-teach-controls.md §"`Ctrl-A` — the App↔Human Mode switch"
                # -- "the human always wins the keyboard" the instant
                # they're attached -- so every key except Esc, Ctrl-] (the
                # detach key), and Ctrl-A (the Mode chord, both handled
                # first below) is a live game keystroke, forwarded raw
                # over the attach connection, never intercepted as a
                # cockpit shortcut. `q`/`Q` -- and, as of WO-P5-061-ENTRY,
                # plain `M` (TradeWars' own Move command) -- are ordinary
                # printable game keystrokes once attached, NOT reserved
                # shortcuts -- reserving them would silently take the
                # keyboard away from the human the moment they typed an
                # otherwise ordinary letter (Samantha REVISE, WO-P4-056;
                # regression pinned by tests/test_cockpit_attach.py::
                # test_run_play_forwards_q_shift_q_and_bare_m_while_attached_
                # esc_and_ctrl_a_reserved).
                #
                # Esc alone stays reserved as the interim safety exit,
                # unchanged by this WO: closing `attach_conn` in the
                # `finally` below releases the human lock daemon-side the
                # same way a crashed `tw attach` already does
                # (`daemon.py::_handle_attach`'s own `finally:
                # lock.release_human()`). Esc is NOT the detach key --
                # canon `spectate-and-attach.md §"Attach — the interactive driving surface"` names Ctrl-]
                # (`_DETACH_KEY` above) as the real graceful-detach
                # affordance (the archive's own `DETACH_KEY`,
                # `interactive_app.py`), wired next (WO-P4-057).
                if key == MODE_KEY:
                    # Ctrl-A: hand the seat to App-hold -- deliberately
                    # DIFFERENT from Ctrl-]'s Spectate target just below
                    # (WO-P5-061-ENTRY, project owner ruling). Closing the
                    # write connection releases the daemon's Human control
                    # lock via the exact same crash-safe path Ctrl-]/Esc
                    # already rely on (`daemon.py::_handle_attach`'s own
                    # `finally: lock.release_human()`, which always lands
                    # on MODE_APP -- `control_lock.py::release_human`'s
                    # own docstring: "Idempotent -- always returns to
                    # MODE_APP") -- never a new wire verb of our own.
                    attach_conn.close()
                    attach_conn = None
                    play.spectating = False
                    play.attached = False  # App-hold: neither Spectate nor Human
                    play.status_line = "released to App — autopilot has the seat (Ctrl-A returns to Human)"
                    continue
                if key == _DETACH_KEY:
                    # Graceful detach: hand the keyboard back to
                    # Spectate deliberately, distinct from Esc's
                    # whole-binding exit above. Closing the write
                    # connection is what releases the daemon's Human
                    # control lock -- the SAME crash-safe path a
                    # dropped/killed attach already takes
                    # (`daemon.py::_handle_attach`'s own `finally:
                    # lock.release_human()`, canon
                    # `spectate-and-attach.md §"Attach — the interactive driving surface"`) -- never a new
                    # wire verb of our own; detach is a close, never a
                    # send.
                    attach_conn.close()
                    attach_conn = None
                    play.spectating = True
                    play.attached = False  # WO-P5-060 lane B: honest badge truth, alongside spectating
                    play.status_line = "detached — spectating"
                    continue
                # WO-P5-067 Accept #2: _recorded_key is set only on branches
                # that actually send a byte to the game.  Refused/dropped
                # paths (UTF-8 multi-byte lead, arrow/function keys) leave it
                # None so those pseudo-keystrokes are never captured.
                _recorded_key = None
                if key in (curses.KEY_ENTER, 10, 13):
                    sent_ok = attach_conn.send_key(b"\r\n")
                    _recorded_key = "\r\n"
                elif key in (curses.KEY_BACKSPACE, 127, 8):
                    # Backspace forwarding is MANDATORY (hub ruling,
                    # WO-P4-056 REVISE) -- a human who cannot correct a
                    # typo while holding the keyboard is materially
                    # impaired. Which raw form `getch()` yields for the
                    # physical Backspace key is terminal/terminfo
                    # dependent (curses.KEY_BACKSPACE=263 if `kbs` is
                    # translated, raw DEL 0x7F or raw BS 0x08 otherwise)
                    # -- never assumed, all three are handled and
                    # canonicalized to the ONE byte the archive's own
                    # curses-attach precedent already established as
                    # correct for this game
                    # (`archive/pre-rebirth-2026-07-23/code/twclient/
                    # interactive_app.py::_encode_key`, `if ch in
                    # (curses.KEY_BACKSPACE, 127, 8): return b"\x08"`) --
                    # ported verbatim rather than re-derived.
                    sent_ok = attach_conn.send_key(b"\x08")
                    _recorded_key = "\x08"
                elif 0 <= key < 256:
                    # WO-AUDIT-COCKPIT-UTF8-GETCH (hub-ruled): curses getch()
                    # yields each UTF-8 byte as its own 0..255 int. Forwarding
                    # every byte of a multi-byte keypress as N separate game
                    # events is the F9 defect. Refuse the lead + consume
                    # continuations; tell on status_line; keep the session.
                    # Bare single-byte 0x80-0xFF (no multi-byte lead) still
                    # forwards — deliberate divergence from a naive
                    # "latin-1 encode the whole keypress" mirror of cli.py.
                    if _utf8_multibyte_len(key) is not None:
                        play.status_line = _refuse_utf8_getch_sequence(stdscr, key)
                        sent_ok = True
                        # UTF-8 multi-byte lead refused; nothing sent; not recorded.
                    else:
                        sent_ok = attach_conn.send_key(bytes([key]))
                        _recorded_key = chr(key)
                else:
                    # Every OTHER curses special key (arrow/function key
                    # etc.) has no single-byte raw form to forward --
                    # silently dropped rather than sending garbage. Hub
                    # ruling: explicitly acceptable to leave unforwarded
                    # this WO, disclosed here and in STATUS, unlike
                    # backspace above. key >= 256 path untouched.
                    sent_ok = True
                if sent_ok and _recorded_key and play.record_session.active:
                    # WO-P5-067 Accept #2: add the keystroke to the active
                    # recording session.  result.raw carries the screen that
                    # prompted this press (the pre-key snapshot; the game's
                    # response arrives asynchronously on the next ensure tick).
                    # Secret detection mirrors the existing attach-redaction
                    # logic: is_probable_secret_prompt on the current prompt.
                    _prompt = (result.raw or {}).get("prompt", "") if result.ok else ""
                    play.record_session.add_step(
                        _recorded_key,
                        (result.raw or {}).get("screen", []) if result.ok else [],
                        is_secret=_record_macro.is_secret_prompt_line(_prompt),
                    )
                if not sent_ok:
                    # The connection broke mid-session (daemon gone,
                    # socket reset, ...) -- honest failure containment,
                    # not a detach decision: a human who thinks they still
                    # have control when the wire is actually dead is a
                    # worse state than falling back to spectate. Mirrors
                    # `_attempt_attach`'s own "never silently look like
                    # success" principle.
                    attach_conn.close()
                    attach_conn = None
                    play.spectating = True
                    play.attached = False  # WO-P5-060 lane B: honest badge truth, alongside spectating
                    play.status_line = "attach connection lost — spectating"
                continue
            action = play.handle_key(key)
            if action is None and key in _AUTONOMY_OFFER_KEYS:
                status = (
                    play.status_provider() if play.status_provider is not None else {}
                )
                offer = _autonomy_policy.choose_offer(status)
                if offer.kind == "idle":
                    play.status_line = f"no autonomy offer — {offer.reason}"
                    continue
                if offer.gated:
                    play.status_line = f"autonomy offer gated — {offer.reason}"
                    continue
                if offer.kind == "explore":
                    pending_confirm_action = "explore"
                    pending_confirm_loop = None
                    pending_confirm_reflex = None
                    pending_confirm_hold = None
                    pending_confirm_trade = None
                    explore_intent_offered = _explore.INTENT_FIND_STARDOCK
                    offer_action = _explore_flags.compose_explore_action(
                        _EXPLORE_STARDOCK_ACTION,
                        dock=explore_dock_opt_in,
                        tolls=explore_tolls_opt_in,
                    )
                    play.begin_arm_confirm(offer_action)
                    continue
                if offer.kind == "run_chain":
                    chain, _caption = play.chain_scalars.bubble_subject()
                    plan = _trade_chain_plan.plan_from_chain(
                        _world_identity.world_id_from_profile(profile), chain
                    )
                    prompt = _trade_chain_plan.compose_confirm_action(
                        plan,
                        cash_floor=_TRADE_CASH_FLOOR,
                        turn_reserve=_TRADE_TURN_RESERVE,
                    )
                    if plan is None or prompt is None:
                        play.status_line = (
                            "did not approve trade — incomplete chain scaffold"
                        )
                        continue
                    pending_confirm_action = "trade"
                    pending_confirm_trade = plan
                    pending_confirm_hold = None
                    pending_confirm_loop = None
                    pending_confirm_reflex = None
                    play.begin_arm_confirm(prompt)
                    continue
                if offer.kind == "upgrade":
                    plan = _stardock_hold_plan.plan_from_status(
                        _world_identity.world_id_from_profile(profile), status
                    )
                    prompt = _stardock_hold_plan.compose_confirm_action(
                        plan, cash_floor=_HOLD_CASH_FLOOR
                    )
                    if plan is None or prompt is None:
                        play.status_line = (
                            "did not approve hold buy — incomplete hold scaffold"
                        )
                        continue
                    pending_confirm_action = "stardock_hold"
                    pending_confirm_hold = plan
                    pending_confirm_trade = None
                    pending_confirm_loop = None
                    pending_confirm_reflex = None
                    play.begin_arm_confirm(prompt)
                    continue
            if (
                action is None
                and explore_offered
                and _explore_flags.resolve_dock_toggle_key(key)
            ):
                # WO-PLAY-EXPLORE-FLAGS: `D` opts in to docking new ports.
                # It NEVER starts anything -- same posture as `E`, which
                # only raises the gate.
                explore_dock_opt_in = not explore_dock_opt_in
                play.status_line = _explore_flags.describe_dock(explore_dock_opt_in)
                continue
            if (
                action is None
                and explore_offered
                and _explore_flags.resolve_tolls_toggle_key(key)
            ):
                # `F` opts in to fighting toll demands. Same shape as `D`.
                #
                # Both toggles sit AFTER `handle_key`, which means pressing
                # one while a confirm gate is standing clears that gate (the
                # gate is single-shot and default-deny, so every non-`y` key
                # cancels it) and returns None to here.
                #
                # That is deliberate, not incidental: changing a flag
                # INVALIDATES any standing confirm, so the line the operator
                # finally says `y` to always describes the flags the run
                # will actually use. The alternative -- letting a toggle
                # ride while the old prompt stayed up -- would leave the
                # gate describing a different run than it arms, which is the
                # single failure mode the confirm gate exists to prevent.
                explore_tolls_opt_in = not explore_tolls_opt_in
                play.status_line = _explore_flags.describe_tolls(explore_tolls_opt_in)
                continue
            if action is None and explore_offered and key in _EXPLORE_OFFER_KEYS:
                # The human asked for the gate. THIS is what raises it --
                # never the ensure result on its own. `handle_key` returned
                # None, so no gate is currently up and no other binding
                # claimed the key.
                pending_confirm_action = "explore"
                pending_confirm_loop = None  # a different gate owns the row now
                pending_confirm_reflex = None
                pending_confirm_hold = None
                pending_confirm_trade = None
                # WO-EXPLORE-AUTOMATION-GATE E3: one affordance, two intents.
                # `E` CYCLES which goal is on offer and raises the gate for
                # it; it never starts anything. The first press of a session
                # is map-fill, so existing muscle memory arms the existing
                # RUN. (It no longer produces the identical LINE --
                # WO-EXPLORE-GATHER-VISIBLE added the dock state to it. The
                # run is what muscle memory is entitled to; the wording was
                # never the promise, and treating it as one is what kept the
                # prompt silent about ports.)
                if explore_intent_offered is None:
                    explore_intent_offered = _explore.ARMABLE_INTENTS[0]
                else:
                    explore_intent_offered = _explore.next_armable_intent(
                        explore_intent_offered
                    )
                # ONE `begin_arm_confirm` call, deliberately: the label is
                # chosen first and the gate raised once. An if/else with a
                # call in each arm reads the same but adds a fourth
                # production call site, and `test_exactly_three_production_
                # call_sites_raise_the_gate` counts them precisely so a new
                # money-path gate cannot appear quietly. One affordance, one
                # call site -- the count stays honest.
                #
                # find-StarDock carries NO cycle count: that run ends on
                # ARRIVAL or exhaustion, not after N sectors, and a prompt
                # promising "×5" would describe the other intent's rule.
                if explore_intent_offered == _explore.INTENT_FIND_STARDOCK:
                    offer_action, offer_cycles = _EXPLORE_STARDOCK_ACTION, None
                else:
                    offer_action, offer_cycles = _EXPLORE_OFFER_ACTION, _EXPLORE_MIN_SECTORS
                # WO-PLAY-EXPLORE-FLAGS: the gate must describe the run it
                # arms, so any opt-in the operator switched on is spelled
                # out IN the line they confirm.
                #
                # WO-EXPLORE-GATHER-VISIBLE applied that rule to the OFF
                # direction too, which is where it had never been applied.
                # This used to return the action text unchanged with both
                # flags off "so the default prompt stays byte-identical to
                # the pre-WO one" -- and a run that PASSES PORTS BY is just
                # as much a property of the run as one that docks. Dock is
                # now always stated; `+fight-tolls` stays ON-only on purpose
                # (see `cockpit/explore_flags.py`: loud toward the safe
                # action, quiet toward the spend).
                offer_action = _explore_flags.compose_explore_action(
                    offer_action,
                    dock=explore_dock_opt_in,
                    tolls=explore_tolls_opt_in,
                )
                play.begin_arm_confirm(offer_action, cycles=offer_cycles)
                continue
            if action is None and key in _HOLD_OFFER_KEYS:
                # WO-STARDOCK-HOLD-UPGRADE-ARM: H raises the hold-buy gate only
                # when the exact scaffold is complete — never invents price /
                # dock / holds.
                status = (
                    play.status_provider() if play.status_provider is not None else {}
                )
                world_id = _world_identity.world_id_from_profile(profile)
                plan = _stardock_hold_plan.plan_from_status(world_id, status)
                prompt = (
                    _stardock_hold_plan.compose_confirm_action(
                        plan, cash_floor=_HOLD_CASH_FLOOR
                    )
                    if plan is not None
                    else None
                )
                if plan is None or prompt is None:
                    play.status_line = (
                        "did not approve hold buy — incomplete hold scaffold"
                    )
                    continue
                pending_confirm_hold = plan
                pending_confirm_action = "stardock_hold"
                pending_confirm_trade = None
                pending_confirm_loop = None
                pending_confirm_reflex = None
                play.begin_arm_confirm(prompt)
                continue
            if action == "pause":
                # WO-AUTOLOOP-RELAUNCH-COCKPIT: Space -- ungated, like panic
                # (see `cockpit/autoloop_controls.py` and `cockpit/panic.py`
                # for why the confirm gate does not apply to a halt
                # direction). `autoloop_pause` never raises and is idempotent
                # daemon-side, so no precondition and no try/except here
                # either, mirroring the panic branch below.
                result = adapters.autoloop_pause(run_dir=run_dir)
                if result.ok:
                    play.status_line = "paused — taught run parked (Ctrl-A to drive, G to relaunch)"
                    autoloop_poll_active = False
                    play.explore_band = None
                else:
                    play.status_line = f"pause failed — {result.reason or 'unknown'}"
                continue
            if action is None and _autoloop_controls.resolve_relaunch_offer_key(key):
                # The human asked for the gate -- never raised unbidden, the
                # same sovereignty posture the explore offer above uses.
                # The disclosure preview happens BEFORE the gate is raised:
                # the label must state the money-path truth on the FIRST
                # keystroke the human sees, not after they have already
                # committed.
                sends_preview = _preview_relaunch_sends(run_dir)
                action_text = _autoloop_controls.compose_relaunch_confirm_action(sends_preview)
                pending_confirm_action = "relaunch"
                pending_confirm_loop = None  # a different gate owns the row now
                pending_confirm_hold = None
                pending_confirm_reflex = None
                play.begin_arm_confirm(action_text)
                continue
            if action == _reflex_controls.REFLEX_OFFER_INTENT:
                # WO-PLAY-REFLEX-ARM: V — ask what the taught library proposes.
                # Preview is free; arming is not. No candidate / STOP /
                # transport fail / incomplete identity → status only, zero
                # gate, zero launch.
                pending_confirm_loop = None
                pending_confirm_hold = None
                pending_confirm_reflex = None
                proposal = adapters.reflex_propose(run_dir=run_dir)
                if not getattr(proposal, "ok", False):
                    play.status_line = _reflex_controls.describe_transport_fail(
                        getattr(proposal, "reason", None)
                    )
                    continue
                macro = getattr(proposal, "macro", None)
                if not macro:
                    play.status_line = _reflex_controls.describe_stop(
                        getattr(proposal, "stop_reason", None)
                    )
                    continue
                rule_id = getattr(proposal, "rule_id", None)
                klass = getattr(proposal, "classification", None)
                if not (
                    isinstance(rule_id, str)
                    and rule_id
                    and isinstance(klass, str)
                    and klass
                ):
                    play.status_line = (
                        "reflex: incomplete identity — not offering arm"
                    )
                    continue
                scope = getattr(proposal, "scope", None)
                pending_confirm_action = "reflex"
                pending_confirm_reflex = {
                    "rule_id": rule_id,
                    "macro": macro,
                    "classification": klass,
                    "scope": scope,
                }
                play.status_line = _reflex_controls.describe_proposal(
                    macro=macro, rule_id=rule_id, classification=klass
                )
                # WO-AUTOLOOP-CYCLES: repeating → confirm shows hard-ceiling
                # cycles; one-shot / missing stays one-pass (cycles=None).
                offer_cycles = (
                    CYCLES_HARD_CEILING if scope == "repeating" else None
                )
                play.begin_arm_confirm(
                    _reflex_controls.compose_reflex_confirm_action(macro),
                    cycles=offer_cycles,
                )
                continue
            if action == "chains_open":
                # WO-PLAY-AUTOLOOP-START: canon's `L)chains`. The store read
                # happens HERE, on the human's keypress -- not on a timer and
                # not at ensure -- so the list can never appear unbidden.
                # `status` is carried alongside the rows because an empty list
                # means "none taught" ONLY under `ok`; `read_loop_store`'s own
                # contract names `status` as the field a caller must branch on
                # before saying anything about how many loops exist.
                #
                # WO-CHAINS-TUI-FULL: the DISCOVERED section's payload is
                # computed here too, on the same keypress, and passed IN so
                # `cockpit.chains` stays finder-free. Display-only by
                # construction: the payload never enters the session's
                # `rows`, so `selected()` / the arm path structurally cannot
                # receive a discovered chain. A raising finder (or a profile
                # that cannot form a `world_id`) must not take the play loop
                # down; `None` renders as the modal's own honest "discovery
                # unavailable" line, so no status_line is spent on it and no
                # absence is fabricated. No exception text is rendered at
                # all, which keeps the secrets rule above moot on this path.
                #
                # Imported HERE, not at module top, for the same reason
                # `session/cli.py::cmd_chains` does it: `chain_search` pulls
                # the finder + trade_adapter + world_model, ~40ms of import
                # CPU nothing else in the cockpit needs — and the launcher's
                # whole-process CPU budget (`tests/test_dead_terminal_spin.py`,
                # 0.5s including imports) is already within ~50ms of the
                # line before it.
                #
                # The GOALS Map row's `known_sectors` is refreshed on this
                # keypress (and on explore terminal poll — see
                # `_poll_explore_status`): `status_provider()` runs once per
                # DRAW, and counting sector files (~26ms at 5000 sectors)
                # cannot go on that path against the budget described above.
                # This keypress already pays for a full world-model pass, so
                # the marginal cost of a directory count is noise. Kept in its
                # own guarded block rather than folded into the discovery below
                # so that a broken finder does not also cost us the count, and
                # so the existing expression's behaviour is untouched.
                try:
                    status = None
                    provider = getattr(play, "status_provider", None)
                    if callable(provider):
                        try:
                            status = provider()
                        except Exception:  # noqa: BLE001
                            status = None
                    play.world_stats.refresh(
                        _world_identity.world_id_from_profile(profile),
                        status=status,
                    )
                except Exception:  # noqa: BLE001
                    pass
                try:
                    from tw2002_aiclient import chain_search as _chain_search

                    discovered = _chain_search.recompute(
                        _world_identity.world_id_from_profile(profile)
                    )
                except Exception:  # noqa: BLE001
                    discovered = None
                try:
                    store = _loop_store.read_loop_store()
                except Exception as exc:  # noqa: BLE001
                    # A raising store read must not take the play loop down.
                    # Type name only, never `str(exc)` -- a store path is not
                    # a safe thing to assume is free of operator identity
                    # (`canon/doctrine/secrets-and-credentials.md`).
                    play.chain_scalars.update(discovered)
                    play.chains_session.open([], "unreadable", discovered=discovered)
                    play.status_line = f"loop store unreadable — {type(exc).__name__}"
                else:
                    play.chain_scalars.update(discovered)
                    play.chains_session.open(
                        _chains.playable_loops(store),
                        _chains.store_status(store),
                        discovered=discovered,
                    )
                # WO-CHAIN-BUBBLE-PAIR-FALLBACK: refresh class-pair cache on L
                # so the always-on strip can fall back when priced cycles miss.
                try:
                    from tw2002_aiclient import chain_detect as _chain_detect

                    play.chain_scalars.update_pairs(
                        _chain_detect.recompute(
                            _world_identity.world_id_from_profile(profile)
                        )
                    )
                except Exception:  # noqa: BLE001
                    pass
                continue
            if action == "chains_close":
                play.chains_session.close()
                continue
            if action == "chains_up":
                play.chains_session.move(-1)
                continue
            if action == "chains_down":
                play.chains_session.move(1)
                continue
            if action == "rules_library_open":
                # WO-PLAY-RULES-LIBRARY: U)rules — read-only blessed peek.
                # Branch on status before claiming a count (absent ≠ empty ≠
                # blind). Drafts stay invisible (include_drafts=False).
                try:
                    store = _rule_store.read_rule_store()
                except Exception as exc:  # noqa: BLE001
                    play.rules_library_session.open([], "unreadable")
                    play.status_line = (
                        f"rule store unreadable — {type(exc).__name__}"
                    )
                else:
                    status = _rules_library.store_status(store)
                    play.rules_library_session.open(
                        _rules_library.blessed_rows(store), status,
                    )
                    if status == "absent":
                        play.status_line = _rules_library.ABSENT_TEXT
                    elif status == "unreadable":
                        play.status_line = _rules_library.UNREADABLE_TEXT
                    elif status == "partial":
                        n = len(play.rules_library_session.rows)
                        play.status_line = (
                            f"blessed rules ({n}) — partial store"
                        )
                    else:
                        n = len(play.rules_library_session.rows)
                        play.status_line = (
                            f"blessed rules ({n})"
                            if n
                            else _rules_library.EMPTY_TEXT
                        )
                continue
            if action == "rules_library_close":
                play.rules_library_session.close()
                continue
            if action == "rules_library_up":
                play.rules_library_session.move(-1)
                continue
            if action == "rules_library_down":
                play.rules_library_session.move(1)
                continue
            if action == "chains_arm":
                # Enter on a row ARMS a pending action; it never starts one.
                # The adapter call lives in the `arm_confirm` branch below,
                # behind `y`. Canon: "A bare Enter must never fire a launch."
                selected = play.chains_session.selected()
                discovered = play.chains_session.selected_discovered()
                if discovered is not None:
                    world_id = _world_identity.world_id_from_profile(profile)
                    plan = _trade_chain_plan.plan_from_chain(
                        world_id, discovered
                    )
                    prompt = _trade_chain_plan.compose_confirm_action(
                        plan,
                        cash_floor=_TRADE_CASH_FLOOR,
                        turn_reserve=_TRADE_TURN_RESERVE,
                    )
                    if plan is None or prompt is None:
                        play.status_line = (
                            "did not approve trade — incomplete chain scaffold"
                        )
                        continue
                    pending_confirm_trade = plan
                    pending_confirm_hold = None
                    pending_confirm_loop = None
                    pending_confirm_action = "trade"
                    pending_confirm_reflex = None
                    play.chains_session.close()
                    play.begin_arm_confirm(prompt)
                    continue
                if selected is None:
                    # Nothing to arm. Say so and leave the popup up rather
                    # than raising a confirm gate for a run with no macro --
                    # a `y/N` prompt naming nothing is worse than no prompt.
                    play.status_line = "nothing to arm — no taught loop selected"
                    continue
                pending_confirm_loop = selected
                pending_confirm_action = "loop"
                pending_confirm_hold = None
                pending_confirm_reflex = None
                play.chains_session.close()
                play.begin_arm_confirm(_chains.compose_arm_action(selected))
                continue
            if action == "arm_confirm" and pending_confirm_action == "trade":
                pending_confirm_action = None
                plan = pending_confirm_trade
                pending_confirm_trade = None
                pending_confirm_hold = None
                pending_confirm_loop = None
                pending_confirm_reflex = None
                if not isinstance(plan, _trade_chain_plan.TradeChainPlan):
                    play.status_line = (
                        "did not arm trade — no exact chain held for this confirm"
                    )
                    continue
                play.status_line = f"starting trade {plan.route}…"
                play.draw()
                try:
                    started = adapters.trade_chain_start(
                        plan.world_id,
                        plan.fingerprint,
                        cash_floor=_TRADE_CASH_FLOOR,
                        turn_reserve=_TRADE_TURN_RESERVE,
                        run_dir=run_dir,
                    )
                except Exception as exc:  # noqa: BLE001
                    play.status_line = f"trade arm failed — {type(exc).__name__}"
                else:
                    if getattr(started, "ok", False):
                        play.status_line = (
                            f"trade armed — {plan.route}, one pass running"
                        )
                        trade_poll_active = _apply_trade_chain_band(
                            play, getattr(started, "raw", None)
                        )
                    else:
                        reason = getattr(started, "reason", None) or "unknown"
                        play.status_line = f"did not arm trade — {reason}"
                continue
            if action == "arm_confirm" and pending_confirm_action == "stardock_hold":
                pending_confirm_action = None
                plan = pending_confirm_hold
                pending_confirm_hold = None
                pending_confirm_trade = None
                pending_confirm_loop = None
                pending_confirm_reflex = None
                if not isinstance(plan, _stardock_hold_plan.StardockHoldPlan):
                    play.status_line = (
                        "did not arm hold buy — no exact hold held for this confirm"
                    )
                    continue
                play.status_line = (
                    f"starting hold buy @ StarDock {plan.stardock_sector}…"
                )
                play.draw()
                try:
                    started = adapters.stardock_hold_start(
                        plan.world_id,
                        plan.fingerprint,
                        stardock_sector=plan.stardock_sector,
                        empty_holds=plan.empty_holds,
                        hold_price=plan.hold_price,
                        credits=plan.credits,
                        qty=plan.qty,
                        cash_floor=_HOLD_CASH_FLOOR,
                        run_dir=run_dir,
                    )
                except Exception as exc:  # noqa: BLE001
                    play.status_line = f"hold arm failed — {type(exc).__name__}"
                else:
                    if getattr(started, "ok", False):
                        play.status_line = (
                            f"hold buy armed — {plan.qty} hold(s) @ "
                            f"StarDock {plan.stardock_sector}, one pass running"
                        )
                    else:
                        reason = getattr(started, "reason", None) or "unknown"
                        play.status_line = f"did not arm hold buy — {reason}"
                continue
            if action == "arm_confirm" and pending_confirm_action == "loop":
                # WO-PLAY-AUTOLOOP-START: the human pressed `y` at the taught-
                # loop confirm. Only NOW does the money-spending adapter call
                # happen.
                #
                # This branch MUST stay above the explore `arm_confirm` below.
                # Explore no longer is an unguarded default (WO-ARM-CONFIRM-
                # EXPLICIT-EXPLORE), but a `y` meant for a taught loop must
                # still never reach explore_start — pinned both ways in
                # `tests/test_play_chains_arm.py`.
                #
                # The name comes from the row the confirm line was composed
                # from, never from a re-read of the store: re-reading between
                # the prompt and the `y` is how an operator ends up arming a
                # different macro than the one they agreed to.
                pending_confirm_action = None
                armed = pending_confirm_loop
                pending_confirm_loop = None
                pending_confirm_hold = None
                pending_confirm_reflex = None
                name = armed.get("name") if isinstance(armed, dict) else None
                if not name:
                    # Fail closed: the gate said "loop" but no row is held.
                    # Reachable only if the stale-pending invariant above
                    # breaks. Refusing costs an operator one keystroke;
                    # guessing costs them live turns on a macro nobody named.
                    play.status_line = "did not arm — no loop held for this confirm"
                    continue
                play.status_line = f"arming {name or '?'}…"
                play.draw()  # the start call blocks; show intent first
                try:
                    started = adapters.autoloop_start(name, run_dir=run_dir)
                except Exception as exc:  # noqa: BLE001
                    # A raising adapter must not take the play loop down --
                    # same containment posture as the explore branch below.
                    # Type name only, never `str(exc)`.
                    play.status_line = f"arm failed — {type(exc).__name__}"
                else:
                    if getattr(started, "ok", False):
                        play.status_line = f"armed {name} — one pass running"
                        autoloop_poll_active = True
                        _apply_autoloop_cycle_band(play, getattr(started, "raw", None))
                    else:
                        reason = getattr(started, "reason", None) or "unknown"
                        play.status_line = f"did not arm — {reason}"
                continue
            if action == "arm_confirm" and pending_confirm_action == "relaunch":
                # WO-AUTOLOOP-RELAUNCH-COCKPIT: the human pressed `y` at the
                # relaunch offer. Only NOW does the money-spending adapter
                # call happen -- the preview above never called it.
                pending_confirm_action = None
                pending_confirm_hold = None
                play.status_line = "relaunching…"
                play.draw()
                result = adapters.autoloop_relaunch(run_dir=run_dir)
                if result.ok:
                    play.status_line = "relaunched — replaying from the start"
                    autoloop_poll_active = True
                    _apply_autoloop_cycle_band(play, result.raw)
                else:
                    play.status_line = f"relaunch failed — {result.reason or 'unknown'}"
                continue
            if action == "arm_confirm" and pending_confirm_action == "reflex":
                # WO-PLAY-REFLEX-ARM: human pressed `y` at the reflex confirm.
                # Launch ONLY through `adapters.reflex_arm` with the exact
                # identity held from preview — never a re-propose, never a
                # direct send.
                pending_confirm_action = None
                identity = pending_confirm_reflex
                pending_confirm_hold = None
                pending_confirm_reflex = None
                if not isinstance(identity, dict):
                    play.status_line = "did not arm — no reflex held for this confirm"
                    continue
                macro = identity.get("macro") or "?"
                play.status_line = f"arming {macro}…"
                play.draw()
                try:
                    started = adapters.reflex_arm(
                        rule_id=identity.get("rule_id"),
                        macro=identity.get("macro"),
                        classification=identity.get("classification"),
                        run_dir=run_dir,
                    )
                except Exception as exc:  # noqa: BLE001
                    play.status_line = f"arm failed — {type(exc).__name__}"
                else:
                    if getattr(started, "ok", False):
                        scope = identity.get("scope")
                        if scope == "repeating":
                            play.status_line = (
                                f"armed {macro} — multi-pass running"
                            )
                        else:
                            play.status_line = f"armed {macro} — one pass running"
                        autoloop_poll_active = True
                        _apply_autoloop_cycle_band(
                            play, getattr(started, "raw", None)
                        )
                    else:
                        reason = getattr(started, "reason", None) or "unknown"
                        play.status_line = f"did not arm — {reason}"
                continue
            if action == "arm_confirm" and pending_confirm_action == "explore":
                # WO-PLAY-EXPLORE-ARM (L3) + WO-ARM-CONFIRM-EXPLICIT-EXPLORE:
                # the human pressed `y` at the explore offer. Explore is NOT
                # the bare `arm_confirm` default — only an explicit
                # `pending_confirm_action == "explore"` (set when `E` raises
                # the gate) may start a runner. `handle_key` has already
                # cleared the gate (single-shot) and only `y`/`Y` can produce
                # this intent -- `resolve_arm_confirm_key` is default-deny, so
                # `Enter`, `Esc`, `N` and every unmapped keycode land on the
                # cancel branch and never reach here.
                #
                # `_EXPLORE_MIN_SECTORS` is the SAME constant the prompt was
                # composed from, so the run cannot start with a different
                # number than the one the human just agreed to.
                #
                # E3: the run uses the intent the RAISED PROMPT was composed
                # from. The `or` is the fail-safe for a gate raised by some
                # future path that never set an intent -- map-fill is the
                # conservative one (bounded by `_EXPLORE_MIN_SECTORS`), where
                # find-StarDock runs until arrival or exhaustion.
                pending_confirm_action = None
                armed_intent = explore_intent_offered or _explore.INTENT_MAP_FILL
                pending_confirm_hold = None
                pending_confirm_reflex = None
                if armed_intent == _explore.INTENT_FIND_STARDOCK:
                    play.status_line = "starting explore — find StarDock…"
                    play.explore_band = "find StarDock starting…"
                else:
                    play.status_line = f"starting explore ×{_EXPLORE_MIN_SECTORS}…"
                    play.explore_band = f"explore ×{_EXPLORE_MIN_SECTORS} starting…"
                play.draw()  # the start call blocks; show intent first
                try:
                    explore = adapters.explore_start_for_profile(
                        profile,
                        min_sectors=_EXPLORE_MIN_SECTORS,
                        intent=armed_intent,
                        # WO-PLAY-EXPLORE-FLAGS: the opt-ins the operator
                        # switched on, and that the confirm line they just
                        # answered spelled out. This supersedes
                        # WO-EXPLORE-DOCK-DEFAULT-OFF's placeholder comment
                        # ("Opt-in later via an explicit Play control if
                        # added") -- this IS that control. The DEFAULT is
                        # still OFF: these are `False` unless `D`/`F` were
                        # pressed, so an operator who only ever presses
                        # `E`,`y` arms exactly the run they always did.
                        #
                        # Passed unconditionally rather than only-when-True
                        # so a dropped forward is a MISSING KWARG (loud, and
                        # pinned) instead of a silent omission that looks
                        # identical to the safe default.
                        #
                        # Neither value is wrapped in `bool(...)` -- see
                        # `cockpit/explore_flags.py` on why symmetrising
                        # these two flags is the money-path hazard here.
                        dock_new_ports=explore_dock_opt_in,
                        fight_tolls=explore_tolls_opt_in,
                    )
                except Exception as exc:  # noqa: BLE001
                    # A raising adapter must not take the play loop down with
                    # it. The operator keeps the cockpit and is told the
                    # start failed -- the same "honest failure containment,
                    # not a control decision" posture the attach path takes
                    # below. Type name only, never `str(exc)`: this call
                    # carries a profile and reaches the daemon, and an
                    # exception message is not a safe place to assume
                    # otherwise (`canon/doctrine/secrets-and-credentials.md`).
                    play.status_line = f"explore failed to start — {type(exc).__name__}"
                    play.explore_band = None      # offer is spent; calm band returns
                    play.explore_decision_lines = None
                else:
                    if getattr(explore, "ok", False):
                        play.status_line = f"explore started — {_EXPLORE_MIN_SECTORS} sectors"
                        play.explore_band = f"explore 0/{_EXPLORE_MIN_SECTORS}…"
                        explore_poll_active = True
                    else:
                        # Report the adapter's machine-readable reason rather
                        # than a cheerful generic: "explore failed" with no
                        # code is the kind of message that sends an operator
                        # to the logs for something the screen already knew.
                        reason = getattr(explore, "reason", None) or "unknown"
                        play.status_line = f"explore did not start — {reason}"
                        play.explore_band = None
                        play.explore_decision_lines = None
                continue
            if action == "arm_confirm":
                # WO-ARM-CONFIRM-EXPLICIT-EXPLORE: fail closed. Unknown /
                # unset / stale `pending_confirm_action` must not start ANY
                # runner — a third arm type that raises the gate but forgets
                # its own branch used to fall into explore here.
                pending_confirm_action = None
                pending_confirm_loop = None
                pending_confirm_hold = None
                pending_confirm_reflex = None
                play.status_line = "did not arm — nothing pending for this confirm"
                continue
            if action == "assign_trigger":
                # WO-P5-068: T Assign-Trigger scaffold.  Create a when+guards
                # stub for the most-recently confirmed screen classification
                # and record it in the play shell's in-memory stub store.
                # This is a DRAFT only -- the stub is NOT on the live
                # autopilot fire path and cannot trigger any send.  Full
                # rule engine + approval gate land in WO-070 family.
                stub = _assign_trigger.create_stub(play.current_classification)
                play.stub_store.set(stub)
                screen_label = play.current_classification or "?"
                play.status_line = f"trigger stub set — screen: {screen_label}"
                continue
            if action == "analyze_open":
                # WO-P5-069: A Analyze on-demand overlay — open.
                # The AI teacher is spectator-only: it reads the settled
                # screen and ledger after the fact.  It NEVER sends a
                # keystroke to the game -- no session.send /
                # attach_conn.send_key call appears here or in any module
                # this branch reaches (structural grep pin:
                # tests/test_cockpit_analyze.py).
                # The draft-rule content path is WO-P5-070; this WO only
                # opens the overlay gate and shows the indicator badge.
                play.analyze_session.open()
                play.status_line = "analyzing — press A or Esc to close"
                continue
            if action == "analyze_close":
                # WO-P5-069: A Analyze on-demand overlay — close.
                # WO-P5-070: closing produces an inert draft and raises the
                # human approval gate — unapproved drafts never reach stub_store.
                play.analyze_session.close()
                draft = _draft_approve.create_analyze_draft(play.current_classification)
                play.pending_analyze_draft = draft
                play.begin_draft_approve(draft)
                screen_label = (draft.get("when") or {}).get("screen") or "?"
                play.status_line = f"analyze draft ({screen_label}) — y/N to approve"
                continue
            if action == "draft_approve":
                # WO-PLAY-RULE-IDENTITY: y accepts the *proposal* and opens
                # typed entry for rule_id / do / priority. Nothing is written
                # to state/rules/ until those three fields complete.
                draft = play.pending_analyze_draft
                if draft is None:
                    play.status_line = "analyze draft approve failed — no draft"
                    continue
                play.begin_rule_identity(draft)
                play.status_line = (
                    "rule identity — rule id, macro, priority, scope "
                    "(one-shot|repeating)"
                )
                continue
            if action == "rule_identity":
                session = play._rule_identity
                play._rule_identity = None
                values = (
                    session.get("values") if isinstance(session, dict) else None
                )
                stub = (
                    (session.get("stub") if isinstance(session, dict) else None)
                    or play.pending_analyze_draft
                )
                play.pending_analyze_draft = None
                if not isinstance(values, dict) or not isinstance(stub, dict):
                    play.status_line = "rule identity failed — session lost"
                    continue
                try:
                    document = _draft_approve.bridge_to_kernel_document(
                        stub,
                        rule_id=values.get("rule_id"),
                        do=values.get("do"),
                        priority=values.get("priority"),
                        scope=values.get("scope"),
                    )
                    _rules_writer.write_draft(document)
                    blessed = _rules_writer.promote_draft(str(values["rule_id"]))
                except (
                    _draft_approve.DraftBridgeError,
                    _rules_writer.RuleWriteError,
                    TypeError,
                    KeyError,
                    ValueError,
                ) as exc:
                    play.status_line = f"rule write refused — {exc}"
                    continue
                approved = _draft_approve.promote_to_approved(stub)
                if approved is not None:
                    play.stub_store.set(approved)
                play.approval_ledger_events.append(
                    {
                        "actor": "app",
                        "event": "analyze_rule_written",
                        "screen": (
                            (stub.get("when") or {}).get("screen") or ""
                        ),
                        "rule_id": values.get("rule_id"),
                        "do": values.get("do"),
                        "scope": values.get("scope"),
                        "path": str(blessed),
                    }
                )
                play.status_line = _draft_approve.compose_rule_blessed_line(
                    values.get("rule_id"),
                    values.get("do"),
                    values.get("scope"),
                )
                continue
            if action == "rule_identity_cancel":
                play._rule_identity = None
                play.pending_analyze_draft = None
                play.status_line = "rule identity cancelled — nothing written"
                continue
            if action == "draft_reject":
                play.pending_analyze_draft = None
                play.status_line = "analyze draft discarded"
                continue
            if action == "record_toggle":
                # WO-P5-067: R Record.  Toggle the in-cockpit recording
                # session.  On first press: start recording, capturing the
                # opening screen from the most recent ensure result.  On
                # second press: finalise and save the macro.  Human
                # keystrokes are fed into the session via the attach path
                # above (add_step on each successful send_key).  The record
                # path never calls explore_start or any send -- RecordSession
                # has no send path of its own.
                if not play.record_session.active:
                    # Start recording: capture the opening screen from the
                    # most recent ensure result.  A missing or bad result
                    # produces empty rows; RecordSession.start() and
                    # LoopRecorder.__init__ degrade safely (NoStartAnchor on
                    # stop if the anchor cannot be read from an empty screen).
                    opening_rows = (result.raw or {}).get("screen", []) if result.ok else []
                    name = _record_macro.auto_name(play.current_classification)
                    play.record_session.start(name, opening_rows)
                    play.status_line = f"recording — {name!r}  (press R to stop)"
                else:
                    # Stop recording: finalise and save.
                    save = play.record_session.save()
                    if save is not None:
                        play.status_line = (
                            f"recorded {save.steps} step(s) → {save.path.name}"
                        )
                    else:
                        play.status_line = (
                            "recording stopped — nothing saved "
                            "(no steps captured or missing sector anchor)"
                        )
                continue
            if action == "panic":
                # WO-P5-071: P panic — halt the taught-run player NOW.
                #
                # No confirm gate, by design and by hub ruling (2026-07-27).
                # Canon's "a bare Enter must never fire a launch" protects
                # the direction that SPENDS turns and credits; this is the
                # halt direction. See `cockpit/panic.py` for the full
                # reasoning and `tests/test_cockpit_panic.py` for the pin
                # that keeps a future "consistency" refactor from adding one.
                #
                # `autoloop_stop` never raises and is idempotent daemon-side,
                # so this needs no try/except of its own and a double-press
                # is harmless.
                results = (
                    adapters.autoloop_stop(run_dir=run_dir),
                    adapters.explore_stop(run_dir=run_dir),
                    adapters.trade_chain_stop(run_dir=run_dir),
                )
                if all(result.ok for result in results):
                    play.status_line = "PANIC — all automation halt requested"
                    autoloop_poll_active = False
                    explore_poll_active = False
                    trade_poll_active = False
                    play.explore_band = None
                else:
                    # Reported, not smoothed. "I could not reach a runner" and
                    # "I halted the run" are different facts, and an operator
                    # who just hit panic is entitled to know which one
                    # happened — a reassuring message here would be the
                    # worst possible lie on this particular key.
                    failures = [
                        result.reason or "unknown"
                        for result in results
                        if not result.ok
                    ]
                    play.status_line = f"PANIC partial — {', '.join(failures)}"
                continue
            if action == "attach":
                if attach_conn is None:
                    conn, error = _attempt_attach(env.socket_path(run_dir))
                    if conn is not None:
                        attach_conn = conn
                        play.spectating = False
                        play.attached = True  # WO-P5-060 lane B: honest badge truth, alongside spectating
                        play.status_line = "attached — you have control (Ctrl-A returns to App)"
                    else:
                        play.status_line = f"attach refused — {error}"
                continue
            if action == "conn_activate":
                # WO-PLAY-CONN-TOGGLE: poll a fresh snapshot for the truthful
                # connection state BEFORE acting -- the cached status from
                # the last draw may be up to 1 s old, and we must not
                # disconnect an already-disconnected session or skip a
                # reconnect because a stale "connected=True" lingered.
                #
                # Failure direction (CC review / Rule 3 lane): unknown
                # status must NOT silently become "disconnected" and fire
                # ensure/reconnect. Only act on an explicit True/False.
                known_connected: bool | None = None
                try:
                    if play.status_provider is not None:
                        current_status = play.status_provider()
                        if (
                            isinstance(current_status, dict)
                            and "connected" in current_status
                            and isinstance(current_status.get("connected"), bool)
                        ):
                            known_connected = current_status["connected"]
                except Exception:  # noqa: BLE001 — refuse live action; do not crash
                    known_connected = None
                if known_connected is None:
                    play.status_line = "connection state unknown — not acting"
                elif known_connected:
                    # Disconnect: close the daemon's telnet socket without
                    # stopping the daemon.  The ensure path (below, on next
                    # activate) will reconnect.
                    # footgun-safe: uses the same run_dir as ensure_session,
                    # so --run-dir isolation is preserved (ADR-001 / WO
                    # constraint).
                    play.status_line = "disconnecting…"
                    play.draw()
                    ok = adapters.disconnect_session(run_dir=run_dir)
                    play.status_line = "disconnected" if ok else "disconnect failed"
                else:
                    # Reconnect: ensure_session already calls
                    # session.reconnect() when session.conn.connected is
                    # False, then replays login (WO-P2-027 path).
                    play.status_line = "reconnecting…"
                    play.draw()
                    result = adapters.ensure_session(
                        profile.name, no_auto_arm=True, run_dir=run_dir
                    )
                    if result.ok:
                        play.status_line = f"reconnected — {result.classification}"
                    else:
                        play.status_line = f"reconnect failed — {result.reason}: {result.detail}"
                play._conn_focused = False  # return chip to resting state after action
                continue
            if action in ("back", "quit"):
                return action
    finally:
        if attach_conn is not None:
            attach_conn.close()
        feed.stop()
        stdscr.timeout(-1)  # restore blocking getch for the caller's own loop


def _bank_view(stdscr: curses.window) -> BankViewScreen:
    """Build the bank view, rendering a read failure as a failure.

    The surface boundary for ``player_bank.BankUnreadable``
    (WO-AUDIT-PLAYER-BANK-STORE-HONESTY) -- the ``cmd_menumap`` shape, where
    the one-file store read aborts and the surface renders the error, rather
    than the reader inventing an empty result. Both bank entry points go
    through here so neither can drift back into showing "(bank empty)" for a
    bank nobody could read.

    ``cause`` leads the detail line because it is what tells the operator which
    job this is -- fixing permissions, replacing a wrong path, or repairing a
    damaged document -- and the exception's own text follows with the specific
    reason and the offending path.
    """
    try:
        entries = player_bank.list_players()
    except player_bank.BankUnreadable as exc:
        return BankViewScreen(stdscr, entries=(), error=f"{exc.cause}: {exc}")
    return BankViewScreen(stdscr, entries=entries)


def _run_bank(stdscr: curses.window) -> str:
    bank = _bank_view(stdscr)
    guard = _DeadTerminalGuard()
    while True:
        bank.draw()
        key = _guarded_getch(stdscr, guard)
        if key == -1:
            continue
        action = bank.handle_key(key)
        if action in ("back", "quit"):
            return action


def _apply_presence(screen: LauncherScreen, *, run_dir=None) -> None:
    """Overlay read-only ONLINE flags from a bounded status poll. Never raises."""
    sticky_fail = (
        screen.presence_note
        if isinstance(screen.presence_note, str)
        and screen.presence_note.startswith("stop failed")
        else None
    )
    try:
        presence = daemon_lifecycle.read_presence(run_dir=run_dir)
        active = daemon_lifecycle.online_profile_name(presence)
        updated = [
            replace(row, online=(active is not None and row.name == active))
            for row in screen.profiles
        ]
        screen.set_profiles(updated)
        if sticky_fail is not None:
            screen.set_presence_note(sticky_fail)
        else:
            screen.set_presence_note(daemon_lifecycle.presence_note(presence))
    except Exception:  # noqa: BLE001 — launcher must stay usable
        if sticky_fail is not None:
            screen.set_presence_note(sticky_fail)
        else:
            screen.set_presence_note("daemon status unavailable — no profile marked online")
        try:
            screen.set_profiles([replace(row, online=False) for row in screen.profiles])
        except Exception:  # noqa: BLE001
            pass


def _confirm_app_quit(stdscr: curses.window, screen: LauncherScreen, *, run_dir=None) -> bool:
    """Whole-app quit gate. True = exit the app; False = stay open.

    No daemon → quit immediately. Otherwise raise default-No confirm; ``y``
    issues one ``stop``. Stop failure keeps the app open with an honest error.
    """
    try:
        if not daemon_lifecycle.should_confirm_quit_stop(run_dir=run_dir):
            return True
    except Exception:  # noqa: BLE001
        pass

    presence = daemon_lifecycle.read_presence(run_dir=run_dir)
    line = daemon_lifecycle.compose_quit_confirm_line(
        daemon_lifecycle.quit_profile_label(presence)
    )
    stdscr.timeout(-1)
    screen.draw_quit_confirm(line)
    while True:
        key = _guarded_getch(stdscr, _DeadTerminalGuard())
        if key == -1:
            continue
        outcome = daemon_lifecycle.resolve_quit_confirm_key(key)
        if outcome != daemon_lifecycle.CONFIRM:
            # Default No: quit the client, leave the daemon running.
            return True
        result = daemon_lifecycle.stop_daemon(run_dir=run_dir)
        if result.ok:
            return True
        # Stop failed — stay in the app; never claim a disconnect.
        detail = result.detail or result.reason or "stop failed"
        screen.set_presence_note(f"stop failed — {detail} (still connected?)")
        screen.draw()
        return False


def _run(stdscr: curses.window) -> None:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)
    stdscr.timeout(-1)
    screen = LauncherScreen(stdscr, profiles=_load_profiles())
    _apply_presence(screen)
    # Automated smoke: draw once and exit clean (hub/script verify without interactive input).
    if os.environ.get("TW2002_LAUNCHER_SMOKE") == "1":
        screen.draw()
        return
    # Hand-off smoke: draw launcher → enter first healthy row → draw play → exit.
    if os.environ.get("TW2002_HANDOFF_SMOKE") == "1":
        if not screen.profiles or screen.profiles[0].error:
            # Ensure a row exists for Proof.
            screen.set_profiles(
                [
                    ProfileRow(
                        name="alpha",
                        handle="Alpha",
                        server="demo-a",
                        host="demo-a.example",
                        game_letter="B",
                    )
                ]
            )
        screen.selected = 0
        screen.draw()
        profile = screen.selected_profile()
        assert profile is not None
        PlayShellScreen(stdscr, profile).draw()
        return
    # Bank smoke: draw bank view once (metadata + boundary) then exit.
    if os.environ.get("TW2002_BANK_SMOKE") == "1":
        # Seed demo profiles into the row model so bank rows aren't empty under DEMO.
        if os.environ.get("TW2002_LAUNCHER_DEMO") == "1":
            # list_players reads disk profiles; for smoke use explicit fixture entries.
            entries = [
                {
                    "name": "scout-b",
                    "handle": "NewPilot",
                    "host": "game.a-net-online.lol",
                    "game_letter": "B",
                    "last_played": "never",
                    "turns_state": "-",
                },
                {
                    "name": "paladin-main",
                    "handle": "PaladinPrime",
                    "host": "tw2002.example.com",
                    "game_letter": "A",
                    "last_played": "2026-07-23",
                    "turns_state": "ok",
                },
            ]
            BankViewScreen(stdscr, entries=entries).draw()
        else:
            _bank_view(stdscr).draw()
        return
    guard = _DeadTerminalGuard()
    while True:
        _apply_presence(screen)
        screen.draw()
        stdscr.timeout(_LAUNCHER_PRESENCE_POLL_MS)
        key = _guarded_getch(stdscr, guard)
        if key == -1:
            continue  # presence poll tick — redraw with fresh ONLINE next loop
        stdscr.timeout(-1)
        action = screen.handle_key(key)
        if action == "quit":
            if _confirm_app_quit(stdscr, screen):
                break
            continue
        if action == "bank":
            result = _run_bank(stdscr)
            if result == "quit":
                if _confirm_app_quit(stdscr, screen):
                    break
            continue
        if action == "create":
            result = _run_create(stdscr)
            if result == "saved":
                screen.set_profiles(_load_profiles())
                if screen.profiles:
                    screen.selected = len(screen.profiles) - 1
            try:
                curses.curs_set(0)
            except curses.error:
                pass
            continue
        if action == "play":
            profile = screen.selected_profile()
            if profile is None:
                continue
            result = _run_play(stdscr, profile)
            # Fresh launcher draw — no play-shell transient state carried back.
            if result == "quit":
                if _confirm_app_quit(stdscr, screen):
                    break
            try:
                curses.curs_set(0)
            except curses.error:
                pass


def _report_dead_terminal(exc: DeadTerminalError) -> None:
    """Best-effort diagnostic for a dead-terminal clean exit.

    Extracted from ``main()`` so it can be unit-tested directly (a real
    dead pty needs a real subprocess to reproduce; a broken ``sys.stderr``
    does not). Never lets a failed print turn a clean shutdown into an
    uncaught second traceback -- confirmed empirically (Samantha review,
    2026-07-26, ``pty.fork()`` + close the master + print from the
    child): writing to the SAME terminal that just died raises ``OSError:
    [Errno 5] Input/output error``. The exit itself is what matters; this
    diagnostic is opportunistic only.
    """
    try:
        print(f"tw2002-aiclient: {exc}", file=sys.stderr)
    except OSError:
        pass


_USAGE = """\
usage: tw2002-aiclient [-h]

Human-piloted TradeWars 2002 trainer (curses cockpit).

options:
  -h, --help  show this help message and exit

Run with no arguments in a real terminal to open the profile picker.
Ops/automation: use ./tw --help
"""


def main(argv: list[str] | None = None) -> int:
    """Product TUI entry. ``--help`` / ``-h`` print usage and exit 0
    without entering ``curses.wrapper`` (WO-TUI-HELP-ARGV).
    """
    if argv is None:
        argv = sys.argv[1:]
    if any(a in ("-h", "--help") for a in argv):
        print(_USAGE, end="" if _USAGE.endswith("\n") else "\n")
        return 0
    if argv:
        print(
            f"tw2002-aiclient: unexpected argument: {argv[0]!r}",
            file=sys.stderr,
        )
        print("Try 'tw2002-aiclient --help' for usage.", file=sys.stderr)
        return 2
    try:
        curses.wrapper(_run)
    except DeadTerminalError as exc:
        # curses.wrapper's own `finally` (no `except` -- see its source)
        # has already restored the terminal by the time this runs, so
        # _report_dead_terminal's print reaches the operator's own
        # remaining terminal (a not-yet-fully-dropped ssh session) or a
        # log -- never a raw traceback for what is an environment
        # condition (WO-TUI-DEAD-TERMINAL-SPIN), not an app bug.
        _report_dead_terminal(exc)
    return 0
