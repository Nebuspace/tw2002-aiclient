"""WO-PLAY-REFLEX-ARM — Play V preview + confirm-arm through reflex_arm.

Product-path pins (drive real ``app._run_play`` with fakes):
  * V + STOP / transport fail → no gate, zero reflex_arm
  * V + proposal → gate raised, still zero launch
  * V then y → reflex_arm once with the exact preview identity
  * V then n → zero launch
  * V does not collide with E/L/A/R/T/D/F/G/P
  * ``_run_play`` has no ``send_request`` / ``session.send``
"""

from __future__ import annotations

import inspect

import pytest

from tw2002_aiclient import adapters, app as app_mod
from tw2002_aiclient.cockpit import reflex_controls as _reflex_controls


class _ReflexResult:
    def __init__(
        self,
        ok=True,
        macro=None,
        rule_id=None,
        stop_reason=None,
        classification=None,
        reason=None,
    ):
        self.ok = ok
        self.macro = macro
        self.rule_id = rule_id
        self.stop_reason = stop_reason
        self.classification = classification
        self.reason = reason
        self.detail = None
        self.raw = None


class _ArmResult:
    def __init__(self, ok=True, reason=None):
        self.ok, self.reason, self.detail, self.raw = ok, reason, None, None


class _Ensure:
    def __init__(self, ok=True, classification="main_command"):
        self.ok = ok
        self.classification = classification
        self.reason = None
        self.detail = None


class _Stdscr:
    def __init__(self, keys):
        self._keys = list(keys) + [27]
        self.rows, self.cols = 40, 160

    def getmaxyx(self):
        return (self.rows, self.cols)

    def getch(self):
        return self._keys.pop(0) if self._keys else 27

    def timeout(self, ms):
        pass

    def erase(self):
        pass

    def refresh(self):
        pass

    def addstr(self, *a, **k):
        pass

    def addnstr(self, *a, **k):
        pass

    def attron(self, a):
        pass

    def attroff(self, a):
        pass

    def hline(self, *a, **k):
        pass

    def vline(self, *a, **k):
        pass

    def border(self, *a, **k):
        pass

    def chgat(self, *a, **k):
        pass

    def keypad(self, flag):
        pass

    def nodelay(self, flag):
        pass


def _drive(monkeypatch, keys, *, propose=None, arm=None):
    """Run ``_run_play``; return (propose_calls, arm_calls, screen)."""
    propose_calls = []
    arm_calls = []

    monkeypatch.setattr(
        adapters, "ensure_session", lambda name, **kw: _Ensure()
    )

    def _propose(**kwargs):
        propose_calls.append(kwargs)
        if propose is None:
            return _ReflexResult(
                ok=True, stop_reason="autopilot_no_candidates:main_command"
            )
        return propose

    def _arm(**kwargs):
        arm_calls.append(kwargs)
        return arm if arm is not None else _ArmResult(ok=True)

    monkeypatch.setattr(adapters, "reflex_propose", _propose)
    monkeypatch.setattr(adapters, "reflex_arm", _arm)
    monkeypatch.setattr(
        adapters,
        "explore_start_for_profile",
        lambda *a, **k: _ArmResult(ok=False, reason="nope"),
        raising=False,
    )
    monkeypatch.setattr(
        adapters, "autoloop_start", lambda *a, **k: _ArmResult(ok=False), raising=False
    )
    monkeypatch.setattr(
        adapters, "autoloop_pause", lambda *a, **k: _ArmResult(ok=False), raising=False
    )
    monkeypatch.setattr(
        adapters, "autoloop_relaunch", lambda *a, **k: _ArmResult(ok=False), raising=False
    )
    monkeypatch.setattr(
        adapters, "autoloop_stop", lambda *a, **k: _ArmResult(ok=True), raising=False
    )
    monkeypatch.setattr(
        adapters, "autoloop_status", lambda *a, **k: _ArmResult(ok=False), raising=False
    )

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

        def draw(self):
            pass

    monkeypatch.setattr(app_mod, "PlayShellScreen", _Spy)
    monkeypatch.setattr(app_mod.curses, "has_colors", lambda: False, raising=False)

    profile = app_mod.ProfileRow(
        name="alpha",
        handle="Alpha",
        server="demo-a",
        host="demo-a.example",
        game_letter="B",
    )
    try:
        app_mod._run_play(_Stdscr(keys), profile)
    except Exception:
        pass
    return propose_calls, arm_calls, seen.get("screen")


