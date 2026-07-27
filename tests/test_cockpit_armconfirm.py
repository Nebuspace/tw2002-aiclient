"""WO-P5-063 -- the confirm-to-arm gate.

Layer-A: canon wording, the y/N/Enter/Esc key matrix, the default-deny key
policy, the danger-BOLD+reverse palette weight, and the two structural
guarantees the Accept turns on -- that a bare Enter cannot arm, and that no
production call site can raise the gate silently.
"""

from __future__ import annotations

import ast
import curses
import inspect
from pathlib import Path

import pytest

from tw2002_aiclient import screens as screens_mod
from tw2002_aiclient.cockpit import armconfirm
from tw2002_aiclient.cockpit.armconfirm import (
    CANCEL,
    CONFIRM,
    CONFIRM_HINT,
    LIVE_MARKER,
    compose_arm_confirm_line,
    resolve_arm_confirm_key,
)
from tw2002_aiclient.cockpit.layout import frame_layout

FULL_ROWS, FULL_COLS = 40, 160
HANDLE = "Alpha"

CANON = Path(__file__).resolve().parents[1] / "canon" / "surfaces"


# --------------------------------------------------------------------------
# The key matrix (Accept #1, #3, #4).
# --------------------------------------------------------------------------

def test_only_y_confirms() -> None:
    assert resolve_arm_confirm_key(ord("y")) == CONFIRM
    assert resolve_arm_confirm_key(ord("Y")) == CONFIRM


@pytest.mark.parametrize(
    "key, name",
    [
        (ord("N"), "N"),
        (ord("n"), "n"),
        (10, "Enter (LF)"),
        (13, "Enter (CR)"),
        (curses.KEY_ENTER, "KEY_ENTER"),
        (27, "Esc"),
        (ord("q"), "q"),
        (ord("Q"), "Q"),
        (1, "Ctrl-A / MODE_KEY"),
        (ord(" "), "Space"),
        (curses.KEY_RESIZE, "KEY_RESIZE"),
        (curses.KEY_LEFT, "arrow"),
        (-1, "getch timeout"),
    ],
)
def test_everything_else_cancels(key: int, name: str) -> None:
    assert resolve_arm_confirm_key(key) == CANCEL, f"{name} must not arm"


def test_bare_enter_does_not_arm() -> None:
    """Accept #3, called out on its own because it is the scar-doctrine one."""
    for enter in (10, 13, curses.KEY_ENTER):
        assert resolve_arm_confirm_key(enter) == CANCEL


def test_policy_is_default_deny_across_the_whole_keycode_space() -> None:
    """The structural claim: `y`/`Y` are the ONLY confirming keycodes.

    Swept rather than sampled, because the value of default-deny is exactly
    its behaviour on keys nobody enumerated.
    """
    confirming = [k for k in range(-1, 2048) if resolve_arm_confirm_key(k) == CONFIRM]
    assert confirming == [ord("Y"), ord("y")]


@pytest.mark.parametrize("hostile", [None, "y", b"y", 1.0, object(), [], {}, True, False])
def test_uninterpretable_keys_cancel(hostile: object) -> None:
    """A key this layer cannot even interpret is the last thing that should
    commit live turns. `True` is included deliberately: `bool` is an `int`
    subclass and `True == 1`, so an unguarded `in` test would let a stray
    boolean through the numeric path."""
    assert resolve_arm_confirm_key(hostile) == CANCEL


# --------------------------------------------------------------------------
# Canon wording (Accept #2's sibling -- the prompt says what runs).
# --------------------------------------------------------------------------

def test_line_matches_canon_shape() -> None:
    line = compose_arm_confirm_line('Play "Ferren-Sol"', cycles=3)
    assert line == 'Play "Ferren-Sol" x3 LIVE?  y/N'


def test_canon_actually_contains_this_shape() -> None:
    """Neither the marker nor the hint is this repo's invention."""
    text = (CANON / "mode-line-and-teach-controls.md").read_text(encoding="utf-8")
    assert 'Play "Ferren-Sol" x3 LIVE?  y/N' in text
    assert LIVE_MARKER in text and CONFIRM_HINT in text


def test_hint_capitalisation_marks_no_as_the_default() -> None:
    """Canon: "the `y/N` capitalization signals the safe default is No"."""
    assert CONFIRM_HINT == "y/N"
    assert CONFIRM_HINT.endswith("N") and CONFIRM_HINT.startswith("y")


