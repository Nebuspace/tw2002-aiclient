"""Current-sector read + the `state` verb (WO-P2-G4-X1).

The theme: **this is the read that gates every send.** `canon/engine/
macros.md` requires replay to re-check the current sector against a macro's
`start_anchor` before pressing anything, and makes the resulting halt
explicitly NOT bypassable by force. Two claims follow, and every assertion
below defends one of them.

1. *Three outcomes, never two.* "the ship is in sector N", "this screen
   makes no claim about where the ship is", and "this screen started to say
   and I could not finish reading it" are three different facts. The
   collapse this repo has now fixed five times (`credentials` /
   `env.load_dotenv` / `get_password` / `daemon_alive` / `loops.loader`)
   would here hand the player a false negative on the one check that gates
   every send -- so the collapse is not merely asserted against, it is
   BUILT (by AST rewrite of the real module source) and shown to fail the
   pins: `test_folding_unreadable_into_absent_fails_these_pins`.

2. *A bounded answer leaves the session, never a screen line.* The `state`
   verb is a NEW structured response landing beside two mirror-carriers
   that were just closed (canon `DECISIONS.md` §C.2 / §C.2.1, and
   `protocol._status_response`'s own docstring, which names re-parsing
   `status["prompt"]` for the sector as the shape that must not come back).
   Two prongs: every value on the wire is an `int` or a member of the
   module's closed vocabularies (structural), and a credential sitting on
   the prompt line does not reach the serialized response while still being
   FOUND on the live-paint surface (empirical, positive control included so
   the absence assert cannot pass by finding nothing).

No network, no live daemon, no real `config/`/`run/`/`state/`: a bare
`Session` never touches the network (`tests/test_session.py` states that
outright) and its `terminal.feed()` takes the same CP437/CRLF bytes the
server would put on the wire.
"""

from __future__ import annotations

import ast
import json
import sys
import types
from pathlib import Path

import pytest

from tw2002_aiclient.session import classify, protocol
from tw2002_aiclient.session import state_parser as sp
from tw2002_aiclient.session.session import Session
from tw2002_aiclient.session.state_parser import (
    OUTCOME_ABSENT,
    OUTCOME_READ,
    OUTCOME_UNREADABLE,
    OUTCOMES,
    REASON_DAMAGED_COMMAND_PROMPT,
    REASON_NOT_TEXT,
    REASON_SESSION_DISCONNECTED,
    REASONS,
    SOURCE_COMMAND_PROMPT,
    SOURCES,
    SectorRead,
    read_current_sector,
    sector_wire,
)

from .conftest import FAKE_HOST, FAKE_PORT

FIXTURES = Path(__file__).parent / "fixtures"
STATE_PARSER_SRC = Path(sp.__file__)

# The live target server's prompt shape, from the real capture in
# `tests/fixtures/port_trade_screen.txt`.
LIVE_PROMPT = "Command [TL=00:00:00]:[21068] (?=Help)? :"
# The computer subsystem's prompt -- a different leading word, the same
# bracket. `classify.py`'s "superset" precedent; one pattern must cover both.
COMPUTER_PROMPT = "Computer command [TL=00:00:00]:[4309] (?=Help)? :"
# The CLASSIC-shape TWGS prompt: `TL=` is a plain turn count and there is NO
# second bracket at all. Canon's `sector_from_command_prompt` calls this out
# by name as the server family this anchor cannot serve.
CLASSIC_PROMPT = "Command [TL=00753:0/0/0/850] (?=Help)? :"


def _wire(text: str) -> bytes:
    """`text` as the server would actually put it on the wire: CRLF line
    endings, CP437 bytes (terminal.py decodes cp437, never UTF-8). Local
    rather than imported -- small harness doubles are duplicated per module
    in this suite instead of coupling test files to each other's privates
    (`tests/test_ensure_login_error_redaction.py::_ScriptedTWGS` states the
    convention)."""
    return text.replace("\n", "\r\n").encode("cp437")


def _live_session(tmp_path, screen: str) -> Session:
    """A real `Session` holding `screen`, marked connected but never
    connected: `Session.__init__` opens no socket, and `conn.connected` is
    the exact flag `protocol._dispatch_ensure` already reads to decide
    whether the pyte buffer describes now or describes a frozen frame."""
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    session.terminal.feed(_wire(screen))
    session.conn.connected = True
    return session


