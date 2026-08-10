"""WO-ARM-HISTORY-RING -- an armed run's sends appear in the session history ring.

The gap this closes was **structural, not a missing row**. Before this WO
`record_history` had exactly two call sites in the whole product tree -- the
`do` and `read` verbs in `session/protocol.py` -- and an armed run reaches
neither: it travels player -> `_ReplayPort.send_and_confirm` -> `settle` ->
`session.send`. So the ring was not incomplete for autopilot sends; it had
never been reachable from the autopilot at all.

Why that matters is narrower than "logging is good". Every other send in this
app happens because a human pressed a key, so the operator's own memory is the
record. An armed run is the first path where the app sends **without a
keystroke behind each send**, which makes it the only path where "what did it
do on my behalf" has no answer outside the app's own say-so. The #224 live
proof stood on the CLI's own `armed — running` banner: a single-source oracle,
adequate as launch evidence and inadequate as an audit trail.

`test_no_run_files_no_rows` is the control that keeps the rest of this file
honest -- without it, rows appearing after a run is equally consistent with
"the port files them" and "something else in the harness files everything".
"""

from __future__ import annotations

import threading

import pytest

from tw2002_aiclient.loops.player import OUTCOME_COMPLETED
from tw2002_aiclient.session import autoloop, protocol
from tw2002_aiclient.session.autoloop import HISTORY_VERB_AUTOLOOP
from tw2002_aiclient.session.control_lock import ControlLock

from .test_autoloop import (
    ONE_STEP,
    TWO_STEPS,
    WireSession,
    make_runner,
    run_to_completion,
    write_macro,
)
from .test_loop_player import ANCHOR_158, PORT


def _rows(session, verb=HISTORY_VERB_AUTOLOOP):
    return [e for e in session.history if e["verb"] == verb]


def _inputs(session):
    return [e["args"]["input"] for e in _rows(session)]


# ---------------------------------------------------------------------------
# The control -- without this, every assertion below is ambiguous
# ---------------------------------------------------------------------------


def test_no_run_files_no_rows(tmp_path):
    """A session that never armed has an empty ring.

    Cheap, and it is what makes the rest of the file mean anything: rows
    appearing after a run is equally consistent with "the port filed them" and
    "this harness files a row for everything it does".
    """
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0]])
    assert session.history == []
    assert _rows(session) == []


# ---------------------------------------------------------------------------
# Accept 1 -- the sends land in the ring
# ---------------------------------------------------------------------------


def test_an_armed_run_files_every_send_it_made(tmp_path):
    """Accept 1, asserted off the ring rather than off the CLI banner."""
    write_macro(tmp_path, "ore-run", TWO_STEPS)
    session = WireSession([ANCHOR_158[0], PORT[0], ANCHOR_158[0]])
    runner = make_runner(tmp_path, session)

    runner.start("ore-run")
    snapshot = run_to_completion(runner, session)

    assert snapshot.report.outcome == OUTCOME_COMPLETED
    assert _inputs(session) == ["P", "1"], "the ring does not hold what the player sent"


def test_the_ledger_is_complete_not_merely_non_empty(tmp_path):
    """Row count must equal the run's own `sends_issued`.

    Two independent counters: the player increments `sends_issued`, the port
    files rows. A ledger holding *some* of the sends is worse than an obviously
    empty one -- it looks like a record while under-reporting what was spent.
    """
    write_macro(tmp_path, "ore-run", TWO_STEPS)
    session = WireSession([ANCHOR_158[0], PORT[0], ANCHOR_158[0]])
    runner = make_runner(tmp_path, session)

    runner.start("ore-run")
    snapshot = run_to_completion(runner, session)

    assert len(_rows(session)) == snapshot.report.sends_issued == 2


def test_the_row_carries_what_was_sent_and_how_it_settled(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0], ANCHOR_158[0]])
    runner = make_runner(tmp_path, session)

    runner.start("ore-run")
    run_to_completion(runner, session)

    row = _rows(session)[0]
    assert row["args"]["input"] == "P"
    assert "wait_prompt" in row["args"]
    assert row["settled_reason"] is not None, "a row with no outcome is half a record"
    assert row["ts"]


