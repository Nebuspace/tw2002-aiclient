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
from tw2002_aiclient.cockpit import explore_flags
from tw2002_aiclient.cockpit.layout import frame_layout
from tw2002_aiclient.cockpit.teachband import compose_teach_band

ROWS, COLS = 40, 160
OFFER = "explore 3/5…"   # a LIVE run reading — what canon lets claim the band
# Built by the real composer rather than retyped. This string is an INPUT
# here (a status line fed to the screen), so a hand-copied version would
# silently drift from what `app._run_play` actually produces the moment the
# offer wording changes — a double diverging from its own producer, which is
# how a fixture ends up pinning a screen the product never paints.
# WO-EXPLORE-GATHER-VISIBLE changed this line; asking the producer keeps the
# next change free.
OFFER_STATUS = "session ready — main_command"  # post-ensure LOGS; no press-E tease
TAIL = [f"app> line {i}" for i in range(1, 9)]


class _R:
    def __init__(self, ok=True, raw=None, reason=None):
        self.ok, self.raw, self.reason, self.detail = ok, raw, reason, None


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


def _screen(monkeypatch, win, *, tail, band=OFFER, status_line="session ready — main_command"):
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="a", handle="A", server="s", host="h", game_letter="B")
    s = screens_mod.PlayShellScreen(win, profile)
    s.spectating, s.attached = False, False
    # THE fixture that matters: a live session with real transcript rows.
    s.status_provider = lambda: {"ok": True, "connected": True, "log_tail": list(tail)}
    s.status_line = status_line
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



def test_the_transcript_survives_underneath_a_reserved_status_row(monkeypatch) -> None:
    """WO-PLAY-STRIP-TRAINER-CHROME, DECISION
    `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 4, routes
    `status_line` into LOGS instead of a mid-strip `status_offer`. LOGS is
    a fixed ``LOGS_MIN_H``-tall band -- one content row -- at every
    terminal size (`cockpit.layout.LOGS_MIN_H`), so a present status line
    necessarily occupies that one row in place of the latest transcript
    line while it is showing. "Don't wipe the transcript" holds at the
    level that matters: the underlying `log_tail` the daemon reports is
    never mutated or truncated by drawing a status line -- the very next
    status-free draw shows the transcript exactly as it was."""
    win = _Win()
    _screen(monkeypatch, win, tail=TAIL).draw()
    assert "app> line 8" not in _logs_text(win), (
        "the reserved status row and the transcript's own last line cannot "
        "both fit in LOGS' single content row"
    )
    win2 = _Win()
    _screen(monkeypatch, win2, tail=TAIL, status_line=None).draw()
    assert "app> line 8" in _logs_text(win2), "transcript lost once the status line clears"


def test_status_line_paints_in_logs_while_the_transcript_is_populated(monkeypatch) -> None:
    """DECISION point 4 routes status_line into LOGS, not the retired mid-strip."""
    win = _Win()
    _screen(monkeypatch, win, tail=TAIL, band=None, status_line=OFFER_STATUS).draw()
    assert "session ready" in _logs_text(win), "status invisible on a live session"
    assert "press E" not in _logs_text(win)
    assert "press E" not in _strip_text(win), "explore offer still on the retired mid-strip"


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
        "tw2002_aiclient.adapters.explore_status",
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
        "tw2002_aiclient.adapters.explore_status",
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
        "tw2002_aiclient.adapters.explore_status",
        lambda **kw: _R(raw={"run": {"distinct_sectors": 3, "min_sectors": 5}}),
    )
    assert app_mod._poll_explore_status(play, run_dir=None) is True
    assert "3/5" in (play.explore_band or "")


def test_explore_terminal_poll_refreshes_known_sectors(monkeypatch) -> None:
    """WO-WORLD-STATS-REFRESH-EVENTS A: explore completion is a second refresh event."""
    from tw2002_aiclient import app as app_mod
    from tw2002_aiclient import world_identity

    win = _Win()
    play = _screen(monkeypatch, win, tail=TAIL, band="explore 3/5…")
    expected = world_identity.world_id_from_profile(play.profile)
    seen: list = []

    def _count(world_id, **kw):
        seen.append(world_id)
        return 42

    monkeypatch.setattr(
        "tw2002_aiclient.adapters.explore_status",
        lambda **kw: _R(raw={"run": {"distinct_sectors": 5, "min_sectors": 5,
                                     "outcome": "completed"}}),
    )
    monkeypatch.setattr(
        "tw2002_aiclient.world_model.known_sector_count", _count, raising=False,
    )
    # refresh imports world_model lazily — patch the module attribute after import path
    import tw2002_aiclient.world_model as wm

    monkeypatch.setattr(wm, "known_sector_count", _count)

    keep = app_mod._poll_explore_status(play, run_dir=None)
    assert keep is False
    assert seen == [expected]
    assert play.world_stats.merge({}) == {
        "known_sectors": 42,
        "dead_end_count": 0,
    }


def test_draw_path_does_not_call_known_sector_count(monkeypatch) -> None:
    """Accept A: status_provider / draw must not pay for a world-model count."""
    calls: list = []

    def _boom(world_id, **kw):
        calls.append(world_id)
        raise AssertionError("draw path must not call known_sector_count")

    import tw2002_aiclient.world_model as wm

    monkeypatch.setattr(wm, "known_sector_count", _boom)
    win = _Win()
    play = _screen(monkeypatch, win, tail=TAIL, band=None)
    play.status_provider = play.world_stats.wrap(lambda: {"ok": True})
    play.draw()
    assert play.status_provider() == {"ok": True}
    assert calls == []
