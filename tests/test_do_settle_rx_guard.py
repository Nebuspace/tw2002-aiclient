"""The `do` verb's post-send settle, against a REAL rendered screen
(WO-DO-SETTLE-RX-GUARD).

`do` is how the App drives the game: send, then wait for the screen to
settle, then hand the caller a `settled_reason` the rest of the system
treats as evidence the command landed. `settled_reason == "prompt"` is
documented as the STRONGEST of the three (canon:
architecture/settle-detection.md -- "the screen is not merely quiet, it is
quiet *on a specific, named shape* the caller was waiting for").

The hole this module exists for: `wait_for_settle`'s prompt branch had no
freshness clause, while its idle branch has carried one from the start
("no new bytes for the debounce window, **and** at least one byte has
arrived since the send"). So a `wait_prompt` that was ALREADY satisfied by
the pre-send screen returned `("prompt", 0.0)` before the game had
responded at all -- and the single most common `do` in this product is
exactly that shape: issued from `Command [TL=` and waiting for
`Command \\[TL=`, which is canon's own worked `tw do` example
(architecture/session-engine.md:196). The App would then believe a command
landed while the screen had not changed, which is precisely the state the
whole escalate-on-unknown safety case is built to make impossible.

**This is NOT the `match_scope` question** (`tests/test_settle_real_screen.py`,
canon ruling open). That one is about WHERE a regex is searched -- whole
grid vs. current prompt line. An awaited prompt that equals the pre-send
prompt matches immediately under BOTH scopes, because it is genuinely on
the current prompt line; only a freshness guard can reject it. The two
defects are orthogonal and neither fix substitutes for the other. See
`test_do_accepts_a_single_echoed_byte_as_new_bytes` below for the seam
where they meet.

**Why a real `Session`.** A fake whose `render_text()` returns a canned
string has no grid, no rows and no byte timeline, so it cannot tell
"settled on the screen the send produced" from "settled on the screen that
was already there" -- which is how this class of defect survives a green
suite. The harness here is the one
`tests/test_settle_real_screen.py` established and is imported from it
rather than re-declared, so both modules move together if the way bytes
reach the terminal ever changes: production `Session`, production pyte
`TerminalScreen`, production `render_cropped()`/`render_text()`, with only
the `clock()`/`sleep()` settle-protocol seams and the socket virtualised.
Requests go through the production `protocol.dispatch()` -- nothing about
the `do` path is stubbed.

**Why these fixtures are real.** `tests/fixtures/port_trade_screen.txt` is
a captured docking at an unprofitable port: the port is buying all three
commodities, the ship holds none of them, so the game prints "You don't
have anything they want..." and drops straight back to `Command [TL=`
without ever showing a port menu. Re-issuing `P` in that sector is
therefore a genuine round trip that starts AND ends on `Command [TL=` --
the equal-prompt case, taken from real captured output rather than
invented. The response below is that same flow one step on (no
first-visit-only docking-log/promotion block, turn counter decremented by
one), the same convention `test_settle_real_screen.py` uses for its own
`_PORT_REDRAW`.
"""

import re
import time
from pathlib import Path

import pytest

from tw2002_aiclient.session import protocol
from tw2002_aiclient.session.connection import TelnetConnection
from tw2002_aiclient.session.session import Session
from tw2002_aiclient.session.settle import wait_for_settle

from .conftest import FAKE_HOST, FAKE_PORT
from .test_settle_real_screen import _LEAVE_PORT, _PORT_REDRAW, RealScreenSession, _wire

_FIXTURES = Path(__file__).parent / "fixtures"

# Canon's own worked `tw do` example (architecture/session-engine.md:196),
# and the awaited shape that is already on screen before the send.
COMMAND_PROMPT_RE = r"Command \[TL="

# The one-turn-later marker that proves the response actually landed. It
# cannot be confused with the pre-send screen, which reads 29990.
_RESPONSE_MARKER = "29989 turns left"
_PRE_SEND_MARKER = "29990 turns left"

