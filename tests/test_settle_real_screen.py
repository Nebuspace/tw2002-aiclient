"""Settle detection against a REAL rendered screen (WO-SETTLE-PROMPT-LINE).

`tests/test_settle.py` proves settle *timing* against pure fakes whose
`render_text()` returns a canned string. That harness structurally cannot
see the defect this module exists for: a canned string has no grid, no
rows, and no notion of "which line is the prompt" -- so a `wait_prompt`
that matches "somewhere on the screen" and one that matches "on the
current prompt line" are indistinguishable to it.

So this module drives the SAME production `settle` functions against the
real `Session` -- real `TerminalScreen` (pyte), real `render_cropped()`,
real `render_text()`, real `current_prompt_line()`. Only the two
documented settle-protocol clock seams (`clock()`/`sleep()`) are
virtualised, plus the byte transport: bytes are handed to the terminal
exactly the way `connection.TelnetConnection._reader_loop` hands them
over (feed under `conn.lock`, then bump `rx_count` by `len(data)` and
stamp `last_rx`). Nothing about rendering or matching is faked.

**Why the screen shape below is not invented.** TradeWars is a DOS BBS
door: it scrolls, it does not clear between screens, so the PREVIOUS
prompt stays plainly visible on the 80x25 grid while the next screen
paints. `tests/fixtures/port_trade_screen.txt` is a real capture that
shows exactly that -- the previous prompt (`Enter your choice [T] ?`) is
sitting at row 2 while the current prompt is `Command [TL=` at row 25.
The fixtures here are that capture replayed as a byte stream and then
carried ONE more step of the same real flow (operator re-enters the
port), which puts `Command [TL=` up the grid and `Enter your choice
[T] ?` on the prompt line. Note also that pyte here is `pyte.Screen`,
which has no history buffer at all -- this is not a scrollback-leak
question; the stale prompt is on the visible grid.
"""

import re
from pathlib import Path

import pytest

from tw2002_aiclient.session.connection import TelnetConnection
from tw2002_aiclient.session.session import Session
from tw2002_aiclient.session.settle import send_and_confirm, wait_for_settle

from .conftest import FAKE_HOST, FAKE_PORT

_FIXTURES = Path(__file__).parent / "fixtures"

# The awaited shape. Canon's own worked example of a `--wait-prompt`
# (canon/architecture/session-engine.md:196).
COMMAND_PROMPT_RE = r"Command \[TL="


def _wire(text):
    """`text` as the server would actually put it on the wire: CRLF line
    endings, CP437 bytes (terminal.py decodes cp437, never UTF-8)."""
    return text.replace("\n", "\r\n").encode("cp437")


# One more step of the captured flow: the operator, sitting at the
# Command prompt the capture ends on, re-enters the port.
_PORT_REDRAW = (
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
    "You have 100,000 credits and 50 empty cargo holds.\n"
    "\n"
)

# ...and the response the caller is actually waiting for: leaving the
# port menu lands back on a NEW Command prompt.
_LEAVE_PORT = (
    "Q\n"
    "\n"
    "You have 100,000 credits and 50 empty cargo holds.\n"
    "\n"
)


class RealScreenSession(Session):
    """The production `Session` with a virtual clock and a scripted byte
    timeline. Everything the settle prompt-match actually reads --
    `render()`, `render_text()`, `current_prompt_line()`, the pyte grid
    underneath them -- is production code, untouched.

    `sleep()` is the only thing that advances simulated time, so a whole
    test runs instantly and deterministically (same convention as
    `test_settle.py`'s `ScriptedSession`).
    """

    def __init__(self, log_dir):
        super().__init__(FAKE_HOST, FAKE_PORT, "settle-real-screen", str(log_dir))
        self._t = 0.0
        self._timeline = []

    # -- the two documented settle-protocol clock seams ------------------

    def clock(self):
        return self._t

    def sleep(self, seconds):
        self._t += seconds
        self._drain()

    # -- byte transport, mirroring connection._reader_loop ---------------

    def feed_now(self, data):
        """Deliver bytes immediately -- used to prime the screen to the
        state the caller finds it in."""
        with self.conn.lock:
            self.conn.terminal.feed(data)
            self.conn.rx_count += len(data)
            self.conn.last_rx = self._t

    def schedule(self, at, data):
        """Deliver bytes once simulated time reaches `at`."""
        self._timeline.append((at, data))
        self._timeline.sort(key=lambda item: item[0])

    def _drain(self):
        while self._timeline and self._timeline[0][0] <= self._t:
            _, data = self._timeline.pop(0)
            self.feed_now(data)


