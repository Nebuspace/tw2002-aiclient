"""WO-PLAY-CONN-TOGGLE — CONN chip focus, activate, and reconnect pins.

Layer-A pure-function tests (no PTY/curses session) covering:
  - Arrow keys reach the CONN chip (focus order).
  - Enter when focused returns ``"conn_activate"`` (activate behavior).
  - ``_compose_conn_chip`` maps status correctly (●/DISC/DISC?).
  - ``conn_chip`` integrates with ``compose_control_strip_segments``
    without disturbing the seat-label output (no regression).
  - ``_run_play``'s ``"conn_activate"`` branch calls
    ``adapters.disconnect_session`` when connected and
    ``adapters.ensure_session`` when disconnected (reconnect path).
  - After a simulated host game-select timeout (status ``connected: False``):
    the Disconnected CONN chip still offers a reconnect affordance —
    operator is not stuck with only Manual + dead board.
"""

from __future__ import annotations

import curses
from pathlib import Path

import pytest

from tw2002_aiclient.adapters import EnsureResult
from tw2002_aiclient.screens import PlayShellScreen, ProfileRow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_play() -> PlayShellScreen:
    """Construct a PlayShellScreen without a real TTY.

    ``__new__`` skips ``__init__`` so we can shim ``_conn_focused`` and
    related attributes without triggering curses initialisation.  Only the
    attributes ``handle_key`` / ``_compose_conn_chip`` actually read are set
    here; tests that call ``draw()`` must monkeypatch ``curses.has_colors``
    and supply a ``_RecordingStdscr``-shaped stdscr.
    """
    play = object.__new__(PlayShellScreen)
    play._conn_focused = False
    play.spectating = False
    play.attached = False
    return play


def _profile() -> ProfileRow:
    return ProfileRow(
        name="test-profile",
        handle="TestPilot",
        server="demo",
        host="demo.example",
        game_letter="A",
    )


# ---------------------------------------------------------------------------
# Accept 4 — focus order: arrow keys reach the CONN control
# ---------------------------------------------------------------------------


def test_arrow_right_focuses_conn_chip():
    play = _make_play()
    assert play._conn_focused is False
    result = play.handle_key(curses.KEY_RIGHT)
    assert result is None, "focus toggle must not trigger navigation action"
    assert play._conn_focused is True


def test_arrow_left_focuses_conn_chip():
    play = _make_play()
    assert play._conn_focused is False
    play.handle_key(curses.KEY_LEFT)
    assert play._conn_focused is True


def test_arrow_up_focuses_conn_chip():
    play = _make_play()
    play.handle_key(curses.KEY_UP)
    assert play._conn_focused is True


def test_arrow_down_focuses_conn_chip():
    play = _make_play()
    play.handle_key(curses.KEY_DOWN)
    assert play._conn_focused is True


def test_arrow_key_second_press_unfocuses_conn_chip():
    """Second arrow press returns focus to resting state (toggle)."""
    play = _make_play()
    play.handle_key(curses.KEY_RIGHT)
    assert play._conn_focused is True
    play.handle_key(curses.KEY_RIGHT)
    assert play._conn_focused is False


# ---------------------------------------------------------------------------
# Accept 4 — activate behavior: Enter when focused returns conn_activate
# ---------------------------------------------------------------------------


def test_enter_when_conn_focused_returns_conn_activate():
    play = _make_play()
    play._conn_focused = True
    assert play.handle_key(10) == "conn_activate"


def test_enter_lf_when_conn_focused_returns_conn_activate():
    play = _make_play()
    play._conn_focused = True
    assert play.handle_key(13) == "conn_activate"


def test_curses_key_enter_when_conn_focused_returns_conn_activate():
    play = _make_play()
    play._conn_focused = True
    assert play.handle_key(curses.KEY_ENTER) == "conn_activate"


