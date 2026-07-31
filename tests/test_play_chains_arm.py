"""WO-PLAY-AUTOLOOP-START -- canon's `L)chains` popup and the taught-loop arm.

Drives the real `app._run_play` with a fake stdscr and mocked adapters, in
the shape `tests/test_play_explore_arm.py` established: these assert the
PRODUCT path, not a re-implementation of it.

The load-bearing test in this file is
`test_confirming_a_loop_does_not_start_explore`. Explore confirm is gated on
`pending_confirm_action == "explore"` (WO-ARM-CONFIRM-EXPLICIT-EXPLORE); the
loop branch must still claim its confirm first so a taught-loop `y` never
reaches explore_start. Both directions are pinned: a loop confirm must not
reach explore, and an explore confirm must not reach autoloop. A third pin
(`test_orphan_arm_confirm_starts_neither_runner`) covers unset/unknown
pending — fail closed, no runner.

The states that matter:
  * `L` -> popup opens, NOTHING armed and no gate raised
  * `L` then Enter -> gate raised naming the selected macro, still nothing started
  * `L` Enter `y` -> autoloop_start once, with the name from the prompt
  * `L` Enter <anything else> -> gate clears, nothing started
  * empty / unreadable store -> no gate, and the empty is not fabricated
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient import adapters, app as app_mod
from tw2002_aiclient.loops import store as _loop_store


class _Result:
    def __init__(self, ok=True, classification="main_command", reason=None, detail=None):
        self.ok, self.classification, self.reason, self.detail = ok, classification, reason, detail


class _AutoLoopResult:
    def __init__(self, ok=True, reason=None):
        self.ok, self.reason, self.detail, self.raw = ok, reason, None, None


class _ExploreResult:
    def __init__(self, ok=True, reason=None):
        self.ok, self.reason, self.detail, self.raw = ok, reason, None, None


class _Stdscr:
    """Feeds a scripted key sequence, then Esc to leave the loop."""

    def __init__(self, keys):
        self._keys = list(keys) + [27, 27]
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


TWO_LOOPS = {
    "status": "ok",
    "loops": [
        {"name": "ore-run-K7", "steps": 12, "draft": False},
        {"name": "fuel-shuttle", "steps": 8, "draft": False},
    ],
}
EMPTY_OK = {"status": "ok", "loops": []}
UNREADABLE = {"status": "unreadable", "loops": []}


def _drive(monkeypatch, keys, *, store=None, started=None, raises=None):
    """Run `_run_play`; return (arm_calls, explore_calls, screen).

    Both adapter spies are installed on EVERY drive, including the explore
    tests -- that is what makes the cross-contamination pin meaningful. A
    file that only stubbed the adapter it expected would report "explore
    started" and never notice autoloop had fired too.
    """
    arm_calls: list = []
    explore_calls: list = []

    monkeypatch.setattr(adapters, "ensure_session", lambda name, **kw: _Result())
    monkeypatch.setattr(
        _loop_store, "read_loop_store",
        (lambda **kw: (_ for _ in ()).throw(raises)) if raises is not None
        else (lambda **kw: TWO_LOOPS if store is None else store),
    )

    def _arm(name=None, **kw):
        arm_calls.append((name, kw))
        return started if started is not None else _AutoLoopResult()

    def _explore(profile, **kw):
        explore_calls.append(kw)
        return _ExploreResult()

    monkeypatch.setattr(adapters, "autoloop_start", _arm, raising=False)
    monkeypatch.setattr(adapters, "explore_start_for_profile", _explore, raising=False)

    seen: dict = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.gate_raises = []
            # Skip App-armed ensure explore kick — this file pins chains, not policy explore.
            self.spectating = True
            seen["screen"] = self

        def begin_arm_confirm(self, action=None, *, cycles=None):
            self.gate_raises.append((action, cycles))
            return super().begin_arm_confirm(action, cycles=cycles)

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
    return arm_calls, explore_calls, seen.get("screen")


L = ord("L")
ENTER = 10
DOWN = 258  # curses.KEY_DOWN


def test_l_opens_the_popup_but_arms_nothing(monkeypatch) -> None:
    """Opening a list is not arming. No gate, no adapter call -- the popup
    is a view until Enter selects and `y` confirms."""
    arm, explore, screen = _drive(monkeypatch, [L])
    assert arm == []
    assert explore == []
    assert screen.gate_raises == [], f"gate raised by merely opening: {screen.gate_raises}"


def test_enter_raises_the_gate_naming_the_macro_and_starts_nothing(monkeypatch) -> None:
    """Canon: "selecting a chain ... *arms* a pending action and raises an
    explicit confirm prompt ... A bare Enter must never fire a launch."
    """
    arm, _explore, screen = _drive(monkeypatch, [L, ENTER])
    assert arm == [], "Enter alone started a run"
    assert len(screen.gate_raises) == 1
    action_text = screen.gate_raises[0][0]
    assert "ore-run-K7" in action_text
    assert "one pass" in action_text


def test_l_enter_y_arms_the_selected_loop(monkeypatch) -> None:
    arm, _explore, _screen = _drive(monkeypatch, [L, ENTER, ord("y")])
    assert len(arm) == 1
    assert arm[0][0] == "ore-run-K7"


def test_confirming_a_loop_does_not_start_explore(monkeypatch) -> None:
    """THE pin. Explore start requires `pending_confirm_action == "explore"`;
    the taught-loop branch must claim the confirm first. Delete the
    `pending_confirm_action == "loop"` branch and this goes red while a
    "something started" assertion would not."""
    arm, explore, _screen = _drive(monkeypatch, [L, ENTER, ord("y")])
    assert len(arm) == 1, "the taught loop did not arm"
    assert explore == [], f"a taught-loop confirm started EXPLORE instead: {explore}"


def test_confirming_explore_does_not_arm_a_loop(monkeypatch) -> None:
    """The same pin from the other side: adding the loop branch must not
    steal the explore path's own confirm."""
    arm, explore, _screen = _drive(monkeypatch, [ord("E")])
    assert len(explore) == 1, "explore did not start"
    assert arm == [], f"an explore start armed a taught loop: {arm}"