# --------------------------------------------------------------------------
# Three outcomes, never two
# --------------------------------------------------------------------------

# The pins that define the trichotomy, factored into one helper so the SAME
# assertions can be run against the real reader and against a deliberately
# collapsed clone of it. Without the second run, "green" would mean "these
# inputs happen to pass", not "the distinction is load-bearing".
def _assert_three_outcomes_distinct(reader) -> None:
    absent = reader(CLASSIC_PROMPT)
    unreadable = reader("Command [TL=00:00:00]:[")
    read = reader(LIVE_PROMPT)

    # Each fact gets its own outcome, and no two of them share one.
    assert read.outcome == OUTCOME_READ
    assert absent.outcome == OUTCOME_ABSENT
    assert unreadable.outcome == OUTCOME_UNREADABLE
    assert len({read.outcome, absent.outcome, unreadable.outcome}) == 3

    # Only the established one carries a number, and it is a real int.
    assert read.sector == 21068 and isinstance(read.sector, int)
    assert absent.sector is None
    assert unreadable.sector is None

    # "I could not finish reading" says WHY; "there is nothing here" has no
    # why to give. That asymmetry is what a caller branches on.
    assert unreadable.reason == REASON_DAMAGED_COMMAND_PROMPT
    assert absent.reason is None


def test_the_three_outcomes_are_distinct_and_only_one_carries_a_number():
    _assert_three_outcomes_distinct(read_current_sector)