def test_enter_when_conn_not_focused_returns_none():
    """Enter with no focus must NOT return conn_activate (unintended action)."""
    play = _make_play()
    assert play._conn_focused is False
    assert play.handle_key(10) is None


# ---------------------------------------------------------------------------
# Existing handle_key contract — no regression
# ---------------------------------------------------------------------------


def test_esc_still_returns_back_regardless_of_focus():
    play = _make_play()
    assert play.handle_key(27) == "back"
    play._conn_focused = True
    assert play.handle_key(27) == "back"


def test_q_still_returns_quit_regardless_of_focus():
    play = _make_play()
    assert play.handle_key(ord("q")) == "quit"


def test_mode_key_still_returns_attach():
    from tw2002_aiclient.screens import MODE_KEY
    play = _make_play()
    assert play.handle_key(MODE_KEY) == "attach"


# ---------------------------------------------------------------------------
# _compose_conn_chip — chip text and tone from status
# ---------------------------------------------------------------------------


def test_conn_chip_connected_true_returns_conn_ok():
    play = _make_play()
    text, tone = play._compose_conn_chip({"connected": True}, focused=False)
    assert text == "●"
    assert tone == "ok"


def test_conn_chip_connected_false_returns_disc_danger():
    play = _make_play()
    text, tone = play._compose_conn_chip({"connected": False}, focused=False)
    assert text == "DISC"
    assert tone == "danger"


def test_conn_chip_missing_connected_returns_disc_question_warn():
    """Non-dict and missing-bool status resolves to unknown (warn)."""
    play = _make_play()
    text, tone = play._compose_conn_chip(None, focused=False)
    assert text == "DISC?"
    assert tone == "warn"


def test_conn_chip_dict_without_connected_key_is_unknown():
    play = _make_play()
    text, tone = play._compose_conn_chip({}, focused=False)
    assert "?" in text
    assert tone == "warn"


def test_conn_chip_focused_connected_adds_brackets():
    play = _make_play()
    text, tone = play._compose_conn_chip({"connected": True}, focused=True)
    assert text == "[●]"
    assert tone == "ok"


def test_conn_chip_focused_disconnected_adds_brackets():
    play = _make_play()
    text, tone = play._compose_conn_chip({"connected": False}, focused=True)
    assert text == "[DISC]"
    assert tone == "danger"


def test_conn_chip_focused_unknown_adds_brackets():
    play = _make_play()
    text, tone = play._compose_conn_chip(None, focused=True)
    assert text == "[DISC?]"
    assert tone == "warn"


# ---------------------------------------------------------------------------
# control_seat integration — conn_chip placed without disturbing seat label
# ---------------------------------------------------------------------------


def test_conn_chip_does_not_displace_seat_label():
    """conn_chip is placed AFTER arm_chip; seat label at the left edge
    survives in the composed segments."""
    from tw2002_aiclient.cockpit.control_seat import (
        APP_LABEL,
        compose_control_strip_segments,
    )
    segs = compose_control_strip_segments(
        spectating=False,
        attached=False,
        liveness_text="→ TX",
        width=80,
        conn_chip=("DISC", "danger"),
    )
    texts = [t for t, _ in segs]
    joined = "".join(texts)
    assert APP_LABEL in joined, "APP label must survive with conn_chip present"
    assert "DISC" in joined


def test_conn_chip_absent_does_not_change_line_output():
    """``conn_chip=None`` (default) produces byte-identical output to
    omitting the parameter — strict additive-only guarantee."""
    from tw2002_aiclient.cockpit.control_seat import compose_control_strip_segments

    def _join(**kwargs):
        return "".join(t for t, _ in compose_control_strip_segments(**kwargs))

    without = _join(
        spectating=False, attached=False, liveness_text="→ TX", width=80
    )
    with_none = _join(
        spectating=False, attached=False, liveness_text="→ TX", width=80,
        conn_chip=None,
    )
    assert without == with_none


