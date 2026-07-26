"""Blank-name-rejection fallback at the outer login gate (WO-MICRO-LOGIN-
BLANK-REJECT). Drives the REAL `login.run_login()`
(`tw2002_aiclient/session/login.py`) against a REAL `Session`
(`tw2002_aiclient/session/session.py`), over a REAL (loopback) TCP
connection, through `tests/fake_twgs.py`'s `outer_name_reject_times`/
`outer_name_reject_then_silent` knobs -- same no-mocked-session discipline
as `test_login.py`/`test_login_resume.py`.

**The captured evidence this WO exists for** (`audit/micro-unknown-step6-
corpus-20260726.md`, from the live-ensure diagnosis against
`twgs.microblaster.net`): the outer gate prints `"Please enter your name
(ENTER for none):"`. The pre-fix automaton always answers blank (canon-
correct), but this particular host rejects it with `"A login name is
required."`, re-prompting three times, then goes completely silent on the
fourth rejection -- no re-prompt at all. `classify_screen` then sees only
the rejection line, matches nothing -> `unknown` -> three stagnant rounds ->
`automaton_stuck:classification='unknown':step=6`.

Three tests:

  1. `test_corpus_repeated_rejection_ends_named_and_bounded_not_unknown` --
     the RED-FIRST reproduction of the exact corpus shape (prompt, "A login
     name is required." x3 [each with a re-prompt], then silence). Run
     against the pre-fix automaton this fails as `LoginStalled`,
     `classification='unknown'` -- the corpus bug, reproduced rather than
     assumed. Against the fix it instead raises a NAMED, bounded
     `login_name_rejected` after exactly two sends (the canon-correct
     blank, then ONE retry with the profile's handle) -- it never even
     reaches the fake's silent branch, because the bounded retry gives up
     before a third guess.
  2. `test_outer_name_handle_retry_succeeds_after_one_blank_rejection` --
     the happy path the fix exists for: a host that rejects only the
     blank (not a real name) reaches `main_command` once the automaton
     retries with the handle.
  3. `test_genuinely_unrecognized_screen_still_raises_automaton_stuck` --
     the stop-on-unknown pin (WO constraint): a screen that never
     classifies `login_name` at all, and so never touches the new branch,
     must still hit the EXISTING, unchanged stop-on-unknown path.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from tw2002_aiclient.session import login
from tw2002_aiclient.session.session import Session

from .fake_twgs import FakeTWGS
from .test_login_redaction import _ScriptedTWGS
from .test_login_redaction import _session_against as _bare_session_against


@contextlib.contextmanager
def _session_against(fake: FakeTWGS, log_dir: Path, *, name: str = "wo-micro-blank-reject"):
    """Same shape as `test_login.py`'s own helper -- see that module's
    docstring for the `tmp_path`-outlives-the-`with`-block rationale."""
    session = Session("127.0.0.1", fake.port, name, str(log_dir))
    session.start(timeout=10)
    try:
        yield session
    finally:
        session.close()


# -- 1: the corpus shape, red-first -------------------------------------


def test_corpus_repeated_rejection_ends_named_and_bounded_not_unknown(tmp_path, monkeypatch):
    """Mirrors `audit/micro-unknown-step6-corpus-20260726.md` exactly:
    prompt, "A login name is required." x3 (each re-prompting), then total
    silence on what would be the fourth reply. Fails against the pre-fix
    automaton as `LoginStalled`/`classification='unknown'` (the corpus bug,
    reproduced live: `automaton_stuck:classification='unknown':step=8`) --
    run this test against the unmodified `login.py` first and confirm that
    failure text before trusting the fix.

    Against the fix: the bounded retry (canon-correct blank, then ONE
    retry with the profile's handle) means the automaton never reaches the
    fake's silent branch at all -- it gives up after the SECOND rejection
    (having sent exactly two things total) with a specific, named
    `login_name_rejected` error instead of the generic unknown/
    automaton_stuck shape. That is itself the "bounded" proof: a host that
    keeps refusing everything cannot make this loop, or even reach the
    corpus's own silent fourth round.

    `_STEP_SETTLE_TIMEOUT_S` is shortened as a CI-speed hygiene measure
    only, not because the fix's own path depends on it: the fix raises
    directly from `_decide()` without ever touching the stagnant-rounds
    wait, so this only matters if a future regression falls back through
    the slow unknown/automaton_stuck path this test used to take (and did,
    pre-fix, at the default budget -- ~36s for 3 stagnant rounds)."""
    monkeypatch.setattr(login, "_STEP_SETTLE_TIMEOUT_S", 1.0)
    handle, game_letter, password = "AEGIS", "F", "sAvEd123Test"
    fake = FakeTWGS(
        handle=handle,
        game_letter=game_letter,
        password=password,
        mode="returning",
        outer_name_reject_times=4,
        outer_name_reject_then_silent=True,
    )

    with fake, _session_against(fake, tmp_path) as session:
        profile = login.LoginProfile(
            name="corpus_reject", handle=handle, game_letter=game_letter, allow_register=False
        )
        with pytest.raises(login.LoginError, match="login_name_rejected") as excinfo:
            login.run_login(
                session, profile, get_password=lambda n: None, save_password=lambda n, pw: None
            )

    assert not fake.errors, fake.errors
    assert "login_name_rejected" in str(excinfo.value)
    # Bounded: the canon-correct blank, then exactly ONE retry with the
    # handle -- never a third guess, and the corpus's own silent-fourth-
    # round shape is never reached at all.
    assert fake.received_inputs["outer_name"] == ["", handle]


# -- 2: the happy path the fix exists for ---------------------------------


def test_outer_name_handle_retry_succeeds_after_one_blank_rejection(tmp_path):
    """A host that rejects only the blank (advertises "(ENTER for none)"
    and then refuses it) is exactly the shape the WO's fallback targets:
    once the automaton retries with the profile's own handle, the host
    accepts it and the rest of the login proceeds completely normally."""
    handle, game_letter, password = "AEGIS", "F", "sAvEd123Test"
    fake = FakeTWGS(
        handle=handle,
        game_letter=game_letter,
        password=password,
        mode="returning",
        outer_name_reject_times=1,
    )

    with fake, _session_against(fake, tmp_path) as session:
        profile = login.LoginProfile(
            name="reject_once", handle=handle, game_letter=game_letter, allow_register=False
        )
        cls, _steps = login.run_login(
            session, profile, get_password=lambda n: password, save_password=lambda n, pw: None
        )

    assert not fake.errors, fake.errors
    assert cls == "main_command"
    # The load-bearing assertion: the SECOND send at this gate was the
    # profile's handle, not another blank -- a pre-fix automaton would send
    # "" again here (FakeTWGS's own reply validation would have flagged
    # that mismatch on `.errors`, asserted clean above).
    assert fake.received_inputs["outer_name"] == ["", handle]
    assert fake.received_passwords == [password]


# -- 3: stop-on-unknown pin ------------------------------------------------


def test_genuinely_unrecognized_screen_still_raises_automaton_stuck(tmp_path, monkeypatch):
    """Stop-on-unknown pin (WO constraint): a screen that is not the outer
    login_name gate at all -- never matches `_OUTER_NAME_PROMPT_RE`, never
    touches the new rejection branch -- must still hit the EXISTING,
    unchanged stop-on-unknown path. The new bounded retry only ever fires
    from inside `login.py`'s `login_name` dispatch; this is the regression
    guard that it doesn't widen what counts as progress for anything else.
    `_STEP_SETTLE_TIMEOUT_S` is shortened because a silent server means
    each stagnation round waits out the full settle budget."""
    monkeypatch.setattr(login, "_STEP_SETTLE_TIMEOUT_S", 0.3)
    script = [("Some unrecognized greeting the automaton has no anchor for at all ###", False)]

    with _ScriptedTWGS(script) as server, _bare_session_against(server.port, tmp_path) as session:
        profile = login.LoginProfile(name="unrelated_unknown", handle="AEGIS", game_letter="F")
        with pytest.raises(login.LoginStalled) as excinfo:
            login.run_login(
                session, profile, get_password=lambda n: None, save_password=lambda n, pw: None
            )

    assert not server.errors, server.errors
    assert "automaton_stuck" in str(excinfo.value)
    assert "classification='unknown'" in str(excinfo.value)