@pytest.fixture
def port_menu_session(tmp_path, monkeypatch):
    """A session whose real pyte grid is sitting at the port menu, with
    the PREVIOUS `Command [TL=` prompt still plainly visible up the grid
    -- the ordinary consequence of a scrolling BBS door, not a contrived
    state. Sends are stubbed at the socket, exactly as test_session.py
    does; everything above the socket is real."""
    monkeypatch.setattr(TelnetConnection, "send_text", lambda *a, **k: None)
    session = RealScreenSession(tmp_path)

    rows = [line.rstrip() for line in (_FIXTURES / "port_trade_screen.txt").read_text().splitlines()]
    # Replay the capture: completed lines, then its live prompt row with
    # the cursor still parked on it (no trailing newline).
    session.feed_now(_wire("\n".join(rows[:-1]) + "\n"))
    session.feed_now(_wire(rows[-1] + " "))
    # One more step of the same flow: re-enter the port. The server
    # echoes the keystroke onto the Command prompt line, then paints.
    session.feed_now(_wire("P\n"))
    session.feed_now(_wire(_PORT_REDRAW))
    session.feed_now(_wire("Enter your choice [T] ? "))

    # Precondition, asserted rather than assumed: the awaited shape is on
    # the grid but is NOT the current prompt.
    assert re.search(COMMAND_PROMPT_RE, session.render_text())
    assert not re.search(COMMAND_PROMPT_RE, session.current_prompt_line())
    assert session.current_prompt_line() == "Enter your choice [T] ?"
    return session


def _schedule_the_real_command_prompt(session, at):
    """The response the caller is actually waiting for, arriving late."""
    session.schedule(at, _wire(_LEAVE_PORT))
    session.schedule(at, _wire("Command [TL=00:00:00]:[21068] (?=Help)? : "))


# -- the defect, pinned exactly as it behaves today -------------------------


def test_default_scope_settles_on_a_stale_command_prompt_up_the_grid(port_menu_session):
    """WHOLE-SCREEN matching returns `prompt` against a `Command [TL=`
    that scrolled up the grid two screens ago, while the screen the
    caller is actually looking at still shows the port menu.

    This pins today's contract (canon settle-detection.md:26 -- "matches
    the rendered screen text") so it can never flip silently. It is also
    the hazard: `settled_reason == "prompt"` is documented as the
    STRONGEST confirmation -- "quiet on a specific, named shape" -- and
    here it is asserted over a screen that is not quiet, on a shape that
    is not the one the send produced.
    """
    session = port_menu_session
    _schedule_the_real_command_prompt(session, at=0.8)

    reason, elapsed = wait_for_settle(session, wait_prompt=COMMAND_PROMPT_RE, timeout_s=8.0)

    assert reason == "prompt"
    assert elapsed == 0.0  # matched on the very first poll, before any wait
    # ...and this is what the caller was actually handed:
    assert session.current_prompt_line() == "Enter your choice [T] ?"


def test_prompt_line_scope_waits_for_the_prompt_the_send_actually_produced(port_menu_session):
    """The same session, the same regex, scoped to the current prompt
    line: the stale row up the grid is ignored and the wait resolves only
    once the real `Command [TL=` prompt lands."""
    session = port_menu_session
    _schedule_the_real_command_prompt(session, at=0.8)

    reason, elapsed = wait_for_settle(
        session, wait_prompt=COMMAND_PROMPT_RE, timeout_s=8.0, match_scope="prompt_line"
    )

    assert reason == "prompt"
    assert elapsed >= 0.8
    assert re.search(COMMAND_PROMPT_RE, session.current_prompt_line())