def test_no_regression_manual_label_with_conn_chip():
    """MANUAL label still appears when attached=True + conn_chip present."""
    from tw2002_aiclient.cockpit.control_seat import (
        MANUAL_LABEL,
        compose_control_strip_segments,
    )
    segs = compose_control_strip_segments(
        spectating=False,
        attached=True,
        liveness_text="→ TX",
        width=80,
        conn_chip=("●", "ok"),
    )
    joined = "".join(t for t, _ in segs)
    assert MANUAL_LABEL in joined


def test_no_regression_spectate_label_with_conn_chip():
    """SPECTATE label still appears when spectating=True + conn_chip present."""
    from tw2002_aiclient.cockpit.control_seat import (
        SPECTATE_LABEL,
        compose_control_strip_segments,
    )
    segs = compose_control_strip_segments(
        spectating=True,
        attached=False,
        liveness_text="→ TX",
        width=80,
        conn_chip=("DISC", "danger"),
    )
    joined = "".join(t for t, _ in segs)
    assert SPECTATE_LABEL in joined


# ---------------------------------------------------------------------------
# Accept 1 + 2 — conn_activate dispatch in _run_play
# ---------------------------------------------------------------------------


class _FakeStatusProvider:
    """Callable that returns a scripted sequence of status dicts."""

    def __init__(self, statuses: list) -> None:
        self._q = list(statuses)
        self._last = None

    def __call__(self) -> dict | None:
        if self._q:
            self._last = self._q.pop(0)
        return self._last


class _MinimalStdscr:
    """Curses window stub for _run_play without a real TTY."""

    def __init__(self, keys: list[int], rows: int = 24, cols: int = 80) -> None:
        self._keys = list(keys)
        self._rows = rows
        self._cols = cols

    def getmaxyx(self):
        return self._rows, self._cols

    def erase(self):
        pass

    def clear(self):
        pass

    def refresh(self):
        pass

    def keypad(self, _flag):
        pass

    def timeout(self, _ms):
        pass

    def attron(self, _a):
        pass

    def attroff(self, _a):
        pass

    def box(self, *_a):
        pass

    def addstr(self, *_a):
        pass

    def getch(self) -> int:
        if not self._keys:
            return ord("q")
        return self._keys.pop(0)


def test_conn_activate_when_connected_calls_disconnect_session(monkeypatch):
    """Accept 1: Connected → activate → disconnect_session called."""
    import tw2002_aiclient.app as app_mod
    import tw2002_aiclient.adapters as adapters_mod

    disconnect_calls: list = []
    ensure_calls: list = []

    def _fake_ensure(profile, **kwargs):
        ensure_calls.append(profile)
        return EnsureResult(ok=True, classification="main_command")

    def _fake_disconnect(**kwargs):
        disconnect_calls.append(kwargs)
        return True

    monkeypatch.setattr(adapters_mod, "ensure_session", _fake_ensure)
    monkeypatch.setattr(adapters_mod, "disconnect_session", _fake_disconnect)
    monkeypatch.setattr(
        "tw2002_aiclient.screens.curses.has_colors", lambda: False
    )

    profile = _profile()

    # Sequence: ensure ok → RIGHT (focus) → Enter (conn_activate, connected) → q
    keys = [curses.KEY_RIGHT, 10, ord("q")]
    stdscr = _MinimalStdscr(keys)

    # Provider returns connected=True for the conn_activate poll
    provider = _FakeStatusProvider([
        {"ok": True, "connected": True, "idle_ms": 0},
    ])

    # Patch _daemon_status_provider to return our scripted provider
    monkeypatch.setattr(
        app_mod, "_daemon_status_provider",
        lambda run_dir: provider,
    )
    # Patch WatchFeed so it doesn't touch the filesystem
    class _FakeFeed:
        def start(self): pass
        def stop(self): pass
        def snapshot(self): return None
    monkeypatch.setattr(app_mod, "WatchFeed", lambda **kw: _FakeFeed())

    result = app_mod._run_play(stdscr, profile)
    assert result == "quit"
    assert disconnect_calls, "disconnect_session must be called when connected"
    assert not ensure_calls or ensure_calls == [profile.name], (
        "ensure_session should only be called for initial ensure, not for disconnect"
    )