# What re-issuing `P` in this sector actually paints, ending back on a new
# `Command [TL=` prompt (see the module docstring for the derivation).
_REDOCK = (
    "P\n"
    "<Port>\n"
    "\n"
    "Docking...\n"
    "One turn deducted, 29989 turns left.\n"
    "\n"
    "Commerce report for Adipocere Primus: 10:56:02 PM Sat Jul 18, 2054\n"
    "\n"
    " Items     Status  Trading % of max OnBoard\n"
    " -----     ------  ------- -------- -------\n"
    "Fuel Ore   Buying    2650    100%       0\n"
    "Organics   Buying    2970    100%       0\n"
    "Equipment  Buying    1220    100%       0\n"
    "\n"
    "You don't have anything they want, and they don't have anything you can buy.\n"
    "\n"
    "You have 100,000 credits and 50 empty cargo holds.\n"
    "\n"
)
_NEW_COMMAND_PROMPT = "Command [TL=00:00:00]:[21068] (?=Help)? : "


class _NoLockServer:
    """`protocol.dispatch`'s `server` with no `control_lock` -- the bare
    harness shape `_driving_dispatch` documents as unrestricted, same as
    `tests/test_cli_ops_verb_b.py`'s own FakeServer."""


@pytest.fixture
def command_prompt_session(tmp_path, monkeypatch):
    """A session whose real pyte grid is sitting at `Command [TL=` -- the
    ordinary state the App issues nearly every `do` from. Socket writes
    are captured instead of sent (so a "did this verb put bytes on the
    wire?" question has a real answer); everything above the socket is
    production code."""
    wire_writes = []
    monkeypatch.setattr(
        TelnetConnection,
        "send_text",
        lambda self, text, enter=True, secret=False: wire_writes.append((text, enter, secret)),
    )
    session = RealScreenSession(tmp_path)
    session.wire_writes = wire_writes

    rows = [line.rstrip() for line in (_FIXTURES / "port_trade_screen.txt").read_text().splitlines()]
    # Replay the capture: completed lines, then its live prompt row with
    # the cursor still parked on it (no trailing newline).
    session.feed_now(_wire("\n".join(rows[:-1]) + "\n"))
    session.feed_now(_wire(rows[-1] + " "))

    # Preconditions, asserted rather than assumed: the shape the caller is
    # about to wait for is ALREADY satisfied by the current screen -- on
    # the current prompt line, not merely somewhere up the grid, so no
    # `match_scope` choice can distinguish it -- and the response has
    # plainly not arrived.
    assert re.search(COMMAND_PROMPT_RE, session.render_text())
    assert re.search(COMMAND_PROMPT_RE, session.current_prompt_line())
    assert _PRE_SEND_MARKER in session.render_text()
    assert _RESPONSE_MARKER not in session.render_text()
    return session


def _schedule_the_response(session, at):
    """The screen `P` actually produces, arriving after a realistic
    round trip rather than instantly."""
    session.schedule(at, _wire(_REDOCK))
    session.schedule(at, _wire(_NEW_COMMAND_PROMPT))


# -- the defect ------------------------------------------------------------


def test_do_never_settles_on_the_prompt_that_was_already_there(command_prompt_session):
    """The headline: `do` sends `P` and waits for `Command \\[TL=` from a
    screen that is ALREADY showing `Command [TL=`. The settle must not
    resolve until the game has actually said something -- otherwise the
    App is handed `settled_reason: prompt`, the strongest confirmation the
    system has, over a screen that never changed.
    """
    session = command_prompt_session
    _schedule_the_response(session, at=0.8)

    resp = protocol.dispatch(
        session,
        "do",
        {"input": "P", "wait_prompt": COMMAND_PROMPT_RE, "timeout": 8.0},
        _NoLockServer(),
    )

    assert resp["ok"] is True
    assert resp["settled_reason"] == "prompt"
    # Not before the game responded...
    assert resp["elapsed"] >= 0.8
    # ...and not dawdling to the budget either once it had.
    assert resp["elapsed"] < 1.0
    # The screen the caller was handed is the one the send produced.
    screen = "\n".join(resp["screen"])
    assert _RESPONSE_MARKER in screen
    assert re.search(COMMAND_PROMPT_RE, resp["prompt"])


