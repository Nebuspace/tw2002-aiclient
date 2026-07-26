"""Login Automaton end-to-end proof (WO-P2-023): drives the REAL
`login.run_login()` (`tw2002_aiclient/session/login.py`) against a REAL
`Session` (`tw2002_aiclient/session/session.py`), over a REAL (loopback)
TCP connection, through a scripted fake TWGS server
(`tests/fake_twgs.py`) -- no mocked session, no real game. Self-contained:
does not depend on `tests/conftest.py` fixtures and never touches real
`config/` (get_password/save_password are injected per-test closures over
a local dict, exactly as `run_login()`'s own signature is designed for).

Proves WO-P2-023's 4 Accept criteria (5 tests -- criterion 1 gets a second,
regression-guard test):
  1. RETURNING -- saved password sent exactly once, reaches main_command.
     Plus `test_returning_slow_transition_reaches_main_command`: a
     legitimate login whose post-password response is slow/two-stage must
     still reach main_command, never false-reject as
     `returning_password_rejected` (Mack HIGH, fixed by folding the
     RETURNING reappearance into the automaton's existing stagnant-rounds
     settle-grace instead of raising on it immediately -- see
     `login.py`'s `_decide()`/`run_login()` for the exact mechanism).
  2. NEW (`allow_register=True`) -- completes registration; the generated
     password is saved via `save_password()` (login.py's own module
     docstring: "Saved the moment it's chosen, before the first send"),
     and the value the server received matches what was saved.
  3. refused (`allow_register=False`) -- char_create's hard gate raises
     `LoginError` before a single byte is sent (not even the "Y").
  4. wrong_password -- a stale/wrong saved credential is sent EXACTLY
     ONCE (canon: `login-automaton.md`'s fail-fast, send-once ceiling for
     RETURNING); the server's re-presented gate is treated as a
     rejection and raises immediately, never reaching main_command and
     never re-sending the already-known-bad value.

Every test also asserts the password never lands in the daemon's own
transcript log (`canon/doctrine/secrets-and-credentials.md`)."""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from tw2002_aiclient.session import login
from tw2002_aiclient.session.session import Session

from .fake_twgs import FakeTWGS


@contextlib.contextmanager
def _session_against(fake: FakeTWGS, log_dir: Path, *, name: str = "wo-p2-023"):
    """A real `Session` connected to `fake` (already started -- see each
    test's `with fake, _session_against(fake, tmp_path) as session:`
    nesting, which starts the fake server before its `.port` is read
    here). `log_dir` is the CALLER's `tmp_path` -- kept alive by pytest
    past this context's own exit (unlike a self-managed tempfile.mkdtemp
    torn down in this function's own `finally`), so a test's
    post-`with`-block transcript assertion can still read it. Session
    itself is always closed in `finally`."""
    session = Session("127.0.0.1", fake.port, name, str(log_dir))
    session.start(timeout=10)
    try:
        yield session
    finally:
        session.close()


def _assert_password_absent_from_transcript(log_dir: Path, secret: str):
    logs = list(log_dir.glob("session-*.log"))
    assert logs, "expected the session to have written a transcript log"
    for log_path in logs:
        content = log_path.read_text(encoding="utf-8", errors="replace")
        assert secret not in content, f"password leaked into {log_path}"


# -- Accept 1: RETURNING -----------------------------------------------------

def test_returning_login_sends_saved_password_once_and_reaches_main_command(tmp_path):
    handle, game_letter, password = "AEGIS", "F", "sAvEd123Test"
    fake = FakeTWGS(handle=handle, game_letter=game_letter, password=password, mode="returning")

    with fake, _session_against(fake, tmp_path) as session:
        profile = login.LoginProfile(
            name="returning", handle=handle, game_letter=game_letter, allow_register=False
        )
        saved = {"returning": password}
        save_calls = []

        cls, _steps = login.run_login(
            session,
            profile,
            get_password=lambda n: saved.get(n),
            save_password=lambda n, pw: save_calls.append((n, pw)),
        )

    assert not fake.errors, fake.errors
    assert cls == "main_command"
    # Sent exactly once -- the fake's single scripted Password? step plus
    # this direct capture (not just the equality check inside it).
    assert fake.received_passwords == [password]
    # A known-good saved credential is never re-saved.
    assert save_calls == []
    _assert_password_absent_from_transcript(tmp_path, password)


def test_returning_slow_transition_reaches_main_command(tmp_path):
    """Mack HIGH regression guard: a legitimate RETURNING login whose
    server response is slow/two-stage (an early ack that still renders as
    `login_password`, then the real next screen ~0.6s later) must reach
    `main_command`, NEVER raise `returning_password_rejected`. Before the
    fix (`_decide()`'s RETURNING reappearance raising immediately, with no
    settle-grace), this exact shape false-rejected a correct password --
    this test must fail against that old code and pass with the fix (see
    WO-P2-023 report for the before/after run confirming it isn't
    vacuous)."""
    handle, game_letter, password = "AEGIS", "F", "sAvEd123Test"
    fake = FakeTWGS(
        handle=handle,
        game_letter=game_letter,
        password=password,
        mode="returning",
        post_password_delay_s=0.6,
    )

    with fake, _session_against(fake, tmp_path) as session:
        profile = login.LoginProfile(
            name="returning_slow", handle=handle, game_letter=game_letter, allow_register=False
        )
        saved = {"returning_slow": password}

        cls, _steps = login.run_login(
            session, profile, get_password=lambda n: saved.get(n), save_password=lambda n, pw: None
        )

    assert not fake.errors, fake.errors
    assert cls == "main_command"
    # Still sent exactly once -- the transient reappearance never
    # triggers a re-send (see _decide()'s RETURNING branch: it returns
    # `None`, not an action, on that reappearance).
    assert fake.received_passwords == [password]
    _assert_password_absent_from_transcript(tmp_path, password)


