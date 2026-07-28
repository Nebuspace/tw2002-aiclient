"""`ensure --profile X` must verify IDENTITY, not just screen CLASS.

WO-ENSURE-PROFILE-IDENTITY-VERIFY. The defect these pin closed: a session
sitting at `main_command` was stamped `session.mark_profile(X)` on the
strength of the screen class alone, whatever server it was actually on --
and that stamp is what arms `guardian._maybe_reconnect` to replay X's
credential after a drop, through a `session.reconnect()` that goes back to
the SESSION's host, never the profile's. The immediate path was the same
shape: on a class miss, `run_login` ran against the EXISTING socket.

So the guarantees here are NEGATIVE ones -- "`mark_profile` was not called",
"`run_login` was not reached" -- and a negative assertion is worthless if the
thing it watches could never have fired in that test anyway. Every such
assertion below is therefore paired with a POSITIVE CONTROL that drives the
same spy through the same dispatch on a MATCHING host and proves it does
fire (`test_matching_host_still_reaches_run_login`,
`test_matching_host_is_still_accepted`).

No network, no credentials, no real hostnames: hosts come from
`conftest.resolve_fake_host_port`, per the WO-GITINIT-SCRUB convention that
a stand-in host is resolved through the real env code rather than typed as a
literal that could later be mistaken for a real one.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.session import credentials, login as login_module, protocol

from .conftest import FAKE_HOST, FAKE_PORT, FakeAttachSession, resolve_fake_host_port

# A second, deliberately DIFFERENT stand-in endpoint -- the "wrong server"
# side of every mismatch case below.
OTHER_HOST, OTHER_PORT = resolve_fake_host_port(
    fake_host="other.test.example", fake_port=2002
)

NON_COMMAND_SCREEN = "Trade Wars 2002 -- some other screen entirely"


class FakeServer:
    """Bare server double -- no `control_lock`, so `_driving_dispatch` stays
    unrestricted (the harness convention `test_ensure_protocol.py` uses)."""


@pytest.fixture
def profiles_toml(tmp_path, monkeypatch):
    """One profile, pointing at FAKE_HOST:FAKE_PORT."""
    p = tmp_path / "profiles.toml"
    p.write_text(
        "[default]\n"
        f'host = "{FAKE_HOST}"\n'
        f"port = {FAKE_PORT}\n"
        'game_letter = "A"\n'
        'handle = "Trader1"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(credentials, "PROFILES_PATH", p)
    return p


class RunLoginSpy:
    """Stands in for `login.run_login` -- records every call, sends nothing.

    Returning `(target, steps)` is the shape a successful login returns, so
    the dispatch continues down its success path and the test can observe
    what happens AFTER a login (specifically: whether the profile stamp
    lands)."""

    def __init__(self, result=("main_command", 3), on_call=None):
        self.calls = []
        self._result = result
        self._on_call = on_call

    def __call__(self, session, profile, **kwargs):
        self.calls.append(profile.name)
        if self._on_call is not None:
            self._on_call(session)
        return self._result


def _session_on(host, port, screen=None):
    session = FakeAttachSession() if screen is None else FakeAttachSession(screen)
    session.host = host
    session.port = port
    return session


def _ensure(session, server=None, profile="default"):
    return protocol.dispatch(
        session, "ensure", {"profile": profile}, server or FakeServer()
    )


# -- 1. mismatch refuses, and does not relabel the session ----------------


def test_wrong_host_is_refused_and_the_session_is_not_relabelled(
    profiles_toml, monkeypatch
):
    """The screen classifies as `main_command` -- the exact input the old
    code accepted as proof -- but the session is on another server."""
    spy = RunLoginSpy()
    monkeypatch.setattr(login_module, "run_login", spy)
    session = _session_on(OTHER_HOST, FAKE_PORT)

    resp = _ensure(session)

    assert resp["ok"] is False
    assert resp["error"] == "profile_host_mismatch:default"
    # The relabel is the part that arms the later credential replay.
    assert session.auto_login_profile is None
    assert spy.calls == []
    assert session.sent == []


# -- 2. mismatch never reaches the credential send ------------------------


def test_wrong_host_never_reaches_run_login(profiles_toml, monkeypatch):
    """Class MISS on a wrong-host session: the old code ran the login
    automaton against the existing socket from here."""
    spy = RunLoginSpy()
    monkeypatch.setattr(login_module, "run_login", spy)
    session = _session_on(OTHER_HOST, FAKE_PORT, screen=NON_COMMAND_SCREEN)

    resp = _ensure(session)

    assert resp["ok"] is False
    assert resp["error"] == "profile_host_mismatch:default"
    assert spy.calls == []
    assert session.auto_login_profile is None


def test_matching_host_still_reaches_run_login(profiles_toml, monkeypatch):
    """POSITIVE CONTROL for the spy above: same screen, same dispatch, same
    monkeypatch -- only the host differs, and the login DOES run. Without
    this, `spy.calls == []` would also pass against a spy that was never
    wired to anything."""
    spy = RunLoginSpy()
    monkeypatch.setattr(login_module, "run_login", spy)
    session = _session_on(FAKE_HOST, FAKE_PORT, screen=NON_COMMAND_SCREEN)

    resp = _ensure(session)

    assert resp["ok"] is True
    assert spy.calls == ["default"]
    assert session.auto_login_profile == "default"


# -- 3. no false refusals -------------------------------------------------


def test_matching_host_is_still_accepted(profiles_toml):
    """The unchanged already-there fast path, on a matching session."""
    session = _session_on(FAKE_HOST, FAKE_PORT)

    resp = _ensure(session)

    assert resp["ok"] is True
    assert resp["already_there"] is True
    assert resp["steps"] == 0
    assert session.auto_login_profile == "default"


def test_case_and_trailing_root_dot_are_the_same_host(profiles_toml):
    """DNS treats `HOST.` and `host` as one name; refusing there would be a
    manufactured refusal."""
    session = _session_on(FAKE_HOST.upper() + ".", FAKE_PORT)

    resp = _ensure(session)

    assert resp["ok"] is True
    assert session.auto_login_profile == "default"


def test_a_doubled_trailing_dot_is_not_the_same_host(profiles_toml):
    """Falsifies the normalisation's other direction: exactly ONE trailing
    root dot is dropped, so `rstrip(".")` -- which would wave `host..`
    through -- is ruled out."""
    session = _session_on(FAKE_HOST + "..", FAKE_PORT)

    resp = _ensure(session)

    assert resp["ok"] is False
    assert resp["error"] == "profile_host_mismatch:default"
    assert session.auto_login_profile is None


def test_session_with_no_usable_port_is_not_refused(profiles_toml):
    """The chosen "nothing to confuse" rule, pinned as a decision: the
    comparison is made iff `session.port` is a usable port. Port 0 is not a
    reachable TCP target, so such a session has never spoken to a game
    server and has no established identity for a profile to contradict --
    a first `ensure` still works."""
    session = _session_on(OTHER_HOST, 0)

    resp = _ensure(session)

    assert resp["ok"] is True
    assert session.auto_login_profile == "default"


def test_empty_host_with_a_real_port_is_still_refused(profiles_toml, monkeypatch):
    """The other side of that rule, and the reason it keys on the PORT
    alone: an empty host with a real port is still a connectable target (it
    resolves to the loopback/any address), so it is compared and refused
    rather than waved through as "no identity"."""
    spy = RunLoginSpy()
    monkeypatch.setattr(login_module, "run_login", spy)
    session = _session_on("", FAKE_PORT, screen=NON_COMMAND_SCREEN)

    resp = _ensure(session)

    assert resp["ok"] is False
    assert resp["error"] == "profile_host_mismatch:default"
    assert spy.calls == []


class DisconnectedSession(FakeAttachSession):
    """A session whose telnet connection is down, recording whether the
    dispatch tried to repair it."""

    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.conn.connected = False
        self.reconnects = 0

    def reconnect(self, timeout=10):
        self.reconnects += 1
        self.conn.connected = True


def test_a_wrong_profile_request_does_not_even_buy_a_reconnect(
    profiles_toml, monkeypatch
):
    """The gate sits BEFORE the dead-connection repair, so a request naming
    the wrong profile is refused without the daemon reconnecting on that
    profile's behalf. (This is the one behaviour the later, use-point
    re-derivations cannot provide: by the time they run, the reconnect has
    already happened.)"""
    spy = RunLoginSpy()
    monkeypatch.setattr(login_module, "run_login", spy)
    session = DisconnectedSession(OTHER_HOST, FAKE_PORT)

    resp = _ensure(session)

    assert resp["ok"] is False
    assert resp["error"] == "profile_host_mismatch:default"
    assert session.reconnects == 0
    assert spy.calls == []


def test_a_matching_profile_still_reconnects(profiles_toml):
    """POSITIVE CONTROL for the counter above: identical session, matching
    host -- the repair still runs, so `reconnects == 0` above is a real
    negative and not a counter that could never move."""
    session = DisconnectedSession(FAKE_HOST, FAKE_PORT)

    resp = _ensure(session)

    assert resp["ok"] is True
    assert session.reconnects == 1


# -- 4. fail closed on an unverifiable identity ---------------------------


def test_resolver_failure_at_the_identity_read_refuses(profiles_toml, monkeypatch):
    """Fail closed: the store went unreadable between the loader's resolve
    and the identity gate's. An identity we cannot establish is never
    treated as a matching one.

    The counter is what makes this land on the NEW code: call 1 is
    `_load_profile`'s own resolve (which has always refused a raising
    resolver, with its own `profile_connection_error:` wording), call 2 is
    the identity gate's."""
    real = credentials.resolve_profile_host_port
    calls = []

    def flaky(profile_name, **kwargs):
        calls.append(profile_name)
        if len(calls) == 1:
            return real(profile_name, **kwargs)
        raise OSError("store vanished")

    monkeypatch.setattr(credentials, "resolve_profile_host_port", flaky)
    spy = RunLoginSpy()
    monkeypatch.setattr(login_module, "run_login", spy)
    session = _session_on(FAKE_HOST, FAKE_PORT)

    resp = _ensure(session)

    assert resp["ok"] is False
    assert resp["error"].startswith("profile_identity_unverified:default:")
    # Type name only -- never the exception's message.
    assert "store vanished" not in resp["error"]
    assert session.auto_login_profile is None
    assert spy.calls == []


