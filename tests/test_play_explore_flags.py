"""WO-PLAY-EXPLORE-FLAGS / WO-PLAY-EXPLORE-GATHER-DEFAULT-ON -- Play explore
automation toggles (dock gather default ON; fight-tolls default OFF).

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

def _drive(monkeypatch, keys, *, ensure=None, explore=None, spectating=False):
    """Run `_run_play`; return (explore_call_kwargs, screen).

    spectating=True skips App-armed ensure kick so toggles/`E` can be the
    first start (policy explore still arms on `E`).
    """
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
            if spectating:
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
    return calls, seen.get("screen")

_E, _Y = ord("E"), ord("y")
_D, _X = ord("D"), ord("X")

# Confirm actions, derived from the module's own constants so the gate-tuple
# pins below stay readable. OFF-marker *content* is pinned by LITERAL in
# `test_the_off_marker_names_both_the_state_and_the_key`.
_OFF_ACTION = f"Explore {explore_flags.DOCK_OFF_MARKER}"
_ON_ACTION = f"Explore {explore_flags.DOCK_MARKER}"

# --------------------------------------------------------------------------
# Play gather defaults ON; fight-tolls stays OFF
# --------------------------------------------------------------------------

def test_default_arm_forwards_dock_on_and_tolls_off(monkeypatch) -> None:
    """App-armed ensure kick → dock True, fight-tolls False, infinite."""
    calls, _screen = _drive(monkeypatch, [])
    assert len(calls) == 1, calls
    assert calls[0]["dock_new_ports"] is True, calls[0]
    assert calls[0]["fight_tolls"] is False, calls[0]
    assert calls[0]["min_sectors"] == app_mod._EXPLORE_POLICY_MIN_SECTORS == 0

def test_e_restarts_without_confirm_gate(monkeypatch) -> None:
    calls, screen = _drive(monkeypatch, [_E], spectating=True)
    assert len(calls) == 1, calls
    assert screen.gate_raises == [], screen.gate_raises
    assert calls[0]["dock_new_ports"] is True
    assert calls[0]["min_sectors"] == 0

def test_dock_toggle_disables_gather_on_e_restart(monkeypatch) -> None:
    """`D` before `E` (no App-armed kick) passes ports (dock OFF)."""
    calls, _screen = _drive(monkeypatch, [_D, _E], spectating=True)
    assert len(calls) == 1, calls
    assert calls[0]["dock_new_ports"] is False, calls[0]
    assert calls[0]["fight_tolls"] is False, calls[0]

def test_tolls_toggle_forwards_true_and_keeps_dock_on(monkeypatch) -> None:
    calls, _screen = _drive(monkeypatch, [_X, _E], spectating=True)
    assert len(calls) == 1, calls
    assert calls[0]["fight_tolls"] is True, calls[0]
    assert calls[0]["dock_new_ports"] is True, calls[0]

def test_dock_off_plus_tolls_on_forwards_both(monkeypatch) -> None:
    calls, _screen = _drive(monkeypatch, [_D, _X, _E], spectating=True)
    assert len(calls) == 1, calls
    assert calls[0]["dock_new_ports"] is False, calls[0]
    assert calls[0]["fight_tolls"] is True, calls[0]

def test_toggling_twice_returns_to_default_on(monkeypatch) -> None:
    calls, _screen = _drive(monkeypatch, [_D, _D, _E], spectating=True)
    assert calls[0]["dock_new_ports"] is True, calls[0]

def test_toggles_alone_do_not_add_starts_beyond_ensure_kick(monkeypatch) -> None:
    """App-armed ensure may kick once; `D`/`X` alone never start another run."""
    calls, screen = _drive(monkeypatch, [_D, _X])
    assert len(calls) == 1, calls  # ensure kick only
    assert screen.gate_raises == [], screen.gate_raises

def test_toggles_alone_arm_nothing_when_not_app_armed(monkeypatch) -> None:
    calls, screen = _drive(monkeypatch, [_D, _X], spectating=True)
    assert calls == [], calls
    assert screen.gate_raises == [], screen.gate_raises

def test_toggles_do_nothing_when_no_explore_offer_is_standing(monkeypatch) -> None:
    calls, screen = _drive(
        monkeypatch, [_D, _X, _E],
        ensure=_Result(ok=True, classification="unknown"),
        spectating=True,
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
    """A policy `explore_start_for_profile(...)` call with dock/tolls kwargs.

    Prefers ``_start_policy_explore`` (trainer path); falls back to the first
    call that forwards both flags as bare names.
    """
    tree = ast.parse(inspect.getsource(app_mod))
    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "explore_start_for_profile":
            candidates.append(node)
    for node in candidates:
        passed = {kw.arg for kw in node.keywords}
        if {"dock_new_ports", "fight_tolls"} <= passed:
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
    for k in (ord("x"), ord("X")):
        assert explore_flags.resolve_tolls_toggle_key(k) is True

def test_the_two_toggles_do_not_share_a_key() -> None:
    """A shared keycode would make one flag unreachable while every
    single-flag test above still passed."""
    assert not (explore_flags.DOCK_TOGGLE_KEYS & explore_flags.TOLLS_TOGGLE_KEYS)

def test_compose_states_no_dock_when_the_operator_has_not_opted_in() -> None:
    """Was `test_compose_returns_the_action_unchanged_when_both_are_off`,
    which asserted `compose_explore_action("Explore") == "Explore"`.

    Silence is not a description. The gate's job is to describe the run it
    arms, and "explore, passing every port" is a different run from
    "explore" — the operator was reading the second and getting the first.
    """
    assert explore_flags.compose_explore_action("Explore") == _OFF_ACTION
    assert explore_flags.compose_explore_action(
        "Explore", dock=False, tolls=False
    ) == _OFF_ACTION

def test_ensure_does_not_paint_gather_hint_or_press_e(monkeypatch) -> None:
    """WO-PLAY-STRIP-POLICY-AUTO REVISE: LOGS has no explore-available tease."""
    _calls, screen = _drive(monkeypatch, [])
    line = screen.status_line or ""
    assert "press E" not in line, line
    assert "D to pass" not in line, line
    assert explore_flags.GATHER_HINT == ""
    assert "GATHER_HINT" not in line

def test_the_off_marker_names_port_trade_not_d_key() -> None:
    """Pinned by LITERAL — gather OFF tracks Port Trade·OFF, not `D to gather`."""
    assert explore_flags.DOCK_OFF_MARKER == "no-dock (Port Trade·OFF)"

def test_compose_appends_markers_in_a_stable_order() -> None:
    """`+dock` is unchanged byte-for-byte — the opted-IN line an operator
    may already recognise must not shift under them (WO regression pin)."""
    assert explore_flags.compose_explore_action("Explore", dock=True) == "Explore +dock"
    assert explore_flags.compose_explore_action(
        "Explore", tolls=True
    ) == f"{_OFF_ACTION} +fight-tolls"
    assert explore_flags.compose_explore_action(
        "Explore", dock=True, tolls=True
    ) == "Explore +dock +fight-tolls"

def test_fight_tolls_stays_silent_when_off_while_dock_speaks() -> None:
    """The asymmetry, pinned so it cannot be "tidied" into symmetry.

    Naming an affordance is a nudge, and nudges are directional. Pointing an
    operator at commodity gathering (or how to re-enable it when OFF) costs
    them nothing; an equally helpful "F to fight tolls" on every prompt would
    advertise a path that SPENDS fighters. Loud toward the safe action, quiet
    toward the spend.
    """
    off = explore_flags.compose_explore_action("Explore", dock=False, tolls=False)
    assert "Port Trade" in off, off
    assert explore_flags.TOLLS_MARKER not in off, off
    assert "toll" not in off.lower(), off
    assert explore_flags.GATHER_HINT == ""

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
