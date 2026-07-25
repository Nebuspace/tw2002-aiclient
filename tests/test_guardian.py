"""SessionGuardian tests (WO-P2-027 reconnect+replay; WO-P2-028 keepalive).

No network, no real threading: `_tick()` is called directly rather than
starting the background thread, matching the fake-clock / direct-call
style used for settle.py tests.
"""

from __future__ import annotations

from tw2002_aiclient.session.guardian import SessionGuardian
from tw2002_aiclient.session.settle import wait_for_settle


class FakeConn:
    def __init__(self, connected=True):
        self.connected = connected


class KeepaliveFakeSession:
    """Stable screen surface for guardian._maybe_keepalive() (WO-P2-028)."""

    def __init__(self, screen_text, last_rx):
        self._text = screen_text
        self.last_rx = last_rx
        self.sent = []
        self.conn = FakeConn(connected=True)

    def render(self):
        return self._text.split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._text

    def send(self, text, enter=True, secret=False, sender="app"):
        self.sent.append((text, secret, sender))


class FakeProfile:
    def __init__(self, name="default", game_letter="F", handle="AEGIS"):
        self.name = name
        self.game_letter = game_letter
        self.handle = handle
        self.ship_name = "Vantage"
        self.planet_name = "Anchorage"
        self.allow_register = False
        self.clear_avoids_on_login = False


class ReconnectFakeSession:
    """Ordered-script double for guardian reconnect + login.run_login settle/send.

    Screen advance on send is deferred to the next sleep() — required by
    settle.send_and_confirm's idle path (rx_count must increase after the
    settle poll starts). Matches tests/test_login.py FakeLoginSession.
    """

    def __init__(self, steps, reconnect_outcomes=None):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._steps = steps
        self._i = 0
        self.sent = []
        self.conn = FakeConn(connected=False)
        self.auto_login_profile = None
        self._reconnect_outcomes = list(reconnect_outcomes or [])
        self.reconnect_calls = 0
        self._pending_advance = False
        self.game_select_answered = False
        self.game_select_letter_sent = False

    def reconnect(self, timeout=10):
        self.reconnect_calls += 1
        if self._reconnect_outcomes:
            outcome = self._reconnect_outcomes.pop(0)
            if outcome is not None:
                raise outcome
        self.conn.connected = True
        self.game_select_answered = False
        self.game_select_letter_sent = False

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self._pending_advance:
            self._pending_advance = False
            if self._i < len(self._steps) - 1:
                self._i += 1
            self.rx_count += 1
            self.last_rx = self.t

    def render(self):
        return self._steps[self._i]["screen"].split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._steps[self._i]["screen"]

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350, prompt_requires_new_bytes=False):
        # WO-DO-SETTLE-RX-GUARD: threaded through rather than dropped.
        # This double DELEGATES to the real `wait_for_settle` (it only
        # adds the step-advance side effect), so silently discarding a
        # settle parameter here would make it quietly lie about the
        # primitive it is standing in for. No caller in this file sets it.
        result = wait_for_settle(
            self,
            wait_prompt=wait_prompt,
            timeout_s=timeout,
            debounce_ms=debounce_ms,
            prompt_requires_new_bytes=prompt_requires_new_bytes,
        )
        step = self._steps[self._i]
        if step.get("auto_advance") and self._i < len(self._steps) - 1:
            self._i += 1
            self.rx_count += 1
            self.last_rx = self.t
        return result

    def send(self, text, enter=True, secret=False, sender="app"):
        self.sent.append((text, secret))
        self._pending_advance = True


def _guardian(session, **kwargs):
    return SessionGuardian(
        session,
        get_password=kwargs.pop("get_password", lambda n: "sAvEd123"),
        save_password=kwargs.pop("save_password", lambda n, pw: None),
        load_profile=kwargs.pop("load_profile", lambda n: FakeProfile(name=n)),
        reconnect_backoff_s=0,
        max_reconnect_attempts=kwargs.pop("max_reconnect_attempts", 3),
        idle_keepalive_ms=kwargs.pop("idle_keepalive_ms", 45_000),
        **kwargs,
    )


# -- D10 idle keepalive (WO-P2-028) ----------------------------------------

def test_keepalive_fires_on_idle_main_command():
    session = KeepaliveFakeSession(
        "Command [TL=00:00:00]:[1] (?=Help)? :", last_rx=-1000.0
    )
    g = _guardian(session, idle_keepalive_ms=100)
    g._tick()
    assert session.sent == [("", False, "app")]


def test_keepalive_does_not_fire_below_idle_threshold():
    import time

    session = KeepaliveFakeSession(
        "Command [TL=00:00:00]:[1] (?=Help)? :", last_rx=time.monotonic()
    )
    g = _guardian(session, idle_keepalive_ms=45_000)
    g._tick()
    assert session.sent == []


def test_keepalive_never_fires_on_password_screen_even_if_idle():
    session = KeepaliveFakeSession("Password?", last_rx=-1000.0)
    g = _guardian(session, idle_keepalive_ms=100)
    g._tick()
    assert session.sent == []


def test_keepalive_never_fires_on_port_trade_screen_even_if_idle():
    session = KeepaliveFakeSession(
        "Fuel Ore   Buying   50%\nHow many holds of Fuel Ore do you want to buy [50]?",
        last_rx=-1000.0,
    )
    g = _guardian(session, idle_keepalive_ms=100)
    g._tick()
    assert session.sent == []


def test_keepalive_never_fires_on_unknown_screen_even_if_idle():
    session = KeepaliveFakeSession(
        "some totally unrecognized screen shape", last_rx=-1000.0
    )
    g = _guardian(session, idle_keepalive_ms=100)
    g._tick()
    assert session.sent == []