def _collapsed_reader():
    """`read_current_sector` with UNREADABLE folded into ABSENT -- the defect
    under guard, and the one this repo has already shipped four times.

    Built by rewriting the REAL module's AST (every `SectorRead(...)` inside
    `read_current_sector` whose `outcome` is `OUTCOME_UNREADABLE` becomes a
    bare `SectorRead(outcome=OUTCOME_ABSENT)`) rather than by hand-writing a
    stub, so the injected defect is measured against the shipping source and
    cannot go stale when that source changes.
    """
    tree = ast.parse(STATE_PARSER_SRC.read_text(encoding="utf-8"))

    class _Collapse(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            if node.name != "read_current_sector":
                return node
            return self.generic_visit(node)

        def visit_Call(self, node):
            self.generic_visit(node)
            if not (isinstance(node.func, ast.Name) and node.func.id == "SectorRead"):
                return node
            for kw in node.keywords:
                if (
                    kw.arg == "outcome"
                    and isinstance(kw.value, ast.Name)
                    and kw.value.id == "OUTCOME_UNREADABLE"
                ):
                    node.keywords = [
                        ast.keyword(arg="outcome", value=ast.Name(id="OUTCOME_ABSENT", ctx=ast.Load()))
                    ]
                    return ast.fix_missing_locations(node)
            return node

    # Only functions are visited by `visit_FunctionDef`; module-level
    # constants keep their real values, so the collapse is exactly the one
    # behavioural change and not a wholesale renaming.
    collapsed_tree = ast.fix_missing_locations(_Collapse().visit(tree))
    name = "state_parser_collapsed"
    module = types.ModuleType(name)
    module.__file__ = str(STATE_PARSER_SRC)
    # Registered in `sys.modules` for the exec and removed straight after:
    # `@dataclass` resolves its own annotations via
    # `sys.modules.get(cls.__module__)`, so an unregistered module makes the
    # decorator raise rather than the collapse show itself.
    sys.modules[name] = module
    try:
        exec(compile(collapsed_tree, str(STATE_PARSER_SRC), "exec"), module.__dict__)
    finally:
        del sys.modules[name]
    return module.read_current_sector


def test_folding_unreadable_into_absent_fails_these_pins():
    """The positive control for the whole file. A suite that only ever runs
    green proves no regression, never coverage -- so the forbidden defect is
    injected and watched to fail.

    It must first still be a WORKING reader (the rewrite is surgical, not a
    lobotomy): the `read` case is untouched and still answers 21068. What
    changes is only that "I could not read this" now renders as "there is
    nothing here" -- and that is what these pins catch.
    """
    collapsed = _collapsed_reader()

    assert collapsed(LIVE_PROMPT).sector == 21068  # still a working reader
    assert collapsed("Command [TL=00:00:00]:[").outcome == OUTCOME_ABSENT  # the defect

    with pytest.raises(AssertionError):
        _assert_three_outcomes_distinct(collapsed)


def test_a_verdict_cannot_carry_a_number_it_did_not_establish():
    """The trichotomy is structural, not conventional: the pairing is
    enforced in `__post_init__`, so no future branch can ship a sector
    alongside an outcome that never established one."""
    with pytest.raises(ValueError):
        SectorRead(outcome=OUTCOME_ABSENT, sector=158)
    with pytest.raises(ValueError):
        SectorRead(outcome=OUTCOME_UNREADABLE, sector=158, reason=REASON_NOT_TEXT)
    with pytest.raises(ValueError):
        SectorRead(outcome=OUTCOME_READ, source=SOURCE_COMMAND_PROMPT)  # read, no number
    with pytest.raises(ValueError):
        SectorRead(outcome=OUTCOME_UNREADABLE)  # unreadable, no reason
    with pytest.raises(ValueError):
        SectorRead(outcome=OUTCOME_ABSENT, reason=REASON_NOT_TEXT)  # absent has no why
    with pytest.raises(ValueError):
        SectorRead(outcome="maybe")  # closed vocabulary


def test_a_boolean_is_not_a_sector():
    """`isinstance(True, int)` holds in Python -- the same trap
    `loops.loader._validate_anchor` documents on the RECORDED half of this
    comparison. Unguarded, `start_anchor: true` meets current sector `True`
    and the anchor check passes on two booleans."""
    with pytest.raises(ValueError):
        SectorRead(outcome=OUTCOME_READ, sector=True, source=SOURCE_COMMAND_PROMPT)


def test_the_verdict_has_no_truthiness_shortcut():
    """`if read:` must not be a way to skip the outcome. A dataclass with no
    `__bool__` and no `__len__` is always truthy, so every outcome -- read,
    absent, unreadable -- is equally truthy and the shortcut is useless
    rather than subtly wrong."""
    verdicts = [
        read_current_sector(LIVE_PROMPT),
        read_current_sector(CLASSIC_PROMPT),
        read_current_sector("Command [TL=00:00:00]:["),
    ]
    assert [bool(v) for v in verdicts] == [True, True, True]
    assert not hasattr(SectorRead, "__bool__")


# --------------------------------------------------------------------------
# The one source -- and the grid it cannot see
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt,expected",
    [
        (LIVE_PROMPT, 21068),
        (COMPUTER_PROMPT, 4309),
        ("Command [TL=00:00:00]:[1] (?=Help)? :", 1),
        ("command [tl=00:00:00]:[777] :", 777),  # anchors are case-insensitive
        ("Command [TL=00753:0/0/0/850]:[4309] (?=Help)? :", 4309),  # classic TL=, bracketed
    ],
)
def test_the_command_prompt_bracket_is_the_sector(prompt, expected):
    read = read_current_sector(prompt)
    assert (read.outcome, read.sector, read.source) == (
        OUTCOME_READ,
        expected,
        SOURCE_COMMAND_PROMPT,
    )


def test_a_prompt_with_no_sector_bracket_is_absent_not_unreadable():
    """The CLASSIC-shape server. Its prompt genuinely makes no
    current-sector claim, so "there is nothing here" is the true answer --
    a disclosed coverage boundary, not a read failure. A consumer tells this
    case apart from any other `absent` using the `classification` that rides
    beside it on the `state` response; see the verb tests below."""
    read = read_current_sector(CLASSIC_PROMPT)
    assert read.outcome == OUTCOME_ABSENT and read.reason is None


@pytest.mark.parametrize(
    "prompt",
    [
        "",  # a blank grid: examined in full, says nothing
        "Enter your choice [T] ?",
        "Do you really want to warp there? (Y/N)",
        "Password:",
        "Select a game :",
        "Sector  : 3034 in uncharted space.",  # a sector DISPLAY, not a claim about the ship
    ],
)
def test_screens_that_make_no_current_sector_claim_are_absent(prompt):
    assert read_current_sector(prompt).outcome == OUTCOME_ABSENT