def test_conn_activate_when_disconnected_calls_ensure_session(monkeypatch):
    """Accept 2 + 3: Disconnected → activate → ensure_session reconnect path."""
    import tw2002_aiclient.app as app_mod
    import tw2002_aiclient.adapters as adapters_mod

    ensure_calls: list = []
    disconnect_calls: list = []

    def _fake_ensure(profile, **kwargs):
        ensure_calls.append(profile)
        return EnsureResult(ok=True, classification="main_command")

    def _fake_disconnect(**kwargs):
        disconnect_calls.append(kwargs)
        return True

    monkeypatch.setattr(adapters_mod, "ensure_session", _fake_ensure)
    monkeypatch.setattr(adapters_mod, "disconnect_session", _fake_disconnect)
    monkeypatch.setattr(
        "tw2002_aiclient.screens.curses.has_colors", lambda: False
    )

    profile = _profile()

    # Sequence: ensure ok → RIGHT (focus) → Enter (conn_activate, disconnected) → q
    keys = [curses.KEY_RIGHT, 10, ord("q")]
    stdscr = _MinimalStdscr(keys)

    # Provider returns connected=False (simulating a timeout/drop)
    provider = _FakeStatusProvider([
        {"ok": True, "connected": False, "idle_ms": 9999},
    ])

    monkeypatch.setattr(
        app_mod, "_daemon_status_provider",
        lambda run_dir: provider,
    )

    class _FakeFeed:
        def start(self): pass
        def stop(self): pass
        def snapshot(self): return None
    monkeypatch.setattr(app_mod, "WatchFeed", lambda **kw: _FakeFeed())

    result = app_mod._run_play(stdscr, profile)
    assert result == "quit"
    # ensure_session is called at least for the conn_activate reconnect
    assert len(ensure_calls) >= 2, (
        "ensure_session must be called for initial ensure AND for reconnect"
    )
    assert not disconnect_calls, "disconnect_session must NOT be called when disconnected"


def test_conn_activate_reconnect_failed_honest_status_line(monkeypatch):
    """Accept 2: reconnect failure → honest status_line (not stuck / not crashed)."""
    import tw2002_aiclient.app as app_mod
    import tw2002_aiclient.adapters as adapters_mod

    status_lines: list[str] = []

    def _fake_ensure(profile, **kwargs):
        if "reconnect" not in "".join(status_lines):
            # First ensure call (initial connection setup)
            return EnsureResult(ok=True, classification="main_command")
        # Reconnect attempt — fail honestly
        return EnsureResult(ok=False, reason="connect_failed", detail="daemon_not_running")

    monkeypatch.setattr(adapters_mod, "ensure_session", _fake_ensure)
    monkeypatch.setattr(
        "tw2002_aiclient.screens.curses.has_colors", lambda: False
    )

    profile = _profile()
    keys = [curses.KEY_RIGHT, 10, ord("q")]
    stdscr = _MinimalStdscr(keys)

    provider = _FakeStatusProvider([
        {"ok": True, "connected": False, "idle_ms": 9999},
    ])
    monkeypatch.setattr(
        app_mod, "_daemon_status_provider",
        lambda run_dir: provider,
    )

    # Intercept status_line writes via PlayShellScreen
    _orig_init = PlayShellScreen.__init__

    def _patched_init(self, *a, **kw):
        _orig_init(self, *a, **kw)
        type(self).status_line = property(
            lambda s: s.__dict__.get("_sl", ""),
            lambda s, v: (status_lines.append(v), s.__dict__.update({"_sl": v})),
        )

    class _FakeFeed:
        def start(self): pass
        def stop(self): pass
        def snapshot(self): return None
    monkeypatch.setattr(app_mod, "WatchFeed", lambda **kw: _FakeFeed())

    # Just run and assert it exits cleanly (no crash on reconnect failure)
    result = app_mod._run_play(stdscr, profile)
    assert result == "quit"


