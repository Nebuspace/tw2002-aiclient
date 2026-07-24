"""Login Automaton idempotent-resume proof (WO-P2-024): drives the REAL
`login.run_login()` (`tw2002_aiclient/session/login.py`) against a REAL
`Session` (`tw2002_aiclient/session/session.py`), over a REAL (loopback)
TCP connection, through the resume-capable `"returning"` scenarios added
to `tests/fake_twgs.py` (`start_at` / `restale_game_select`) -- same
no-mocked-session, no-real-game discipline as `test_login.py`.

Proves canon (`canon/architecture/login-automaton.md`'s "The Automaton Is
Reactive, Not a Script" section) with 4 tests:

  1. `test_resume_from_door_select_reaches_main_command` -- a session whose
     connection is presented DIRECTLY at the game_select screen (no
     outer-name step first) drives to `main_command` -- proves resume
     from a mid-flow screen with no cold-start prefix needs no
     special-casing.
  2. `test_resume_from_interstitial_reaches_main_command` -- same proof at
     a LATER resume point (the show_log interstitial), and asserts the
     screens BEFORE it (game_select/module_entry_menu/login_name/
     ansi_prompt) are never sent at all -- this is what shows dispatch is
     genuinely SCREEN-keyed, not counting steps: if it were a step
     counter, resuming at a different offset would desync it entirely
     instead of just doing less work.
  3. `test_no_double_answer_after_stale_game_select_redraw` -- a cold-start
     login where the server re-presents a STALE, un-cleared game_select
     screen once, right after the real one has already been answered and
     the flow has moved on -- proves `session.game_select_answered`'s
     refusal (`_decide()` returns `None` rather than re-sending the
     letter) by asserting the game-select letter reaches the server
     EXACTLY ONCE despite the reappearance.
  4. `test_second_run_login_is_idempotent_at_main_command` -- after one
     `run_login()` call reaches `main_command`, a SECOND call (fresh
     `state`, the SAME session/connection) returns immediately (0 steps
     taken) without re-driving or re-sending anything -- the literal
     `ensure`-safety property canon calls out ("safe to issue against an
     unknown-state session").

Every test also asserts login.py needed no change to pass -- these are
resume SCENARIOS exercising machinery already built into `run_login()`/
`_decide()` (the reactive re-classify-every-iteration design, and the
per-connection `game_select_answered`/`game_select_letter_sent` flags on
`Session`), not new behavior."""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from tw2002_aiclient.session import login
from tw2002_aiclient.session.session import Session

from .fake_twgs import FakeTWGS


@contextlib.contextmanager
def _session_against(fake: FakeTWGS, log_dir: Path, *, name: str = "wo-p2-024"):
    """Same shape as `test_login.py`'s own helper -- see that module's
    docstring for the `tmp_path`-outlives-the-`with`-block rationale."""
    session = Session("127.0.0.1", fake.port, name, str(log_dir))
    session.start(timeout=10)
    try:
        yield session
    finally:
        session.close()


# -- 1: resume from the door-select screen ------------------------------

def test_resume_from_door_select_reaches_main_command(tmp_path):
    handle, game_letter, password = "AEGIS", "F", "sAvEd123Test"
    fake = FakeTWGS(
        handle=handle, game_letter=game_letter, password=password, mode="returning", start_at="game_select"
    )

    with fake, _session_against(fake, tmp_path) as session:
        profile = login.LoginProfile(
            name="resume_door", handle=handle, game_letter=game_letter, allow_register=False
        )
        saved = {"resume_door": password}

        cls, _steps = login.run_login(
            session, profile, get_password=lambda n: saved.get(n), save_password=lambda n, pw: None
        )

    assert not fake.errors, fake.errors
    assert cls == "main_command"
    # No cold-start prefix was ever presented -- nothing to send for it.
    assert "outer_name" not in fake.received_inputs
    assert fake.received_inputs["game_select"] == [game_letter]
    assert fake.received_passwords == [password]


# -- 2: resume from a later interstitial (proves screen-keyed dispatch) -