def test_orphan_arm_confirm_starts_neither_runner(monkeypatch) -> None:
    """WO-ARM-CONFIRM-EXPLICIT-EXPLORE Accept #3: `arm_confirm` with no
    (or unknown) pending discriminator must start nothing — the old bare
    fallthrough started explore here."""
    arm_calls: list = []
    explore_calls: list = []
    monkeypatch.setattr(adapters, "ensure_session", lambda name, **kw: _Result())
    monkeypatch.setattr(
        _loop_store, "read_loop_store",
        lambda **kw: TWO_LOOPS,
    )

    def _arm(name=None, **kw):
        arm_calls.append((name, kw))
        return _AutoLoopResult()

    def _explore(profile, **kw):
        explore_calls.append(kw)
        return _ExploreResult()

    monkeypatch.setattr(adapters, "autoloop_start", _arm, raising=False)
    monkeypatch.setattr(adapters, "explore_start_for_profile", _explore, raising=False)

    seen: dict = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._orphan_fired = False
            self.spectating = True  # no App-armed ensure explore kick
            seen["screen"] = self

        def handle_key(self, key):
            # Inject a confirm without any offer path having set
            # `pending_confirm_action` in `_run_play`.
            if key == ord("y") and not self._orphan_fired:
                self._orphan_fired = True
                return "arm_confirm"
            return super().handle_key(key)

        def draw(self):
            pass

    monkeypatch.setattr(app_mod, "PlayShellScreen", _Spy)
    monkeypatch.setattr(app_mod.curses, "has_colors", lambda: False, raising=False)
    profile = app_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    try:
        app_mod._run_play(_Stdscr([ord("y")]), profile)
    except Exception:
        pass
    assert arm_calls == [], f"orphan confirm started autoloop: {arm_calls}"
    assert explore_calls == [], f"orphan confirm started explore: {explore_calls}"
    assert "nothing pending" in (seen["screen"].status_line or "")


