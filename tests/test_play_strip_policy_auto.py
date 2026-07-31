"""WO-PLAY-STRIP-POLICY-AUTO — Mode-leave halt + App-armed auto-fire.

DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 6: under
`APP-ARMED` with the matching toggle ON, the App reaches a live trade/
hold-buy start with no human `y`. Point 1: leaving App for Manual (`^A` to
`MANUAL-HUMAN`) halts every live App runner.

Two registers, mirroring this package's own established split
(``tests/test_play_panic_wire.py``):

1. Unit-level pins on ``app._stop_live_runners`` / ``app._autonomy_auto_fire``
   themselves — the pure decision/gate logic, isolated from the curses loop.
2. A full-``_run_play``-loop wire pin (the harness from
   ``tests/test_play_explore_arm.py`` / ``tests/test_play_panic_wire.py``) —
   composer/unit-level pins alone cannot see whether some OTHER app-loop
   branch shadows or never reaches the new wiring.
"""

from __future__ import annotations

from tw2002_aiclient import (
    adapters,
    app as app_mod,
    autonomy_policy as _autonomy_policy,
    stardock_hold_plan as _stardock_hold_plan,
    trade_chain_plan as _trade_chain_plan,
)


# ---------------------------------------------------------------------------
# Unit-level: `_stop_live_runners`
# ---------------------------------------------------------------------------


class _StopResult:
    def __init__(self, ok=True, reason=None):
        self.ok, self.reason, self.detail, self.raw = ok, reason, None, None


def test_stop_live_runners_calls_all_four_stop_verbs(monkeypatch):
    calls = []
    for verb in ("autoloop_stop", "explore_stop", "trade_chain_stop", "stardock_hold_stop"):
        monkeypatch.setattr(
            adapters, verb,
            (lambda name: lambda **kw: (calls.append((name, kw)) or _StopResult()))(verb),
        )
    all_ok, failures = app_mod._stop_live_runners(run_dir="/tmp/rd")
    assert all_ok is True
    assert failures == []
    names = [name for name, _kw in calls]
    assert names == ["autoloop_stop", "explore_stop", "trade_chain_stop", "stardock_hold_stop"]
    for _name, kw in calls:
        assert kw == {"run_dir": "/tmp/rd"}


def test_stop_live_runners_reports_partial_failure_honestly(monkeypatch):
    monkeypatch.setattr(adapters, "autoloop_stop", lambda **kw: _StopResult(ok=False, reason="boom"))
    monkeypatch.setattr(adapters, "explore_stop", lambda **kw: _StopResult())
    monkeypatch.setattr(adapters, "trade_chain_stop", lambda **kw: _StopResult())
    monkeypatch.setattr(adapters, "stardock_hold_stop", lambda **kw: _StopResult())
    all_ok, failures = app_mod._stop_live_runners(run_dir=None)
    assert all_ok is False
    assert failures == ["boom"]


def test_stop_live_runners_never_raises_on_adapter_exception(monkeypatch):
    def _raise(**kw):
        raise RuntimeError("transport exploded")

    monkeypatch.setattr(adapters, "autoloop_stop", _raise)
    monkeypatch.setattr(adapters, "explore_stop", lambda **kw: _StopResult())
    monkeypatch.setattr(adapters, "trade_chain_stop", lambda **kw: _StopResult())
    monkeypatch.setattr(adapters, "stardock_hold_stop", lambda **kw: _StopResult())
    all_ok, failures = app_mod._stop_live_runners(run_dir=None)
    assert all_ok is False
    assert failures  # honest — did not silently claim success


# ---------------------------------------------------------------------------
# Unit-level: `_autonomy_auto_fire`
# ---------------------------------------------------------------------------


class _FakeChainScalars:
    def __init__(self, chain=object()):
        self._chain = chain

    def bubble_subject(self):
        return self._chain, "caption"


class _FakePlay:
    def __init__(self, *, status=None, port_trade_on=True, cargo_upgrade_on=True, ship_upgrade_on=True):
        self._status = status if status is not None else {}
        self.status_provider = lambda: self._status
        self.chain_scalars = _FakeChainScalars()
        self.port_trade_on = port_trade_on
        self.cargo_upgrade_on = cargo_upgrade_on
        self.ship_upgrade_on = ship_upgrade_on
        self.status_line = ""
        self.explore_band = None
        self.draw_calls = 0

    def draw(self):
        self.draw_calls += 1


class _TradeResult:
    def __init__(self, ok=True, reason=None, raw=None):
        self.ok, self.reason, self.detail, self.raw = ok, reason, None, raw


class _HoldResult:
    def __init__(self, ok=True, reason=None, raw=None):
        self.ok, self.reason, self.detail, self.raw = ok, reason, None, raw


