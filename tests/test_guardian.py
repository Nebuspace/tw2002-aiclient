"""SessionGuardian tests (WO-P2-027 reconnect+replay; WO-P2-028 keepalive).

No network, no real threading: `_tick()` is called directly rather than
starting the background thread, matching the fake-clock / direct-call
style used for settle.py tests.
"""

from __future__ import annotations

from tw2002_aiclient.session.guardian import SessionGuardian
from tw2002_aiclient.session.settle import MATCH_SCOPE_SCREEN, wait_for_settle


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

    def current_prompt_line(self):
        # WO-DO-PROMPT-LINE-PIN: mirrors the real `Session.
        # current_prompt_line()` (last non-empty row of the current
        # render, stripped). Needed because `wait_settle` below DELEGATES
        # to the real `wait_for_settle`, and `settle._match_source`
        # refuses `match_scope="prompt_line"` on a session that cannot
        # serve this accessor -- deliberately, rather than degrading to a
        # whole-screen search. No caller in this file sets that scope
        # today; the accessor is here so one CAN, instead of hitting a
        # TypeError that says nothing about the test's own subject.
        rows = self.render()
        return rows[-1].strip() if rows else ""

    def wait_settle(
        self,
        wait_prompt=None,
        timeout=8.0,
        debounce_ms=350,
        prompt_requires_new_bytes=False,
        match_scope=MATCH_SCOPE_SCREEN,
    ):
        # WO-DO-SETTLE-RX-GUARD / WO-DO-PROMPT-LINE-PIN: threaded through
        # rather than dropped. This double DELEGATES to the real
        # `wait_for_settle` (it only adds the step-advance side effect),
        # so silently discarding a settle parameter here would make it
        # quietly lie about the primitive it is standing in for. No caller
        # in this file sets either one.
        result = wait_for_settle(
            self,
            wait_prompt=wait_prompt,
            timeout_s=timeout,
            debounce_ms=debounce_ms,
            prompt_requires_new_bytes=prompt_requires_new_bytes,
            match_scope=match_scope,
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


def test_keepalive_never_fires_on_a_port_quantity_screen_even_if_idle():
    """Renamed from ...on_port_trade_screen... and pinned by class, because
    the class this screen carries CHANGED: its live prompt is a buy
    quantity, which WO-CLASSIFY-BLOCK-TITLES now names `money_prompt`
    (canon DECISIONS §A.2, never-auto-action) where it used to fall
    through to the `port_trade` content anchor. The keepalive behaviour is
    identical either way -- `_maybe_keepalive` acts on `main_command`
    alone -- but the old NAME asserted a class the classifier no longer
    returns here, which would have quietly become a lie.

    The screen matters more than most: canon's P-QTY is exactly about
    `[50]`-style brackets that a bare Enter ACCEPTS, so the keepalive's
    bare Enter would buy 50 holds."""
    from tw2002_aiclient.session.classify import NEVER_AUTO_ACTION_CLASSES, classify_screen

    text = "Fuel Ore   Buying   50%\nHow many holds of Fuel Ore do you want to buy [50]?"
    prompt = text.splitlines()[-1]
    assert classify_screen(text, prompt) in NEVER_AUTO_ACTION_CLASSES

    session = KeepaliveFakeSession(text, last_rx=-1000.0)
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


def test_reconnecting_property_mirrors_the_private_flag():
    """WO-DIAGNOSE-EXPLORE-HALT-GAME-SELECT-LIVE-SESSION: the public
    read-only surface another driver (ExploreRunner) polls -- pinned
    separately from the private flag so a rename of the internal
    attribute is caught here rather than silently breaking that
    consumer's `getattr(guardian, "reconnecting", False)` into an
    always-False no-op."""
    session = KeepaliveFakeSession(
        "Command [TL=00:00:00]:[1] (?=Help)? :", last_rx=-1000.0
    )
    g = _guardian(session)
    assert g.reconnecting is False
    g._reconnect_in_flight = True
    assert g.reconnecting is True
    g._reconnect_in_flight = False
    assert g.reconnecting is False


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
    assert g.reconnect_exhausted is True
    # Sticky: a later poll must NOT silently forever-retry.
    g._tick()
    assert session.reconnect_calls == 3


def test_reconnect_exhausted_clears_on_manual_clear_and_allows_retry():
    session = ReconnectFakeSession(
        steps=[{"screen": "unused", "expect": None}],
        reconnect_outcomes=[OSError("down")] * 6,
    )
    session.auto_login_profile = "default"
    g = _guardian(session, max_reconnect_attempts=2)
    g._tick()
    assert g.reconnect_exhausted is True
    assert session.reconnect_calls == 2
    g.clear_reconnect_exhausted()
    assert g.reconnect_exhausted is False
    g._tick()
    assert session.reconnect_calls == 4
    assert g.reconnect_exhausted is True


def test_reconnect_exhausted_clears_when_socket_comes_back():
    session = ReconnectFakeSession(
        steps=[{"screen": "unused", "expect": None}],
        reconnect_outcomes=[OSError("down")] * 3,
    )
    session.auto_login_profile = "default"
    g = _guardian(session, max_reconnect_attempts=2)
    g._tick()
    assert g.reconnect_exhausted is True
    session.conn.connected = True  # manual ensure / attach restored the link
    g._tick()
    assert g.reconnect_exhausted is False


def test_reconnect_exhausted_does_not_take_human_mode():
    """(C) exhaustion must not auto-MODE_HUMAN / touch a control lock."""
    session = ReconnectFakeSession(
        steps=[{"screen": "unused", "expect": None}],
        reconnect_outcomes=[OSError("down")] * 3,
    )
    session.auto_login_profile = "default"
    g = _guardian(session, max_reconnect_attempts=2)
    g._tick()
    assert g.reconnect_exhausted is True
    assert not hasattr(g, "control_lock") or g.__dict__.get("control_lock") is None


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


# -- WO-GUARDIAN-KEEPALIVE-LEDGER ------------------------------------------

def test_keepalive_writes_app_ledger_row(tmp_path):
    from tw2002_aiclient.ledger import read_entries, LedgerWriter

    session = KeepaliveFakeSession(
        "Command [TL=00:00:00]:[1] (?=Help)? :", last_rx=-1000.0
    )
    session.session_id = "guardian-keepalive-test"
    ledger = LedgerWriter(path=tmp_path / "ledger.jsonl")
    g = _guardian(session, idle_keepalive_ms=100, ledger=ledger)
    g._tick()
    assert session.sent == [("", False, "app")]
    rows = read_entries(tmp_path / "ledger.jsonl")
    assert len(rows) == 1
    assert rows[0]["actor"] == "app"
    assert rows[0]["session_id"] == "guardian-keepalive-test"
    assert rows[0]["input"] == ""


def test_keepalive_without_ledger_still_sends():
    session = KeepaliveFakeSession(
        "Command [TL=00:00:00]:[1] (?=Help)? :", last_rx=-1000.0
    )
    g = _guardian(session, idle_keepalive_ms=100)  # ledger=None
    g._tick()
    assert session.sent == [("", False, "app")]


def test_daemon_shares_ledger_with_guardian():
    src = __import__("pathlib").Path(__file__).resolve().parents[1] / "tw2002_aiclient" / "session" / "daemon.py"
    text = src.read_text(encoding="utf-8")
    assert "ledger = LedgerWriter()" in text
    assert "ledger=ledger" in text
    assert "server.ledger = ledger" in text


# -- WO-FIX-SESSIONGUARDIAN-EXHAUSTED-RECONNECT-SILENT (status wire) --------

def test_status_surfaces_reconnect_exhausted_intervention(tmp_path):
    """(B) sticky exhaust appears on status["intervention"] with typed code."""
    from tw2002_aiclient.session import protocol
    from tw2002_aiclient.session.session import Session

    class _Server:
        watch_hub = None
        control_lock = None
        autoloop = None
        trade_chain = None
        guardian = None

    session = Session("127.0.0.1", 65000, "sg-exhaust", str(tmp_path))
    session.conn.connected = False
    g = _guardian(
        ReconnectFakeSession(
            steps=[{"screen": "unused", "expect": None}],
            reconnect_outcomes=[OSError("down")] * 3,
        ),
        max_reconnect_attempts=2,
    )
    g.session.auto_login_profile = "default"
    g._tick()
    assert g.reconnect_exhausted is True
    server = _Server()
    server.guardian = g
    # Minimal screen surface for _status_response classify path
    session.conn.connected = False
    resp = protocol._status_response(session, server)
    assert resp["intervention"]["needs_attention"] is True
    codes = [
        (r.get("code") if isinstance(r, dict) else r)
        for r in resp["intervention"]["reasons"]
    ]
    assert "reconnect_exhausted" in codes
    # WO-CLEANUP-GUARDIAN-RECONNECT-DIAGNOSTICS-UNWIRED
    reason = next(
        r for r in resp["intervention"]["reasons"]
        if isinstance(r, dict) and r.get("code") == "reconnect_exhausted"
    )
    assert reason.get("detail") == g.last_reconnect_error
    assert "reconnect" in resp
    assert resp["reconnect"]["exhausted"] is True
    assert resp["reconnect"]["count"] == 0
    assert resp["reconnect"]["last_error"] == g.last_reconnect_error
    assert "down" in resp["reconnect"]["last_error"]


def test_status_reconnect_diagnostics_when_guardian_idle(tmp_path):
    """Guardian attached but not exhausted still emits status["reconnect"]."""
    from tw2002_aiclient.session import protocol
    from tw2002_aiclient.session.session import Session

    class _Server:
        watch_hub = None
        control_lock = None
        autoloop = None
        trade_chain = None
        guardian = None

    session = Session("127.0.0.1", 65000, "sg-idle", str(tmp_path))
    session.conn.connected = True
    g = _guardian(
        ReconnectFakeSession(
            steps=[{"screen": "unused", "expect": None}],
            reconnect_outcomes=[],
        ),
        max_reconnect_attempts=2,
    )
    g.reconnect_count = 3
    g.last_reconnect_error = None
    g.reconnect_exhausted = False
    server = _Server()
    server.guardian = g
    resp = protocol._status_response(session, server)
    assert "intervention" not in resp or "reconnect_exhausted" not in [
        (r.get("code") if isinstance(r, dict) else r)
        for r in (resp.get("intervention") or {}).get("reasons") or []
    ]
    assert resp["reconnect"] == {
        "count": 3,
        "exhausted": False,
        "last_error": None,
    }


def test_status_omits_reconnect_when_no_guardian(tmp_path):
    """Additive: test doubles without guardian keep the key absent."""
    from tw2002_aiclient.session import protocol
    from tw2002_aiclient.session.session import Session

    class _Server:
        watch_hub = None
        control_lock = None
        autoloop = None
        trade_chain = None
        guardian = None

    session = Session("127.0.0.1", 65000, "sg-none", str(tmp_path))
    session.conn.connected = True
    resp = protocol._status_response(session, _Server())
    assert "reconnect" not in resp