def test_a_profile_with_no_resolvable_host_is_refused(tmp_path, monkeypatch):
    """End-to-end fail-closed for the ORDINARY unresolvable profile. This
    refusal comes from `_load_profile`'s pre-existing
    `profile_connection_error:` branch, not from the new gate -- recorded
    here so the identity story is complete and so the provenance of the
    refusal is not overstated."""
    p = tmp_path / "profiles.toml"
    p.write_text(
        "[default]\n" 'game_letter = "A"\n' 'handle = "Trader1"\n', encoding="utf-8"
    )
    monkeypatch.setattr(credentials, "PROFILES_PATH", p)
    spy = RunLoginSpy()
    monkeypatch.setattr(login_module, "run_login", spy)
    session = _session_on(FAKE_HOST, FAKE_PORT)

    resp = _ensure(session)

    assert resp["ok"] is False
    assert resp["error"].startswith("profile_connection_error:default:")
    assert session.auto_login_profile is None
    assert spy.calls == []


# -- 5. Accept 2: the check cannot be trusted forward ---------------------


class RetargetingSession(FakeAttachSession):
    """A session whose connect target changes UNDER the dispatch, on the
    `render()` call that sits between the gate and the use points.

    This is the deterministic model of the stop-in-flight race: a daemon
    stop/restart burst landing in that window is the real-world way the
    session a dispatch is holding stops being the session it verified. It
    is injected at `render()` because that -- with `classify_screen` -- is
    the only work between the two, so it reproduces the window exactly
    without depending on thread scheduling."""

    def __init__(self, host, port, new_host, screen=None):
        if screen is None:
            super().__init__()
        else:
            super().__init__(screen)
        self.host = host
        self.port = port
        self._new_host = new_host
        self.renders = 0

    def render(self):
        self.renders += 1
        if self.renders == 1:
            self.host = self._new_host
        return super().render()