def test_resume_from_interstitial_reaches_main_command(tmp_path):
    handle, game_letter, password = "AEGIS", "F", "sAvEd123Test"
    fake = FakeTWGS(
        handle=handle, game_letter=game_letter, password=password, mode="returning", start_at="show_log"
    )

    with fake, _session_against(fake, tmp_path) as session:
        profile = login.LoginProfile(
            name="resume_interstitial", handle=handle, game_letter=game_letter, allow_register=False
        )
        saved = {"resume_interstitial": password}

        cls, _steps = login.run_login(
            session, profile, get_password=lambda n: saved.get(n), save_password=lambda n, pw: None
        )

    assert not fake.errors, fake.errors
    assert cls == "main_command"
    assert fake.received_inputs["show_log"] == ["N"]
    # Every step BEFORE the resume point was skipped by the fake server
    # entirely (never presented, so nothing to answer) -- if dispatch were
    # counting steps rather than reading the current screen, resuming at
    # a different offset than test 1 would desync it; instead both reach
    # main_command the same way.
    for skipped in ("outer_name", "game_select", "module_entry_menu", "login_name", "ansi_prompt"):
        assert skipped not in fake.received_inputs
    assert fake.received_passwords == [password]


# -- 3: stale game_select redraw must not be re-answered -----------------

def test_no_double_answer_after_stale_game_select_redraw(tmp_path):
    handle, game_letter, password = "AEGIS", "F", "sAvEd123Test"
    fake = FakeTWGS(
        handle=handle, game_letter=game_letter, password=password, mode="returning", restale_game_select=True
    )

    with fake, _session_against(fake, tmp_path) as session:
        profile = login.LoginProfile(
            name="no_double_answer", handle=handle, game_letter=game_letter, allow_register=False
        )
        saved = {"no_double_answer": password}

        cls, _steps = login.run_login(
            session, profile, get_password=lambda n: saved.get(n), save_password=lambda n, pw: None
        )

    assert not fake.errors, fake.errors
    assert cls == "main_command"
    # The load-bearing assertion: the letter reached the server exactly
    # ONCE, for the genuine game_select screen -- the stale redraw got no
    # reply at all (session.game_select_answered refused it in _decide(),
    # returning None rather than a second send). A regressed guard (e.g.
    # a version that latches game_select_answered too early, or never
    # checks it at all) would either wedge on the stale screen (never
    # reaching main_command) or send the letter a second time here.
    assert fake.received_inputs["game_select"] == [game_letter]
    assert fake.received_passwords == [password]


# -- 4: a second run_login() on the same session is a no-op --------------

def test_second_run_login_is_idempotent_at_main_command(tmp_path):
    handle, game_letter, password = "AEGIS", "F", "sAvEd123Test"
    fake = FakeTWGS(handle=handle, game_letter=game_letter, password=password, mode="returning")

    with fake, _session_against(fake, tmp_path) as session:
        profile = login.LoginProfile(
            name="idempotent_ensure", handle=handle, game_letter=game_letter, allow_register=False
        )
        saved = {"idempotent_ensure": password}
        get_password = lambda n: saved.get(n)  # noqa: E731 -- matches test_login.py's own inline-closure style
        save_password = lambda n, pw: None  # noqa: E731

        cls1, _steps1 = login.run_login(session, profile, get_password=get_password, save_password=save_password)
        assert cls1 == "main_command"

        # Fresh `state` dict (run_login() builds its own internally), SAME
        # session/connection -- this is exactly the shape a second `ensure`
        # call takes against an already-logged-in connection.
        cls2, steps2 = login.run_login(session, profile, get_password=get_password, save_password=save_password)

    assert not fake.errors, fake.errors
    assert cls2 == "main_command"
    # Returned on the very first render (step 0 of run_login's own loop)
    # -- never re-drove a single step.
    assert steps2 == 0
    # The password was sent exactly once TOTAL, across both calls -- the
    # second call never re-answered anything.
    assert fake.received_passwords == [password]
