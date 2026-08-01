"""Pause + relaunch reach the app-loop wire (WO-AUTOLOOP-RELAUNCH-COCKPIT).

# Why this file exists, separate from the composer/screen-level pins

``tests/test_cockpit_autoloop_controls.py`` proves the keys resolve and the
label renders meaning. ``tests/test_cockpit_pause_key.py`` proves the
cockpit returns the right intent and raises no gate for pause. **Neither
proves the app loop acts on either intent.** `tests/test_play_panic_wire.py`
found exactly this class of gap for panic (composer green, wire absent,
4976 tests still passing with the whole ``if action == "panic":`` block
deleted) -- this file is that same measured discipline applied to pause and
relaunch.

The harness is ``tests/test_play_explore_arm.py``'s: drive the real
``app._run_play`` with a fake stdscr and mocked adapters/transport, so
these assertions are about the PRODUCT path, not a re-implementation.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient import adapters, app as app_mod


class _Ensure:
    def __init__(self, ok=True, classification="main_command"):
        self.ok, self.classification, self.reason, self.detail = ok, classification, None, None


class _AutoloopResult:
    def __init__(self, ok=True, reason=None, raw=None):
        self.ok, self.reason, self.detail, self.raw = ok, reason, None, raw


class _Stdscr:
    """Feeds a scripted key sequence, then Esc to leave the loop."""

    def __init__(self, keys):
        self._keys = list(keys) + [27]
        self.rows, self.cols = 40, 180

    def getmaxyx(self): return (self.rows, self.cols)
    def getch(self): return self._keys.pop(0) if self._keys else 27
    def timeout(self, ms): pass
    def erase(self): pass
    def refresh(self): pass
    def addstr(self, *a, **k): pass
    def addnstr(self, *a, **k): pass
    def attron(self, a): pass
    def attroff(self, a): pass
    def hline(self, *a, **k): pass
    def vline(self, *a, **k): pass
    def border(self, *a, **k): pass
    def chgat(self, *a, **k): pass
    def keypad(self, flag): pass
    def nodelay(self, flag): pass


def _drive(
    monkeypatch, keys, *,
    pause_result=None, relaunch_result=None,
    status_sends_issued=5, status_ok=True,
):
    """Run `_run_play`; return (pause_calls, relaunch_calls, status_calls, screen)."""
    pause_calls, relaunch_calls, status_calls = [], [], []

    monkeypatch.setattr(adapters, "ensure_session", lambda name, **kw: _Ensure())

    def _pause(**kw):
        pause_calls.append(kw)
        return pause_result if pause_result is not None else _AutoloopResult()

    def _relaunch(**kw):
        relaunch_calls.append(kw)
        return relaunch_result if relaunch_result is not None else _AutoloopResult()

    monkeypatch.setattr(adapters, "autoloop_pause", _pause, raising=False)
    monkeypatch.setattr(adapters, "autoloop_relaunch", _relaunch, raising=False)

    def _status(**kw):
        status_calls.append(kw)
        if not status_ok:
            return _AutoloopResult(ok=False, reason="autoloop_unavailable")
        return _AutoloopResult(
            ok=True,
            raw={
                "ok": True,
                "running": False,
                "run": {"sends_issued": status_sends_issued},
                "stand_down": "pause",
            },
        )

    monkeypatch.setattr(adapters, "autoloop_status", _status, raising=False)

    seen = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.gate_raises = []
            self.actions = []
            seen["screen"] = self

        def begin_arm_confirm(self, action=None, *, cycles=None):
            self.gate_raises.append((action, cycles))
            return super().begin_arm_confirm(action, cycles=cycles)

        def handle_key(self, key):
            action = super().handle_key(key)
            self.actions.append((key, action))
            return action

        def draw(self):  # keep the fake stdscr out of real curses paint paths
            pass

    monkeypatch.setattr(app_mod, "PlayShellScreen", _Spy)
    monkeypatch.setattr(app_mod.curses, "has_colors", lambda: False, raising=False)

    profile = app_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    try:
        app_mod._run_play(_Stdscr(keys), profile)
    except Exception:
        pass
    return pause_calls, relaunch_calls, status_calls, seen.get("screen")


# --------------------------------------------------------------------------
# Pause -- ungated, reaches the adapter on the first press
# --------------------------------------------------------------------------

@pytest.mark.parametrize("key", [ord(" ")])
def test_pause_key_reaches_the_adapter(monkeypatch, key):
    """THE pin this file exists for (pause half). Goes red if the app.py
    routing is removed."""
    pause_calls, relaunch_calls, _status, _screen = _drive(monkeypatch, [key])
    assert len(pause_calls) == 1, "Space did not reach adapters.autoloop_pause"
    assert relaunch_calls == []


def test_pause_does_not_pass_through_a_confirm_gate(monkeypatch):
    pause_calls, _r, _s, screen = _drive(monkeypatch, [ord(" ")])
    assert len(pause_calls) == 1
    assert screen.gate_raises == [], (
        f"pause routed through a confirm gate: {screen.gate_raises}"
    )


def test_pause_double_press_is_harmless(monkeypatch):
    pause_calls, _r, _s, _screen = _drive(monkeypatch, [ord(" "), ord(" ")])
    assert len(pause_calls) == 2


def test_successful_pause_is_reported(monkeypatch):
    _p, _r, _s, screen = _drive(monkeypatch, [ord(" ")])
    assert "paused" in (screen.status_line or "")


def test_failed_pause_is_reported_as_a_failure(monkeypatch):
    _p, _r, _s, screen = _drive(
        monkeypatch, [ord(" ")],
        pause_result=_AutoloopResult(ok=False, reason="autoloop_unavailable"),
    )
    line = screen.status_line or ""
    assert "failed" in line
    assert "autoloop_unavailable" in line
    assert "paused —" not in line, "reported a pause that did not happen"


# --------------------------------------------------------------------------
# Relaunch -- confirm-gated; G raises, only y fires
# --------------------------------------------------------------------------

def test_g_raises_the_gate_but_arms_nothing(monkeypatch):
    _p, relaunch_calls, _s, screen = _drive(monkeypatch, [ord("G")])
    assert len(screen.gate_raises) == 1
    assert relaunch_calls == []


def test_g_previews_the_wire_before_raising_the_gate(monkeypatch):
    """The label the human sees on the FIRST keystroke must already carry
    the real (previewed) disclosure -- not a placeholder filled in later."""
    _p, relaunch_calls, status_calls, screen = _drive(
        monkeypatch, [ord("G")], status_sends_issued=12,
    )
    assert len(status_calls) == 1, "relaunch offer did not preview autoloop_status"
    assert relaunch_calls == [], "relaunch fired before the human confirmed"
    ((action, _cycles),) = screen.gate_raises
    assert "12 sends already issued" in action
    assert "replays from the beginning" in action


def test_g_then_y_fires_relaunch_once(monkeypatch):
    pause_calls, relaunch_calls, _s, screen = _drive(monkeypatch, [ord("G"), ord("y")])
    assert len(relaunch_calls) == 1
    assert pause_calls == []
    assert "relaunched" in (screen.status_line or "")


@pytest.mark.parametrize("key", [ord("N"), ord("n"), 10, 13, 27, ord("q")])
def test_non_y_never_fires_relaunch(monkeypatch, key):
    """Default-deny at the product layer, not just in the resolver --
    mirrors `test_play_explore_arm.py`'s own version of this pin."""
    _p, relaunch_calls, _s, _screen = _drive(monkeypatch, [ord("G"), key])
    assert relaunch_calls == [], f"key {key} fired relaunch"