# -- Accept 2: NEW registration ----------------------------------------------

def test_new_registration_completes_and_saves_generated_password_before_send(tmp_path):
    handle, game_letter = "AEGIS", "F"
    ship_name, planet_name = "Vantage", "Anchorage"
    fake = FakeTWGS(
        handle=handle,
        game_letter=game_letter,
        password="unused-new-registration-branch",
        mode="new",
        ship_name=ship_name,
        planet_name=planet_name,
    )

    with fake, _session_against(fake, tmp_path) as session:
        profile = login.LoginProfile(
            name="new_reg",
            handle=handle,
            game_letter=game_letter,
            allow_register=True,
            ship_name=ship_name,
            planet_name=planet_name,
        )
        saved = {}
        save_calls = []

        def save_password(name, pw):
            saved[name] = pw
            save_calls.append((name, pw))

        cls, _steps = login.run_login(
            session, profile, get_password=lambda n: saved.get(n), save_password=save_password
        )

    assert not fake.errors, fake.errors  # includes the create/repeat identical-resend check
    assert cls == "main_command"
    assert fake.generated_password is not None
    assert len(fake.generated_password) == 8
    assert fake.generated_password.isalnum()
    # `save_password()` is called exactly once, with the SAME value the
    # server actually received -- login.py's own module docstring: "Saved
    # the moment it's chosen, before the first send -- maximally
    # recoverable even if a later step fails" (login.py:330-336).
    assert save_calls == [("new_reg", fake.generated_password)]
    assert saved["new_reg"] == fake.generated_password
    _assert_password_absent_from_transcript(tmp_path, fake.generated_password)


# -- Accept 3: registration refused ------------------------------------------

def test_registration_refused_raises_before_any_char_create_send(tmp_path):
    handle, game_letter = "SomeoneNew", "F"
    fake = FakeTWGS(
        handle=handle, game_letter=game_letter, password="unused-refused-branch", mode="refused"
    )

    with fake, _session_against(fake, tmp_path) as session:
        profile = login.LoginProfile(
            name="refused", handle=handle, game_letter=game_letter, allow_register=False
        )
        with pytest.raises(login.LoginError, match="registration_not_permitted"):
            login.run_login(
                session, profile, get_password=lambda n: None, save_password=lambda n, pw: None
            )

        # Synchronize on the server's own observation window BEFORE this
        # `with` block's teardown runs (`session.close()` then
        # `fake.stop()`). Skipping this reopens a genuine teardown race
        # (WO-SUITE-PARALLEL-FLAKE, forced repro measured 18/30): `stop()`
        # must forcibly close the connection to wake the OTHER 3 modes'
        # unbounded recv loops, and that same close can race
        # `_expect_silence`'s own bounded recv if it is still in flight --
        # see `FakeTWGS.wait_for_silence_check`'s docstring for the
        # measured failure mode this closes.
        assert fake.wait_for_silence_check(timeout=5.0), (
            "FakeTWGS never finished observing post-char_create silence"
        )

    assert not fake.errors, fake.errors
    # Not even the "Y" -- the automaton's allow_register guard raises
    # before returning any action at all (see login.py's char_create
    # branch: the LoginError is raised in place of a send tuple).
    assert fake.received_after_char_create is False


# -- Accept 4: wrong saved password -------------------------------------------

def test_wrong_saved_password_fails_fast_never_reaches_main_command(tmp_path):
    handle, game_letter = "AEGIS", "F"
    wrong_password = "totallyWrongSavedPw1"
    fake = FakeTWGS(
        handle=handle, game_letter=game_letter, password="the-real-password-unused-here", mode="wrong_password"
    )

    with fake, _session_against(fake, tmp_path) as session:
        profile = login.LoginProfile(
            name="wrong_pw", handle=handle, game_letter=game_letter, allow_register=False
        )
        with pytest.raises(login.LoginError, match="returning_password_rejected"):
            login.run_login(
                session, profile, get_password=lambda n: wrong_password, save_password=lambda n, pw: None
            )

    assert not fake.errors, fake.errors
    # Canon (login-automaton.md): RETURNING sends a saved password EXACTLY
    # ONCE -- a rejection fails loud immediately rather than re-sending the
    # same already-known-bad value up to a retry ceiling (server-lockout
    # risk). Never 6 (the old _MAX_PASSWORD_RETRIES-bounded behavior).
    assert fake.received_passwords == [wrong_password]
    _assert_password_absent_from_transcript(tmp_path, wrong_password)
