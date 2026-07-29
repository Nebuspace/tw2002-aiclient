"""WO-PLAY-EXPLORE-FLAGS -- Play's default-OFF opt-in for the two explore
automation flags.

These drive the real `app._run_play` with a fake stdscr and a mocked
adapter, so the assertions are about the PRODUCT path rather than a
re-implementation of it -- same harness shape as
`tests/test_play_explore_arm.py`.

# What is actually being pinned, and why it is the forward and not the outcome

The failure this WO is most exposed to is a flag that reads as wired and
forwards nothing: the operator presses `D`, the confirm line says `+dock`,
the run starts, and `dock_new_ports` never reaches the adapter. Every
outcome-shaped assertion ("the run started", "ok is True") passes just as
happily in that world. So these tests assert **the kwargs that arrive at
`explore_start_for_profile`** -- the one observation that can tell the two
worlds apart.

# The asymmetry pin

`dock_new_ports` and `fight_tolls` must NOT be tidied into symmetry: the
adapter forwards `fight_tolls` un-coerced so a non-bool trips
`invalid_fight_tolls` daemon-side, where `bool("no") is True` would have
armed combat. `test_call_site_does_not_coerce_either_flag` pins the absence
of `bool(...)` at the Play call site structurally (AST, not grep -- a text
search hits docstrings and comments and would stay green on the real
defect), with a non-vacuity control so a broken matcher cannot pass for
free.
"""

from __future__ import annotations

import ast
import inspect
import types

import pytest

from tw2002_aiclient import adapters, app as app_mod
from tw2002_aiclient.cockpit import explore_flags


class _Result:
    def __init__(self, ok=True, classification="main_command", reason=None, detail=None):
        self.ok, self.classification, self.reason, self.detail = ok, classification, reason, detail


class _ExploreResult:
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


def _drive(monkeypatch, keys, *, ensure=None, explore=None):
    """Run `_run_play`; return (explore_call_kwargs, screen)."""
    calls = []

    monkeypatch.setattr(
        adapters, "ensure_session",
        lambda name, **kw: ensure if ensure is not None else _Result(),
    )

    def _explore(profile, **kw):
        calls.append(kw)
        return explore if explore is not None else _ExploreResult()

    monkeypatch.setattr(adapters, "explore_start_for_profile", _explore, raising=False)

    seen = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.gate_raises = []
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
    return calls, seen.get("screen")


_E, _Y = ord("E"), ord("y")
_D, _F = ord("D"), ord("F")


# --------------------------------------------------------------------------
# The default is OFF, in both directions
# --------------------------------------------------------------------------

def test_default_arm_forwards_both_flags_off(monkeypatch) -> None:
    """`E`,`y` with no toggle pressed forwards both flags explicitly False.

    Asserted as `is False` rather than falsy: `None`, `0` and `""` are all
    falsy and all mean something different to the adapter, which omits the
    payload key on `None`.
    """
    calls, _screen = _drive(monkeypatch, [_E, _Y])
    assert len(calls) == 1, calls
    assert calls[0]["dock_new_ports"] is False, calls[0]
    assert calls[0]["fight_tolls"] is False, calls[0]


def test_default_confirm_line_is_byte_identical_to_the_pre_wo_prompt(monkeypatch) -> None:
    """An operator who never presses `D`/`F` sees exactly the old prompt.

    This is the pin that stops a marker leaking into the default path --
    the confirm line is what the human's muscle memory reads before
    spending turns.
    """
    _calls, screen = _drive(monkeypatch, [_E])
    assert screen.gate_raises == [("Explore", 5)], screen.gate_raises


# --------------------------------------------------------------------------
# Opting in forwards the exact value, and says so on the line being confirmed
# --------------------------------------------------------------------------

def test_dock_toggle_forwards_true_and_leaves_tolls_off(monkeypatch) -> None:
    calls, _screen = _drive(monkeypatch, [_D, _E, _Y])
    assert len(calls) == 1, calls
    assert calls[0]["dock_new_ports"] is True, calls[0]
    assert calls[0]["fight_tolls"] is False, calls[0]


