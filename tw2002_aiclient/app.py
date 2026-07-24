"""Curses app entry — launcher ↔ create form ↔ play shell (WO-P1-010…016)."""

from __future__ import annotations

import os

import curses

from tw2002_aiclient.screens import (
    CreateFormScreen,
    LauncherScreen,
    PlayShellScreen,
    ProfileRow,
)
from tw2002_aiclient.session import credentials


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
                error=summary.get("error"),  # type: ignore[arg-type]
            )
        )
    return rows


def _load_profiles() -> list[ProfileRow]:
    """Resolve launcher rows: fixtures override disk for automated Proof.

    Env fixtures (disclose in STATUS):
    - ``TW2002_LAUNCHER_FIXTURE=broken`` — one broken row + healthy CTA
    - ``TW2002_LAUNCHER_FIXTURE=worldid`` — two same host+letter, different handle
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


def _run_play(stdscr: curses.window, profile: ProfileRow) -> str:
    """Bind profile to a fresh play-shell placeholder; Esc ends the binding."""
    play = PlayShellScreen(stdscr, profile)
    while True:
        play.draw()
        key = stdscr.getch()
        if key == -1:
            continue
        action = play.handle_key(key)
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
    while True:
        screen.draw()
        key = stdscr.getch()
        if key == -1:
            continue
        action = screen.handle_key(key)
        if action == "quit":
            break
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