def test_do_reports_timeout_not_prompt_when_the_game_says_nothing(command_prompt_session):
    """Same equal-prompt shape, but the game never answers. The honest
    result is the bounded-failure one (`timeout`), never a `prompt`
    asserted over a screen nothing happened to.

    This is also the anti-hang proof. Simulated time advances ONLY inside
    `session.sleep()`, so a settle loop that spun without sleeping could
    never reach its own deadline and this test would hang rather than
    fail: the fact that it returns at all is the evidence that the guard
    polls and the timeout still governs. The bound is checked too -- it
    returns AT the budget, not some multiple of it.
    """
    session = command_prompt_session  # nothing scheduled: the screen just sits there

    resp = protocol.dispatch(
        session,
        "do",
        {"input": "P", "wait_prompt": COMMAND_PROMPT_RE, "timeout": 0.5},
        _NoLockServer(),
    )

    assert resp["settled_reason"] == "timeout"
    assert 0.5 <= resp["elapsed"] < 0.6
    assert _RESPONSE_MARKER not in "\n".join(resp["screen"])


def test_do_returns_on_real_wall_clock_time_when_the_game_says_nothing(tmp_path, monkeypatch):
    """The anti-hang proof again, this time through the PRODUCTION clock
    seams.

    Every other test here virtualises `clock()`/`sleep()` for determinism,
    which means they prove the loop terminates in SIMULATED time. A guard
    that wedged the real `Session` -- polling without ever sleeping, or
    never re-reading its own deadline -- would still look fine to them.
    So this one uses `Session` exactly as the daemon does: real
    `time.monotonic()`, real `time.sleep()`, only the socket stubbed. It
    costs a real fraction of a second on purpose.
    """
    monkeypatch.setattr(TelnetConnection, "send_text", lambda *a, **k: None)
    session = Session(FAKE_HOST, FAKE_PORT, "do-guard-wallclock", str(tmp_path))
    with session.conn.lock:
        session.conn.terminal.feed(_wire(_NEW_COMMAND_PROMPT))
        session.conn.rx_count += 1
        session.conn.last_rx = time.monotonic()
    assert re.search(COMMAND_PROMPT_RE, session.current_prompt_line())

    # The counterfactual, on the same real clock: the UNGUARDED wait --
    # which is exactly what `do` used to issue -- resolves instantly on
    # the prompt that is already sitting there. No edit to the source is
    # needed to show what was being fixed.
    before = time.monotonic()
    reason, elapsed = session.wait_settle(wait_prompt=COMMAND_PROMPT_RE, timeout=0.3)
    assert reason == "prompt"
    assert elapsed < 0.001  # the first poll, before any sleep -- microseconds
    assert time.monotonic() - before < 0.05

    started = time.monotonic()
    resp = protocol.dispatch(
        session,
        "do",
        {"input": "P", "wait_prompt": COMMAND_PROMPT_RE, "timeout": 0.3},
        _NoLockServer(),
    )
    took = time.monotonic() - started

    assert resp["settled_reason"] == "timeout"
    # Bounded by its own budget in real seconds -- not spinning, and not
    # waiting past the deadline it was given (one poll interval of slack).
    assert 0.3 <= took < 0.6


# -- what the guard must NOT do --------------------------------------------


def test_do_with_no_wait_prompt_still_settles_on_idle(command_prompt_session):
    """`do` without a `wait_prompt` has no prompt branch to guard, and its
    idle path already carried the freshness clause. Pinned so the guard
    cannot be widened into the path it was never about."""
    session = command_prompt_session
    _schedule_the_response(session, at=0.1)

    resp = protocol.dispatch(
        session, "do", {"input": "P", "timeout": 8.0}, _NoLockServer()
    )

    assert resp["settled_reason"] == "idle"
    # ~0.1 for the response + the 350ms debounce window.
    assert 0.45 <= resp["elapsed"] < 0.7
    assert _RESPONSE_MARKER in "\n".join(resp["screen"])


def test_do_still_falls_through_to_idle_when_the_wait_prompt_never_matches(command_prompt_session):
    """A `wait_prompt` the response never satisfies must still settle on
    `idle` at the debounce window, exactly as before -- the guard gates
    the prompt branch only, and must never promote a legitimate idle into
    a full-budget timeout."""
    session = command_prompt_session
    _schedule_the_response(session, at=0.1)

    resp = protocol.dispatch(
        session,
        "do",
        {"input": "P", "wait_prompt": r"Docking\s+complete", "timeout": 8.0},
        _NoLockServer(),
    )

    assert resp["settled_reason"] == "idle"
    assert 0.45 <= resp["elapsed"] < 0.7


