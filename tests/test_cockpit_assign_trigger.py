"""WO-P5-068 — T Assign-Trigger scaffold.

Pins:

1.  Schema round-trip: ``create_stub`` returns the correct ``when+guards``
    structure; ``"do"`` is always ``None``; ``screen`` is stamped correctly.
2.  ``StubStore`` get/set/clear lifecycle.
3.  ``T`` key returns ``"assign_trigger"`` intent from ``PlayShellScreen.
    handle_key`` (both cases: ``t`` and ``T``).
4.  ``T`` does NOT call ``explore_start`` / send — no fire path on assign.
5.  Explore ``E`` path is unchanged by this WO.
6.  The ``assign_trigger`` module itself has no send path (grep guard).
"""

from __future__ import annotations

import inspect
import re

import pytest

from tw2002_aiclient.cockpit import assign_trigger


# ---------------------------------------------------------------------------
# 1 — Schema round-trip
# ---------------------------------------------------------------------------

def test_create_stub_returns_correct_schema() -> None:
    stub = assign_trigger.create_stub("main_command")
    assert stub["when"]["screen"] == "main_command"
    assert stub["when"]["guards"] == []
    assert stub["do"] is None


def test_create_stub_do_is_always_none() -> None:
    """``do`` must be None at scaffold time — no macro wired yet."""
    for cls in ("main_command", "game_select", "unknown", "", None):
        stub = assign_trigger.create_stub(cls)
        assert stub["do"] is None, f"do is not None for screen_class={cls!r}"


def test_create_stub_non_str_screen_class_degrades_to_empty() -> None:
    """Honest absence beats a wrong class name."""
    for bad in (None, 0, [], object(), b"bytes"):
        stub = assign_trigger.create_stub(bad)
        assert stub["when"]["screen"] == "", f"bad input {bad!r} yielded non-empty screen"


def test_create_stub_guards_is_always_empty_list() -> None:
    """Guards are Phase 6 — scaffold always leaves them empty."""
    stub = assign_trigger.create_stub("main_command")
    assert stub["when"]["guards"] == []
    # Verify it is a fresh list, not a shared mutable default
    stub["when"]["guards"].append("x")
    stub2 = assign_trigger.create_stub("main_command")
    assert stub2["when"]["guards"] == [], "guards list is shared across calls"


@pytest.mark.parametrize("hostile", [None, 0, [], object(), b"x"])
def test_create_stub_never_raises(hostile: object) -> None:
    result = assign_trigger.create_stub(hostile)
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 2 — StubStore lifecycle
# ---------------------------------------------------------------------------

def test_stub_store_get_returns_none_before_set() -> None:
    store = assign_trigger.StubStore()
    assert store.get() is None


def test_stub_store_set_and_get_round_trip() -> None:
    store = assign_trigger.StubStore()
    stub = assign_trigger.create_stub("main_command")
    store.set(stub)
    assert store.get() == stub


def test_stub_store_set_replaces_previous() -> None:
    store = assign_trigger.StubStore()
    store.set(assign_trigger.create_stub("screen_a"))
    store.set(assign_trigger.create_stub("screen_b"))
    assert store.get()["when"]["screen"] == "screen_b"


def test_stub_store_clear_removes_stub() -> None:
    store = assign_trigger.StubStore()
    store.set(assign_trigger.create_stub("main_command"))
    store.clear()
    assert store.get() is None


def test_stub_store_set_ignores_non_dict() -> None:
    """Non-dict input is silently dropped — does not replace a valid stub."""
    store = assign_trigger.StubStore()
    valid = assign_trigger.create_stub("main_command")
    store.set(valid)
    for bad in (None, "string", 42, [], object()):
        store.set(bad)
        assert store.get() == valid, f"non-dict {bad!r} replaced the valid stub"


@pytest.mark.parametrize("hostile", [None, "x", 0, [], object()])
def test_stub_store_methods_never_raise(hostile: object) -> None:
    store = assign_trigger.StubStore()
    store.set(hostile)  # must not raise
    _ = store.get()     # must not raise
    store.clear()       # must not raise


# ---------------------------------------------------------------------------
# 3 — T key intent from handle_key
# ---------------------------------------------------------------------------

def _make_play():
    """Return a PlayShellScreen with a minimal fake stdscr."""
    import curses
    from tw2002_aiclient.screens import PlayShellScreen, ProfileRow

    class _Stdscr:
        def getmaxyx(self): return (40, 160)
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
    # Temporarily patch curses.has_colors so __init__ doesn't fail outside a terminal
    import unittest.mock as mock
    with mock.patch.object(curses, "has_colors", return_value=False):
        with mock.patch.object(curses, "start_color", return_value=None):
            with mock.patch.object(curses, "init_pair", return_value=None):
                with mock.patch.object(curses, "color_pair", return_value=0):
                    play = PlayShellScreen(_Stdscr(), profile)
    return play


