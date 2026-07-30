"""WO-PLAY-CHAIN-BUBBLE-VIZ — bubbles paint under the viewport without ``L``.

Structural + draw pins: the chain region appears when geometry allows, the
cached best chain reaches the strip, and the draw path never imports
``chain_search``.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tw2002_aiclient import screens as screens_mod
from tw2002_aiclient.chain_status import ChainScalars
from tw2002_aiclient.cockpit.layout import CHAIN_VIZ_H, frame_layout
from tw2002_aiclient.cockpit import chain_bubbles


class _Chain:
    def __init__(self, sectors):
        self.sectors = tuple(sectors)


class _Result:
    def __init__(self, chains):
        self.chains = tuple(chains)
        self.reason = None
        self.truncated = False


class _Win:
    def __init__(self, rows=40, cols=160):
        self._r, self._c = rows, cols
        self.writes: list[tuple[int, int, str]] = []

    def getmaxyx(self):
        return (self._r, self._c)

    def erase(self):
        pass

    def refresh(self):
        pass

    def addstr(self, y, x, s, attr=0):
        self.writes.append((y, x, s))

    def addnstr(self, y, x, s, n, attr=0):
        self.writes.append((y, x, s[:n]))

    def attron(self, a):
        pass

    def attroff(self, a):
        pass

    def hline(self, *a, **k):
        pass

    def vline(self, *a, **k):
        pass

    def border(self, *a, **k):
        pass

    def chgat(self, *a, **k):
        pass


def _screen(monkeypatch, win, *, status):
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="a", handle="A", server="s", host="h", game_letter="B"
    )
    s = screens_mod.PlayShellScreen(win, profile)
    s.spectating, s.attached = False, False
    s.status_provider = lambda: status
    return s


def _region_text(win, region):
    if region is None:
        return ""
    lo, hi = region["y"], region["y"] + region["h"]
    return "".join(t for (y, _x, t) in win.writes if lo <= y < hi)


def test_bubbles_paint_from_cached_best_chain_without_pressing_l(monkeypatch):
    win = _Win(40, 160)
    play = _screen(
        monkeypatch,
        win,
        status={
            "ok": True,
            "connected": True,
            "classification": "main_command",
            "hud": {"sector": {"value": 10, "age_s": 0.0}},
            "log_tail": ["app> line"],
        },
    )
    play.chain_scalars.update(
        _Result([_Chain([10, 11, 12, 10])])
    )
    play.draw()
    regions = frame_layout(40, 160)
    text = _region_text(win, regions["chain"])
    assert regions["chain"] is not None
    assert regions["chain"]["h"] == CHAIN_VIZ_H
    assert "10" in text
    assert "★" in text


def test_draw_path_does_not_import_chain_search():
    """Accept #4 — structural pin against draw-path recompute."""
    src = Path(screens_mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    assert "chain_search" not in imports
    assert "world_model" not in imports
    # Composer is pure; screens may import it.
    assert chain_bubbles.CHAIN_VIZ_H == 5


def test_short_terminal_folds_chain_and_keeps_viewport():
    regions = frame_layout(34, 160)
    assert regions["chain"] is None
    assert regions["center"]["h"] == 27
    assert regions["center"]["border"] is True