def test_do_accepts_a_single_echoed_byte_as_new_bytes(command_prompt_session):
    """The guard's honest residual, pinned as a known property rather than
    discovered later.

    `rx_count` is a BYTE counter (`connection._reader_loop` bumps it by
    `len(data)`), so the server echoing the keystroke -- one byte, before
    it has painted anything at all -- is enough to open the gate, after
    which the whole-screen search finds the pre-send `Command [TL=` still
    sitting there. What is left is the same GUARD weakness
    `send_and_confirm`'s own `rx_count > rx_at_send` clause has always had
    (`test_settle_real_screen.py::test_send_and_confirm_false_confirms_on_
    the_stale_line_despite_the_rx_guard`).

    **`match_scope` does NOT close this residual, and an earlier revision
    of this docstring said it did.** That claim holds only for the
    stale-ROW shape, where the awaited text sits somewhere up the grid.
    Here the awaited text IS the pre-send prompt line, so the echo lands
    on that very line (`Command [TL=...]: P`) and keeps matching under
    `"prompt_line"` exactly as it does under `"screen"` -- measured, not
    reasoned: `test_prompt_line_scope_does_not_close_the_equal_prompt_
    residual` below. That is this module's own opening point (an awaited
    prompt equal to the pre-send prompt matches under BOTH scopes) and
    `settle.py`'s ("`match_scope` cannot close this one"); nothing on the
    scope axis rescues it. Only a stronger freshness predicate could, and
    matching `send_and_confirm`'s guard byte-for-byte is a deliberate
    choice: a stronger one here (N bytes? a changed render?) would be a
    second, weaker copy of what `match_scope` does for the stale-ROW
    case, and a changed-render predicate would turn a legitimate
    identical repaint into a timeout.

    The guard's own claim is narrower and it fully delivers it: a settle
    can no longer be asserted when the game has said *nothing whatsoever*.
    """
    session = command_prompt_session
    # The echo of the keystroke, and nothing else -- the real screen never
    # arrives.
    session.schedule(0.04, _wire("P"))

    resp = protocol.dispatch(
        session,
        "do",
        {"input": "P", "wait_prompt": COMMAND_PROMPT_RE, "timeout": 8.0},
        _NoLockServer(),
    )

    assert resp["settled_reason"] == "prompt"
    # The lower bound is what makes this non-vacuous: the guard DID hold
    # the wait past t=0 (the defect returned at 0.0 flat), and the echo at
    # t=0.04 is what released it. The upper bound is the residual.
    assert 0.04 <= resp["elapsed"] < 0.2
    screen = "\n".join(resp["screen"])
    assert _PRE_SEND_MARKER in screen
    assert _RESPONSE_MARKER not in screen


# -- the OTHER stale window on this same verb: a row up the grid -----------
#
# Everything above is the EQUAL-PROMPT shape (awaited text == pre-send
# prompt line). The stale-ROW shape is the other half of `do`'s settle
# story and canon now names it: research/tw2002-screen-patterns.md
# P-SETTLE-LINE -- "New bytes since send do not prove the match is on new
# content; a stale copy of the target text elsewhere on the grid still
# hits... Do not treat whole-screen regex success as proof the *live*
# prompt matched."
#
# `test_settle_real_screen.py` proves that shape at the `wait_for_settle`
# layer. Nothing proved it at the `do` VERB, with this verb's
# `prompt_requires_new_bytes=True` also in play -- which is the
# combination that actually ships on the drive path.


