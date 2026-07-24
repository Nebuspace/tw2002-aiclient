"""Curses app entry — launcher ↔ create form ↔ play shell (WO-P1-010…016)."""

from __future__ import annotations

import os

import curses

from tw2002_aiclient import adapters
from tw2002_aiclient.screens import (
    BankViewScreen,
    CreateFormScreen,
    LauncherScreen,
    PlayShellScreen,
    ProfileRow,
)
from tw2002_aiclient.session import cli as session_cli
from tw2002_aiclient.session import credentials, env, player_bank
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
    try:
        while True:
            play.draw()
            key = stdscr.getch()
            if key == -1:
                continue
            action = play.handle_key(key)
            if action in ("back", "quit"):
                return action
    finally:
        feed.stop()
        stdscr.timeout(-1)  # restore blocking getch for the caller's own loop


def _run_bank(stdscr: curses.window) -> str:
    bank = BankViewScreen(stdscr, entries=player_bank.list_players())
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
            BankViewScreen(stdscr, entries=player_bank.list_players()).draw()
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
