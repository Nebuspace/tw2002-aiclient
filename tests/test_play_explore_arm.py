"""WO-PLAY-EXPLORE-ARM (L3) -- the post-ensure explore offer in Play.

The first production use of the confirm-to-arm gate. Drives the real
`app._run_play` with a fake stdscr and a mocked adapter (L2 is not on `main`
yet; the contract is pinned in `WO-PLAY-EXPLORE-ADAPTER.md`), so these
assertions are about the PRODUCT path, not a re-implementation of it.

Two deliberate keys, hub-ruled 2026-07-27T03:35:06Z: ensure ANNOUNCES the
offer, `E` raises the gate, `y` starts. The gate is never raised unbidden --
a modal raised on its own consumes the operator's next keystroke, and
measurement showed that key is usually their Ctrl-A attach chord (33
pre-existing `_run_play` tests went red on exactly that swallow). Same
sovereignty posture as WO-P5-065's prompt-to-attach: offer, do not take.

The states that matter:
  * ensure lands `main_command` -> offer ANNOUNCED, no gate up
  * `E` -> gate raised, still nothing started
  * `E` then `y` -> explore started once, with the confirmed cycle count
  * `E` then anything else -> gate clears, explore NOT started
  * ensure failed / other classification -> no offer, and `E` does nothing
"""

from __future__ import annotations

import types

import pytest

from tw2002_aiclient import adapters, app as app_mod
from tw2002_aiclient.cockpit import explore_flags as _explore_flags

# WO-EXPLORE-GATHER-VISIBLE: the default confirm action now states the
# opted-OUT dock state instead of staying silent. Derived here for
# readability; the marker's CONTENT is pinned by literal in
# `tests/test_play_explore_flags.py`, which is the assertion a deletion
# cannot slip past.
_OFF_ACTION = f"Explore {_explore_flags.DOCK_OFF_MARKER}"


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


def _drive(monkeypatch, keys, *, ensure=None, explore=None, raises=None):
    """Run `_run_play`; return (explore_calls, screen).

    `screen.gate_raises` records every `begin_arm_confirm` invocation IN
    ORDER. Checking the final `_arm_confirm` value instead would be
    vacuous: every drive ends with Esc, which clears the gate, so an
    auto-raised gate and a never-raised one look identical afterwards.
    Found by mutating the product to auto-raise and watching this file stay
    green.
    """
    calls = []

    monkeypatch.setattr(
        adapters, "ensure_session",
        lambda name, **kw: ensure if ensure is not None else _Result(),
    )

    def _explore(profile, **kw):
        calls.append(kw)
        if raises is not None:
            raise raises
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


def test_offer_is_announced_but_the_gate_is_not_raised_unbidden(monkeypatch) -> None:
    """The design correction: ensure ANNOUNCES the offer, it does not raise
    a modal gate. A gate raised unbidden consumes the operator's next
    keystroke -- measured: 33 pre-existing `_run_play` tests went red because
    the swallowed key was their Ctrl-A attach chord."""
    _calls, screen = _drive(monkeypatch, [])
    # WO-PLAY-OFFER-VISIBLE-ON-LIVE: offer lives on status_line and paints on
    # the control strip mid segment when LOGS has a real tail.
    assert "press E" in (screen.status_line or "")
    assert screen.gate_raises == [], (
        f"gate was raised without the human asking: {screen.gate_raises}"
    )


def test_e_raises_the_gate_and_then_y_starts_explore(monkeypatch) -> None:
    calls, screen = _drive(monkeypatch, [ord("E"), ord("y")])
    assert len(calls) == 1
    assert calls[0]["min_sectors"] == app_mod._EXPLORE_MIN_SECTORS


def test_e_alone_raises_the_gate_but_arms_nothing(monkeypatch) -> None:
    """`E` raises the gate; it does not start anything. Only `y` does."""
    calls, screen = _drive(monkeypatch, [ord("E")])
    assert screen.gate_raises == [(_OFF_ACTION, 5)], screen.gate_raises
    assert calls == []


def test_e_does_nothing_when_no_offer_is_standing(monkeypatch) -> None:
    calls, screen = _drive(
        monkeypatch, [ord("E"), ord("y")],
        ensure=_Result(ok=True, classification="unknown"),
    )
    assert screen.gate_raises == [], "E raised a gate with no offer standing"
    assert calls == []


def test_y_starts_explore_once_with_the_confirmed_cycle_count(monkeypatch) -> None:
    calls, screen = _drive(monkeypatch, [ord("E"), ord("y")])
    assert len(calls) == 1, f"expected exactly one explore start, got {len(calls)}"
    assert calls[0]["min_sectors"] == app_mod._EXPLORE_MIN_SECTORS == 5
    assert "explore started" in (screen.status_line or "")


@pytest.mark.parametrize("key", [ord("N"), ord("n"), 10, 13, 27, ord("q")])
def test_non_y_never_starts_explore(monkeypatch, key: int) -> None:
    """Default-deny at the product layer, not just in the resolver."""
    calls, _screen = _drive(monkeypatch, [ord("E"), key])
    assert calls == [], f"key {key} started explore"


def test_no_offer_when_ensure_failed(monkeypatch) -> None:
    calls, screen = _drive(
        monkeypatch, [ord("E"), ord("y")],
        ensure=_Result(ok=False, classification=None, reason="login_stalled", detail="x"),
    )
    assert calls == [], "explore offered after a failed ensure"
    assert "ensure failed" in (screen.status_line or "")


@pytest.mark.parametrize("classification", ["unknown", "game_select", "login_prompt", None, ""])
def test_no_offer_when_the_session_did_not_land_main_command(monkeypatch, classification) -> None:
    """`ok` alone is not enough -- the offer is gated on the literal ready
    classification, so explore is never armed against an unknown screen."""
    calls, _screen = _drive(
        monkeypatch, [ord("E"), ord("y")], ensure=_Result(ok=True, classification=classification)
    )
    assert calls == [], f"explore offered at classification={classification!r}"


def test_adapter_failure_is_reported_not_swallowed(monkeypatch) -> None:
    calls, screen = _drive(
        monkeypatch, [ord("E"), ord("y")], explore=_ExploreResult(ok=False, reason="daemon_not_running")
    )
    assert len(calls) == 1
    assert "daemon_not_running" in (screen.status_line or "")


def test_a_raising_adapter_does_not_take_the_play_loop_down(monkeypatch) -> None:
    """And the message carries the exception TYPE only -- this call reaches
    the daemon with a profile, and an exception message is not a safe place
    to assume otherwise."""
    secret = "hunter2-SUPERSECRET"
    calls, screen = _drive(monkeypatch, [ord("E"), ord("y")], raises=RuntimeError(secret))
    assert len(calls) == 1
    assert "explore failed to start" in (screen.status_line or "")
    assert "RuntimeError" in (screen.status_line or "")
    assert secret not in (screen.status_line or "")
