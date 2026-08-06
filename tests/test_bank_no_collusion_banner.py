"""Pin: BankViewScreen paints the no-collusion boundary at the rotation touchpoint."""

from __future__ import annotations

import curses

from tw2002_aiclient.screens import (
    BOUNDARY_LINE_1,
    BOUNDARY_LINE_2,
    BankViewScreen,
)


class _RecordingStdscr:
    def __init__(self, rows: int = 24, cols: int = 100) -> None:
        self._rows = rows
        self._cols = cols
        self.texts: list[str] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self._rows, self._cols

    def erase(self) -> None:
        self.texts = []

    def refresh(self) -> None:
        pass

    def attron(self, _attr: int) -> None:
        pass

    def attroff(self, _attr: int) -> None:
        pass

    def box(self, *_a) -> None:
        pass

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.texts.append(text)


def test_bank_view_paints_no_collusion_boundary_lines(monkeypatch) -> None:
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    stdscr = _RecordingStdscr()
    BankViewScreen(stdscr, entries=()).draw()
    joined = "\n".join(stdscr.texts)
    assert BOUNDARY_LINE_1 in joined
    assert BOUNDARY_LINE_2 in joined
