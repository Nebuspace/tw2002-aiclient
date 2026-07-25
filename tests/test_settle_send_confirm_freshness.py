"""`send_and_confirm`'s freshness floor vs `wait_for_settle`'s
(WO-SEND-CONFIRM-RX-DEDUP).

`settle.py` carries TWO "has anything arrived since we sent?" guards that
read like copies of each other:

  * `send_and_confirm`'s own -- `rx_at_send = session.rx_count` captured
    **before** `session.send()`, then `rx_count > rx_at_send` re-checked
    around each inner wait, advancing one poll tick on a stale match.
  * `wait_for_settle(prompt_requires_new_bytes=True)` -- `start_rx_count`
    captured at **wait entry**, i.e. after `send()` has returned, with the
    prompt branch simply refusing to match until it moves.

They are NOT copies, and this module exists to keep that fact provable
rather than asserted. The whole difference is WHERE THE FLOOR IS TAKEN,
and it is observable in exactly one situation: a byte that lands while
`send()` itself is running. Under `send_and_confirm`'s floor that byte is
NEW (it postdates the reading); under `wait_for_settle`'s it is OLD (it
predates the reading). Everywhere else the two agree to the last float
bit -- which is what `test_the_two_floors_agree_...` below pins, so the
difference can never be over-claimed either.

**Why the window is real and not a thought experiment.** `Session.send()`
is not instantaneous: it takes `send_lock`, may sleep up to
`MIN_SEND_GAP_S` (0.15s) for the anti-hammer guardrail, writes the socket,
and writes the transcript log -- all while the reader thread keeps
delivering bytes into the same `rx_count`. Bytes landing in that window
come from whatever was ALREADY painting; they are not a response to the
send that is still in progress.

**Why this is pinned rather than fixed.** The two guards embody opposite
answers to a question canon has not ruled on, and each is documented as
correct where it lives:

  * `wait_for_settle`'s docstring argues wait-entry is "the most faithful
    point available", precisely because bytes from a previous command
    still painting are "correctly counted as OLD, which a floor captured
    before the send would have mistaken for a response".
  * `send_and_confirm`'s own comment argues pre-send, because a floor
    taken after `send()` returns can never be cleared at all when the
    whole response is already in hand by then -- the shape the
    synchronous-bump test doubles (`tests/test_haggle.py` and siblings,
    banked in `pytest.ini`) are built on.

Both are true. Which one `send_and_confirm` should use is a design call,
not a tidy-up, so today's behaviour is pinned exactly as it behaves --
including the hazard in `test_send_and_confirm_confirms_a_screen_the_send_
never_produced_...`, which is a false confirm reported as True.

**What these tests kill.** Two mutations pass the entire collected suite
today (2791 tests, zero failures), which is how "these two guards are
redundant" survived as an opinion:

  M1  move `rx_at_send = session.rx_count` to after `session.send(...)`.
  M2  delete the outer guard entirely and pass
      `prompt_requires_new_bytes=True` to the inner `wait_for_settle`.

Both are caught by the first test below, and only by it -- the other three
are the surrounding measurement (what the other floor does on the same
timeline, and where the two provably agree), not additional tripwires.
Said plainly here so nobody reads four tests as four independent guards.

**Why a real `Session`.** Same reason `test_do_settle_rx_guard.py` gives:
a fake whose `render_text()` returns a canned string has no grid and no
byte timeline, so it cannot tell "settled on the screen the send produced"
from "settled on the screen that was already there". The harness is
`test_settle_real_screen.py`'s, imported rather than re-declared so both
modules move together: production `Session`, production pyte
`TerminalScreen`, production `render_text()`, with only the
`clock()`/`sleep()` settle-protocol seams and the socket virtualised.
"""

import re

import pytest

from tw2002_aiclient.session.connection import TelnetConnection
from tw2002_aiclient.session.settle import send_and_confirm, wait_for_settle

from .test_settle_real_screen import COMMAND_PROMPT_RE, RealScreenSession, _wire

