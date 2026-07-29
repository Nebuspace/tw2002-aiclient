"""E3: one `E` affordance, two armable intents (WO-EXPLORE-AUTOMATION-GATE).

Drives the real `app._run_play`, in the shape `tests/test_play_explore_arm.py`
established. The properties that matter are about AGREEMENT — the run that
starts must be the run the prompt described:

* the first `E` of a session offers map-fill — the same RUN existing muscle
  memory has always armed. (It is no longer the same WORDS: since
  WO-EXPLORE-GATHER-VISIBLE the line also states the dock state, because a
  prompt silent about ports let an operator arm "explore, passing every
  port" believing it was "explore". The run is the promise here; the
  wording never was.);
* `E` CYCLES the offer and never starts anything;
* `y` runs the intent the RAISED PROMPT named, not whatever the cycle
  advanced to afterwards;
* the number shown is the number sent.

`find_stardock` deliberately carries no cycle count: it ends on arrival or
exhaustion, so a "×5" would be describing map-fill's stopping rule.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient import adapters, app as app_mod
from tw2002_aiclient.cockpit import explore_flags
from tw2002_aiclient import explore as explore_mod


class _Result:
    def __init__(self, ok=True, classification="main_command", reason=None, detail=None):
        self.ok, self.classification, self.reason, self.detail = ok, classification, reason, detail


class _ExploreResult:
    def __init__(self, ok=True, reason=None):
        self.ok, self.reason, self.detail, self.raw = ok, reason, None, None


class _Stdscr:
    def __init__(self, keys):
        self._keys = list(keys) + [27, 27]
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


def _drive(monkeypatch, keys):
    """Return (explore_call_kwargs, screen). `screen.gate_raises` records every
    gate raise IN ORDER — checking the final `_arm_confirm` would be vacuous
    because every drive ends with Esc, which clears it."""
    calls: list = []
    monkeypatch.setattr(adapters, "ensure_session", lambda name, **kw: _Result())

    def _explore_start(profile, **kw):
        calls.append(kw)
        return _ExploreResult()

    monkeypatch.setattr(adapters, "explore_start_for_profile", _explore_start, raising=False)

    seen: dict = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.gate_raises = []
            seen["screen"] = self

        def begin_arm_confirm(self, action=None, *, cycles=None):
            self.gate_raises.append((action, cycles))
            return super().begin_arm_confirm(action, cycles=cycles)

        def draw(self):
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
    return calls, seen.get("screen")


E = ord("E")
N = ord("n")
Y = ord("y")


# --------------------------------------------------------------- the cycle

def test_the_first_E_offers_map_fill_exactly_as_before(monkeypatch) -> None:
    """Muscle memory must not arm a different RUN than it armed yesterday.

    WO-EXPLORE-GATHER-VISIBLE changed the WORDS on that line without
    changing the run, and this test had been asserting both through one
    equality. The two are now separated, because they are different
    promises: the intent is still map-fill and the count is still
    `_EXPLORE_MIN_SECTORS` — asserted below, unchanged — while the action
    text additionally states the dock state.

    Keeping the old equality would have made "the prompt may never gain a
    word" a property of the intent cycle, which it never was. It is the
    silence that was the bug: a line saying nothing about ports let an
    operator arm "explore, passing every port" believing it was "explore".
    """
    _calls, screen = _drive(monkeypatch, [E])
    assert len(screen.gate_raises) == 1
    action, cycles = screen.gate_raises[0]
    # The INTENT label is still pinned exactly, as the leading clause — a
    # change to which run `E` first offers still fails here.
    assert action.startswith(app_mod._EXPLORE_OFFER_ACTION), action
    assert explore_flags.DOCK_OFF_MARKER in action, action
    assert cycles == app_mod._EXPLORE_MIN_SECTORS


def test_pressing_E_again_cycles_to_find_stardock(monkeypatch) -> None:
    _calls, screen = _drive(monkeypatch, [E, N, E])
    assert len(screen.gate_raises) == 2
    assert "StarDock" in screen.gate_raises[1][0]


def test_the_stardock_offer_carries_no_cycle_count(monkeypatch) -> None:
    """It ends on arrival or exhaustion; "×5" would be map-fill's rule."""
    _calls, screen = _drive(monkeypatch, [E, N, E])
    assert screen.gate_raises[1][1] is None


def test_the_cycle_wraps_back_to_map_fill(monkeypatch) -> None:
    _calls, screen = _drive(monkeypatch, [E, N, E, N, E])
    assert len(screen.gate_raises) == 3
    assert screen.gate_raises[2] == screen.gate_raises[0]


def test_cycling_never_starts_a_run(monkeypatch) -> None:
    """`E` chooses; only `y` spends."""
    calls, _screen = _drive(monkeypatch, [E, N, E, N, E, N])
    assert calls == []


# ------------------------------------------------------------- what runs

def test_confirming_the_first_offer_runs_map_fill(monkeypatch) -> None:
    calls, _screen = _drive(monkeypatch, [E, Y])
    assert len(calls) == 1
    assert calls[0].get("intent") == explore_mod.INTENT_MAP_FILL


def test_confirming_the_cycled_offer_runs_find_stardock(monkeypatch) -> None:
    calls, _screen = _drive(monkeypatch, [E, N, E, Y])
    assert len(calls) == 1
    assert calls[0].get("intent") == explore_mod.INTENT_FIND_STARDOCK


def test_the_run_uses_the_intent_the_PROMPT_named(monkeypatch) -> None:
    """The pin against reading the cycle variable at confirm time. If `y`
    resolved the intent from the cycle rather than from the raised offer, the
    operator would get the run they were about to look at, not the one they
    agreed to."""
    calls, screen = _drive(monkeypatch, [E, N, E, Y])
    prompted = screen.gate_raises[-1][0]
    assert "StarDock" in prompted
    assert calls[0].get("intent") == explore_mod.INTENT_FIND_STARDOCK


def test_the_prompt_number_is_the_number_that_runs(monkeypatch) -> None:
    """Behavioural replacement for the old source-literal pin in
    `test_cockpit_armconfirm.py`: the number SHOWN equals the number SENT."""
    calls, screen = _drive(monkeypatch, [E, Y])
    _action, shown = screen.gate_raises[0]
    assert calls[0].get("min_sectors") == shown


def test_cancelling_never_starts_either_intent(monkeypatch) -> None:
    for cancel in (N, ord("N"), 27, 10, 13):
        calls, _screen = _drive(monkeypatch, [E, cancel])
        assert calls == [], f"key {cancel!r} started a run"
        calls, _screen = _drive(monkeypatch, [E, N, E, cancel])
        assert calls == [], f"key {cancel!r} started a stardock run"


# ------------------------------------------------------- the intent vocabulary

def test_the_armable_intents_are_a_closed_ordered_set():
    assert explore_mod.ARMABLE_INTENTS == (
        explore_mod.INTENT_MAP_FILL,
        explore_mod.INTENT_FIND_STARDOCK,
    )
    assert set(explore_mod.ARMABLE_INTENTS) <= explore_mod.INTENTS


def test_next_armable_intent_never_raises_and_restarts_on_junk():
    for bogus in (None, "", "formations", 7, [], object()):
        assert explore_mod.next_armable_intent(bogus) == explore_mod.INTENT_MAP_FILL