def test_the_reader_cannot_see_the_grid_only_the_prompt_line():
    """Scoping to the prompt line is structural here, not a convention: the
    function's whole input IS the prompt line, so stale or forged body
    content has no path to it. This is canon's P-SETTLE-LINE discipline
    taken past a `match_scope` flag -- there is no scope to get wrong.

    Measured by handing the reader a whole screen whose body carries a
    DIFFERENT bracket from its prompt line, both ways round.
    """
    body_sector = "Command [TL=00:00:00]:[999] (?=Help)? :"
    screen = body_sector + "\nsome later output\n" + LIVE_PROMPT

    # Whole screen: `re` without MULTILINE would still scan across the
    # newlines, and the stale 999 is right there to be found.
    assert "999" in screen

    # The reader is only ever given the last line, and 999 is unreachable.
    assert read_current_sector(screen.splitlines()[-1]).sector == 21068

    # And the belt-and-braces, MEASURED rather than assumed: handed the whole
    # block by a mistaken caller, the `[ \t]`-only patterns still cannot
    # splice two lines into one match, and last-match still takes the
    # bottom-most -- so a stale bracket up the grid cannot win even then.
    assert read_current_sector(screen).sector == 21068
    assert read_current_sector(LIVE_PROMPT + "\nsome later output\n" + body_sector).sector == 999


def test_the_sector_status_line_is_not_admitted_as_a_current_sector_source():
    """The load-bearing omission, measured on this repo's own captured
    fixture rather than argued.

    `warp_confirm_prompt.txt` is a `Sector : N` line followed immediately by
    `Warps to Sector(s) :` -- it PASSES the archive's `is_genuine_sector_
    status()` provenance gate -- sitting under a mid-transaction
    `warp_confirm` stall. Whether 3034 is where the ship IS or where it is
    about to GO is settled by nothing in canon or in this tree, so it is not
    a current-sector source. The archive's `parse_state()` would have
    answered 3034 here and stamped it into a macro's `start_anchor`.
    """
    screen = (FIXTURES / "warp_confirm_prompt.txt").read_text(encoding="utf-8")
    assert "Sector  : 3034" in screen  # the number is right there
    assert "Warps to Sector(s)" in screen  # and it passes the provenance gate

    for line in screen.splitlines():
        assert read_current_sector(line).sector is None


# --------------------------------------------------------------------------
# Damaged, not absent
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt",
    [
        "Command [TL=00:00:00]:[",  # bracket opened, nothing in it
        "Command [TL=00:00:00]:[210",  # truncated mid-number, no closing bracket
        "Command [TL=00:00:00]:[]",  # opened and closed, empty
        "Command [TL=00:00:00]:[????]",  # cells the server never resolved
        "Command [TL=00:00:00]:[ ]",
    ],
)
def test_a_damaged_sector_bracket_is_unreadable_not_absent(prompt):
    """Reachable in ordinary operation, not merely defensive: `state` is the
    cheap-poll verb and does not settle, so a poll landing mid-paint sees
    exactly this. Note the truncated case in particular -- reading `210` out
    of `[210` would be a plausible, wrong sector that could satisfy an
    anchor check."""
    read = read_current_sector(prompt)
    assert read.outcome == OUTCOME_UNREADABLE
    assert read.reason == REASON_DAMAGED_COMMAND_PROMPT
    assert read.sector is None


def test_a_later_damaged_bracket_beats_an_earlier_resolved_one():
    """Last-match applied to the DAMAGE check, not only to the value. Canon's
    hard rule is bottom-most/most-recently-printed wins; reading the earlier
    number because the later one is broken would be first-match-wins by the
    back door -- exactly the simplification canon says never to make."""
    read = read_current_sector("Command [TL=00:00:00]:[158] Command [TL=00:00:00]:[")
    assert read.outcome == OUTCOME_UNREADABLE

    # ...and the same discipline the other way: a later RESOLVED bracket
    # wins over an earlier one.
    assert read_current_sector(
        "Command [TL=00:00:00]:[158] Command [TL=00:00:00]:[231] :"
    ).sector == 231


@pytest.mark.parametrize("value", [None, b"Command [TL=00:00:00]:[1]", 158, {"prompt": "x"}])
def test_something_that_is_not_a_screen_line_is_unreadable(value):
    read = read_current_sector(value)
    assert read.outcome == OUTCOME_UNREADABLE and read.reason == REASON_NOT_TEXT


