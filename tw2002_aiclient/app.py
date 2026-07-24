"""Curses app entry — routes a real TTY into the pre-cockpit launcher (WO-P1-010)."""

from __future__ import annotations

import curses

from tw2002_aiclient.screens import LauncherScreen, ProfileRow


def _demo_profiles() -> list[ProfileRow]:
    """Optional smoke rows when TW2002_LAUNCHER_DEMO=1 (no credentials / no passwords)."""
    import os

    if os.environ.get("TW2002_LAUNCHER_DEMO") != "1":
        return []
    return [
        ProfileRow(name="alpha", handle="Alpha", server="demo-a"),
        ProfileRow(name="bravo", handle="Bravo", server="demo-b"),
    ]


def _run(stdscr: curses.window) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(-1)
    screen = LauncherScreen(stdscr, profiles=_demo_profiles())
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