@pytest.fixture
def stale_row_session(tmp_path, monkeypatch):
    """The same real capture as `command_prompt_session`, carried one more
    step of the same real flow (operator re-enters the port) so the
    awaited `Command [TL=` is UP THE GRID and the current prompt line is
    the port menu. Same priming `test_settle_real_screen.py`'s
    `port_menu_session` uses; rebuilt here because this module needs the
    socket-capturing `wire_writes` shape `protocol.dispatch` is driven
    through."""
    wire_writes = []
    monkeypatch.setattr(
        TelnetConnection,
        "send_text",
        lambda self, text, enter=True, secret=False: wire_writes.append((text, enter, secret)),
    )
    session = RealScreenSession(tmp_path)
    session.wire_writes = wire_writes

    rows = [line.rstrip() for line in (_FIXTURES / "port_trade_screen.txt").read_text().splitlines()]
    session.feed_now(_wire("\n".join(rows[:-1]) + "\n"))
    session.feed_now(_wire(rows[-1] + " "))
    session.feed_now(_wire("P\n"))
    session.feed_now(_wire(_PORT_REDRAW))
    session.feed_now(_wire("Enter your choice [T] ? "))

    # Preconditions, asserted rather than assumed -- and the mirror image
    # of `command_prompt_session`'s: the awaited shape is on the grid but
    # is NOT the current prompt, so here the two scopes CAN disagree.
    assert re.search(COMMAND_PROMPT_RE, session.render_text())
    assert not re.search(COMMAND_PROMPT_RE, session.current_prompt_line())
    assert session.current_prompt_line() == "Enter your choice [T] ?"
    return session


def _schedule_the_real_command_prompt(session, at):
    """The screen the caller is actually waiting for: leaving the port
    menu lands back on a NEW `Command [TL=` prompt."""
    session.schedule(at, _wire(_LEAVE_PORT))
    session.schedule(at, _wire(_NEW_COMMAND_PROMPT))


def test_do_false_settles_on_a_command_prompt_left_up_the_grid(stale_row_session):
    """P-SETTLE-LINE on the live drive path, pinned as it behaves TODAY.

    `do` sends `Q` and waits for `Command \\[TL=` while the port menu is on
    screen and a `Command [TL=` from two screens ago is still plainly
    visible up the grid (TradeWars is a scrolling BBS door; it does not
    clear between screens, and `pyte.Screen` keeps no history buffer, so
    this is the visible grid, not a scrollback leak).

    The rx guard does not save it: `rx_count` is a byte counter, so the
    single echoed keystroke opens the gate, and the whole-screen search
    then matches the stale row. The App is handed `settled_reason:
    prompt` -- documented as the STRONGEST confirmation, "quiet on a
    specific, named shape" -- at t=0.04, for a screen whose live prompt
    line is the port menu and whose real `Command [TL=` does not arrive
    until t=3.0.

    Pinned rather than fixed: `do` cannot currently REQUEST prompt-line
    scope (`Session.wait_settle` has no `match_scope` parameter to pass
    one through), and P-SETTLE-LINE forbids closing the gap by flipping a
    default -- "which canon doc governs default `match_scope`" is an open
    question, "until ruled, do not flip defaults in a drive-by tip; pin
    prompt-line scope where a WO explicitly Accepts it."
    """
    session = stale_row_session
    # The keystroke echo -- one byte, all the guard requires.
    session.schedule(0.04, _wire("Q"))
    # The screen the caller is actually waiting for, much later.
    _schedule_the_real_command_prompt(session, at=3.0)

    resp = protocol.dispatch(
        session,
        "do",
        {"input": "Q", "wait_prompt": COMMAND_PROMPT_RE, "timeout": 8.0},
        _NoLockServer(),
    )

    assert resp["settled_reason"] == "prompt"  # <-- the false settle
    assert resp["elapsed"] < 0.5  # long before the real prompt at t=3.0
    # ...and this is the screen the App was actually handed:
    assert not re.search(COMMAND_PROMPT_RE, resp["prompt"])
    assert not re.search(COMMAND_PROMPT_RE, session.current_prompt_line())


def test_prompt_line_scope_withholds_the_strongest_reason_on_the_stale_row(stale_row_session):
    """What pinning `do` to prompt-line scope would actually buy -- stated
    precisely, because it is NOT "the wait holds out for the real prompt".

    Issued exactly as `do` issues it (`session.send(...)` then the settle,
    with `prompt_requires_new_bytes=True`), only with the scope narrowed.
    `wait_for_settle` returns on the FIRST of prompt/idle/timeout, so once
    the stale row stops matching, the echo byte plus a quiet debounce
    window legitimately satisfies the IDLE branch at ~0.4s.

    So the win is a downgrade of the CLAIM, not a longer wait: `prompt`
    ("quiet on a specific, named shape" -- false here) becomes `idle`
    ("it went quiet; I never saw your shape" -- true here). That is
    exactly canon's ordering of the three reasons, and it is what
    P-SETTLE-LINE's "do not treat whole-screen regex success as proof the
    live prompt matched" buys on this path.
    """
    session = stale_row_session
    session.schedule(0.04, _wire("Q"))
    _schedule_the_real_command_prompt(session, at=3.0)

    session.send("Q", enter=True, secret=False, sender="app")
    reason, elapsed = wait_for_settle(
        session,
        wait_prompt=COMMAND_PROMPT_RE,
        timeout_s=8.0,
        prompt_requires_new_bytes=True,
        match_scope="prompt_line",
    )

    assert reason == "idle"  # NOT "prompt" -- the strongest claim is withheld
    assert 0.35 <= elapsed < 0.5  # the echo at 0.04 + the 350ms debounce
    assert not re.search(COMMAND_PROMPT_RE, session.current_prompt_line())


