"""protocol.py's `ensure` verb dispatch -- the control-lock gate (safety
fix: `ensure` drives the login automaton, a keystroke-sending verb same
as do/send/replay/play/haggle, but was previously dispatched with no
control_lock gate at all -- see `_driving_dispatch`'s docstring). No
network -- same bare dispatch-harness convention as
tests/test_crawl_start_protocol.py; `FakeAttachSession` (conftest.py) is
reused rather than a bespoke double since `_dispatch_ensure` needs the
full `.conn.connected`/`.render()`/`.record_history()` surface it already
provides, and its default screen already classifies `main_command` --
exercising the already_there fast path with zero login-automaton
complexity."""

import pytest

from twclient import credentials, protocol
from twclient.control_lock import MODE_AI_PILOT, MODE_AUTO_LOOP, ControlLock

from .conftest import FakeAttachSession


class FakeServer:
    """Deliberately bare by default -- no `.control_lock`, matching
    protocol.py's documented bare-dispatch-harness convention
    (`_driving_dispatch` treats a missing control_lock as
    unrestricted)."""


@pytest.fixture
def profiles_toml(tmp_path, monkeypatch):
    """"default" (autonomous left at its safe-by-default `False`) plus
    "armed" (`autonomous = true`) -- same two-profile shape
    test_autopilot_protocol.py's own `profiles_toml` fixture already
    establishes, reused here for the WO-FA6 auto-start-on-connect tests
    below."""
    p = tmp_path / "profiles.toml"
    p.write_text(
        "[default]\n"
        'host = "test.example"\n'
        "port = 2002\n"
        'game_letter = "A"\n'
        'handle = "Trader1"\n'
        "\n"
        "[armed]\n"
        'host = "test.example"\n'
        "port = 2002\n"
        'game_letter = "A"\n'
        'handle = "Trader2"\n'
        "autonomous = true\n"
    )
    monkeypatch.setattr(credentials, "PROFILES_PATH", p)
    return p


# -- control-lock gating (same guard do/send/replay/play/haggle share) ------


def test_ensure_refused_while_human_is_attached(profiles_toml):
    session = FakeAttachSession()
    server = FakeServer()
    server.control_lock = ControlLock()
    server.control_lock.take_human()

    resp = protocol.dispatch(session, "ensure", {"profile": "default"}, server)

    assert resp == {"ok": False, "error": "controller_locked_by_human"}
    assert session.sent == []  # _dispatch_ensure never ran -- zero keystrokes


# -- the gate must not regress ensure's documented, everyday use ------------


def test_ensure_still_drives_normally_under_ai_pilot(profiles_toml):
    session = FakeAttachSession()  # default screen already classifies main_command
    server = FakeServer()
    server.control_lock = ControlLock()  # explicit ai_pilot, not just "missing"

    resp = protocol.dispatch(session, "ensure", {"profile": "default"}, server)

    assert resp["ok"] is True
    assert resp["already_there"] is True
    assert resp["steps"] == 0
    assert session.sent == []  # already at target -- the automaton never ran


def test_ensure_still_drives_normally_with_no_control_lock_at_all(profiles_toml):
    """The pre-existing bare-dispatch-harness convention (no
    `server.control_lock` attribute at all) must keep working too."""
    session = FakeAttachSession()

    resp = protocol.dispatch(session, "ensure", {"profile": "default"}, FakeServer())

    assert resp["ok"] is True
    assert resp["already_there"] is True


# -- WO-FA6: post-login auto-start-on-connect (autopilot.py's
# maybe_auto_start, P1-d) -- wiring only, no arm-posture change ------------


class _OneStepEnsureSession(FakeAttachSession):
    """Reaches `target` after exactly ONE login-automaton step, so a test
    can drive a GENUINE `run_login` pass through the real `_dispatch_
    ensure`/`build_response` surface -- not just the already-there fast
    path every other fixture in this file exercises.

    Starts classified `pause_key` (`"  [Pause]"` -- the exact literal
    tests/test_classify.py's own `test_pause_key` and
    tests/test_login.py's own scripted step both use), whose `_decide()`
    handling (login.py's D7-nuisance branch) is a bare blank Enter with
    no `wait_hint` -- so `send_and_confirm` resolves it via the plain
    IDLE path, the exact mechanism `FakeAttachSession.sleep()`'s own
    deferred-`_pending_advance` discipline (see its docstring) already
    supports for real, no network. This subclass adds only the ONE thing
    that discipline doesn't already do on its own: flip `self._screen`
    to the real target screen once that Enter's confirm resolves --
    reusing (never re-inventing) the base class's own timing.

    `_dispatch_ensure`'s fresh-login-success branch also calls
    `session.mark_profile(profile.name)` (real `Session.mark_profile`'s
    exact effect) -- absent from the base `FakeAttachSession` because no
    existing test in this file has ever driven a real login through it
    before; added here rather than to the shared fixture, since it's
    only needed on this one path."""

    def __init__(self, target_screen):
        super().__init__(initial_screen="  [Pause]")
        self._target_screen = target_screen
        self.auto_login_profile = None  # mirrors real Session.__init__'s own default

    def sleep(self, seconds):
        advancing = self._pending_advance
        super().sleep(seconds)
        if advancing:
            self._screen = self._target_screen

    def mark_profile(self, profile_name):
        self.auto_login_profile = profile_name