_PROFILE = app_mod.ProfileRow(name="a", handle="A", server="s", host="h", game_letter="B")

_TRADE_PLAN = _trade_chain_plan.TradeChainPlan(
    world_id="w1", fingerprint="fp1", sectors=(1, 2, 1),
    commodities=("Fuel Ore", "Organics"), turns=4, cr_per_turn=80.0,
)
_HOLD_PLAN = _stardock_hold_plan.StardockHoldPlan(
    world_id="w1", fingerprint="fp2", stardock_sector=7,
    empty_holds=3, hold_price=100, credits=10_000, qty=3,
)


def _offer(kind, gated=False):
    return _autonomy_policy.AutonomyOffer(kind=kind, reason="test", gated=gated)


def test_idle_or_explore_offer_never_fires_an_adapter(monkeypatch):
    calls = []
    monkeypatch.setattr(adapters, "trade_chain_start", lambda *a, **k: calls.append("trade") or _TradeResult())
    monkeypatch.setattr(adapters, "stardock_hold_start", lambda *a, **k: calls.append("hold") or _HoldResult())
    for kind in ("idle", "explore"):
        monkeypatch.setattr(_autonomy_policy, "choose_offer", lambda *_a, **_k: _offer(kind))
        play = _FakePlay()
        result = app_mod._autonomy_auto_fire(play, profile=_PROFILE, run_dir=None)
        assert result == (False, False)
    assert calls == []


def test_gated_offer_never_fires(monkeypatch):
    monkeypatch.setattr(_autonomy_policy, "choose_offer", lambda *_a, **_k: _offer("run_chain", gated=True))
    calls = []
    monkeypatch.setattr(adapters, "trade_chain_start", lambda *a, **k: calls.append(1) or _TradeResult())
    play = _FakePlay()
    assert app_mod._autonomy_auto_fire(play, profile=_PROFILE, run_dir=None) == (False, False)
    assert calls == []


def test_run_chain_offer_with_port_trade_off_never_fires(monkeypatch):
    monkeypatch.setattr(_autonomy_policy, "choose_offer", lambda *_a, **_k: _offer("run_chain"))
    monkeypatch.setattr(_trade_chain_plan, "plan_from_chain", lambda *_a, **_k: _TRADE_PLAN)
    calls = []
    monkeypatch.setattr(adapters, "trade_chain_start", lambda *a, **k: calls.append(1) or _TradeResult())
    play = _FakePlay(port_trade_on=False)
    assert app_mod._autonomy_auto_fire(play, profile=_PROFILE, run_dir=None) == (False, False)
    assert calls == []


def test_run_chain_offer_with_port_trade_on_fires_with_no_confirm(monkeypatch):
    monkeypatch.setattr(_autonomy_policy, "choose_offer", lambda *_a, **_k: _offer("run_chain"))
    monkeypatch.setattr(_trade_chain_plan, "plan_from_chain", lambda *_a, **_k: _TRADE_PLAN)
    calls = []

    def _start(world_id, fingerprint, *, cash_floor, turn_reserve, run_dir):
        calls.append((world_id, fingerprint, cash_floor, turn_reserve, run_dir))
        return _TradeResult(ok=True, raw={"running": True, "run": {"route": "1>2>1"}})

    monkeypatch.setattr(adapters, "trade_chain_start", _start)
    play = _FakePlay(port_trade_on=True)
    trade_poll, hold_poll = app_mod._autonomy_auto_fire(play, profile=_PROFILE, run_dir="/rd")
    assert calls == [("w1", "fp1", app_mod._TRADE_CASH_FLOOR, app_mod._TRADE_TURN_RESERVE, "/rd")]
    assert trade_poll is True
    assert hold_poll is False
    assert "App-armed" in play.status_line
    assert play.draw_calls == 1


def test_upgrade_offer_with_cargo_off_never_fires(monkeypatch):
    monkeypatch.setattr(_autonomy_policy, "choose_offer", lambda *_a, **_k: _offer("upgrade"))
    monkeypatch.setattr(_stardock_hold_plan, "plan_from_status", lambda *_a, **_k: _HOLD_PLAN)
    calls = []
    monkeypatch.setattr(adapters, "stardock_hold_start", lambda *a, **k: calls.append(1) or _HoldResult())
    play = _FakePlay(cargo_upgrade_on=False)
    assert app_mod._autonomy_auto_fire(play, profile=_PROFILE, run_dir=None) == (False, False)
    assert calls == []