def test_cycle_count_omitted_rather_than_guessed() -> None:
    for bad in (None, 0, -3, "3", 1.5, True, object()):
        line = compose_arm_confirm_line("Arm autopilot", cycles=bad)
        assert " x" not in line, f"cycles={bad!r} invented a count: {line!r}"


def test_unlabelled_gate_still_names_the_risk() -> None:
    for empty in (None, "", "   ", 0, object()):
        line = compose_arm_confirm_line(empty)
        assert line.endswith(f"{LIVE_MARKER}  {CONFIRM_HINT}")
        assert line.strip() != f"{LIVE_MARKER}  {CONFIRM_HINT}", "prompt lost its subject"


def test_embedded_newline_cannot_push_the_hint_off_the_line() -> None:
    line = compose_arm_confirm_line("Arm\nautopilot\r\nx99")
    assert "\n" not in line and "\r" not in line
    assert line.endswith(f"{LIVE_MARKER}  {CONFIRM_HINT}")


def test_compose_is_ascii_and_unicode_ok_is_inert() -> None:
    assert compose_arm_confirm_line("Arm", cycles=2, unicode_ok=True) == \
        compose_arm_confirm_line("Arm", cycles=2, unicode_ok=False)
    assert compose_arm_confirm_line("Arm").isascii()


# --------------------------------------------------------------------------
# The palette weight (Accept #2) -- pinned by attr identity, not tone name.
# --------------------------------------------------------------------------

class _Win:
    def __init__(self, rows=FULL_ROWS, cols=FULL_COLS):
        self._rows, self._cols = rows, cols
        self.writes: list[tuple[int, int, str, int]] = []

    def getmaxyx(self): return (self._rows, self._cols)
    def erase(self): pass
    def refresh(self): pass
    def addstr(self, y, x, s, attr=0): self.writes.append((y, x, s, attr))
    def addnstr(self, y, x, s, n, attr=0): self.writes.append((y, x, s[:n], attr))
    def attron(self, a): pass
    def attroff(self, a): pass
    def hline(self, *a, **k): pass
    def vline(self, *a, **k): pass
    def border(self, *a, **k): pass
    def chgat(self, *a, **k): pass


def _screen(monkeypatch, win):
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    s = screens_mod.PlayShellScreen(win, profile)
    s.spectating = False
    s.attached = False
    s.status_provider = lambda: None
    return s


def test_gate_attr_carries_bold_and_reverse(monkeypatch) -> None:
    s = _screen(monkeypatch, _Win())
    attr = s._arm_confirm_attr()
    assert attr & curses.A_BOLD, "gate lost the table row's BOLD"
    assert attr & curses.A_REVERSE, "gate lost reverse-video"


def test_gate_attr_is_not_the_non_bold_viewport_danger(monkeypatch) -> None:
    """The trap this WO was warned about.

    `visual-language.md:58` = danger red/**bold** (the 7-tone table row, and
    it lists the live-play y/N confirm among its own examples).
    `visual-language.md:83` = danger red **non-bold**, a deliberate override
    for the viewport border only, exposed as `_viewport_danger_attr`.
    Using the latter here renders the money-path gate QUIETER than the frame
    around it while still passing any "is it danger-toned?" check.
    """
    s = _screen(monkeypatch, _Win())
    assert s._arm_confirm_attr() != s._viewport_danger_attr


def test_canon_grounds_both_danger_weights() -> None:
    text = (CANON / "visual-language.md").read_text(encoding="utf-8")
    assert "the live-play `y/N` confirm" in text
    assert "non-bold" in text  # the deliberate per-surface override exists


# --------------------------------------------------------------------------
# The screens wire.
# --------------------------------------------------------------------------

def test_cockpit_opens_with_no_gate_pending(monkeypatch) -> None:
    """A freshly opened cockpit can never be one keystroke from arming."""
    assert _screen(monkeypatch, _Win())._arm_confirm is None


def test_y_does_nothing_when_no_gate_is_up(monkeypatch) -> None:
    s = _screen(monkeypatch, _Win())
    assert s.handle_key(ord("y")) is None
    assert s._arm_confirm is None


def test_gate_confirm_returns_intent_and_closes(monkeypatch) -> None:
    s = _screen(monkeypatch, _Win())
    s.begin_arm_confirm("Arm autopilot", cycles=3)
    assert s._arm_confirm is not None
    assert s.handle_key(ord("y")) == "arm_confirm"
    assert s._arm_confirm is None, "gate must be single-shot"


