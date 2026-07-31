"""The List Loops overlay actually REACHES THE SCREEN (WO-LOOPS-POPUP-OVERLAY).

Separate from `tests/test_play_chains_arm.py` on purpose: that file drives
the real `_run_play` but stubs `draw()` to keep a fake stdscr out of curses
paint paths, so every assertion in it would stay green against a popup that
renders nothing at all. A composer with passing unit tests and no wire to
the screen is the failure this file exists to make impossible.

Same `_Win` recording harness the confirm-gate's own visibility tests use.
"""

from __future__ import annotations

import curses

import pytest

from tw2002_aiclient import screens as screens_mod
from tw2002_aiclient.cockpit import chains

FULL_ROWS, FULL_COLS = 40, 180


class _Win:
    def __init__(self, rows=FULL_ROWS, cols=FULL_COLS):
        self._rows, self._cols = rows, cols
        self.writes: list[tuple[int, int, str, int]] = []

    def getmaxyx(self): return (self._rows, self._cols)
    def erase(self): pass
    def refresh(self): pass
    def addstr(self, y, x, s, attr=0): self.writes.append((y, x, s, attr))
    def addnstr(self, y, x, s, n, attr=0): self.writes.append((y, x, s[:n], attr))
    def attron(self, a): pass
    def attroff(self, a): pass
    def hline(self, *a, **k): pass
    def vline(self, *a, **k): pass
    def border(self, *a, **k): pass
    def chgat(self, *a, **k): pass


def _screen(monkeypatch, win):
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    s = screens_mod.PlayShellScreen(win, profile)
    s.spectating = False
    s.attached = False
    s.status_provider = lambda: None
    return s


ROWS = [
    {"name": "ore-run-K7", "steps": 12},
    {"name": "fuel-shuttle", "steps": 8},
]


def _painted(win) -> str:
    return "\n".join(text for (_y, _x, text, _a) in win.writes)


def test_a_closed_popup_paints_nothing(monkeypatch) -> None:
    """The control: the macro names must not be on screen until L opens it.
    Without this, the visibility assertion below could pass against a popup
    that is always drawn."""
    win = _Win()
    s = _screen(monkeypatch, win)
    s.draw()
    assert "ore-run-K7" not in _painted(win)


def test_an_open_popup_reaches_the_screen(monkeypatch) -> None:
    win = _Win()
    s = _screen(monkeypatch, win)
    s.chains_session.open(ROWS, "ok")
    s.draw()
    body = _painted(win)
    assert chains.TITLE == "List Loops"
    assert chains.TITLE in body, "the List Loops overlay title never reached the screen"
    assert "ore-run-K7" in body
    assert "fuel-shuttle" in body


def test_the_selected_row_is_marked_on_screen(monkeypatch) -> None:
    """Canon's `▸` selected/armed row marker has to be visible, not merely
    returned by the composer -- the operator picks which macro spends live
    turns by reading exactly this."""
    win = _Win()
    s = _screen(monkeypatch, win)
    s.chains_session.open(ROWS, "ok")
    s.chains_session.move(1)
    s.draw()
    marked = [t for (_y, _x, t, _a) in win.writes if chains.SELECTED_UNICODE in t]
    assert marked, "no selection marker painted"
    assert any("fuel-shuttle" in t for t in marked), (
        "the marker is on screen but not on the selected row"
    )


def test_an_unreadable_store_does_not_paint_the_empty_placeholder(monkeypatch) -> None:
    win = _Win()
    s = _screen(monkeypatch, win)
    s.chains_session.open([], "unreadable")
    s.draw()
    body = _painted(win)
    assert chains.EMPTY_TEXT not in body
    assert chains.UNKNOWN in body


def test_the_confirm_line_still_paints_over_an_open_popup(monkeypatch) -> None:
    """Draw order: the popup is painted BEFORE the confirm gate, so the one
    prompt that spends live turns is never covered by the list that raised
    it."""
    win = _Win()
    s = _screen(monkeypatch, win)
    s.chains_session.open(ROWS, "ok")
    s.begin_arm_confirm("Arm ore-run-K7 — one pass, 12 steps")
    s.draw()
    assert any("LIVE?" in t for (_y, _x, t, _a) in win.writes), (
        "the confirm line was lost behind the popup"
    )


def test_a_raising_composer_closes_the_popup_rather_than_leaving_it_blind(
    monkeypatch,
) -> None:
    """If the body cannot be composed, an OPEN popup would still route Enter
    to `chains_arm` while showing the operator nothing to select from. The
    draw path closes it instead."""
    monkeypatch.setattr(
        chains, "compose_chain_lines",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    win = _Win()
    s = _screen(monkeypatch, win)
    s.chains_session.open(ROWS, "ok")
    s.draw()
    assert s.chains_session.is_open is False