# The pre-send screen, and the shape the caller waits for -- deliberately
# the SAME shape. This is canon's own worked example (a `do`/confirm issued
# from `Command [TL=` waiting for `Command \[TL=`) and the case where a
# freshness floor is the only thing that can tell the two apart.
_COMMAND_PROMPT = "Command [TL=00:00:00]:[21068] (?=Help)? : "

# One turn later: proof the response actually landed. The pre-send screen
# cannot be mistaken for it.
_RESPONSE = (
    "\n"
    "One turn deducted, 29989 turns left.\n"
    "\n"
    "Command [TL=00:00:00]:[21067] (?=Help)? : "
)
_RESPONSE_MARKER = "29989 turns left"


@pytest.fixture
def at_command_prompt(tmp_path, monkeypatch):
    """Factory: a real `Session` parked on `Command [TL=`.

    `build(bytes_during_send=True)` makes the socket write itself deliver a
    byte -- the live shape where the reader thread lands data belonging to
    a PREVIOUS screen while `send()` is still inside its anti-hammer pause
    or its transcript write. It is delivered through `feed_now()`, the same
    `connection._reader_loop` mirror every other test in this harness uses,
    so `rx_count` moves exactly as it would live.
    """
    holder = {}

    def build(bytes_during_send=False):
        def send_text(self, text, enter=True, secret=False):
            if bytes_during_send:
                holder["session"].feed_now(_wire("P"))

        monkeypatch.setattr(TelnetConnection, "send_text", send_text)
        session = RealScreenSession(tmp_path)
        holder["session"] = session
        session.feed_now(_wire(_COMMAND_PROMPT))

        # Preconditions, asserted rather than assumed: the awaited shape is
        # ALREADY satisfied -- on the current prompt line, not merely
        # somewhere up the grid, so no `match_scope` choice can distinguish
        # it (that is the separate defect in test_settle_real_screen.py) --
        # and the response has plainly not arrived.
        assert re.search(COMMAND_PROMPT_RE, session.render_text())
        assert re.search(COMMAND_PROMPT_RE, session.current_prompt_line())
        assert _RESPONSE_MARKER not in session.render_text()
        return session

    return build


# -- the floor is taken BEFORE send(), and it is observable ----------------


def test_send_and_confirm_confirms_a_screen_the_send_never_produced_when_a_byte_crosses_the_send_boundary(
    at_command_prompt,
):
    """Today's contract, pinned exactly as it behaves -- and the hazard.

    A single byte lands DURING `send()`. Nothing else ever arrives: the
    response to `P` never comes, and the screen still reads the pre-send
    `Command [TL=`. Because `rx_at_send` was read before that byte,
    `rx_count > rx_at_send` is already true on the very first poll, so the
    pre-send match is accepted at once -- `confirmed=True`, at `elapsed`
    0.0, on a screen the send did not produce.

    That is the exact shape `settle.py`'s module docstring calls "a desync
    the caller MUST treat as unsafe", reported here as safe. It is pinned
    rather than fixed because the fix is a choice between two documented
    floors (see this module's docstring), which is canon's call and not a
    refactor's.

    Kills M1: with the capture moved after `send()` the byte is inside the
    floor, the guard never opens, and this returns `("timeout", ..., False)`.
    """
    session = at_command_prompt(bytes_during_send=True)

    reason, elapsed, confirmed = send_and_confirm(
        session, "P", confirm_prompt=COMMAND_PROMPT_RE, enter=True, timeout_s=1.0
    )

    assert reason == "prompt"
    assert confirmed is True  # <-- the false confirm
    assert elapsed == 0.0  # before any simulated time passed at all
    # ...and this is what the caller was actually handed: no response, and
    # the echoed keystroke sitting on the end of the pre-send prompt line.
    assert _RESPONSE_MARKER not in session.render_text()
    assert session.current_prompt_line().endswith("P")