def test_prompt_line_scope_still_times_out_when_the_prompt_never_arrives(port_menu_session):
    """Bounded, not a new hang: the narrowed match must still fall
    through to `timeout` on the existing budget when the awaited prompt
    genuinely never shows up -- never wait past it."""
    session = port_menu_session  # nothing scheduled: the port menu just sits there

    reason, elapsed = wait_for_settle(
        session, wait_prompt=COMMAND_PROMPT_RE, timeout_s=0.5, poll_interval_s=0.05,
        match_scope="prompt_line",
    )

    assert reason == "timeout"
    assert elapsed >= 0.5


# -- send_and_confirm: the rx_count guard does NOT close this window --------


def test_send_and_confirm_false_confirms_on_the_stale_line_despite_the_rx_guard(port_menu_session):
    """`send_and_confirm`'s stale-pre-send guard (`rx_count > rx_at_send`)
    only proves SOMETHING arrived since the send -- not that the awaited
    screen did. A single echoed keystroke satisfies it, and the
    whole-screen match then confirms against the stale row up the grid.
    The 150ms stability re-check does not catch it either: that re-check
    is also a whole-screen search, and the stale row is still there.

    Confirmed=True on a screen that never arrived is the exact shape the
    module docstring calls "a desync the caller MUST treat as unsafe" --
    reported here as True.
    """
    session = port_menu_session
    # The echo of the keystroke: the server puts a "Q" on the port-menu
    # prompt line. Realistic, and only 1 byte -- but rx_count is a byte
    # counter, so 1 byte is all the guard requires.
    session.schedule(0.04, _wire("Q"))
    # The screen the caller is actually waiting for is much later.
    _schedule_the_real_command_prompt(session, at=3.0)

    reason, elapsed, confirmed = send_and_confirm(
        session, "Q", confirm_prompt=COMMAND_PROMPT_RE, enter=True, timeout_s=8.0
    )

    assert reason == "prompt"
    assert confirmed is True  # <-- the false confirm
    assert elapsed < 0.5  # long before the real prompt at t=3.0
    assert "Command [TL=" not in session.current_prompt_line()


def test_send_and_confirm_prompt_line_scope_confirms_only_the_real_screen(port_menu_session):
    """Same timeline, scoped to the prompt line: the echo no longer
    confirms anything, and the confirm resolves on the screen the send
    actually produced."""
    session = port_menu_session
    session.schedule(0.04, _wire("Q"))
    _schedule_the_real_command_prompt(session, at=3.0)

    reason, elapsed, confirmed = send_and_confirm(
        session, "Q", confirm_prompt=COMMAND_PROMPT_RE, enter=True, timeout_s=8.0,
        match_scope="prompt_line",
    )

    assert reason == "prompt"
    assert confirmed is True
    assert elapsed >= 3.0
    assert re.search(COMMAND_PROMPT_RE, session.current_prompt_line())


def test_send_and_confirm_prompt_line_scope_rechecks_stability_on_the_prompt_line(port_menu_session):
    """The post-match stability re-check must use the SAME scope as the
    match that triggered it. If it fell back to a whole-screen search, a
    prompt that flashed and moved on would still find its own text up the
    grid and re-confirm -- re-opening the hole one line lower down."""
    session = port_menu_session
    _schedule_the_real_command_prompt(session, at=0.5)
    # A beat after the Command prompt paints, the screen moves on (an
    # unsolicited interjection lands). The Command prompt text is still
    # ON the grid -- just no longer the prompt line.
    session.schedule(0.60, _wire("\nA new ship has entered the sector.\n[Pause]"))

    reason, elapsed, confirmed = send_and_confirm(
        session, "Q", confirm_prompt=COMMAND_PROMPT_RE, enter=True, timeout_s=1.5,
        stability_pause_s=0.15, match_scope="prompt_line",
    )

    assert reason == "prompt"  # it did match, transiently
    assert confirmed is False  # ...but was gone from the prompt line on the re-check
    assert re.search(COMMAND_PROMPT_RE, session.render_text())  # still on the grid


