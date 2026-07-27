"""`P` panic reaches the halt -- the app-loop wire (WO-P5-071).

# Why this file is separate from `test_cockpit_panic.py`

That file proves the key resolves to an intent and that the cockpit raises
no confirm gate. **Neither of those proves the app loop acts on the
intent.** Measured, not assumed: deleting the whole ``if action ==
"panic":`` block from ``app.py`` left the entire suite green at 4976
tests. `P` would return its intent, fall through the if-chain, and do
nothing -- while the taught run kept spending turns and credits.

That is the worst available failure mode for this particular key, and it
is invisible to every composer-level test. Same class of gap the coverage
meter had at WO-P5-072 (composer green, wire absent); found the same way,
by deleting the wire and watching nothing complain.

The harness is ``tests/test_play_explore_arm.py``'s -- a scripted stdscr
driving the real ``app._run_play`` with the adapter mocked, so these
assertions are about the PRODUCT path rather than a re-implementation of
it.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient import adapters, app as app_mod


class _Ensure:
    def __init__(self, ok=True, classification="main_command"):
        self.ok, self.classification, self.reason, self.detail = ok, classification, None, None


class _StopResult:
    def __init__(self, ok=True, reason=None):
        self.ok, self.reason, self.detail, self.raw = ok, reason, None, None


class _Stdscr:
    """Feeds a scripted key sequence, then Esc to leave the loop."""

    def __init__(self, keys):
        self._keys = list(keys) + [27]
        self.rows, self.cols = 40, 160

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


def _drive(monkeypatch, keys, *, stop_result=None, raises=None):
    """Run `_run_play`; return (stop_calls, screen).

    `screen.gate_raises` records every `begin_arm_confirm` IN ORDER.
    Inspecting the final `_arm_confirm` instead would be vacuous -- every
    drive ends with Esc, which clears the gate, so "gate raised then
    dismissed" and "gate never raised" look identical afterwards. That
    exact vacuity was found on this surface once already
    (`test_play_explore_arm.py`), so the recorder is reused rather than
    the mistake repeated.
    """
    stop_calls = []

    monkeypatch.setattr(adapters, "ensure_session", lambda name, **kw: _Ensure())

    def _stop(**kw):
        stop_calls.append(kw)
        if raises is not None:
            raise raises
        return stop_result if stop_result is not None else _StopResult()

    monkeypatch.setattr(adapters, "autoloop_stop", _stop, raising=False)

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
            # Record what each key RESOLVED TO, in order. End-state reads
            # are not usable here: every drive ends with Esc, and Esc is
            # itself meaningful to several handlers (it closes the analyze
            # overlay, WO-P5-069), so "the key worked and was later undone"
            # and "the key never worked" are indistinguishable afterwards.
            # This recorder was added after that exact mistake failed a
            # test in this file.
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
    return stop_calls, seen.get("screen")


# --------------------------------------------------------------------------
# The wire
# --------------------------------------------------------------------------

@pytest.mark.parametrize("key", [ord("p"), ord("P")])
def test_panic_key_reaches_the_halt(monkeypatch, key):
    """THE pin this file exists for. Goes red if the app.py routing is
    removed -- the deletion that left the rest of the suite green."""
    stop_calls, _screen = _drive(monkeypatch, [key])
    assert len(stop_calls) == 1, "P did not reach adapters.autoloop_stop"


def test_panic_does_not_pass_through_a_confirm_gate(monkeypatch):
    """The no-confirm asymmetry at LOOP level, not just key level.

    A confirm gate could be raised by the app loop rather than the cockpit,
    which the key-level pin in `test_cockpit_panic.py` would not see.
    """
    stop_calls, screen = _drive(monkeypatch, [ord("P")])
    assert len(stop_calls) == 1
    assert screen.gate_raises == [], (
        f"panic routed through a confirm gate: {screen.gate_raises}"
    )


def test_halt_happens_on_the_first_press_not_the_second(monkeypatch):
    """No 'press again to confirm' behaviour smuggled in as a non-modal
    substitute for the gate."""
    stop_calls, _ = _drive(monkeypatch, [ord("P")])
    assert len(stop_calls) == 1


def test_double_press_is_harmless(monkeypatch):
    """The daemon verb is idempotent, so two presses are two honest halts
    rather than an error the operator has to interpret."""
    stop_calls, _ = _drive(monkeypatch, [ord("P"), ord("P")])
    assert len(stop_calls) == 2


# --------------------------------------------------------------------------
# Honest reporting -- the operator must know whether the halt landed
# --------------------------------------------------------------------------

def test_successful_halt_is_reported(monkeypatch):
    _stop_calls, screen = _drive(monkeypatch, [ord("P")])
    assert "PANIC" in (screen.status_line or "")
    assert "halted" in (screen.status_line or "")


def test_failed_halt_is_reported_as_a_failure(monkeypatch):
    """`autoloop_unavailable` means the halt reached no runner. Saying
    anything reassuring here would be the worst possible lie on this key."""
    _stop_calls, screen = _drive(
        monkeypatch, [ord("P")],
        stop_result=_StopResult(ok=False, reason="autoloop_unavailable"),
    )
    line = screen.status_line or ""
    assert "failed" in line
    assert "autoloop_unavailable" in line
    assert "halted" not in line, "reported a halt that did not happen"


@pytest.mark.parametrize("key,expected", [
    (ord("a"), "analyze_open"),
    (ord("r"), "record_toggle"),
    (ord("t"), "assign_trigger"),
])
def test_panic_does_not_shadow_the_teach_keys_in_the_real_loop(monkeypatch, key, expected):
    """`P` sits after A/R/T in the handler; adding it must not shadow them.

    Asserts on what each key RESOLVED TO rather than on end state -- the
    drive's trailing Esc closes the analyze overlay (WO-P5-069), so an
    end-state read cannot tell "worked then undone" from "never worked".
    """
    _stop_calls, screen = _drive(monkeypatch, [key])
    assert (key, expected) in screen.actions


def test_panic_resolves_to_its_own_intent_in_the_real_loop(monkeypatch):
    _stop_calls, screen = _drive(monkeypatch, [ord("P")])
    assert (ord("P"), "panic") in screen.actions