def test_a_send_that_never_confirmed_is_still_filed(tmp_path):
    """The row a post-mortem most wants is the one from the step that failed.

    `_record` runs after the settle **unconditionally**, and this is the pin
    for that word -- the docstring claimed it before this test existed, which
    is a claim rather than a guarantee. Recording only confirmed sends would
    build a ledger that is most incomplete exactly when it matters: the turns
    were spent either way, and "we sent P and it never confirmed" is the whole
    story of a bad run.
    """
    write_macro(tmp_path, "ore-run", [("P", "NEVER-MATCHES-THIS-PROMPT", "main_command")])
    session = WireSession([ANCHOR_158[0], ANCHOR_158[0]])
    runner = make_runner(tmp_path, session)

    runner.start("ore-run")
    snapshot = run_to_completion(runner, session)

    assert snapshot.report.outcome != OUTCOME_COMPLETED, "this fixture was meant to fail"
    assert _inputs(session) == ["P"], "the failed step left no trace in the ledger"


# ---------------------------------------------------------------------------
# The autopilot rows must be distinguishable from the operator's own
# ---------------------------------------------------------------------------


def test_an_autopilot_send_is_not_filed_as_a_do(tmp_path):
    """The single most important thing the ring must convey is **who sent it**.

    `sender` on the session cannot draw this line -- a `do` is already
    `sender="app"` -- so if autopilot sends were filed under `"do"` the ledger
    would be technically complete and practically useless: the rows a
    post-mortem is looking for would be indistinguishable from the ones it is
    not.
    """
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0], ANCHOR_158[0]])
    runner = make_runner(tmp_path, session)

    runner.start("ore-run")
    run_to_completion(runner, session)

    assert _rows(session, "do") == [], "an armed send was filed as an operator `do`"
    assert len(_rows(session)) == 1
    assert HISTORY_VERB_AUTOLOOP != "do"


# ---------------------------------------------------------------------------
# Accept 2 -- the human path is untouched
# ---------------------------------------------------------------------------


class _Server:
    def __init__(self, session, lock):
        self.session = session
        self.control_lock = lock


def test_the_operator_do_verb_still_files_exactly_one_do_row(tmp_path):
    """Accept 2 regression. The human path must be byte-identical, and the
    risk here is *extra* rows, not missing ones -- a change that filed at the
    session level would double-record every `do`."""
    session = WireSession([ANCHOR_158[0], ANCHOR_158[0]])
    lock = ControlLock()

    protocol.dispatch(session, "do", {"input": "P"}, _Server(session, lock))

    assert len(_rows(session, "do")) == 1
    assert _rows(session) == [], "the operator's own send was filed as autopilot"


def test_a_read_still_files_a_read_row(tmp_path):
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()

    protocol.dispatch(session, "read", {}, _Server(session, lock))

    assert len(_rows(session, "read")) == 1
    assert _rows(session) == []


# ---------------------------------------------------------------------------
# `_record` itself -- the failure directions, unit-tested
# ---------------------------------------------------------------------------


class _RecordingDouble:
    """Minimal session: records history, renders one screen."""

    def __init__(self, render_error=None, record_error=None):
        self.history = []
        self._render_error = render_error
        self._record_error = record_error

    def render(self):
        if self._render_error is not None:
            raise self._render_error
        return ["Command [TL=00:00:00]:[1] (?=Help)? :"]

    def record_history(self, verb, args, prompt, classification, settled_reason):
        if self._record_error is not None:
            raise self._record_error
        self.history.append(
            {
                "verb": verb,
                "args": args,
                "prompt": prompt,
                "classification": classification,
                "settled_reason": settled_reason,
            }
        )


def _port(session):
    return autoloop._ReplayPort(session, ControlLock(), threading.Event())


def test_a_send_is_never_dropped_because_the_screen_could_not_be_read():
    """A failed render costs the prompt field, never the row.

    The first draft wrapped the render and the record in one `except: pass`,
    which would have dropped the whole row on a render hiccup -- losing the
    evidence that a send happened at all, which is the one fact this ledger
    exists to carry.
    """
    session = _RecordingDouble(render_error=OSError("wire gone"))
    _port(session)._record("P", None, "idle")

    assert len(session.history) == 1, "the send vanished from the ledger with the screen"
    assert session.history[0]["args"]["input"] == "P"
    assert session.history[0]["prompt"] == ""