# -- what the narrowing costs, stated rather than discovered later ----------


def test_prompt_line_scope_cannot_match_a_multi_line_wait_prompt(port_menu_session):
    """The honest cost of the narrowing, pinned so it is a documented
    property and not a surprise: a `wait_prompt` written to span rows
    matches under the default screen scope and CANNOT match under
    `prompt_line`. `--wait-prompt` is operator-supplied and free-form, so
    a cross-row pattern is expressible; under `prompt_line` it degrades
    to a `timeout`, never a wrong match. (Every `wait_prompt` example in
    canon -- session-engine.md:196/212, macros.md:182 -- is a single-line
    prompt anchor.)"""
    session = port_menu_session
    cross_row = r"empty cargo holds\.\s*\n\s*Enter your choice"

    assert re.search(cross_row, session.render_text())  # the shape really is on screen

    reason, _elapsed = wait_for_settle(
        session, wait_prompt=cross_row, timeout_s=0.3, poll_interval_s=0.05
    )
    assert reason == "prompt"  # default scope: matches across rows

    reason, _elapsed = wait_for_settle(
        session, wait_prompt=cross_row, timeout_s=0.3, poll_interval_s=0.05,
        match_scope="prompt_line",
    )
    assert reason == "timeout"  # narrowed scope: cannot span rows


def test_prompt_line_scope_still_honors_the_case_sensitivity_invariant(port_menu_session):
    """Canon hard rule (settle-detection.md "Invariant: wait_prompt Is
    Case-Sensitive") is a property of the compile, not of the scope --
    re-proved on the narrowed path so a future scope change can't quietly
    take IGNORECASE with it."""
    session = port_menu_session
    _schedule_the_real_command_prompt(session, at=0.2)

    reason, _elapsed = wait_for_settle(
        session, wait_prompt=r"command \[tl=", timeout_s=0.6, poll_interval_s=0.05,
        match_scope="prompt_line",
    )

    assert reason == "timeout"
    # The correctly-cased pattern would have matched by now -- proving
    # the timeout is the case rule, not a broken scope.
    assert re.search(COMMAND_PROMPT_RE, session.current_prompt_line())


# -- no silent degradation ---------------------------------------------------


def test_unknown_match_scope_is_rejected_loudly(port_menu_session):
    """A typo'd scope must never fall back to the permissive whole-screen
    search -- that would silently reinstate the defect at the one call
    site that asked not to have it."""
    with pytest.raises(ValueError, match="match_scope"):
        wait_for_settle(port_menu_session, wait_prompt=COMMAND_PROMPT_RE, match_scope="prompt-line")

    with pytest.raises(ValueError, match="match_scope"):
        send_and_confirm(
            port_menu_session, "Q", confirm_prompt=COMMAND_PROMPT_RE, match_scope="whole_screen"
        )


def test_prompt_line_scope_refuses_a_session_without_the_accessor():
    """`settle`'s session protocol is duck-typed and documents
    `render_text()`; `current_prompt_line()` is an ADDITIONAL requirement
    that only the prompt-line scope imposes. A session that cannot serve
    it must fail loudly at wait entry rather than degrade to a
    whole-screen search."""

    class RenderTextOnly:
        rx_count = 0
        last_rx = 0.0

        def clock(self):
            return 0.0

        def sleep(self, seconds):
            pass

        def render_text(self):
            return "Command [TL=00:00:00]:[1] (?=Help)? :"

    with pytest.raises(TypeError, match="current_prompt_line"):
        wait_for_settle(RenderTextOnly(), wait_prompt=COMMAND_PROMPT_RE, match_scope="prompt_line")