_TARGET_SCREEN = "Command [TL=00:00:00]:[1234] (?=Help)? :"  # same literal FakeAttachSession's own default screen uses


def test_ensure_genuine_connect_with_an_autonomous_profile_arms_the_loop_once(profiles_toml):
    """(i) genuine-connect (the login automaton actually ran, `already_
    there is False`) + (ii) `server.autopilot_loop is None` (nothing
    stashed yet) => the hook arms exactly once: stashed on `server.
    autopilot_loop`/`autopilot_engine`, same slots a manual
    `autopilot_start` already fills."""
    session = _OneStepEnsureSession(_TARGET_SCREEN)
    server = FakeServer()
    server.control_lock = ControlLock()

    resp = protocol.dispatch(session, "ensure", {"profile": "armed"}, server)

    assert resp["ok"] is True
    assert resp["already_there"] is False  # proves the automaton genuinely ran, not the fast path
    loop = server.autopilot_loop
    assert loop is not None
    assert loop.running is True
    assert server.autopilot_engine is loop.engine
    assert server.control_lock.mode == MODE_AUTO_LOOP

    assert loop.stop() is True  # halts cleanly within its own join_timeout
    assert server.control_lock.mode == MODE_AI_PILOT


def test_ensure_reaching_target_with_the_shipped_default_profile_starts_and_sends_nothing(profiles_toml):
    """SAFETY (falsifiable): the ordinary "default" profile -- `autonomous`
    left at its safe-by-default `False`, the posture every profile
    actually shipped has -- must arm NOTHING and send NOTHING when
    `ensure` reaches target, the identical posture a real daemon has on
    every real connect today. (Uses the already-there fast path, same as
    before this revise -- explicitly kept per the hub's own instruction,
    since it's still a valid regression check even though (i)'s
    genuine-connect gate below would ALSO block this path on its own.)"""
    session = FakeAttachSession()
    server = FakeServer()
    server.control_lock = ControlLock()

    resp = protocol.dispatch(session, "ensure", {"profile": "default"}, server)

    assert resp["ok"] is True
    assert getattr(server, "autopilot_loop", None) is None
    assert getattr(server, "autopilot_engine", None) is None
    assert session.sent == []
    assert server.control_lock.mode == MODE_AI_PILOT


def test_repeated_ensure_never_rearms_over_a_halted_loop(profiles_toml):
    """mack HIGH (WO-FA6 revise) -- the safety halt is STICKY. First
    `ensure` is a genuine connect that arms `loop1`; `loop1` then halts
    (mode back to `ai_pilot`, `.last_error` set -- reproducing exactly
    what `AutopilotLoop._run()`'s own two halt branches leave behind, via
    `.stop()` + a direct `.last_error` assignment rather than fabricating
    a live crash/desync). A LATER, routine `ensure` on the SAME
    already-connected session hits the ordinary already-there fast path
    (the fake screen never moved) -- it must NOT re-arm, NOT clobber
    `server.autopilot_loop`, and NOT clear `loop1.last_error`. Revert the
    sticky-halt fix (drop the `server.autopilot_loop is not None` guard in
    `_maybe_auto_start_after_ensure`) and this goes RED: `second_loop` would
    be a fresh, DIFFERENT `AutopilotLoop` instance."""
    session = _OneStepEnsureSession(_TARGET_SCREEN)
    server = FakeServer()
    server.control_lock = ControlLock()

    first = protocol.dispatch(session, "ensure", {"profile": "armed"}, server)
    assert first["ok"] is True
    assert first["already_there"] is False
    loop1 = server.autopilot_loop
    assert loop1 is not None

    assert loop1.stop() is True
    loop1.last_error = "settle_unconfirmed: halted rather than ticking past a send/settle desync"
    assert server.control_lock.mode == MODE_AI_PILOT

    second = protocol.dispatch(session, "ensure", {"profile": "armed"}, server)
    assert second["ok"] is True
    assert second["already_there"] is True  # the routine re-ensure hits the fast path -- nothing moved
    assert server.autopilot_loop is loop1  # never replaced
    assert loop1.last_error == "settle_unconfirmed: halted rather than ticking past a send/settle desync"
    assert server.control_lock.mode == MODE_AI_PILOT  # never resurrected into MODE_AUTO_LOOP


