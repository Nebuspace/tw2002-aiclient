"""Curses app entry — launcher ↔ create form ↔ play shell (WO-P1-010…016)."""

from __future__ import annotations

import os

import curses

from tw2002_aiclient import adapters
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
from tw2002_aiclient.watchfeed import WatchFeed


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
    while True:
        form.draw()
        key = stdscr.getch()
        if key == -1:
            continue
        action = form.handle_key(key)
        if action in ("saved", "cancel"):
            return action


# Ctrl-] (ASCII 29, the classic telnet escape) is canon's own designated
# graceful detach key -- `spectate-and-attach.md:100-102` ("The detach key
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


def _run_play(stdscr: curses.window, profile: ProfileRow) -> str:
    """Bind profile to a fresh play-shell placeholder; Esc ends the binding."""
    run_dir = env.resolve_run_dir()
    play = PlayShellScreen(stdscr, profile)
    play.status_provider = _daemon_status_provider(run_dir)
    play.status_line = "Ensuring session…"
    play.draw()  # show the ensuring state during the (blocking) wait below
    # no_auto_arm=True: ensure only reaches main_command and stops, even if
    # the profile itself enables autopilot -- no surprise auto-arm here.
    result = adapters.ensure_session(profile.name, no_auto_arm=True)
    if result.ok:
        play.status_line = f"session ready — {result.classification}"
    else:
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
    try:
        while True:
            play.draw()
            key = stdscr.getch()
            if key == -1:
                continue
            if attach_conn is not None and key != 27:
                # Attached: canon `mode-line-and-teach-controls.md:42-44`
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
                # canon `spectate-and-attach.md:100-102` names Ctrl-]
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
                    # `spectate-and-attach.md:91-96`) -- never a new
                    # wire verb of our own; detach is a close, never a
                    # send.
                    attach_conn.close()
                    attach_conn = None
                    play.spectating = True
                    play.attached = False  # WO-P5-060 lane B: honest badge truth, alongside spectating
                    play.status_line = "detached — spectating"
                    continue
                if key in (curses.KEY_ENTER, 10, 13):
                    sent_ok = attach_conn.send_key(b"\r\n")
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
                elif 0 <= key < 256:
                    sent_ok = attach_conn.send_key(bytes([key]))
                else:
                    # Every OTHER curses special key (arrow/function key
                    # etc.) has no single-byte raw form to forward --
                    # silently dropped rather than sending garbage. Hub
                    # ruling: explicitly acceptable to leave unforwarded
                    # this WO, disclosed here and in STATUS, unlike
                    # backspace above.
                    sent_ok = True
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
    while True:
        bank.draw()
        key = stdscr.getch()
        if key == -1:
            continue
        action = bank.handle_key(key)
        if action in ("back", "quit"):
            return action


def _run(stdscr: curses.window) -> None:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)
    stdscr.timeout(-1)
    screen = LauncherScreen(stdscr, profiles=_load_profiles())
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
    while True:
        screen.draw()
        key = stdscr.getch()
        if key == -1:
            continue
        action = screen.handle_key(key)
        if action == "quit":
            break
        if action == "bank":
            result = _run_bank(stdscr)
            if result == "quit":
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
                break
            try:
                curses.curs_set(0)
            except curses.error:
                pass


def main() -> int:
    curses.wrapper(_run)
    return 0