def test_v_key_resolves_and_avoids_reserved_letters():
    assert _reflex_controls.resolve_reflex_offer_key(ord("v"))
    assert _reflex_controls.resolve_reflex_offer_key(ord("V"))
    for letter in "EeLlAaRrTtDdFfGgPp ":
        assert not _reflex_controls.resolve_reflex_offer_key(ord(letter))
    assert not _reflex_controls.resolve_reflex_offer_key(True)
    assert not _reflex_controls.resolve_reflex_offer_key("v")


def test_screens_handle_key_returns_reflex_offer_intent():
    # Minimal screen: object.__new__ skips paint setup; handle_key still runs.
    play = object.__new__(app_mod.PlayShellScreen)
    play.analyze_session = type("A", (), {"is_open": False})()
    play.chains_session = type("C", (), {"is_open": False})()
    play.rules_library_session = type("R", (), {"is_open": False})()
    play._arm_confirm = None
    play._draft_approve = None
    play._rule_identity = None
    play._conn_focused = False
    assert play.handle_key(ord("v")) == _reflex_controls.REFLEX_OFFER_INTENT
    assert play.handle_key(ord("V")) == _reflex_controls.REFLEX_OFFER_INTENT


def test_no_candidate_raises_no_gate_and_zero_arm(monkeypatch):
    propose_calls, arm_calls, screen = _drive(
        monkeypatch,
        [ord("v")],
        propose=_ReflexResult(
            ok=True, stop_reason="autopilot_no_candidates:main_command"
        ),
    )
    assert len(propose_calls) == 1
    assert arm_calls == []
    assert screen.gate_raises == []
    assert "nothing" in (screen.status_line or "")


def test_transport_fail_raises_no_gate_and_zero_arm(monkeypatch):
    propose_calls, arm_calls, screen = _drive(
        monkeypatch,
        [ord("v")],
        propose=_ReflexResult(ok=False, reason="daemon_unreachable"),
    )
    assert len(propose_calls) == 1
    assert arm_calls == []
    assert screen.gate_raises == []
    assert "daemon_unreachable" in (screen.status_line or "")


def test_proposal_raises_gate_without_launch(monkeypatch):
    prop = _ReflexResult(
        ok=True, macro="ore-run", rule_id="r1", classification="main_command"
    )
    propose_calls, arm_calls, screen = _drive(monkeypatch, [ord("v")], propose=prop)
    assert len(propose_calls) == 1
    assert arm_calls == []
    assert screen.gate_raises == [("Arm ore-run", None)]
    assert "proposes ore-run" in (screen.status_line or "")


def test_confirm_y_launches_once_with_exact_identity(monkeypatch):
    prop = _ReflexResult(
        ok=True, macro="ore-run", rule_id="r1", classification="main_command"
    )
    propose_calls, arm_calls, screen = _drive(
        monkeypatch, [ord("v"), ord("y")], propose=prop, arm=_ArmResult(ok=True)
    )
    assert len(propose_calls) == 1
    assert len(arm_calls) == 1
    assert arm_calls[0]["rule_id"] == "r1"
    assert arm_calls[0]["macro"] == "ore-run"
    assert arm_calls[0]["classification"] == "main_command"
    assert screen.gate_raises == [("Arm ore-run", None)]
    assert "armed ore-run" in (screen.status_line or "")


@pytest.mark.parametrize("key", [ord("N"), ord("n"), 10, 13, ord("q")])
def test_non_y_never_launches(monkeypatch, key: int):
    prop = _ReflexResult(
        ok=True, macro="ore-run", rule_id="r1", classification="main_command"
    )
    _, arm_calls, _screen = _drive(monkeypatch, [ord("v"), key], propose=prop)
    assert arm_calls == [], f"key {key} launched reflex_arm"


def test_incomplete_identity_raises_no_gate(monkeypatch):
    prop = _ReflexResult(
        ok=True, macro="ore-run", rule_id=None, classification="main_command"
    )
    _, arm_calls, screen = _drive(monkeypatch, [ord("v"), ord("y")], propose=prop)
    assert arm_calls == []
    assert screen.gate_raises == []
    assert "incomplete identity" in (screen.status_line or "")


def test_pending_confirm_action_reflex_is_explicit_in_source():
    src = inspect.getsource(app_mod)
    assert 'pending_confirm_action = "reflex"' in src
    assert 'pending_confirm_action == "reflex"' in src
    assert "adapters.reflex_arm(" in src


def test_run_play_has_no_direct_send_request():
    src = inspect.getsource(app_mod._run_play)
    assert "send_request" not in src
    # Launch must go through adapters.reflex_arm (already pinned above).
    assert "adapters.reflex_arm(" in inspect.getsource(app_mod)