def test_the_inner_prompt_guard_refuses_the_very_timeline_send_and_confirm_accepts(
    at_command_prompt,
):
    """The non-equivalence, driven head-to-head.

    Same real session, same byte crossing the same `send()`, same regex,
    same budget -- routed through `wait_for_settle`'s guard instead, whose
    floor is taken at wait entry. It refuses, and spends the whole budget
    doing it.

    So the outer guard is not a redundant copy of the inner one: on this
    timeline they return different reasons AND different confirmations.
    Whichever is right, they cannot be collapsed into each other without
    picking one.

    This test is the EVIDENCE for that claim, not a tripwire -- it never
    touches `send_and_confirm`, so it stays green under both mutations.
    It is what the row above would become under M2.
    """
    session = at_command_prompt(bytes_during_send=True)

    session.send("P", enter=True)
    reason, elapsed = wait_for_settle(
        session, wait_prompt=COMMAND_PROMPT_RE, timeout_s=1.0, prompt_requires_new_bytes=True
    )

    assert reason == "timeout"
    assert elapsed >= 1.0
    # Non-vacuous: the regex genuinely matches the screen throughout. Only
    # the floor is holding the match back.
    assert re.search(COMMAND_PROMPT_RE, session.current_prompt_line())


# -- ...and NOWHERE else --------------------------------------------------


@pytest.mark.parametrize("arrives_at", [0.2, 0.8])
def test_the_two_floors_agree_to_the_last_bit_when_no_byte_crosses_the_send_boundary(
    at_command_prompt, arrives_at
):
    """The other half, without which the difference above would be
    over-claimed: when nothing lands during `send()` the two floors are the
    same number, and both paths agree on reason AND on `elapsed` exactly --
    not approximately.

    This is the measurement that retires the standing guess that the outer
    loop's own budget recomputation and poll tick make its "elapsed
    accounting differ subtly" from the inner wait's. They do not differ at
    all: both walk the same `poll_interval_s` grid from the same instant,
    and `send_and_confirm` discards the inner `elapsed` and re-measures
    from its own `start` anyway.

    Asserted as exact equality between the two paths (never against a
    hard-coded float), so it stays true if the poll grid or the fixture
    timeline is ever retuned, and stays a real comparison either way.
    """
    confirming = at_command_prompt()
    confirming.schedule(arrives_at, _wire(_RESPONSE))
    reason_a, elapsed_a, confirmed_a = send_and_confirm(
        confirming, "P", confirm_prompt=COMMAND_PROMPT_RE, enter=True, timeout_s=8.0
    )

    waiting = at_command_prompt()
    waiting.schedule(arrives_at, _wire(_RESPONSE))
    waiting.send("P", enter=True)
    reason_b, elapsed_b = wait_for_settle(
        waiting, wait_prompt=COMMAND_PROMPT_RE, timeout_s=8.0, prompt_requires_new_bytes=True
    )

    assert (reason_a, confirmed_a) == ("prompt", True)
    assert reason_b == "prompt"
    assert elapsed_a == elapsed_b
    # Non-vacuous: both really did wait for the response rather than
    # matching the identical pre-send prompt shape at t=0.
    assert arrives_at <= elapsed_a < arrives_at + 0.1
    assert _RESPONSE_MARKER in confirming.render_text()


def test_the_two_floors_agree_on_the_timeout_path_when_nothing_ever_arrives(at_command_prompt):
    """Companion to the above on the failure path -- the case where the
    pre-send shape sits there matching forever and no byte ever comes.

    Both floors hold, both spend the whole budget, and both report the same
    `elapsed`. Worth its own test because this is the path where the outer
    loop's structure is most visibly different (it re-enters
    `wait_for_settle` once per poll tick, each time getting an immediate
    `"prompt"` it then discards) -- and it still lands on the same number.
    """
    confirming = at_command_prompt()
    reason_a, elapsed_a, confirmed_a = send_and_confirm(
        confirming, "P", confirm_prompt=COMMAND_PROMPT_RE, enter=True, timeout_s=0.5
    )

    waiting = at_command_prompt()
    waiting.send("P", enter=True)
    reason_b, elapsed_b = wait_for_settle(
        waiting, wait_prompt=COMMAND_PROMPT_RE, timeout_s=0.5, prompt_requires_new_bytes=True
    )

    assert (reason_a, confirmed_a) == ("timeout", False)
    assert reason_b == "timeout"
    assert elapsed_a == elapsed_b
    assert elapsed_a >= 0.5