def test_upgrade_offer_with_cargo_on_fires_with_no_confirm(monkeypatch):
    monkeypatch.setattr(_autonomy_policy, "choose_offer", lambda *_a, **_k: _offer("upgrade"))
    monkeypatch.setattr(_stardock_hold_plan, "plan_from_status", lambda *_a, **_k: _HOLD_PLAN)
    calls = []

    def _start(world_id, fingerprint, *, stardock_sector, empty_holds, hold_price, credits, qty, cash_floor, run_dir):
        calls.append((world_id, fingerprint, stardock_sector, qty, run_dir))
        return _HoldResult(ok=True)

    monkeypatch.setattr(adapters, "stardock_hold_start", _start)
    play = _FakePlay(cargo_upgrade_on=True)
    trade_poll, hold_poll = app_mod._autonomy_auto_fire(play, profile=_PROFILE, run_dir="/rd")
    assert calls == [("w1", "fp2", 7, 3, "/rd")]
    assert trade_poll is False
    assert hold_poll is True
    assert "App-armed" in play.status_line


def test_upgrade_offer_already_running_refusal_is_quiet(monkeypatch):
    """`already_running` is the daemon safely refusing a same-tick re-fire —
    must not spam `status_line` every idle tick."""
    monkeypatch.setattr(_autonomy_policy, "choose_offer", lambda *_a, **_k: _offer("upgrade"))
    monkeypatch.setattr(_stardock_hold_plan, "plan_from_status", lambda *_a, **_k: _HOLD_PLAN)
    monkeypatch.setattr(
        adapters, "stardock_hold_start",
        lambda *a, **k: _HoldResult(ok=False, reason="already_running"),
    )
    play = _FakePlay(cargo_upgrade_on=True)
    play.status_line = "unchanged"
    trade_poll, hold_poll = app_mod._autonomy_auto_fire(play, profile=_PROFILE, run_dir=None)
    assert (trade_poll, hold_poll) == (False, False)
    assert play.status_line == "App-armed — starting hold buy @ StarDock 7… (Cargo Hold Upgrade\u00b7ON)"


def test_ship_upgrade_toggle_never_reaches_any_adapter(monkeypatch):
    """WO scope #4: Ship Upgrade gates nothing — no engine/offer kind exists.
    Structural pin: regardless of ``ship_upgrade_on``, no ship-shaped adapter
    call happens, and the (irrelevant) toggle never changes the outcome for
    an unrelated offer kind."""
    monkeypatch.setattr(_autonomy_policy, "choose_offer", lambda *_a, **_k: _offer("explore"))
    play_on = _FakePlay(ship_upgrade_on=True)
    play_off = _FakePlay(ship_upgrade_on=False)
    assert app_mod._autonomy_auto_fire(play_on, profile=_PROFILE, run_dir=None) == (False, False)
    assert app_mod._autonomy_auto_fire(play_off, profile=_PROFILE, run_dir=None) == (False, False)
    assert not hasattr(adapters, "ship_upgrade_start")


def test_never_raises_on_hostile_status_provider(monkeypatch):
    play = _FakePlay()

    def _raise():
        raise RuntimeError("boom")

    play.status_provider = _raise
    # choose_offer is NOT patched here — real function, fed `{}` — proving
    # the degrade path all the way through rather than mocking it away.
    assert app_mod._autonomy_auto_fire(play, profile=_PROFILE, run_dir=None) == (False, False)


def test_incomplete_plan_is_an_honest_no_op(monkeypatch):
    """`plan_from_chain`/`plan_from_status` returning `None` (incomplete
    scaffold) must never be treated as a fire — same honesty the `H`/`O`
    keys already give."""
    monkeypatch.setattr(_autonomy_policy, "choose_offer", lambda *_a, **_k: _offer("run_chain"))
    monkeypatch.setattr(_trade_chain_plan, "plan_from_chain", lambda *_a, **_k: None)
    calls = []
    monkeypatch.setattr(adapters, "trade_chain_start", lambda *a, **k: calls.append(1) or _TradeResult())
    play = _FakePlay(port_trade_on=True)
    assert app_mod._autonomy_auto_fire(play, profile=_PROFILE, run_dir=None) == (False, False)
    assert calls == []


# ---------------------------------------------------------------------------
# Full-loop wire pins — Mode-leave halt
# ---------------------------------------------------------------------------


class _Ensure:
    def __init__(self, ok=True, classification="main_command"):
        self.ok, self.classification, self.reason, self.detail = ok, classification, None, None


class _StdscrKeys:
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


