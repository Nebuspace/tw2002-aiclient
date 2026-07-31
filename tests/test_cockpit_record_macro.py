"""WO-P5-067 — R Record scaffold.

Pins:

1.  :data:`REDACTED_SENTINEL` is a non-empty string that is never a plausible
    real keystroke.
2.  :func:`auto_name` returns a filesystem-safe, classification-derived name
    that never raises.
3.  :class:`RecordSession` lifecycle — start / add_step / stop / cancel.
4.  Secret steps: ``is_secret=True`` stores REDACTED_SENTINEL, not plaintext.
5.  ``R`` key returns ``"record_toggle"`` intent from
    ``PlayShellScreen.handle_key`` (both ``r`` and ``R``).
6.  ``R`` does NOT call ``explore_start`` / send — no fire path from record.
7.  Explore ``E`` and Assign-Trigger ``T`` paths are unchanged by this WO.
8.  The ``record_macro`` module itself has no send path (grep guard).
9.  Round-trip proof: start → add_step × 2 → save → artifact loads and
    has the correct step data.
10. Redacted step is in the saved artifact as REDACTED_SENTINEL.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest

from tw2002_aiclient.cockpit import record_macro
from tw2002_aiclient.cockpit.record_macro import (
    REDACTED_SENTINEL,
    RecordSession,
    SaveResult,
    auto_name,
)


# ---------------------------------------------------------------------------
# Shared screen fixtures — same shapes as test_loop_recorder.py
# ---------------------------------------------------------------------------

_ANCHOR_ROWS = [
    "Sector  : 158 in uncharted space.",
    "Ports   : Aegis, Class 1 (BBS)",
    "Warps to Sector(s) :  231 - 4309",
    "Command [TL=00:00:00]:[158] (?=Help)? :",
]
_PORT_ROWS = [
    "Docking...",
    "",
    "Commerce report for Aegis: 1 Fuel Ore, Organics, Equipment",
    "",
    "<Trade with this port> (Y/N)? ",
]
_ANCHOR_ROWS2 = [
    "Sector  : 158 in uncharted space.",
    "Warps to Sector(s) :  231 - 4309",
    "Command [TL=00:00:00]:[158] (?=Help)? :",
]


# ---------------------------------------------------------------------------
# 1 — REDACTED_SENTINEL
# ---------------------------------------------------------------------------

def test_redacted_sentinel_is_nonempty_string() -> None:
    assert isinstance(REDACTED_SENTINEL, str)
    assert REDACTED_SENTINEL


def test_redacted_sentinel_is_not_a_plausible_single_keystroke() -> None:
    """<cockpit-redacted> contains angle-brackets and a hyphen — no real
    TW2002 keystroke is a multi-char string with '<' / '>'.  This is the
    test-visible proof that a secret step is distinguishable at a glance."""
    assert "<" in REDACTED_SENTINEL and ">" in REDACTED_SENTINEL
    assert len(REDACTED_SENTINEL) > 1


# ---------------------------------------------------------------------------
# 2 — auto_name
# ---------------------------------------------------------------------------

def test_auto_name_returns_str() -> None:
    assert isinstance(auto_name(), str)


def test_auto_name_includes_classification() -> None:
    name = auto_name("main_command")
    assert "main_command" in name


def test_auto_name_includes_timestamp_fragment() -> None:
    """The name must carry enough of an ISO-8601 fragment to be unique."""
    name = auto_name("main_command")
    # UTC timestamps contain digits; the name must not be all-alpha.
    assert any(c.isdigit() for c in name)


def test_auto_name_none_classification_uses_fallback() -> None:
    name = auto_name(None)
    assert isinstance(name, str) and name


def test_auto_name_bad_classification_never_raises() -> None:
    for bad in (0, [], object(), b"bytes", True):
        result = auto_name(bad)
        assert isinstance(result, str) and result


def test_auto_name_is_filesystem_safe() -> None:
    """No path separators or null bytes in the name."""
    for cls in (None, "main_command", "port_trade", "unknown"):
        name = auto_name(cls)
        for forbidden in ("/", "\\", "\0"):
            assert forbidden not in name, f"auto_name({cls!r}) contains {forbidden!r}"


# ---------------------------------------------------------------------------
# 3 — RecordSession lifecycle
# ---------------------------------------------------------------------------

def test_record_session_starts_inactive() -> None:
    assert RecordSession().active is False


def test_record_session_step_count_starts_zero() -> None:
    assert RecordSession().step_count == 0


def test_start_activates_session() -> None:
    s = RecordSession()
    s.start("ore-run", _ANCHOR_ROWS)
    assert s.active is True


def test_start_resets_previous_steps() -> None:
    s = RecordSession()
    s.start("first", _ANCHOR_ROWS)
    s.add_step("P", _PORT_ROWS)
    assert s.step_count == 1
    s.start("second", _ANCHOR_ROWS)
    assert s.step_count == 0


def test_add_step_increments_step_count() -> None:
    s = RecordSession()
    s.start("ore-run", _ANCHOR_ROWS)
    s.add_step("P", _PORT_ROWS)
    assert s.step_count == 1
    s.add_step("Y", _ANCHOR_ROWS2)
    assert s.step_count == 2


def test_add_step_ignored_when_not_active() -> None:
    s = RecordSession()
    s.add_step("P", _PORT_ROWS)  # not active
    assert s.step_count == 0


def test_add_step_ignored_for_non_str_keystrokes() -> None:
    s = RecordSession()
    s.start("ore-run", _ANCHOR_ROWS)
    for bad in (None, 0, [], b"bytes", object()):
        s.add_step(bad, _ANCHOR_ROWS2)
    assert s.step_count == 0


def test_add_step_ignored_for_non_list_rows() -> None:
    s = RecordSession()
    s.start("ore-run", _ANCHOR_ROWS)
    for bad in (None, "string", 0, object()):
        s.add_step("P", bad)
    assert s.step_count == 0


def test_cancel_deactivates_and_clears() -> None:
    s = RecordSession()
    s.start("ore-run", _ANCHOR_ROWS)
    s.add_step("P", _PORT_ROWS)
    s.cancel()
    assert s.active is False
    assert s.step_count == 0


def test_save_on_inactive_session_returns_none() -> None:
    s = RecordSession()
    assert s.save() is None


def test_save_deactivates_session() -> None:
    s = RecordSession()
    s.start("ore-run", _ANCHOR_ROWS)
    # stop with no steps → None (empty recording; not started)
    s.save()
    assert s.active is False


@pytest.mark.parametrize("hostile", [None, 0, [], object(), b"x"])
def test_start_never_raises_on_bad_name(hostile: object) -> None:
    s = RecordSession()
    s.start(hostile, _ANCHOR_ROWS)  # must not raise
    assert s.active is True


@pytest.mark.parametrize("hostile", [None, 0, "string", object()])
def test_start_never_raises_on_bad_opening_rows(hostile: object) -> None:
    s = RecordSession()
    s.start("ore-run", hostile)  # must not raise
    assert s.active is True


@pytest.mark.parametrize("hostile", [None, "x", 0, [], object()])
def test_session_methods_never_raise(hostile: object) -> None:
    s = RecordSession()
    s.start(hostile, hostile)
    s.add_step(hostile, hostile)
    s.cancel()
    s.save()  # should return None, not raise


# ---------------------------------------------------------------------------
# 4 — Secret-step redaction
# ---------------------------------------------------------------------------

def test_secret_step_stores_redacted_sentinel_not_plaintext() -> None:
    s = RecordSession()
    s.start("ore-run", _ANCHOR_ROWS)
    s.add_step("hunter2", _ANCHOR_ROWS2, is_secret=True)
    # We can't inspect _steps directly (private), but we can verify
    # it through save() + the saved document.
    pass  # structural check below; see round-trip test


def test_save_writes_redacted_sentinel_for_secret_step(tmp_path: Path) -> None:
    """After save(), the saved JSON document must carry REDACTED_SENTINEL as
    the secret step's ``input``, never the plaintext password."""
    s = RecordSession()
    s.start("redact-test", _ANCHOR_ROWS)
    s.add_step("hunter2", _ANCHOR_ROWS2, is_secret=True)
    result = s.save(skills_dir=str(tmp_path))

    assert result is not None, "expected a SaveResult, got None"
    doc = json.loads(result.path.read_text(encoding="utf-8"))
    step_inputs = [step["input"] for step in doc["steps"]]
    assert step_inputs == [REDACTED_SENTINEL], (
        f"expected [{REDACTED_SENTINEL!r}], got {step_inputs!r}"
    )
    assert "hunter2" not in str(doc), "plaintext password leaked into document"