def test_tolls_toggle_forwards_true_and_leaves_dock_off(monkeypatch) -> None:
    """The two flags are independent -- pinned separately in both directions
    so a wire that forwards one value to both slots cannot pass."""
    calls, _screen = _drive(monkeypatch, [_F, _E, _Y])
    assert len(calls) == 1, calls
    assert calls[0]["fight_tolls"] is True, calls[0]
    assert calls[0]["dock_new_ports"] is False, calls[0]


def test_both_toggles_forward_both_true(monkeypatch) -> None:
    calls, _screen = _drive(monkeypatch, [_D, _F, _E, _Y])
    assert len(calls) == 1, calls
    assert calls[0]["dock_new_ports"] is True, calls[0]
    assert calls[0]["fight_tolls"] is True, calls[0]


def test_opt_in_is_spelled_out_in_the_line_the_operator_confirms(monkeypatch) -> None:
    """Accept 2: opt-in is visible BEFORE/AS PART OF the confirm, never a
    silent side effect of `y`.

    ONE `_drive` per test, deliberately: a second call in the same test
    re-reads `app_mod.PlayShellScreen`, which is already the first call's
    spy, so the new spy SUBCLASSES it and `begin_arm_confirm` records the
    same raise twice. Caught here by that exact double-count.
    """
    _calls, screen = _drive(monkeypatch, [_D, _E])
    assert screen.gate_raises == [("Explore +dock", 5)], screen.gate_raises


def test_both_opt_ins_are_spelled_out_together(monkeypatch) -> None:
    _calls, screen = _drive(monkeypatch, [_D, _F, _E])
    assert screen.gate_raises == [("Explore +dock +fight-tolls", 5)], screen.gate_raises


def test_toggling_twice_returns_to_off(monkeypatch) -> None:
    calls, screen = _drive(monkeypatch, [_D, _D, _E, _Y])
    assert calls[0]["dock_new_ports"] is False, calls[0]
    assert screen.gate_raises == [("Explore", 5)], screen.gate_raises


# --------------------------------------------------------------------------
# A toggle never starts anything, and never survives an unanswered gate
# --------------------------------------------------------------------------

def test_toggles_alone_arm_nothing_and_raise_no_gate(monkeypatch) -> None:
    calls, screen = _drive(monkeypatch, [_D, _F])
    assert calls == [], calls
    assert screen.gate_raises == [], screen.gate_raises


def test_toggling_while_the_gate_is_up_clears_it_and_arms_nothing(monkeypatch) -> None:
    """Deliberate: changing a flag INVALIDATES a standing confirm.

    The gate is single-shot and default-deny, so `D` cancels it like any
    non-`y` key. That is the property worth having -- it makes it
    impossible to answer `y` to a line composed under different flags than
    the run will use.
    """
    calls, screen = _drive(monkeypatch, [_E, _D, _Y])
    assert calls == [], calls
    assert screen.gate_raises == [("Explore", 5)], screen.gate_raises


def test_toggles_do_nothing_when_no_explore_offer_is_standing(monkeypatch) -> None:
    """Same guard `E` carries: no offer, no opt-in. Otherwise the flags
    could be set on a screen where explore was never on the table.

    The `calls == []` half of this is NOT enough on its own and was
    measured to be vacuous: with no offer standing, `E` refuses to raise
    the gate anyway, so nothing arms whether or not the toggle fired. A
    mutation removing `and explore_offered` from the toggle branch left
    this test GREEN. The status line is the observable that can actually
    tell the two worlds apart -- the toggle's only visible effect.
    """
    calls, screen = _drive(
        monkeypatch, [_D, _F, _E, _Y],
        ensure=_Result(ok=True, classification="unknown"),
    )
    assert calls == [], calls
    assert screen.gate_raises == [], screen.gate_raises
    status = screen.status_line or ""
    assert status != explore_flags.describe_dock(True), status
    assert status != explore_flags.describe_dock(False), status
    assert status != explore_flags.describe_tolls(True), status
    assert status != explore_flags.describe_tolls(False), status


# --------------------------------------------------------------------------
# The asymmetry pin -- structural, with a non-vacuity control
# --------------------------------------------------------------------------