def test_keepalive_never_fires_on_confirm_screen_even_if_idle():
    session = KeepaliveFakeSession(
        "Do you really want to warp there? (Y/N)", last_rx=-1000.0
    )
    g = _guardian(session, idle_keepalive_ms=100)
    g._tick()
    assert session.sent == []


def test_keepalive_never_fires_on_combat_class_even_if_idle():
    # Classifier has no dedicated combat gate today; pin Accept via injected class.
    session = KeepaliveFakeSession(
        "Command [TL=00:00:00]:[1] (?=Help)? :", last_rx=-1000.0
    )
    g = _guardian(
        session,
        idle_keepalive_ms=100,
        classify_screen=lambda text, prompt: "combat",
    )
    g._tick()
    assert session.sent == []


def test_keepalive_at_most_one_per_idle_window():
    session = KeepaliveFakeSession(
        "Command [TL=00:00:00]:[1] (?=Help)? :", last_rx=-1000.0
    )
    g = _guardian(session, idle_keepalive_ms=100)
    g._tick()
    g._tick()
    assert session.sent == [("", False, "app")]


def test_keepalive_skipped_when_disconnected():
    session = KeepaliveFakeSession(
        "Command [TL=00:00:00]:[1] (?=Help)? :", last_rx=-1000.0
    )
    session.conn.connected = False
    session.auto_login_profile = None  # reconnect no-op
    g = _guardian(session, idle_keepalive_ms=100)
    keepalive_calls = []
    real = g._maybe_keepalive

    def spy():
        keepalive_calls.append(1)
        return real()

    g._maybe_keepalive = spy
    g._tick()
    assert keepalive_calls == []
    assert session.sent == []


def test_keepalive_skipped_during_reconnect_burst():
    session = KeepaliveFakeSession(
        "Command [TL=00:00:00]:[1] (?=Help)? :", last_rx=-1000.0
    )
    g = _guardian(session, idle_keepalive_ms=100)
    g._reconnect_in_flight = True
    g._maybe_keepalive()
    assert session.sent == []


# -- D9 reconnect + login-replay (WO-P2-027) --------------------------------

def test_reconnect_skipped_without_a_recorded_profile():
    session = ReconnectFakeSession(steps=[{"screen": "unused", "expect": None}])
    session.auto_login_profile = None
    g = _guardian(session)
    g._tick()
    assert session.reconnect_calls == 0


def test_reconnect_replays_saved_password_login_to_main_command():
    steps = [
        {"screen": "What is your name?", "expect": None},
        {"screen": "Password?", "expect": None},
        {"screen": "Hello AEGIS, welcome to:", "expect": None, "auto_advance": True},
        {"screen": "Command [TL=00:00:00]:[24146] (?=Help)? :", "expect": None},
    ]
    session = ReconnectFakeSession(steps)
    session.auto_login_profile = "default"
    saved_calls = []
    g = _guardian(
        session,
        get_password=lambda n: "sAvEd123",
        save_password=lambda n, pw: saved_calls.append(pw),
    )
    g._tick()
    assert session.reconnect_calls == 1
    assert session.conn.connected is True
    assert g.reconnect_count == 1
    assert g.last_reconnect_error is None
    # RETURNING branch used the saved credential -- never generated/saved a new one.
    assert saved_calls == []
    secret_sends = [t for t, s in session.sent if s]
    assert secret_sends == ["sAvEd123"]


def test_reconnect_retries_after_a_failed_attempt_then_succeeds():
    steps = [
        {"screen": "What is your name?", "expect": None},
        {"screen": "Password?", "expect": None},
        {"screen": "Command [TL=00:00:00]:[24146] (?=Help)? :", "expect": None},
    ]
    session = ReconnectFakeSession(
        steps, reconnect_outcomes=[OSError("connection refused"), None]
    )
    session.auto_login_profile = "default"
    g = _guardian(session, max_reconnect_attempts=5)
    g._tick()
    assert session.reconnect_calls == 2  # first failed, second succeeded
    assert g.reconnect_count == 1


def test_reconnect_gives_up_after_max_attempts_without_raising():
    session = ReconnectFakeSession(
        steps=[{"screen": "unused", "expect": None}],
        reconnect_outcomes=[OSError("down")] * 5,
    )
    session.auto_login_profile = "default"
    g = _guardian(session, max_reconnect_attempts=3)
    g._tick()  # must not raise
    assert session.reconnect_calls == 3
    assert g.reconnect_count == 0
    assert "down" in g.last_reconnect_error


def test_reconnect_without_saved_password_surfaces_as_last_error_not_a_crash():
    steps = [
        {"screen": "What is your name?", "expect": None},
        {"screen": "Password?", "expect": None},
    ]
    session = ReconnectFakeSession(steps)
    session.auto_login_profile = "default"
    g = _guardian(session, get_password=lambda n: None, max_reconnect_attempts=2)
    g._tick()  # must not raise
    assert "returning_no_saved_password" in g.last_reconnect_error
    assert g.reconnect_count == 0


def test_reconnect_unverified_screen_is_not_reported_as_success():
    """Resume success iff verified main_command — unknown/stuck ≠ success."""
    steps = [
        {"screen": "What is your name?", "expect": None},
        {"screen": "some totally unrecognized screen shape", "expect": None},
    ]
    session = ReconnectFakeSession(steps)
    session.auto_login_profile = "default"
    g = _guardian(session, max_reconnect_attempts=1)
    g._tick()  # must not raise
    assert session.reconnect_calls == 1
    assert g.reconnect_count == 0
    assert g.last_reconnect_error is not None
    assert "automaton_stuck" in g.last_reconnect_error