@pytest.mark.parametrize("key", [ord("N"), ord("n"), 10, 13, 27, ord("q"), 1, -1])
def test_gate_cancels_with_no_state_change_and_no_leak(monkeypatch, key: int) -> None:
    """Accept #1: `N`/Esc/any other key cancels **with no state change**.

    The leak this guards: `Esc` returns "back" and `q` returns "quit" in the
    handler below the gate. If the gate were placed after them, cancelling
    would also tear down the screen.
    """
    s = _screen(monkeypatch, _Win())
    s.begin_arm_confirm("Arm autopilot")
    before = (s.spectating, s.attached, s._conn_focused)
    assert s.handle_key(key) is None, f"key {key} leaked an intent while gating"
    assert s._arm_confirm is None
    assert (s.spectating, s.attached, s._conn_focused) == before


def test_gate_intercepts_before_every_other_binding(monkeypatch) -> None:
    """Same keys, gate down -> their normal meanings still work."""
    s = _screen(monkeypatch, _Win())
    assert s.handle_key(27) == "back"
    assert s.handle_key(ord("q")) == "quit"
    assert s.handle_key(screens_mod.MODE_KEY) == "attach"


def test_gate_renders_on_the_control_strip_row(monkeypatch) -> None:
    win = _Win()
    s = _screen(monkeypatch, win)
    s.begin_arm_confirm('Play "Ferren-Sol"', cycles=3)
    s.draw()
    region = frame_layout(FULL_ROWS, FULL_COLS)["control_strip"]
    rows = {y for (y, _x, text, _a) in win.writes if "LIVE?" in text}
    assert rows, "confirm line never reached the screen"
    assert region["y"] in rows


def test_gate_is_drawn_with_the_loud_attr(monkeypatch) -> None:
    win = _Win()
    s = _screen(monkeypatch, win)
    s.begin_arm_confirm("Arm autopilot")
    s.draw()
    attrs = [a for (_y, _x, text, a) in win.writes if "LIVE?" in text]
    assert attrs, "confirm line never drawn"
    for a in attrs:
        assert a & curses.A_BOLD and a & curses.A_REVERSE


# --------------------------------------------------------------------------
# Accept #5 -- no silent arm inject in any code path.
# --------------------------------------------------------------------------

def test_exactly_three_production_call_sites_raise_the_gate() -> None:
    """WO-PLAY-EXPLORE-ARM flipped this pin once already; WO-AUTOLOOP-
    RELAUNCH-COCKPIT flipped it again; WO-PLAY-AUTOLOOP-START flips it a
    third time, deliberately.

    WO-P5-063 shipped the gate with ZERO production callers and a pin
    asserting exactly that, so the first one would have to be a decision
    rather than an accident. L3 was that decision: the post-ensure explore
    offer in `app._run_play`. WO-AUTOLOOP-RELAUNCH-COCKPIT adds a second,
    equally deliberate one in the same function: the relaunch offer, gated
    on `resolve_relaunch_offer_key` rather than on any "is a run active"
    precondition (the daemon itself refuses honestly -- `not_paused` /
    `no_resumable_run` -- so this cockpit adds no redundant client-side
    gate of its own).

    WO-PLAY-AUTOLOOP-START adds the third: canon's `L)chains` Trade-Loop-
    Chains popup, where `Enter` on a taught-macro row raises the gate. It is
    the same deliberate shape as the two before it -- selection ARMS a
    pending action and nothing else, and only a subsequent `y` reaches
    `adapters.autoloop_start`. Canon names this one directly:
    `mode-line-and-teach-controls.md` §"Confirm-gate — never one keystroke
    to live money" ("selecting a chain ... arms a pending action and raises
    an explicit confirm prompt").

    The pin is UPDATED, not deleted -- it now asserts there are exactly
    THREE production call sites, all in `app.py`. A FOURTH caller appearing
    without its own WO still goes red first, which is the property that
    made the original worth having. Deleting it would have converted a
    live guard into silence at the exact moment it started guarding
    something real.

    This test caught the third addition on its first full-suite run, which
    is the whole argument for a counted tripwire over a "gates are gated"
    assertion: the count is what makes a new money path impossible to add
    quietly.
    """
    root = Path(screens_mod.__file__).resolve().parent
    callers = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            func = getattr(node, "func", None)
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if isinstance(node, ast.Call) and name == "begin_arm_confirm":
                callers.append(path.name)
    assert callers == ["app.py", "app.py", "app.py"], (
        f"expected exactly three production callers, all in app.py (the "
        f"post-ensure explore offer, the relaunch offer, and the L)chains "
        f"taught-loop arm); found {callers}"
    )