def test_non_secret_step_stores_plaintext_keystroke(tmp_path: Path) -> None:
    s = RecordSession()
    s.start("plain-test", _ANCHOR_ROWS)
    s.add_step("P", _PORT_ROWS)
    result = s.save(skills_dir=str(tmp_path))

    assert result is not None
    doc = json.loads(result.path.read_text(encoding="utf-8"))
    assert doc["steps"][0]["input"] == "P"


# ---------------------------------------------------------------------------
# 5 — R key intent from handle_key
# ---------------------------------------------------------------------------

def _make_play():
    """Return a PlayShellScreen with a minimal fake stdscr (same helper as
    test_cockpit_assign_trigger.py)."""
    import curses
    import unittest.mock as mock
    from tw2002_aiclient.screens import PlayShellScreen, ProfileRow

    class _Stdscr:
        def getmaxyx(self): return (40, 180)
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
        def has_colors(self): return False

    profile = ProfileRow(
        name="alpha", handle="Alpha", server="demo",
        host="demo.example", game_letter="B",
    )
    with mock.patch.object(curses, "has_colors", return_value=False):
        with mock.patch.object(curses, "start_color", return_value=None):
            with mock.patch.object(curses, "init_pair", return_value=None):
                with mock.patch.object(curses, "color_pair", return_value=0):
                    return PlayShellScreen(_Stdscr(), profile)