def test_relaunch_preview_degrades_to_unknown_when_status_fails(monkeypatch):
    """No runner / non-`ok` status must render `?`, never an invented `0`."""
    _p, _r, _s, screen = _drive(monkeypatch, [ord("G")], status_ok=False)
    ((action, _cycles),) = screen.gate_raises
    assert "? sends already issued" in action


def test_successful_relaunch_is_reported(monkeypatch):
    _p, _r, _s, screen = _drive(monkeypatch, [ord("G"), ord("y")])
    assert "relaunched" in (screen.status_line or "")


def test_failed_relaunch_is_reported_as_a_failure(monkeypatch):
    _p, _r, _s, screen = _drive(
        monkeypatch, [ord("G"), ord("y")],
        relaunch_result=_AutoloopResult(ok=False, reason="not_paused"),
    )
    line = screen.status_line or ""
    assert "failed" in line
    assert "not_paused" in line
    assert "relaunched —" not in line, "reported a relaunch that did not happen"


def test_pause_then_relaunch_do_not_confuse_each_others_gate_state(monkeypatch):
    """Pause (ungated) between the relaunch offer and its confirm must not
    leave the loop thinking a relaunch is still pending when it isn't, or
    vice versa."""
    pause_calls, relaunch_calls, _s, screen = _drive(
        monkeypatch, [ord(" "), ord("G"), ord("y"), ord(" ")]
    )
    assert len(pause_calls) == 2
    assert len(relaunch_calls) == 1


# --------------------------------------------------------------------------
# Neither key shadows the trainer toggle keys or the teach keys in the real
# loop. `p` is a local Port Trade toggle, not panic, on this calm path
# (hub REVISE 2026-07-31, WO-PLAY-STRIP-TRAINER-CHROME) -- it returns no
# intent, so its expected `screen.actions` entry is `None`, not `"panic"`.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("key,expected", [
    (ord("p"), None),
    (ord("a"), "analyze_open"),
    (ord("r"), "record_toggle"),
    (ord("t"), "trade_loop_toggle"),
])
def test_pause_and_relaunch_do_not_shadow_existing_keys(monkeypatch, key, expected):
    _p, _r, _s, screen = _drive(monkeypatch, [key])
    assert (key, expected) in screen.actions


# --------------------------------------------------------------------------
# Never "resume"
# --------------------------------------------------------------------------

def test_no_resume_string_anywhere_on_the_relaunch_path(monkeypatch):
    _p, _r, _s, screen = _drive(monkeypatch, [ord("G"), ord("y")])
    assert "resume" not in (screen.status_line or "").lower()
    for action, _cycles in screen.gate_raises:
        assert "resume" not in (action or "").lower()
