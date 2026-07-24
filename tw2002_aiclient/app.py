"""Curses app entry — routes a real TTY into the pre-cockpit launcher (WO-P1-010)."""

from __future__ import annotations

import curses

from tw2002_aiclient.screens import LauncherScreen, ProfileRow


def _demo_profiles() -> list[ProfileRow]:
    """Optional smoke rows when TW2002_LAUNCHER_DEMO=1 (local stubs only)."""
    import os

    if os.environ.get("TW2002_LAUNCHER_DEMO") != "1":
        return []
    return [
        ProfileRow(name="alpha", handle="Alpha", server="demo-a"),
        ProfileRow(name="bravo", handle="Bravo", server="demo-b"),
    ]


def _run(stdscr: curses.window) -> None:
    import os

    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(-1)
    screen = LauncherScreen(stdscr, profiles=_demo_profiles())
    # Automated smoke: draw once and exit clean (hub/pty verify without interactive input).
    if os.environ.get("TW2002_LAUNCHER_SMOKE") == "1":
        screen.draw()
        return
    while True:
        screen.draw()
        key = stdscr.getch()
        if key == -1:
            continue
        action = screen.handle_key(key)
        if action == "quit":
            break


def main() -> int:
    curses.wrapper(_run)
    return 0