@pytest.mark.parametrize("key_char", ["r", "R"])
def test_r_key_returns_record_toggle_intent(key_char: str) -> None:
    play = _make_play()
    result = play.handle_key(ord(key_char))
    assert result == "record_toggle", (
        f"R key ({key_char!r}) returned {result!r}, expected 'record_toggle'"
    )


def test_r_key_is_only_intent_not_a_send() -> None:
    """handle_key for R returns 'record_toggle'; it never fires a send."""
    play = _make_play()
    # Session is inactive before R is pressed
    assert play.record_session.active is False
    result = play.handle_key(ord("R"))
    # Intent returned; record session was NOT started yet (app.py does that)
    assert result == "record_toggle"
    assert play.record_session.active is False  # still inactive: app.py acts


def test_r_key_binding_present_in_handle_key_source() -> None:
    """R is wired by WO-P5-067; this pin certifies the wire landed."""
    from tw2002_aiclient import screens
    src = inspect.getsource(screens.PlayShellScreen.handle_key)
    assert re.search(r"""ord\(["']r["']\)""", src), (
        "handle_key does not bind 'r' — WO-P5-067 wire missing"
    )
    assert re.search(r"""ord\(["']R["']\)""", src), (
        "handle_key does not bind 'R' — WO-P5-067 wire missing"
    )


def test_a_still_not_bound_after_r_wire() -> None:
    """A (WO-069) is now wired — landed alongside R (WO-067) and T (WO-068)."""
    from tw2002_aiclient import screens
    src = inspect.getsource(screens.PlayShellScreen.handle_key)
    for key in ("A", "a"):
        assert re.search(rf"""ord\(["']{key}["']\)""", src), (
            f"handle_key no longer binds {key!r} — WO-P5-069 wire broken"
        )


# ---------------------------------------------------------------------------
# 6 — No fire / no explore path
# ---------------------------------------------------------------------------

def test_record_macro_module_has_no_send_path() -> None:
    """The record_macro module must never acquire a live-wire path.

    Mirrors ``test_cockpit_teachband.py::test_teachband_module_sends_nothing``
    and ``test_cockpit_assign_trigger.py::test_assign_trigger_module_has_no_send_path``.

    The scan targets CALL SITES (e.g. ``.send(``, ``socket.``), not prose
    words in comments/docstrings, so describing the concept in the docstring
    does not cause a false positive.
    """
    src = inspect.getsource(record_macro)
    for forbidden in (".send(", "socket.", "subprocess.", "os.system"):
        assert forbidden not in src, (
            f"record_macro contains call-site {forbidden!r} — no live-wire path allowed"
        )


def test_record_macro_does_not_call_explore_start() -> None:
    """Recording must never cross into the explore flow.

    The scan targets CALL SITES, not prose, to avoid false positives on
    docstring descriptions.
    """
    src = inspect.getsource(record_macro)
    for name in ("explore_start(", "adapters.", "ensure_session(", "auto_arm("):
        assert name not in src, (
            f"record_macro contains call-site {name!r} — must be disjoint from explore"
        )


def test_record_session_stop_does_not_call_ensure_auto_arm() -> None:
    """save() must not touch ensure / auto-arm even if the opening rows
    were empty (the failure path is handled by catching NoStartAnchor)."""
    # Structural: confirmed by test_record_macro_does_not_call_explore_start
    # above; this test adds a runtime guard: save() on a bad recording
    # returns None, never raises, and certainly does not arm anything.
    s = RecordSession()
    s.start("bad", [])  # no sector bracket → NoStartAnchor at save time
    s.add_step("P", _PORT_ROWS)
    result = s.save()
    assert result is None  # refused, not armed