def test_the_one_caller_is_gated_not_raised_unconditionally() -> None:
    """The gate must be raised only behind a guard -- never on entry.

    Structural (AST), not a source-text match. An earlier draft of this pin
    asserted a literal source line and broke the moment the guard was
    refactored from an inline comparison to a named flag, while the
    behaviour was correct throughout -- a check answering "does this exact
    string appear" while claiming "is the call guarded".

    Hub ruling 2026-07-27T03:35:06Z: do NOT auto-raise the modal confirm
    gate. A modal raised unbidden consumes the operator's next keystroke,
    and that key is usually their Ctrl-A attach chord.
    """
    from tw2002_aiclient import app as app_mod

    tree = ast.parse(inspect.getsource(app_mod))

    def _calls_begin(node):
        return any(
            isinstance(n, ast.Call)
            and (getattr(n.func, "attr", None) == "begin_arm_confirm")
            for n in ast.walk(node)
        )

    guarded = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _calls_begin(node):
            guarded.append(ast.dump(node.test))
    assert guarded, "begin_arm_confirm is not inside any `if` -- raised unconditionally"
    # And the guard is the standing-offer flag, not merely `result.ok`.
    assert any("explore_offered" in g or "_EXPLORE_OFFER_KEYS" in g for g in guarded), guarded


def test_the_offer_is_gated_on_the_ready_classification() -> None:
    """`ok` alone is not enough: the offer stands only at the literal ready
    classification, so explore is never offered against an unknown screen."""
    from tw2002_aiclient import app as app_mod

    assert app_mod._EXPLORE_OFFER_CLASSIFICATION == "main_command"
    src = inspect.getsource(app_mod)
    assert "_EXPLORE_OFFER_CLASSIFICATION" in src


def test_prompt_and_run_share_one_cycle_constant() -> None:
    """The confirm gate's whole value is that the prompt is the truth about
    what happens next. If the number shown and the number sent came from
    two literals, they could drift and the human would be agreeing to
    something other than what runs."""
    from tw2002_aiclient import app as app_mod

    src = inspect.getsource(app_mod)
    assert "cycles=_EXPLORE_MIN_SECTORS" in src
    assert "min_sectors=_EXPLORE_MIN_SECTORS" in src


def test_gate_module_holds_no_send_or_daemon_path() -> None:
    """Structural, not textual.

    A `forbidden in source` grep fails here for the wrong reason: this
    module's docstring quotes the WO constraint "...not the daemon call",
    so the word appears precisely where the module explains it does NOT do
    the thing. Docstrings and comments are not code -- walk the AST and
    look at identifiers that are actually referenced, plus imports.
    """
    tree = ast.parse(inspect.getsource(armconfirm))
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)
        elif isinstance(node, ast.Import):
            referenced.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            referenced.add((node.module or "").split(".")[0])
            referenced.update(a.name for a in node.names)

    forbidden = {"send", "sendall", "send_request", "send_text", "send_bytes",
                 "socket", "subprocess", "daemon", "conn", "connection"}
    hits = referenced & forbidden
    assert hits == set(), f"armconfirm references {sorted(hits)} in CODE"


def test_that_ast_check_would_actually_catch_a_send() -> None:
    """The bypass meta-test: prove the guard above is not vacuous.

    A structural check that cannot fail is worse than no check, so feed it
    a module that really does reference a send path and confirm it trips.
    """
    tree = ast.parse("import socket\ndef go(s):\n    s.send_request('x')\n")
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)
        elif isinstance(node, ast.Import):
            referenced.update(a.name.split(".")[0] for a in node.names)
    assert referenced & {"send_request", "socket"} == {"send_request", "socket"}


def test_confirm_intent_is_a_bare_string_not_a_call(monkeypatch) -> None:
    """The intent must stay inert: `handle_key` returns a signal, it does not
    arm anything itself (WO constraint -- write-back is still a 062 stub)."""
    s = _screen(monkeypatch, _Win())
    s.begin_arm_confirm("Arm autopilot")
    assert s.handle_key(ord("y")) == "arm_confirm"
    src = inspect.getsource(screens_mod.PlayShellScreen.handle_key)
    assert "arm_confirm" in src
    for forbidden in ("send_request(", "autopilot_start", "explore_start"):
        assert forbidden not in src