def test_the_sector_value_is_not_range_checked():
    """Symmetric with `loops.loader._validate_anchor`, which declines to
    range-check the RECORDED anchor for the same reason: a wrong sector is
    caught by the start-anchor comparison and halts safely, and inventing a
    galaxy size in one half of a comparison but not the other is how the
    halves stop agreeing."""
    assert read_current_sector("Command [TL=00:00:00]:[0] :").sector == 0
    assert read_current_sector("Command [TL=00:00:00]:[99999999999] :").sector == 99999999999


# --------------------------------------------------------------------------
# The answer that leaves the session is bounded
# --------------------------------------------------------------------------

# A credential deliberately WITHOUT the substring "password": `classify.py`'s
# `login_password` gate anchor is exactly `re.compile(r"password", re.I)`, so
# a sentinel containing it would change the screen's own classification and
# stop being the scenario under test. Same reasoning as
# `tests/test_status_prompt_redaction.py`'s sentinel.
CREDENTIAL = "hunter2-Vx9qLp-secret"


def _every_wire_value(obj):
    """Flattened leaf values of a JSON-shaped response."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from _every_wire_value(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _every_wire_value(item)
    else:
        yield obj


@pytest.mark.parametrize(
    "prompt",
    [
        LIVE_PROMPT,
        CLASSIC_PROMPT,
        COMPUTER_PROMPT,
        "Command [TL=00:00:00]:[",
        "",
        CREDENTIAL,
        "Sector  : 3034 in uncharted space.",
        "Command [TL=" + CREDENTIAL + "]:[42] :",  # a credential INSIDE the anchor
    ],
)
def test_every_value_on_the_sector_wire_is_an_int_or_a_closed_vocabulary_term(prompt):
    """The structural half of "no raw screen line". Not "we looked and did
    not see the screen" -- there is no string in this answer that did not
    come from the module's own constants, so there is no branch that COULD
    emit a slice of the screen.

    The last case matters most: the anchor's own `TL=` body is free text the
    server controls, and it is walked past, never captured.
    """
    allowed_strings = OUTCOMES | SOURCES | REASONS | {"outcome", "sector", "source", "reason"}
    wire = sector_wire(read_current_sector(prompt))

    assert json.loads(json.dumps(wire)) == wire  # JSON-safe by construction
    for value in _every_wire_value(wire):
        assert isinstance(value, int) or value in allowed_strings, value
    assert CREDENTIAL not in json.dumps(wire)


def test_a_verdict_omits_the_keys_it_did_not_earn():
    """Omitted, never `null`: a caller reaching straight for the number on a
    verdict that never established one fails loudly instead of quietly
    binding `None` -- the same choice `_status_response` made for `prompt`
    and `_login_failure_response` made for `screen`. `outcome` is always
    present, so "there is no number here" is never said by silence."""
    read = sector_wire(read_current_sector(LIVE_PROMPT))
    assert read == {"outcome": OUTCOME_READ, "sector": 21068, "source": SOURCE_COMMAND_PROMPT}

    absent = sector_wire(read_current_sector(CLASSIC_PROMPT))
    assert absent == {"outcome": OUTCOME_ABSENT}
    with pytest.raises(KeyError):
        absent["sector"]

    unreadable = sector_wire(read_current_sector("Command [TL=00:00:00]:["))
    assert unreadable == {
        "outcome": OUTCOME_UNREADABLE,
        "reason": REASON_DAMAGED_COMMAND_PROMPT,
    }
    with pytest.raises(KeyError):
        unreadable["sector"]


# --------------------------------------------------------------------------
# The `state` verb
# --------------------------------------------------------------------------


def test_the_state_verb_answers_the_sector_off_a_real_captured_screen(tmp_path):
    """End to end through the daemon's real dispatch chokepoint, on the real
    captured `port_trade_screen.txt` -- a screen carrying no `Sector :` line
    at all, only its own trailing prompt. This is exactly the case canon
    introduced the prompt anchor for: the arrival burst scrolled the status
    display off the fixed grid."""
    screen = (FIXTURES / "port_trade_screen.txt").read_text(encoding="utf-8")
    assert "Sector" not in screen  # no status line survived the burst
    session = _live_session(tmp_path, screen)

    resp = protocol.dispatch(session, "state", {}, server=None)

    assert resp["ok"] is True
    assert resp["state"]["sector"] == {
        "outcome": OUTCOME_READ,
        "sector": 21068,
        "source": SOURCE_COMMAND_PROMPT,
    }
    assert resp["classification"] == "main_command"


def test_the_state_verb_never_reads_a_sector_off_a_dead_socket(tmp_path):
    """A frozen frame names where the ship WAS. That is the one failure
    direction canon forbids outright, because a stale-but-matching sector
    does not merely mislead -- it SATISFIES the start-anchor guard and lets
    a replay proceed from the wrong sector, which is the live incident
    `macros.md` exists to prevent.

    The positive control is the whole test: the very same buffer answers
    21068 while connected, so this proves the guard is what withholds the
    number, not that the number was unavailable anyway.
    """
    screen = (FIXTURES / "port_trade_screen.txt").read_text(encoding="utf-8")
    session = _live_session(tmp_path, screen)

    assert protocol.dispatch(session, "state", {}, None)["state"]["sector"]["sector"] == 21068

    session.conn.connected = False
    resp = protocol.dispatch(session, "state", {}, None)

    assert resp["state"]["sector"] == {
        "outcome": OUTCOME_UNREADABLE,
        "reason": REASON_SESSION_DISCONNECTED,
    }
    assert resp["connected"] is False
    # The buffer still holds the number -- nothing was cleared, and nothing
    # about the LIVE PAINT path changed.
    assert "21068" in session.render_text()


def test_a_classic_server_prompt_is_absent_and_tellable_apart_from_any_other_absent(tmp_path):
    """The disclosed coverage boundary, and the composition that keeps it
    honest without new machinery: `classification` rides beside the verdict,
    so `main_command` + `absent` reads as "a command prompt that states no
    sector" -- distinguishable from a login screen's `absent` using two
    closed-vocabulary fields and no screen content."""
    session = _live_session(tmp_path, CLASSIC_PROMPT)
    resp = protocol.dispatch(session, "state", {}, None)
    assert resp["state"]["sector"] == {"outcome": OUTCOME_ABSENT}
    assert resp["classification"] == "main_command"

    other = _live_session(tmp_path, "Use ANSI graphics? (Y/N)")
    other_resp = protocol.dispatch(other, "state", {}, None)
    assert other_resp["state"]["sector"] == {"outcome": OUTCOME_ABSENT}
    assert other_resp["classification"] == "ansi_prompt"

    assert resp["classification"] != other_resp["classification"]


def test_the_state_response_carries_no_screen_line_while_the_live_paint_still_does(tmp_path):
    """The empirical half of "no raw screen line", with its positive control.

    An echoing server puts the operator's credential on the prompt line
    (canon's RX-side no-leak guarantee openly rests on this not happening;
    `secrets-and-credentials.md` Code Divergence #1). The `state` response
    must not carry it -- and the assert only means something because the
    SAME screen is shown to still carry it on the live-paint path, so the
    test proves it found the credential and then found it withheld, rather
    than passing by finding nothing.
    """
    session = _live_session(tmp_path, "Password: " + CREDENTIAL)

    state_resp = protocol.dispatch(session, "state", {}, None)
    serialized = json.dumps(state_resp)

    assert CREDENTIAL not in serialized
    # Nor any other slice of the screen: every string on this response is a
    # key, a closed-vocabulary term, or `classify`'s own closed vocabulary.
    allowed = (
        OUTCOMES
        | SOURCES
        | REASONS
        | classify._RETURNABLE_CLASSES
        | {"ok", "state", "sector", "outcome", "source", "reason", "classification", "connected"}
    )
    for value in _every_wire_value(state_resp):
        assert isinstance(value, (int, bool)) or value in allowed, value

    # POSITIVE CONTROL: the live-paint path is untouched and still shows what
    # the server painted. Without this the absence assert above would pass
    # just as happily on an empty screen.
    assert CREDENTIAL in json.dumps(protocol.build_response(session))


def test_the_state_verb_takes_no_driver_slot_and_records_no_history(tmp_path):
    """A read verb that can drive is not a read verb. `state` is polled by
    spectators and by a player about to decide whether it MAY press keys, so
    it must not contend for the keyboard: taking the control lock would turn
    "the human is playing" into a refusal, i.e. a fourth outcome nobody asked
    for. Measured against a server whose lock refuses everything."""

    class _RefuseEverything:
        mode = "human"

        def is_auto_loop_held(self):
            return False

        def app_may_send(self):
            return False

        def acquire_driver(self):  # pragma: no cover - must never be reached
            raise AssertionError("`state` acquired the driver slot")

    session = _live_session(tmp_path, LIVE_PROMPT)
    server = types.SimpleNamespace(control_lock=_RefuseEverything())

    resp = protocol.dispatch(session, "state", {}, server)

    assert resp["state"]["sector"]["sector"] == 21068
    assert session.history == []  # not a driving event; nothing to record
    assert session.last_sent is None  # and nothing went out


# --------------------------------------------------------------------------
# Structural pins -- the bounds this slice was built inside
# --------------------------------------------------------------------------

_SEND_SYMBOLS = frozenset({
    "send_key", "send_raw", "send_request", "sendall", "send", "send_text",
    "send_bytes", "AttachInputConn", "attach_client", "cmd_do", "cmd_send",
})


def _reflected_name(call):
    """`getattr(o, "send_raw")` with a string-literal name -- the alias /
    reflection door a plain Attribute match never sees. Same shape as
    `tests/test_loop_loader.py`'s scanner."""
    if isinstance(call.func, ast.Name) and call.func.id in {"getattr", "setattr"}:
        if len(call.args) >= 2:
            arg = call.args[1]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value
    if (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "__getattribute__"
        and call.args
    ):
        arg = call.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return None


def _send_violations(source: str) -> list[str]:
    tree = ast.parse(source)
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in {"socket", "telnetlib"}:
                    bad.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.split(".")[0] in {"socket", "telnetlib"}:
                bad.append(f"from {mod} import ...")
            # A pure parser importing a live sibling (`session`, `connection`,
            # `protocol`, `cli`) is the edge that would let it grow a wire.
            if mod in {"session", "connection", "protocol", "cli", "attach_client"}:
                bad.append(f"from .{mod} import ...")
        elif isinstance(node, ast.Attribute) and node.attr in _SEND_SYMBOLS:
            bad.append(f".{node.attr}")
        elif isinstance(node, ast.Name) and node.id in _SEND_SYMBOLS:
            bad.append(node.id)
        elif isinstance(node, ast.Call):
            if _reflected_name(node) in _SEND_SYMBOLS:
                bad.append(f"reflected {_reflected_name(node)}")
    return bad


def test_the_state_parser_cannot_send_a_keystroke():
    """A read verb's substrate must not be able to drive. Enforced, not
    asserted -- and with a positive control, because without one this passes
    on a broken parse or a blocklist that matches nothing."""
    assert _send_violations("from .session import Session") != []
    assert _send_violations("import socket") != []
    assert _send_violations("conn.send_raw('P')") != []
    assert _send_violations("getattr(conn, 'send_key')('P')") != []
    assert _send_violations("import re\nfrom dataclasses import dataclass") == []

    assert _send_violations(STATE_PARSER_SRC.read_text(encoding="utf-8")) == []


def test_the_state_parser_is_pure_and_imports_nothing_live():
    """It reads text and returns a verdict: no filesystem, no clock, no
    session. That is what lets a caller trust that two identical screens
    produce two identical answers."""
    tree = ast.parse(STATE_PARSER_SRC.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"re", "dataclasses", "typing", "__future__"}, imported


def test_no_player_and_no_anchor_comparison_snuck_in():
    """The slice boundary, enforced. X1 produces the read; comparing it to a
    macro's `start_anchor`, deciding to halt, and pressing anything are X3's,
    and none of them is licensed here. A `start_anchor` mentioned in prose is
    fine; one that is CODE is the boundary being crossed."""
    source = STATE_PARSER_SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Docstring nodes are `Constant`s too, and this module's prose mentions
    # `start_anchor` repeatedly on purpose. Exclude them BY NODE IDENTITY
    # rather than by text pattern -- a text-pattern exclusion is how a
    # vocabulary ban quietly stops covering anything.
    doc_values = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    assert doc_values  # the exclusion set is non-empty, or this proves nothing
    live_strings = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in doc_values
    ]
    assert "start_anchor" in source  # the prose does discuss it...
    assert "start_anchor" not in live_strings  # ...and no live code names it

    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert names.isdisjoint({"start_anchor", "replay", "load_loop", "Loop"})

    writes = [
        n.func.attr
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in {"write_text", "write_bytes", "mkdir", "unlink", "rename", "dump"}
    ]
    assert writes == []