@pytest.mark.parametrize("key_char", ["t", "T"])
def test_t_key_returns_assign_trigger_intent(key_char: str) -> None:
    play = _make_play()
    result = play.handle_key(ord(key_char))
    assert result == "assign_trigger", (
        f"T key ({key_char!r}) returned {result!r}, expected 'assign_trigger'"
    )


def test_t_key_is_only_intent_not_a_send() -> None:
    """handle_key for T returns 'assign_trigger'; it never fires a send."""
    play = _make_play()
    # The store is empty before T is pressed
    assert play.stub_store.get() is None
    result = play.handle_key(ord("T"))
    # Intent returned; no stub written yet (app.py does the write)
    assert result == "assign_trigger"
    assert play.stub_store.get() is None  # still empty: app.py hasn't acted


def test_e_key_is_not_assign_trigger() -> None:
    """E is Explore, not Assign-Trigger.  T must not steal Explore's lane."""
    play = _make_play()
    for key_char in ("e", "E"):
        result = play.handle_key(ord(key_char))
        assert result != "assign_trigger", (
            f"E ({key_char!r}) returned 'assign_trigger' — explore lane stolen"
        )


# ---------------------------------------------------------------------------
# 4 — No fire path: assign_trigger module sends nothing
# ---------------------------------------------------------------------------

def test_assign_trigger_module_has_no_send_path() -> None:
    """The assign_trigger module must never acquire a send path.

    Mirrors ``test_teachband_module_sends_nothing`` in
    ``test_cockpit_teachband.py`` — same discipline, same grep.
    """
    src = inspect.getsource(assign_trigger)
    for forbidden in ("send", "write", "socket", "subprocess", "os.system"):
        assert forbidden not in src, (
            f"assign_trigger references {forbidden!r} — no send path allowed"
        )


def test_assign_trigger_does_not_call_explore_start() -> None:
    """Creating a stub must never call explore_start (or any adapter).

    A regression would appear if the scaffold accidentally crossed into
    the explore flow.
    """
    src = inspect.getsource(assign_trigger)
    for name in ("explore_start", "explore", "adapters"):
        assert name not in src, (
            f"assign_trigger references {name!r} — must be disjoint from explore"
        )


# ---------------------------------------------------------------------------
# 5 — Explore E path unchanged
# ---------------------------------------------------------------------------

def test_handle_key_e_is_not_assign_trigger(monkeypatch) -> None:
    """E/e must never be assign_trigger — explore path untouched."""
    play = _make_play()
    for key_char in ("e", "E"):
        result = play.handle_key(ord(key_char))
        assert result != "assign_trigger"


def test_handle_key_t_not_in_explore_keys() -> None:
    """T must not appear in app._EXPLORE_OFFER_KEYS."""
    from tw2002_aiclient import app as app_mod
    assert ord("t") not in app_mod._EXPLORE_OFFER_KEYS
    assert ord("T") not in app_mod._EXPLORE_OFFER_KEYS


# ---------------------------------------------------------------------------
# 6 — PlayShellScreen wiring guard (structural, like teachband pin)
# ---------------------------------------------------------------------------

def test_t_binding_present_in_handle_key_source() -> None:
    """T is wired by WO-P5-068; this pin certifies the wire landed."""
    from tw2002_aiclient import screens
    src = inspect.getsource(screens.PlayShellScreen.handle_key)
    assert re.search(r"""ord\(["']t["']\)""", src), (
        "handle_key does not bind 't' — WO-P5-068 wire missing"
    )
    assert re.search(r"""ord\(["']T["']\)""", src), (
        "handle_key does not bind 'T' — WO-P5-068 wire missing"
    )


def test_a_still_not_bound() -> None:
    """A (WO-069) is now wired — its intent must be analyze_open/analyze_close.

    R is wired by WO-P5-067; T by WO-P5-068; A by WO-P5-069 (this WO).
    """
    from tw2002_aiclient import screens
    src = inspect.getsource(screens.PlayShellScreen.handle_key)
    for key in ("A", "a"):
        assert re.search(rf"""ord\(["']{key}["']\)""", src), (
            f"handle_key no longer binds {key!r} — WO-P5-069 wire broken"
        )
    # Verify the intent it returns, not just binding presence.
    # handle_key returns the INTENT only; app.py does the open()/close() call.
    from tw2002_aiclient.screens import PlayShellScreen, ProfileRow
    import unittest.mock as mock
    import curses

    class _Stdscr:
        def getmaxyx(self): return (40, 160)
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

    profile = ProfileRow(name="alpha", handle="Alpha", server="demo",
                         host="demo.example", game_letter="B")
    with mock.patch.object(curses, "has_colors", return_value=False):
        with mock.patch.object(curses, "start_color", return_value=None):
            with mock.patch.object(curses, "init_pair", return_value=None):
                with mock.patch.object(curses, "color_pair", return_value=0):
                    play = PlayShellScreen(_Stdscr(), profile)
    # Session starts closed → first A returns analyze_open
    assert play.handle_key(ord("a")) == "analyze_open"
    # Simulate app.py's action handler opening the session
    play.analyze_session.open()
    # Session now open → second A returns analyze_close
    assert play.handle_key(ord("a")) == "analyze_close"
