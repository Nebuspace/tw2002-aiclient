"""Pre-cockpit launcher screens (WO-P1-010 / WO-P1-011).

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
    error: str | None = None  # parse failure — row stays visible (never dropped)


TITLE = " TW2002 AICLIENT "
SUBTITLE = " SELECT PROFILE "
CREATE_CTA = "Create New Player"


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
    """Branded profile picker: titled list, ↑/↓ selection, ``q`` to quit.

    Always ends with a **Create New Player** CTA. Empty picker = CTA only (cold join).
    Broken profiles keep their ``error`` inline and use a warn tint when color is available.
    """

    def __init__(self, stdscr: curses.window, profiles: Sequence[ProfileRow] | None = None) -> None:
        self.stdscr = stdscr
        self.profiles: list[ProfileRow] = list(profiles or ())
        self.selected = 0  # index into selectable items (profiles + trailing CTA)
        self._chrome = curses.A_NORMAL
        self._warn = curses.A_BOLD
        self._init_colors()

    @property
    def _n_items(self) -> int:
        # profiles (0..n) + Create CTA as last selectable
        return len(self.profiles) + 1

    def _init_colors(self) -> None:
        if not curses.has_colors():
            self._chrome = curses.A_BOLD
            self._warn = curses.A_BOLD | curses.A_UNDERLINE
            return
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        self._chrome = curses.color_pair(1)
        self._warn = curses.color_pair(2) | curses.A_BOLD

    def _is_cta(self, index: int) -> bool:
        return index == len(self.profiles)

    def draw(self) -> None:
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
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
        y = list_top

        # Profile rows (including broken — never silently dropped).
        for i, row in enumerate(self.profiles):
            if y >= max_y - 2:
                break
            selected = i == self.selected
            if row.error:
                label = f"{row.name}  ·  ERROR: {row.error}"
                base = self._warn
            else:
                label = f"{row.name}  ·  {row.handle}  ·  {row.server}"
                if row.game_letter:
                    label += f"  [{row.game_letter}]"
                base = curses.A_NORMAL
            attr = (base | curses.A_REVERSE) if selected else base
            prefix = "▸ " if selected else "  "
            _safe_addstr(self.stdscr, y, 3, prefix + label, attr)
            y += 1

        # Create New Player CTA — sole content when the picker is empty.
        if y < max_y - 2:
            cta_index = len(self.profiles)
            selected = self.selected == cta_index
            attr = curses.A_REVERSE if selected else curses.A_BOLD
            prefix = "▸ " if selected else "  "
            _safe_addstr(self.stdscr, y, 3, prefix + CREATE_CTA, attr)

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
        n = self._n_items
        if key in (curses.KEY_UP, ord("k")):
            self.selected = (self.selected - 1) % n
        elif key in (curses.KEY_DOWN, ord("j")):
            self.selected = (self.selected + 1) % n
        return None