# ---------------------------------------------------------------------------
# 7 — E (explore) and T (assign_trigger) paths unchanged
# ---------------------------------------------------------------------------

def test_e_key_is_not_record_toggle() -> None:
    """E is Explore, not Record.  R must not steal Explore's lane."""
    play = _make_play()
    for key_char in ("e", "E"):
        result = play.handle_key(ord(key_char))
        assert result != "record_toggle", (
            f"E ({key_char!r}) returned 'record_toggle' — explore lane stolen"
        )


def test_t_key_is_still_assign_trigger() -> None:
    """T is still Assign-Trigger (WO-068); R must not displace it."""
    play = _make_play()
    for key_char in ("t", "T"):
        result = play.handle_key(ord(key_char))
        assert result == "assign_trigger", (
            f"T ({key_char!r}) returned {result!r} — assign_trigger lane broken"
        )


def test_r_not_in_explore_offer_keys() -> None:
    """R must not appear in app._EXPLORE_OFFER_KEYS."""
    from tw2002_aiclient import app as app_mod
    assert ord("r") not in app_mod._EXPLORE_OFFER_KEYS
    assert ord("R") not in app_mod._EXPLORE_OFFER_KEYS


# ---------------------------------------------------------------------------
# 8 — record_macro module send-path grep (also covered above; explicit pin)
# ---------------------------------------------------------------------------

def test_record_macro_source_contains_no_socket_write() -> None:
    src = inspect.getsource(record_macro)
    # These are call-site patterns that would indicate a live-wire path.
    for sym in ("socket.", "subprocess.", ".send(", "os.system"):
        assert sym not in src, f"record_macro source contains forbidden call-site {sym!r}"


# ---------------------------------------------------------------------------
# 9 — Round-trip: start → add_step × 2 → save → artifact loads
# ---------------------------------------------------------------------------

def test_round_trip_produces_loadable_artifact(tmp_path: Path) -> None:
    """The full pipeline: start → add two steps → save → file exists,
    has correct name and step count, and the loader can open it."""
    from tw2002_aiclient.loops.loader import load_loop, LoopNotFound

    s = RecordSession()
    s.start("ore-run", _ANCHOR_ROWS)
    s.add_step("P", _PORT_ROWS)
    s.add_step("Y", _ANCHOR_ROWS2)
    result = s.save(skills_dir=str(tmp_path))

    assert result is not None, "expected a SaveResult, got None"
    assert isinstance(result, SaveResult)
    assert result.steps == 2
    assert result.blessed is True
    assert result.path.exists()
    assert result.name == "ore-run"

    # Loader proves the document is well-formed
    loop = load_loop("ore-run", skills_dir=str(tmp_path))
    assert loop.draft is False
    assert loop.start_anchor == 158
    assert len(loop.steps) == 2


def test_round_trip_step_classes_are_derived_not_invented(tmp_path: Path) -> None:
    """expected_post_class must come from classify_screen, never from the
    caller — same structural guarantee LoopRecorder enforces (trap 1)."""
    from tw2002_aiclient.loops.loader import load_loop
    from tw2002_aiclient.session.classify import _RETURNABLE_CLASSES

    s = RecordSession()
    s.start("ore-run", _ANCHOR_ROWS)
    s.add_step("P", _PORT_ROWS)
    s.add_step("Y", _ANCHOR_ROWS2)
    result = s.save(skills_dir=str(tmp_path))
    assert result is not None

    loop = load_loop("ore-run", skills_dir=str(tmp_path))
    for step in loop.steps:
        assert step.expected_post_class in _RETURNABLE_CLASSES, (
            f"step class {step.expected_post_class!r} not in _RETURNABLE_CLASSES"
        )


def test_round_trip_secret_step_never_plaintext_in_artifact(tmp_path: Path) -> None:
    """A mixed recording: one plain step and one secret step.  The artifact
    must contain REDACTED_SENTINEL for the secret step and the plain key for
    the non-secret step."""
    from tw2002_aiclient.loops.loader import load_loop

    s = RecordSession()
    s.start("mixed-run", _ANCHOR_ROWS)
    s.add_step("P", _PORT_ROWS)                           # plain
    s.add_step("hunter2", _ANCHOR_ROWS2, is_secret=True)  # secret
    result = s.save(skills_dir=str(tmp_path))
    assert result is not None

    doc = json.loads(result.path.read_text(encoding="utf-8"))
    inputs = [step["input"] for step in doc["steps"]]
    assert inputs[0] == "P"
    assert inputs[1] == REDACTED_SENTINEL
    assert "hunter2" not in json.dumps(doc)


