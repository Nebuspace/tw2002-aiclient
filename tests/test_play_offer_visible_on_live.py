"""WO-PLAY-OFFER-VISIBLE-ON-LIVE — the offer must paint on a LIVE session.

The defect these pins exist for was invisible to every suite in the tree: the
offer was written to `status_line`, which `screens.py` renders ONLY when the
LOGS band has no daemon tail. No fixture ever drove a populated `log_tail`, so
every assertion passed while the live cockpit showed nothing (live prove,
`audit/live-play-ladder-newchar-9795263-20260727T0430Z.md`).

So the load-bearing thing here is the FIXTURE, not the assertion: every test
below supplies real tail content. Written against an empty tail, these would
pass against the broken code -- which is exactly how it shipped.
"""

from __future__ import annotations

from tw2002_aiclient import screens as screens_mod
from tw2002_aiclient.cockpit.layout import frame_layout
from tw2002_aiclient.cockpit.teachband import compose_teach_band

ROWS, COLS = 40, 160
OFFER = "explore 3/5…"   # a LIVE run reading — what canon lets claim the band
TAIL = [f"app> line {i}" for i in range(1, 9)]


class _Win:
    def __init__(self, rows=ROWS, cols=COLS):
        self._r, self._c = rows, cols
        self.writes: list[tuple[int, int, str]] = []

    def getmaxyx(self): return (self._r, self._c)
    def erase(self): pass
    def refresh(self): pass
    def addstr(self, y, x, s, attr=0): self.writes.append((y, x, s))
    def addnstr(self, y, x, s, n, attr=0): self.writes.append((y, x, s[:n]))
    def attron(self, a): pass
    def attroff(self, a): pass
    def hline(self, *a, **k): pass
    def vline(self, *a, **k): pass
    def border(self, *a, **k): pass
    def chgat(self, *a, **k): pass


def _screen(monkeypatch, win, *, tail, band=OFFER):
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="a", handle="A", server="s", host="h", game_letter="B")
    s = screens_mod.PlayShellScreen(win, profile)
    s.spectating, s.attached = False, False
    # THE fixture that matters: a live session with real transcript rows.
    s.status_provider = lambda: {"ok": True, "connected": True, "log_tail": list(tail)}
    s.status_line = "session ready — main_command"
    s.explore_band = band
    return s


def _strip_text(win, rows=ROWS, cols=COLS):
    region = frame_layout(rows, cols)["control_strip"]
    lo, hi = region["y"], region["y"] + region["h"]
    return "".join(t for (y, _x, t) in win.writes if lo <= y < hi)


def _logs_text(win, rows=ROWS, cols=COLS):
    region = frame_layout(rows, cols)["logs"]
    lo, hi = region["y"], region["y"] + region["h"]
    return "".join(t for (y, _x, t) in win.writes if lo <= y < hi)



def test_the_transcript_is_untouched(monkeypatch) -> None:
    """Constraint: not 'status_line replaces LOGS'. The band never had to
    give anything up, because the offer went to the control strip instead."""
    win = _Win()
    _screen(monkeypatch, win, tail=TAIL).draw()
    assert "app> line 8" in _logs_text(win), "transcript lost"



def test_calm_band_returns_when_nothing_is_claimed(monkeypatch) -> None:
    win = _Win()
    _screen(monkeypatch, win, tail=TAIL, band=None).draw()
    strip = _strip_text(win)
    assert compose_teach_band() in strip
    assert "press E" not in strip


def test_progress_text_paints_the_same_way(monkeypatch) -> None:
    """L4's live readout uses the same seam, so it inherits the fix."""
    win = _Win()
    _screen(monkeypatch, win, tail=TAIL, band="explore 3/5…").draw()
    assert "explore 3/5" in _strip_text(win)



def test_band_is_released_when_the_run_reaches_a_terminal_outcome(monkeypatch) -> None:
    """A stale `explore 3/5…` left frozen on the band after the run ends is a
    live-looking run that is not running — the same honesty failure as a
    freeze detector that reports healthy."""
    from tw2002_aiclient import app as app_mod

    win = _Win()
    play = _screen(monkeypatch, win, tail=TAIL, band="explore 3/5…")
    monkeypatch.setattr(
        app_mod.adapters, "explore_status",
        lambda **kw: _R(raw={"run": {"distinct_sectors": 5, "min_sectors": 5,
                                     "outcome": "completed"}}),
    )
    keep = app_mod._poll_explore_status(play, run_dir=None)
    assert keep is False
    assert play.explore_band is None, "stale claim survived a completed run"


def test_band_is_released_when_the_status_reading_is_unavailable(monkeypatch) -> None:
    """No evidence must not render as a healthy run."""
    from tw2002_aiclient import app as app_mod

    win = _Win()
    play = _screen(monkeypatch, win, tail=TAIL, band="explore 3/5…")
    monkeypatch.setattr(
        app_mod.adapters, "explore_status",
        lambda **kw: _R(ok=False, reason="daemon_not_running"),
    )
    assert app_mod._poll_explore_status(play, run_dir=None) is False
    assert play.explore_band is None


def test_band_keeps_the_claim_while_the_run_is_still_going(monkeypatch) -> None:
    """The release must not become an excuse to drop a live reading."""
    from tw2002_aiclient import app as app_mod

    win = _Win()
    play = _screen(monkeypatch, win, tail=TAIL, band="explore 0/5…")
    monkeypatch.setattr(
        app_mod.adapters, "explore_status",
        lambda **kw: _R(raw={"run": {"distinct_sectors": 3, "min_sectors": 5}}),
    )
    assert app_mod._poll_explore_status(play, run_dir=None) is True
    assert "3/5" in (play.explore_band or "")