def _explore_start_call_node() -> ast.Call:
    """The `explore_start_for_profile(...)` call node inside `_run_play`."""
    tree = ast.parse(inspect.getsource(app_mod))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "explore_start_for_profile":
            return node
    raise AssertionError("no explore_start_for_profile call site found in app.py")


def test_the_call_site_this_pin_inspects_actually_exists() -> None:
    """Non-vacuity control.

    Without this, a rename or a refactor that moved the call would make
    `_explore_start_call_node` raise inside the pin below -- and a pin that
    errors for the wrong reason is indistinguishable from one that passes
    for the right one until someone reads the traceback.
    """
    node = _explore_start_call_node()
    passed = {kw.arg for kw in node.keywords}
    assert "dock_new_ports" in passed, passed
    assert "fight_tolls" in passed, passed


def test_call_site_does_not_coerce_either_flag() -> None:
    """Neither flag may be wrapped in `bool(...)` at the Play call site.

    `bool()` here is a no-op today -- a toggle only ever produces
    True/False -- which is exactly what makes it dangerous to write: it
    reads as harmless tidying, it matches `session/cli.py:952`'s house
    style, and it would still be there the day a non-bool can reach this
    layer. At that point `bool("no")` is `True` and an operator who
    declined combat has armed it.

    AST rather than grep: a text search for `bool(` hits the docstrings and
    comments that explain this very rule, so it would stay green on the
    real defect.
    """
    node = _explore_start_call_node()
    for kw in node.keywords:
        if kw.arg not in ("dock_new_ports", "fight_tolls"):
            continue
        assert isinstance(kw.value, ast.Name), (
            f"{kw.arg} must be forwarded as a bare name, got "
            f"{ast.dump(kw.value)} -- see cockpit/explore_flags.py on why "
            f"these two flags must not be symmetrised."
        )


# --------------------------------------------------------------------------
# The composer / key resolver in isolation (hardening family: never raises)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [None, True, False, "d", 3.0, object(), b"d"])
def test_toggle_resolvers_reject_non_keycodes(bad) -> None:
    """`True == 1` in Python, so a stray bool must not read as Ctrl-A -- the
    same guard `armconfirm.resolve_arm_confirm_key` carries."""
    assert explore_flags.resolve_dock_toggle_key(bad) is False
    assert explore_flags.resolve_tolls_toggle_key(bad) is False


def test_toggle_resolvers_accept_both_cases() -> None:
    for k in (ord("d"), ord("D")):
        assert explore_flags.resolve_dock_toggle_key(k) is True
    for k in (ord("f"), ord("F")):
        assert explore_flags.resolve_tolls_toggle_key(k) is True


def test_the_two_toggles_do_not_share_a_key() -> None:
    """A shared keycode would make one flag unreachable while every
    single-flag test above still passed."""
    assert not (explore_flags.DOCK_TOGGLE_KEYS & explore_flags.TOLLS_TOGGLE_KEYS)


def test_compose_returns_the_action_unchanged_when_both_are_off() -> None:
    assert explore_flags.compose_explore_action("Explore") == "Explore"
    assert explore_flags.compose_explore_action(
        "Explore", dock=False, tolls=False
    ) == "Explore"


def test_compose_appends_markers_in_a_stable_order() -> None:
    assert explore_flags.compose_explore_action("Explore", dock=True) == "Explore +dock"
    assert explore_flags.compose_explore_action("Explore", tolls=True) == "Explore +fight-tolls"
    assert explore_flags.compose_explore_action(
        "Explore", dock=True, tolls=True
    ) == "Explore +dock +fight-tolls"


@pytest.mark.parametrize("bad", [None, 3, object(), b"x"])
def test_compose_never_raises_on_a_bad_action(bad) -> None:
    out = explore_flags.compose_explore_action(bad, dock=True, tolls=True)
    assert isinstance(out, str)
    assert explore_flags.DOCK_MARKER in out


def test_describe_states_the_consequence_not_the_variable_name() -> None:
    """An operator reading `dock ON` learns nothing about what it spends."""
    assert "commodities" in explore_flags.describe_dock(True)
    assert "passed by" in explore_flags.describe_dock(False)
    assert "FOUGHT" in explore_flags.describe_tolls(True)
    assert "halt" in explore_flags.describe_tolls(False)
