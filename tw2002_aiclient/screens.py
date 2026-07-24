"""Pre-cockpit launcher screens (WO-P1-010).

Credentials/secrets are never collected or shown on this surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import curses


@dataclass(frozen=True)
class ProfileRow:
    """Non-secret profile summary for the picker (name/handle/server only)."""

    name: str
    handle: str
    server: str
    game_letter: str = ""


TITLE = " TW2002 AICLIENT "
SUBTITLE = " SELECT PROFILE "


def _safe_addstr(win: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    try:
        max_y, max_x = win.getmaxyx()
        if y < 0 or y >= max_y or x >= max_x:
            return
        clipped = text[: max(0, max_x - x - 1)]
        if clipped:
            win.addstr(y, x, clipped, attr)
    except curses.error:
        pass


class LauncherScreen:
    """Branded profile picker: titled list, ↑/↓ selection, ``q`` to quit."""

    def __init__(self, stdscr: curses.window, profiles: Sequence[ProfileRow] | None = None) -> None:
        self.stdscr = stdscr
        self.profiles: list[ProfileRow] = list(profiles or ())
        self.selected = 0
        self._chrome = curses.A_NORMAL
        self._init_colors()

    def _init_colors(self) -> None:
        if not curses.has_colors():
            self._chrome = curses.A_BOLD
            return
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        self._chrome = curses.color_pair(1)

    def draw(self) -> None:
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        # Outer thin box (cyan chrome) — titled.
        if max_y >= 3 and max_x >= 10:
            try:
                self.stdscr.attron(self._chrome)
                self.stdscr.box()
                self.stdscr.attroff(self._chrome)
            except curses.error:
                pass
            _safe_addstr(self.stdscr, 0, 2, TITLE, self._chrome | curses.A_BOLD)
            _safe_addstr(self.stdscr, 1, 2, SUBTITLE, self._chrome)

        list_top = 3
        if not self.profiles:
            _safe_addstr(
                self.stdscr,
                list_top,
                4,
                "(no profiles yet — create flow is a later WO)",
                curses.A_DIM,
            )
        else:
            for i, row in enumerate(self.profiles):
                y = list_top + i
                if y >= max_y - 2:
                    break
                label = f"{row.name}  ·  {row.handle}  ·  {row.server}"
                if row.game_letter:
                    label += f"  [{row.game_letter}]"
                attr = curses.A_REVERSE if i == self.selected else curses.A_NORMAL
                prefix = "▸ " if i == self.selected else "  "
                _safe_addstr(self.stdscr, y, 3, prefix + label, attr)

        _safe_addstr(
            self.stdscr,
            max_y - 2,
            3,
            "↑/↓ select   q quit",
            self._chrome,
        )
        self.stdscr.refresh()

    def handle_key(self, key: int) -> str | None:
        """Return ``\"quit\"`` to leave the launcher, else ``None``."""
        if key in (ord("q"), ord("Q")):
            return "quit"
        if not self.profiles:
            return None
        if key in (curses.KEY_UP, ord("k")):
            self.selected = (self.selected - 1) % len(self.profiles)
        elif key in (curses.KEY_DOWN, ord("j")):
            self.selected = (self.selected + 1) % len(self.profiles)
        return None