def test_idempotent_already_there_ensure_arms_when_armed_and_no_loop_stashed(profiles_toml):
    """WO-AUTOPILOT-AFTER-ENSURE: mid-session already-there `ensure` with
    `autonomous=true` and `autopilot_loop is None` MUST arm -- that is the
    accept path ("ensure → autopilot without manual play"). Sticky-halt
    still blocks re-arm when a halted loop is stashed (see
    `test_repeated_ensure_never_rearms_over_a_halted_loop`)."""
    session = FakeAttachSession()  # default screen already classifies main_command
    server = FakeServer()
    server.control_lock = ControlLock()

    resp = protocol.dispatch(session, "ensure", {"profile": "armed"}, server)

    assert resp["ok"] is True
    assert resp["already_there"] is True
    loop = server.autopilot_loop
    assert loop is not None
    assert loop.running is True
    assert server.control_lock.mode == MODE_AUTO_LOOP
    assert loop.stop() is True


def test_ensure_clears_fighter_option_then_arms_for_autonomous_profile(profiles_toml):
    """WO-AUTOPILOT-AFTER-ENSURE: Option? (no Pay) before main_command —
    ensure clears Attack + qty once, reaches target, arms the loop."""
    toll = (
        "Your fighters: 30 vs. theirs: 1\n"
        "Option? (A,D,I,R,S,?):?"
    )
    qty = (
        "Your fighters: 30 vs. theirs: 1\n"
        "How many fighters do you wish to use (0 to 30) [0]?"
    )
    target = "Command [TL=00:00:00]:[1234] (?=Help)? :"

    class _TollThenMain(FakeAttachSession):
        def __init__(self):
            super().__init__(initial_screen=toll)

        def sleep(self, seconds):
            advancing = self._pending_advance
            super().sleep(seconds)
            if not advancing or not self.sent:
                return
            last = self.sent[-1][0]
            if last == "A":
                self._screen = qty
            elif last.isdigit():
                self._screen = target

    session = _TollThenMain()
    server = FakeServer()
    server.control_lock = ControlLock()

    resp = protocol.dispatch(session, "ensure", {"profile": "armed"}, server)

    assert resp["ok"] is True
    sent_keys = [s[0] for s in session.sent]
    assert "A" in sent_keys
    assert "1" in sent_keys
    loop = server.autopilot_loop
    assert loop is not None
    assert loop.running is True
    assert server.control_lock.mode == MODE_AUTO_LOOP
    assert loop.stop() is True


def test_ensure_with_no_control_lock_at_all_arms_nothing(profiles_toml):
    """The bare dispatch-harness convention (no `server.control_lock` at
    all) must never attempt an auto-start -- `_maybe_auto_start_after_
    ensure` has no lock to gate `enter_auto_loop()` against, so it no-ops
    rather than guessing. Routed through a genuine connect (not the
    already-there path) so this actually exercises the `control_lock is
    None` guard inside the hook, rather than being blocked earlier by
    the genuine-connect gate alone."""
    session = _OneStepEnsureSession(_TARGET_SCREEN)
    server = FakeServer()

    resp = protocol.dispatch(session, "ensure", {"profile": "armed"}, server)

    assert resp["ok"] is True
    assert resp["already_there"] is False
    assert getattr(server, "autopilot_loop", None) is None


def test_ensure_refused_under_human_attach_arms_nothing_even_for_an_autonomous_profile(profiles_toml):
    """Companion to `test_ensure_refused_while_human_is_attached` above,
    naming the autonomous "armed" profile this time: a human-attached
    `ensure` is refused by `_driving_dispatch` before `_dispatch_ensure`
    (and therefore this hook) ever runs at all -- no loop, regardless of
    which profile was named."""
    session = FakeAttachSession()
    server = FakeServer()
    server.control_lock = ControlLock()
    server.control_lock.take_human()

    resp = protocol.dispatch(session, "ensure", {"profile": "armed"}, server)

    assert resp == {"ok": False, "error": "controller_locked_by_human"}
    assert session.sent == []
    assert getattr(server, "autopilot_loop", None) is None