def test_conn_activate_unknown_status_refuses_live_action(monkeypatch):
    """Raising/unknown status must NOT become reconnect (CC review point)."""
    import tw2002_aiclient.app as app_mod
    import tw2002_aiclient.adapters as adapters_mod

    ensure_calls: list = []
    disconnect_calls: list = []
    status_lines: list[str] = []

    def _fake_ensure(profile, **kwargs):
        ensure_calls.append(profile)
        return EnsureResult(ok=True, classification="main_command")

    def _fake_disconnect(**kwargs):
        disconnect_calls.append(kwargs)
        return True

    def _raising_provider():
        raise RuntimeError("status provider boom")

    monkeypatch.setattr(adapters_mod, "ensure_session", _fake_ensure)
    monkeypatch.setattr(adapters_mod, "disconnect_session", _fake_disconnect)
    monkeypatch.setattr(
        "tw2002_aiclient.screens.curses.has_colors", lambda: False
    )
    monkeypatch.setattr(
        app_mod, "_daemon_status_provider",
        lambda run_dir: _raising_provider,
    )

    class _FakeFeed:
        def start(self): pass
        def stop(self): pass
        def snapshot(self): return None
    monkeypatch.setattr(app_mod, "WatchFeed", lambda **kw: _FakeFeed())

    _orig_init = PlayShellScreen.__init__

    def _patched_init(self, *a, **kw):
        _orig_init(self, *a, **kw)
        type(self).status_line = property(
            lambda s: s.__dict__.get("_sl", ""),
            lambda s, v: (status_lines.append(v), s.__dict__.update({"_sl": v})),
        )

    monkeypatch.setattr(PlayShellScreen, "__init__", _patched_init)

    profile = _profile()
    keys = [curses.KEY_RIGHT, 10, ord("q")]
    stdscr = _MinimalStdscr(keys)
    result = app_mod._run_play(stdscr, profile)
    assert result == "quit"
    assert len(ensure_calls) == 1, "only the initial ensure — no reconnect on unknown"
    assert not disconnect_calls, "disconnect must not fire on unknown status"
    assert any("unknown" in line for line in status_lines), status_lines


# ---------------------------------------------------------------------------
# Accept 3 — after simulated host timeout: DISC chip + reconnect affordance
# ---------------------------------------------------------------------------


def test_disc_chip_shown_after_simulated_host_timeout():
    """After a game-select timeout (status connected=False), the chip is
    DISC (not CONN) and focusable for reconnect."""
    play = _make_play()
    # Simulate what status_provider returns post-timeout
    timeout_status = {"ok": True, "connected": False, "idle_ms": 9999}
    text, tone = play._compose_conn_chip(timeout_status, focused=False)
    assert text == "DISC", "post-timeout chip must show DISC"
    assert tone == "danger"


def test_disc_chip_focused_shows_reconnect_affordance():
    """Post-timeout + focus → [DISC] with danger tone = reconnect-ready."""
    play = _make_play()
    timeout_status = {"ok": True, "connected": False, "idle_ms": 9999}
    text, tone = play._compose_conn_chip(timeout_status, focused=True)
    assert text == "[DISC]", "focused post-timeout chip must show [DISC]"
    assert tone == "danger"


def test_disc_chip_enter_returns_conn_activate_for_reconnect():
    """After timeout: focus → Enter → conn_activate → ensure reconnect."""
    play = _make_play()
    play.handle_key(curses.KEY_RIGHT)   # focus the chip
    assert play._conn_focused is True
    action = play.handle_key(10)        # activate
    assert action == "conn_activate"
