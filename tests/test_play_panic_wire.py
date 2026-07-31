"""`P` panic -- retired from the calm play-shell wire (hub REVISE
2026-07-31, WO-PLAY-STRIP-TRAINER-CHROME).

# Why this file still exists (now proving the opposite claim)

This file used to prove ``P`` reached ``adapters.autoloop_stop`` through the
real app loop (WO-P5-071). The STATUS-DONE cut of WO-PLAY-STRIP-TRAINER-
CHROME retired the ``P panic`` calm-band token but left the OLD ``P``
key BINDING live underneath the NEW ``P)ort Trade`` label -- a
plausible-but-wrong claim (the band said one thing, the handler did
another) caught in hub REVISE. ``screens.py::PlayShellScreen.handle_key``
no longer calls ``panic.resolve_panic_key``/``panic.PANIC_INTENT`` at all
(see ``tests/test_cockpit_panic.py``'s own structural pin on that); ``P``
now flips the trainer's local ``port_trade_on`` toggle instead.

Measured, not assumed, the same way the original file was: driving ``P``
through the real loop with ``adapters.autoloop_stop`` mocked now records
**zero** calls -- proving the retirement reaches all the way through the
app loop, not just the cockpit's own ``handle_key`` return value (a
composer/handler-level pin alone cannot see whether some OTHER app-loop
branch still calls the stop path for an unrelated reason).

``cockpit/panic.py`` itself, and its own halt call sites for a FUTURE
policy WO, are unchanged -- only this one calm-path wire is gone. See
``tests/test_play_strip_trainer_toggles.py`` for the dedicated pins on the
new ``P``/``C``/``S`` local-toggle behavior (composer + cockpit-handler
level); this file stays scoped to the full-loop non-regression proof.

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
    other_stop_calls = []

    monkeypatch.setattr(adapters, "ensure_session", lambda name, **kw: _Ensure())

    def _stop(**kw):
        stop_calls.append(kw)
        if raises is not None:
            raise raises
        return stop_result if stop_result is not None else _StopResult()

    monkeypatch.setattr(adapters, "autoloop_stop", _stop, raising=False)
    monkeypatch.setattr(
        adapters,
        "explore_stop",
        lambda **kw: (other_stop_calls.append(("explore", kw)) or _StopResult()),
        raising=False,
    )
    monkeypatch.setattr(
        adapters,
        "trade_chain_stop",
        lambda **kw: (other_stop_calls.append(("trade", kw)) or _StopResult()),
        raising=False,
    )

    seen = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.gate_raises = []
            self.actions = []
            self.other_stop_calls = other_stop_calls
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
# The retirement -- `P` no longer reaches the halt, at the FULL loop level
# --------------------------------------------------------------------------

@pytest.mark.parametrize("key", [ord("p"), ord("P")])
def test_p_no_longer_reaches_the_halt(monkeypatch, key):
    """THE pin this file exists for, now proving the opposite of its
    original claim. Goes red if a future edit silently re-wires `P` back
    onto the halt path without updating the calm band's own label."""
    stop_calls, screen = _drive(monkeypatch, [key])
    assert stop_calls == [], "P must not reach adapters.autoloop_stop on this calm path"
    assert screen.other_stop_calls == [], "P must not reach explore/trade stop either"


def test_p_does_not_pass_through_a_confirm_gate(monkeypatch):
    """`P` is a bare local toggle -- it must never raise the confirm gate,
    the same no-gate posture the retired panic wire also held (for a
    different reason: panic was halt-direction; the toggle spends nothing
    at all)."""
    _stop_calls, screen = _drive(monkeypatch, [ord("P")])
    assert screen.gate_raises == [], (
        f"P routed through a confirm gate: {screen.gate_raises}"
    )


def test_p_toggles_port_trade_at_the_full_loop_level(monkeypatch):
    """The new wire's own full-loop proof, mirroring this file's original
    reasoning: a composer/handler-level pin alone cannot see whether
    `app.py`'s loop construction somehow shadows or discards the toggle
    before it reaches the live `PlayShellScreen` instance the loop holds."""
    _stop_calls, screen = _drive(monkeypatch, [ord("P")])
    assert screen.port_trade_on is False  # started True (DECISION default)
    assert (ord("P"), None) in screen.actions


def test_double_press_toggles_back(monkeypatch):
    """Two presses return to the starting state -- a plain flip, not a
    one-way latch or (the old panic behavior) two independent halts."""
    _stop_calls, screen = _drive(monkeypatch, [ord("P"), ord("P")])
    assert screen.port_trade_on is True
    assert _stop_calls == []


def test_p_does_not_shadow_the_teach_keys_in_the_real_loop(monkeypatch):
    """`P`/`C`/`S` sit after A/R/T in the handler; adding them must not
    shadow those teach keys.

    Asserts on what each key RESOLVED TO rather than on end state -- the
    drive's trailing Esc closes the analyze overlay (WO-P5-069), so an
    end-state read cannot tell "worked then undone" from "never worked".
    """
    for key, expected in ((ord("a"), "analyze_open"), (ord("r"), "record_toggle"), (ord("t"), "assign_trigger")):
        _stop_calls, screen = _drive(monkeypatch, [key])
        assert (key, expected) in screen.actions