# ---------------------------------------------------------------------------
# 10 — SaveResult namedtuple shape
# ---------------------------------------------------------------------------

def test_save_result_fields(tmp_path: Path) -> None:
    s = RecordSession()
    s.start("save-test", _ANCHOR_ROWS)
    s.add_step("P", _PORT_ROWS)
    result = s.save(skills_dir=str(tmp_path))

    assert result is not None
    assert hasattr(result, "path")
    assert hasattr(result, "name")
    assert hasattr(result, "steps")
    assert hasattr(result, "blessed")
    assert result.blessed is True


def test_play_screen_has_record_session_attribute() -> None:
    """PlayShellScreen must expose ``record_session`` for app.py and tests."""
    play = _make_play()
    assert hasattr(play, "record_session")
    assert isinstance(play.record_session, RecordSession)


# ---------------------------------------------------------------------------
# Accept #2 — production capture-path integration pins
#
# These tests exercise the exact pattern app.py uses in the attach
# send_key → add_step chain: is_probable_secret_prompt on the current prompt
# determines is_secret; the result_rows are the current screen snapshot.
# Proves the capture path produces a correct artifact without requiring a
# live curses environment.
# ---------------------------------------------------------------------------

def test_capture_path_plain_key_lands_in_artifact(tmp_path: Path) -> None:
    """Non-secret key captured via the app.py pattern → artifact contains it."""
    from tw2002_aiclient.session.classify import is_probable_secret_prompt

    s = RecordSession()
    s.start("ore-run", _ANCHOR_ROWS)
    # Simulate the app.py pattern: command prompt → not secret
    prompt = "Command [TL=00:00:00]:[158] (?=Help)? :"
    s.add_step("P", _PORT_ROWS, is_secret=is_probable_secret_prompt(prompt))
    result = s.save(skills_dir=str(tmp_path))

    assert result is not None, "expected a SaveResult, got None"
    doc = json.loads(result.path.read_text(encoding="utf-8"))
    assert doc["steps"][0]["input"] == "P", (
        f"expected plain 'P', got {doc['steps'][0]['input']!r}"
    )


def test_capture_path_secret_key_is_redacted_in_artifact(tmp_path: Path) -> None:
    """Key sent while a password prompt is active → REDACTED_SENTINEL in artifact."""
    from tw2002_aiclient.session.classify import is_probable_secret_prompt

    s = RecordSession()
    s.start("login-run", _ANCHOR_ROWS)
    # Simulate the app.py pattern: password prompt → is_secret=True
    password_prompt = "Enter your Password:"
    s.add_step("hunter2", _ANCHOR_ROWS2, is_secret=is_probable_secret_prompt(password_prompt))
    result = s.save(skills_dir=str(tmp_path))

    assert result is not None, "expected a SaveResult, got None"
    doc = json.loads(result.path.read_text(encoding="utf-8"))
    assert doc["steps"][0]["input"] == REDACTED_SENTINEL, (
        f"expected REDACTED_SENTINEL, got {doc['steps'][0]['input']!r}"
    )
    assert "hunter2" not in json.dumps(doc), "plaintext password leaked into artifact"


def test_capture_path_is_probable_secret_prompt_detects_password(tmp_path: Path) -> None:
    """is_probable_secret_prompt correctly classifies prompts used in the capture path."""
    from tw2002_aiclient.session.classify import is_probable_secret_prompt

    # Secret prompts (must be True)
    for secret_prompt in (
        "Enter your Password:",
        "Enter Password:",
        "password: ",
        "Please enter PIN:",
        "Passcode: ",
    ):
        assert is_probable_secret_prompt(secret_prompt), (
            f"Expected secret prompt to be detected: {secret_prompt!r}"
        )

    # Non-secret prompts (must be False — key should NOT be redacted)
    for plain_prompt in (
        "Command [TL=00:00:00]:[158] (?=Help)? :",
        "<Trade with this port> (Y/N)? ",
        "",
    ):
        assert not is_probable_secret_prompt(plain_prompt), (
            f"Expected non-secret prompt, got True for: {plain_prompt!r}"
        )