def test_a_retarget_between_the_gate_and_the_use_cannot_yield_ok(profiles_toml):
    """Accept 2, reuse path: the session passed the gate, then became a
    session on another server before the `mark_profile` stamp. The stamp is
    the arming step, so this must refuse rather than return `ok: True`."""
    session = RetargetingSession(FAKE_HOST, FAKE_PORT, OTHER_HOST)

    resp = _ensure(session)

    assert session.renders >= 1  # the injection really ran
    assert resp["ok"] is False
    assert resp["error"] == "profile_host_mismatch:default"
    assert session.auto_login_profile is None


def test_a_retarget_between_the_gate_and_the_use_cannot_reach_run_login(
    profiles_toml, monkeypatch
):
    """Accept 2, login path: same window, class MISS -- the credential send
    must not happen at all."""
    spy = RunLoginSpy()
    monkeypatch.setattr(login_module, "run_login", spy)
    session = RetargetingSession(
        FAKE_HOST, FAKE_PORT, OTHER_HOST, screen=NON_COMMAND_SCREEN
    )

    resp = _ensure(session)

    assert resp["ok"] is False
    assert resp["error"] == "profile_host_mismatch:default"
    assert spy.calls == []


def test_a_retarget_during_the_login_withholds_the_profile_stamp(
    profiles_toml, monkeypatch
):
    """Accept 2, widest window: the login itself. A refusal here cannot
    un-send what already went out, so it does the one thing still available
    -- it leaves `auto_login_profile` unset, so no FUTURE reconnect replays
    this credential for a session whose target is no longer vouched for."""

    def retarget(session):
        session.host = OTHER_HOST

    spy = RunLoginSpy(on_call=retarget)
    monkeypatch.setattr(login_module, "run_login", spy)
    session = _session_on(FAKE_HOST, FAKE_PORT, screen=NON_COMMAND_SCREEN)

    resp = _ensure(session)

    assert spy.calls == ["default"]  # the login really did run
    assert resp["ok"] is False
    assert resp["error"] == "profile_host_mismatch:default"
    assert session.auto_login_profile is None


# -- 6. port-only mismatch ------------------------------------------------


def test_port_mismatch_alone_is_refused(profiles_toml, monkeypatch):
    """Right host, wrong port -- a different game server on the same
    machine is a different world with different characters. Its own error
    name: reporting this as `profile_host_mismatch` would tell the operator
    something false about their config while refusing it."""
    spy = RunLoginSpy()
    monkeypatch.setattr(login_module, "run_login", spy)
    assert OTHER_PORT != FAKE_PORT  # the case is only real while these differ
    session = _session_on(FAKE_HOST, OTHER_PORT, screen=NON_COMMAND_SCREEN)

    resp = _ensure(session)

    assert resp["ok"] is False
    assert resp["error"] == "profile_port_mismatch:default"
    assert spy.calls == []
    assert session.auto_login_profile is None