def test_explore_confirm_still_requires_explicit_pending(monkeypatch) -> None:
    """Proof Accept #1: explore start is gated on explicit pending=explore."""
    arm, explore, _screen = _drive(monkeypatch, [ord("E")])
    assert explore and not arm
    src = Path(app_mod.__file__).read_text(encoding="utf-8")
    assert 'if action == "arm_confirm" and pending_confirm_action == "explore"' in src
    # Fail-closed bare confirm must not invoke explore_start.
    bare = src.split('if action == "arm_confirm":', 1)[1].split("if action ==", 1)[0]
    assert "explore_start" not in bare


def test_cancelling_the_confirm_does_not_arm(monkeypatch) -> None:
    for cancel_key in (ord("n"), ord("N"), 27, ENTER, ord("Y") + 1):
        arm, _explore, _screen = _drive(monkeypatch, [L, ENTER, cancel_key])
        assert arm == [], f"key {cancel_key!r} armed a live run"


def test_bare_enter_at_the_gate_is_not_a_confirm(monkeypatch) -> None:
    """Called out separately because canon names it: "A bare Enter must
    never fire a launch." `resolve_arm_confirm_key` is default-deny, and
    this pins that the gate keeps that posture on this path."""
    arm, _explore, _screen = _drive(monkeypatch, [L, ENTER, ENTER])
    assert arm == []


def test_moving_the_cursor_arms_the_row_the_prompt_named(monkeypatch) -> None:
    arm, _explore, screen = _drive(monkeypatch, [L, DOWN, ENTER, ord("y")])
    assert len(arm) == 1
    assert arm[0][0] == "fuel-shuttle"
    assert "fuel-shuttle" in screen.gate_raises[0][0], (
        "the prompt named a different macro than the one that ran"
    )


def test_an_empty_store_raises_no_gate(monkeypatch) -> None:
    arm, _explore, screen = _drive(monkeypatch, [L, ENTER], store=EMPTY_OK)
    assert arm == []
    assert screen.gate_raises == [], "a confirm gate was raised for no macro"


def test_an_unreadable_store_is_not_reported_as_empty(monkeypatch) -> None:
    """"could not read the store" and "you have taught nothing" are
    different facts, and only one of them is safe to show an operator
    deciding whether their macros survived."""
    _arm, _explore, screen = _drive(monkeypatch, [L], store=UNREADABLE)
    assert screen.chains_session.status == "unreadable"


def test_a_raising_store_read_does_not_take_down_the_play_loop(monkeypatch) -> None:
    _arm, _explore, screen = _drive(monkeypatch, [L], raises=OSError("disk gone"))
    assert screen is not None
    assert screen.chains_session.status == "unreadable"
    assert "OSError" in (screen.status_line or "")


def test_a_daemon_refusal_is_surfaced_not_smoothed(monkeypatch) -> None:
    arm, _explore, screen = _drive(
        monkeypatch, [L, ENTER, ord("y")],
        started=_AutoLoopResult(ok=False, reason="locked_by_active_driver"),
    )
    assert len(arm) == 1
    assert "locked_by_active_driver" in (screen.status_line or "")


def test_the_name_sent_is_the_name_confirmed(monkeypatch) -> None:
    """The row is held from the moment the prompt is composed, never re-read
    at `y`. A re-read between prompt and confirm is how an operator ends up
    running a different macro than the one they agreed to."""
    arm, _explore, screen = _drive(monkeypatch, [L, ENTER, ord("y")])
    assert arm[0][0] in screen.gate_raises[0][0]