def _drive(monkeypatch, keys, *, attach_ok=True):
    """Run `_run_play` for real; return (stop_calls, screen).

    Harness lifted from ``tests/test_play_panic_wire.py`` — the same
    "record what each key resolved to" recorder, since every drive ends
    with Esc and end-state reads cannot distinguish "acted then undone"
    from "never acted".
    """
    stop_calls: dict[str, list] = {"autoloop": [], "explore": [], "trade": [], "hold": []}

    monkeypatch.setattr(adapters, "ensure_session", lambda name, **kw: _Ensure())
    monkeypatch.setattr(
        adapters, "autoloop_stop",
        lambda **kw: (stop_calls["autoloop"].append(kw) or _StopResult()), raising=False,
    )
    monkeypatch.setattr(
        adapters, "explore_stop",
        lambda **kw: (stop_calls["explore"].append(kw) or _StopResult()), raising=False,
    )
    monkeypatch.setattr(
        adapters, "trade_chain_stop",
        lambda **kw: (stop_calls["trade"].append(kw) or _StopResult()), raising=False,
    )
    monkeypatch.setattr(
        adapters, "stardock_hold_stop",
        lambda **kw: (stop_calls["hold"].append(kw) or _StopResult()), raising=False,
    )
    # Auto-fire is exercised by its own dedicated unit tests above — silence
    # it here (idle offer) so this harness stays scoped to the halt wire,
    # matching test_play_panic_wire.py's own scope discipline.
    monkeypatch.setattr(_autonomy_policy, "choose_offer", lambda *_a, **_k: _offer("idle"))

    def _attach(_sock_path):
        if attach_ok:
            class _Conn:
                def close(self): pass
            return _Conn(), None
        return None, "refused-for-test"

    monkeypatch.setattr(app_mod, "_attempt_attach", _attach)

    seen = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.gate_raises = []
            self.actions = []
            seen["screen"] = self

        def begin_arm_confirm(self, action=None, *, cycles=None):
            self.gate_raises.append((action, cycles))
            return super().begin_arm_confirm(action, cycles=cycles)

        def handle_key(self, key):
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
        app_mod._run_play(_StdscrKeys(keys), profile)
    except Exception:
        pass
    return stop_calls, seen.get("screen")


def test_mode_leave_halts_all_four_runners(monkeypatch):
    """Accept #1: `^A` to Manual stops live App runners — through the real
    app loop, not just a composer-level return value."""
    stop_calls, screen = _drive(monkeypatch, [app_mod.MODE_KEY])
    assert screen.attached is True
    for name in ("autoloop", "explore", "trade", "hold"):
        assert len(stop_calls[name]) == 1, f"{name}_stop not called exactly once: {stop_calls[name]}"


def test_mode_leave_halt_reports_partial_failure(monkeypatch):
    monkeypatch.setattr(adapters, "ensure_session", lambda name, **kw: _Ensure())
    monkeypatch.setattr(adapters, "autoloop_stop", lambda **kw: _StopResult(ok=False, reason="boom"), raising=False)
    monkeypatch.setattr(adapters, "explore_stop", lambda **kw: _StopResult(), raising=False)
    monkeypatch.setattr(adapters, "trade_chain_stop", lambda **kw: _StopResult(), raising=False)
    monkeypatch.setattr(adapters, "stardock_hold_stop", lambda **kw: _StopResult(), raising=False)
    monkeypatch.setattr(_autonomy_policy, "choose_offer", lambda *_a, **_k: _offer("idle"))

    def _attach(_sock_path):
        class _Conn:
            def close(self): pass
        return _Conn(), None

    monkeypatch.setattr(app_mod, "_attempt_attach", _attach)
    monkeypatch.setattr(app_mod.curses, "has_colors", lambda: False, raising=False)

    seen = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            seen["screen"] = self

        def draw(self):
            pass

    monkeypatch.setattr(app_mod, "PlayShellScreen", _Spy)
    profile = app_mod.ProfileRow(name="a", handle="A", server="s", host="h", game_letter="B")
    try:
        app_mod._run_play(_StdscrKeys([app_mod.MODE_KEY]), profile)
    except Exception:
        pass
    screen = seen["screen"]
    assert screen.attached is True  # attach still succeeds
    assert "halt partial" in screen.status_line
    assert "boom" in screen.status_line


def test_mode_leave_does_not_pass_through_a_confirm_gate(monkeypatch):
    """The halt + attach never raises the money-path confirm gate."""
    _stop_calls, screen = _drive(monkeypatch, [app_mod.MODE_KEY])
    assert screen.gate_raises == []


def test_p_c_s_still_toggle_and_do_not_shadow_mode_leave(monkeypatch):
    """P/C/S local toggles are untouched by this WO — pressing them does not
    itself trigger the halt (only Mode-leave does)."""
    stop_calls, screen = _drive(monkeypatch, [ord("P"), ord("C"), ord("S")])
    assert screen.port_trade_on is False
    assert screen.cargo_upgrade_on is False
    assert screen.ship_upgrade_on is False
    for name in ("autoloop", "explore", "trade", "hold"):
        assert stop_calls[name] == []
