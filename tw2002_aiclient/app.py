"""Curses app entry — routes a real TTY into the pre-cockpit launcher (WO-P1-010/011)."""

from __future__ import annotations

import os

import curses

from tw2002_aiclient.screens import LauncherScreen, ProfileRow


def _load_profiles() -> list[ProfileRow]:
    """Resolve launcher rows for smoke / fixtures (no credentials module yet).

    Env fixtures (disclose in STATUS):
    - ``TW2002_LAUNCHER_FIXTURE=broken`` — one broken row (missing game_letter) + healthy CTA
    - ``TW2002_LAUNCHER_DEMO=1`` — two healthy demo rows
    - default — empty list (cold join → Create CTA only)
    """
    fixture = os.environ.get("TW2002_LAUNCHER_FIXTURE", "").strip().lower()
    if fixture == "broken":
        return [
            ProfileRow(
                name="broken-pilot",
                handle="?",
                server="?",
                error="missing game_letter",
            )
        ]
    if os.environ.get("TW2002_LAUNCHER_DEMO") == "1":
        return [
            ProfileRow(name="alpha", handle="Alpha", server="demo-a", game_letter="B"),
            ProfileRow(name="bravo", handle="Bravo", server="demo-b", game_letter="B"),
        ]
    return []


def _run(stdscr: curses.window) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(-1)
    screen = LauncherScreen(stdscr, profiles=_load_profiles())
    # Automated smoke: draw once and exit clean (hub/script verify without interactive input).
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