def test_prompt_line_scope_does_not_close_the_equal_prompt_residual(command_prompt_session):
    """The other half of the same truth, so the scope fix is never
    oversold: on the EQUAL-PROMPT shape, narrowing the scope changes
    nothing at all.

    `settle.py` asserts this in prose ("`match_scope` cannot close this
    one... the awaited shape genuinely IS on the current prompt line, so
    it matches immediately under BOTH scopes") and this module's own
    docstring opens with it, but nothing executed it. It matters because
    the tempting reading of `test_do_accepts_a_single_echoed_byte_as_new_
    bytes` is "the `match_scope` fix will close that residual too" -- it
    will not, and a future reader who assumes otherwise would think the
    stale-pre-send window was shut when it is still open.

    Same timeline as that test: the echo lands, the real screen never
    arrives. Under `"prompt_line"` the echo appends to the prompt line
    itself (`Command [TL=...]: P`), which still satisfies the regex.
    """
    session = command_prompt_session
    session.schedule(0.04, _wire("P"))  # echo only; the response never comes

    session.send("P", enter=True, secret=False, sender="app")
    reason, elapsed = wait_for_settle(
        session,
        wait_prompt=COMMAND_PROMPT_RE,
        timeout_s=8.0,
        prompt_requires_new_bytes=True,
        match_scope="prompt_line",
    )

    assert reason == "prompt"  # unchanged by the narrowing
    assert elapsed < 0.2
    # The awaited shape really is on the prompt line -- with the echo on
    # the end of it -- which is why no scope choice can reject it...
    assert re.search(COMMAND_PROMPT_RE, session.current_prompt_line())
    assert session.current_prompt_line().endswith("P")
    # ...while the response the send was supposed to produce never landed.
    assert _RESPONSE_MARKER not in session.render_text()


# -- `read` is a different question and must be untouched ------------------


def test_read_still_returns_at_t0_on_a_prompt_already_on_screen(command_prompt_session):
    """`read` sends NOTHING -- it asks "is this prompt there?" about the
    screen as it stands. Returning immediately when the answer is yes is
    its correct contract, not the same defect, and the guard must not
    reach it. Pinned, because this is the behaviour a well-meaning
    "fix the same bug everywhere" pass would break."""
    session = command_prompt_session

    resp = protocol.dispatch(
        session,
        "read",
        {"wait_prompt": COMMAND_PROMPT_RE, "timeout": 8.0},
        _NoLockServer(),
    )

    assert resp["settled_reason"] == "prompt"
    assert resp["elapsed"] == 0.0
    assert session.wire_writes == []  # read-only: not one byte on the wire
    assert session.last_sent is None


def test_wait_for_settle_prompt_guard_is_off_by_default(command_prompt_session):
    """At the settle layer: the guard is opt-in, so every OTHER caller --
    `read`, `send_and_confirm`'s inner waits, `login`'s bare settles --
    keeps the match-wins-immediately-at-t0 contract it was written
    against. Only `do`'s post-send wait asks for it."""
    session = command_prompt_session

    reason, elapsed = wait_for_settle(session, wait_prompt=COMMAND_PROMPT_RE, timeout_s=8.0)
    assert (reason, elapsed) == ("prompt", 0.0)

    reason, elapsed = wait_for_settle(
        session, wait_prompt=COMMAND_PROMPT_RE, timeout_s=0.5, prompt_requires_new_bytes=True
    )
    assert reason == "timeout"
    assert elapsed >= 0.5