def test_a_broken_ring_is_loud_not_silent():
    """`record_history` failing is NOT swallowed.

    It appends a dict to a list and has no realistic failure mode, so catching
    it would buy nothing and cost everything: a ring that silently stopped
    recording on the one path that needs it is exactly the loss this WO closes.
    Contrast the render above, which touches live wire state mid-run.
    """
    session = _RecordingDouble(record_error=RuntimeError("ring broken"))
    with pytest.raises(RuntimeError):
        _port(session)._record("P", None, "idle")


def test_the_prompt_recorded_is_the_screen_behind_the_send():
    session = _RecordingDouble()
    _port(session)._record("P", "Command", "idle")

    row = session.history[0]
    assert row["prompt"] == "Command [TL=00:00:00]:[1] (?=Help)? :"
    assert row["args"] == {"input": "P", "wait_prompt": "Command"}


def test_classification_is_left_absent_rather_than_guessed():
    """Not laziness: this layer does not classify, the player does, from its
    own `screen()`. Classifying here would describe a *different* render than
    the one the player decided on -- the race `screen()` exists to close. An
    empty field is honest; a second opinion taken at another instant and filed
    as if it described this one is worse than none."""
    session = _RecordingDouble()
    _port(session)._record("P", None, "idle")

    assert session.history[0]["classification"] is None


# ---------------------------------------------------------------------------
# Accept 3 -- secrets. A tripwire, deliberately, not a redaction branch
# ---------------------------------------------------------------------------


def test_the_replay_port_never_sends_a_secret():
    """The reason there is no redaction branch in `_record`.

    `settle.send_and_confirm` / `send_and_confirm_for` *do* take a `secret`
    parameter, and the port does not pass it, so a taught-macro step can never
    be a secret send today. A redaction branch here would therefore be
    unreachable code that reads as a live guard -- and an unreachable guard on
    a secrets path is worse than none, because it answers "is this handled?"
    with a yes nobody can falsify.

    This is the tripwire instead: route a secret through the player and this
    goes red, and whoever did it has to handle redaction deliberately rather
    than discover it in a log.
    """
    import ast
    import inspect

    source = inspect.getsource(autoloop._ReplayPort.send_and_confirm)
    # Port now routes through send_and_confirm_for(..., profile=...); still must
    # not pass secret= (defaults False inside settle).
    call = next(
        n for n in ast.walk(ast.parse(source.strip()))
        if isinstance(n, ast.Call)
        and getattr(n.func, "attr", None) == "send_and_confirm_for"
    )
    passed = {kw.arg for kw in call.keywords}
    assert "secret" not in passed, (
        "the replay port now passes `secret` -- `_record` needs a redaction branch"
    )
    assert "profile" in passed, "replay port must name a settle profile"

    from tw2002_aiclient.session import settle as settle_mod

    assert inspect.signature(settle_mod.send_and_confirm).parameters["secret"].default is False
    assert inspect.signature(settle_mod.send_and_confirm_for).parameters["secret"].default is False


def test_that_tripwire_can_actually_fire():
    """Control: the extractor finds a `secret` kwarg when one is present."""
    import ast

    tree = ast.parse(
        "x = _settle.send_and_confirm_for(s, k, profile='stable_idle', secret=True)"
    )
    call = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and getattr(n.func, "attr", None) == "send_and_confirm_for"
    )
    assert "secret" in {kw.arg for kw in call.keywords}


# ---------------------------------------------------------------------------
# The structural claim: the ring is now reachable from the autopilot
# ---------------------------------------------------------------------------


def test_record_history_is_reachable_from_the_autoloop_path():
    """The gap was that `record_history` had no call site the player could
    reach. Pinned structurally so a refactor that moves the call out of the
    port fails here rather than in a post-mortem months later."""
    import ast
    import inspect

    source = inspect.getsource(autoloop._ReplayPort)
    names = {
        getattr(n.func, "attr", None)
        for n in ast.walk(ast.parse(source.strip()))
        if isinstance(n, ast.Call)
    }
    assert "record_history" in names
