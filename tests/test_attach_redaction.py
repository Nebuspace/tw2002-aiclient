"""WO-CLEANPREEMPT secret sub-diff: cipher's proven leak, flipped
end-to-end against REAL production code -- `twclient.session.Session.
send_raw()` -> `twclient.connection.TelnetConnection.send_bytes()` ->
`twclient.logging_util.TranscriptLogger` (the LOG sink), `twclient.
protocol.record_attach_keystroke()` -> a REAL `twclient.ledger.
LedgerWriter` (the LEDGER sink), and `session.last_sent` ->
`protocol.build_response()`'s `sent_input` field (the THIRD sink --
`tw watch`/`tw spectate`'s TX-channel and any `build_response`-based verb
read a secret attach keystroke through exactly this field, confirmed via
`watch.py`'s own `build_response(self.session)` calls) -- not a
hand-mirrored approximation of any of the three chains.

Background: cipher's repro showed every `tw attach` keystroke was logged
UNREDACTED regardless of what prompt it was answering (`connection.
send_bytes` unconditionally `log_raw()`'d every byte) -- a human-typed
password at a `Password:` prompt landed cleartext in the transcript.
This file proves a KNOWN SENTINEL, typed char-by-char exactly like a real
interactive keystroke stream, never lands in cleartext in any of the
three sinks, across the ordinary case, a broadened secret-anchor case
(PIN), and the staleness case (mack's finding: the screen transitions to
a secret prompt DURING send_raw()'s fence-wait).

**Methodology note (matches tests/test_login_redaction.py's own
finding):** a bare interactive-shell `grep` can be FALSE-CLEAN against a
transcript containing NUL/control/ANSI bytes -- every log-content check
here uses Python-level `open(...).read()`/`open(..., "rb").read()` + `in`
(bypasses any shell grep function's `-I` heuristic entirely) or the
`_grep_a_contains()` helper (`grep -a`, force-text), cross-imported from
test_login_redaction.py rather than re-implemented."""

import threading
import time

from twclient import protocol
from twclient.connection import TelnetConnection
from twclient.control_lock import ControlLock
from twclient.ledger import LedgerWriter, read_entries
from twclient.logging_util import TranscriptLogger
from twclient.session import Session

from .conftest import FAKE_HOST, FAKE_PORT
from .test_login_redaction import _grep_a_contains

SENTINEL = "HUNTER2SENTINEL"


class _StubSocket:
    """Discards every byte instead of touching a real network socket --
    same convention as tests/test_login_redaction.py's own _StubSocket."""

    def sendall(self, data):
        pass


class _FakeLedgerServer:
    def __init__(self, ledger):
        self.ledger = ledger


def _make_session(tmp_path, screen_bytes):
    """A real Session, network-free (bare construction never touches the
    socket -- only .start()/.reconnect() do), with its terminal seeded to
    `screen_bytes` and its connection's socket stubbed so send_raw()'s
    eventual `conn.send_bytes()` -> `sock.sendall()` is a real no-op
    rather than a network call."""
    session = Session(FAKE_HOST, FAKE_PORT, None, tmp_path)
    session.conn._sock = _StubSocket()
    session.terminal.feed(screen_bytes)
    return session


def _typed_content_from_log(log_content):
    """Reconstructs exactly what was typed from a raw transcript, since
    `send_raw()` calls `send_bytes()` ONCE PER KEYSTROKE -- each
    character lands on its OWN `log_raw()` line, so a multi-character
    sentinel never appears as one contiguous substring in the log
    regardless of redaction; checking `SENTINEL in log_content` is the
    WRONG test for a char-by-char keystroke stream. `log_raw()`'s own
    two-line shape (`"[{ts}] {direction} (...)\\n{text}\\n"`) and
    `log_redacted()`'s one-line shape (`"[{ts}] {direction} <<...>>\\n"`)
    both put every TIMESTAMP/header line at the start of a bracket
    ("[") -- filtering those out and joining what's left reconstructs
    the typed sequence precisely: the real characters when unredacted,
    or nothing at all when every keystroke was redacted."""
    return "".join(line for line in log_content.splitlines() if not line.startswith("["))


def _type_sentinel_via_attach(session, server, sentinel, control_lock=None):
    """Drives `sentinel` through the REAL attach keystroke path, one
    character at a time, byte-for-byte the same shape daemon.py's real
    `CommandHandler._handle_attach` loop uses: capture `pre_text` ->
    `session.send_raw()` -> `protocol.record_attach_keystroke()` reading
    back `session.last_sent`/`session.last_sent_secret`."""
    for ch in sentinel:
        pre_text = session.render_text(session.render())
        session.send_raw(ch.encode("latin-1"), control_lock=control_lock)
        protocol.record_attach_keystroke(
            server, session, pre_text, session.last_sent, session.last_sent_secret
        )


# -- the flip of cipher's repro: a password prompt --------------------------


def test_flip_ciphers_repro_sentinel_typed_at_password_prompt_never_leaks(tmp_path):
    session = _make_session(tmp_path, b"Password:")
    ledger_path = tmp_path / "ledger.jsonl"
    server = _FakeLedgerServer(LedgerWriter(path=ledger_path))

    _type_sentinel_via_attach(session, server, SENTINEL)
    session.logger.close()

    log_content = open(session.logger.path, encoding="utf-8").read()
    assert SENTINEL not in log_content
    assert _typed_content_from_log(log_content) == ""  # nothing reconstructs at all
    # An "absence" assertion alone can't distinguish "properly redacted"
    # from "this code path never ran at all" -- confirm log_redacted()'s
    # own marker actually fired, once per keystroke.
    assert log_content.count("secret input redacted") == len(SENTINEL)
    assert SENTINEL.encode() not in open(session.logger.path, "rb").read()
    assert _grep_a_contains(session.logger.path, SENTINEL) is False

    entries = read_entries(path=ledger_path)
    assert len(entries) == len(SENTINEL)
    assert all(e["input"] == "<redacted>" for e in entries)
    raw_ledger = open(ledger_path, encoding="utf-8").read()
    assert SENTINEL not in raw_ledger
    assert _grep_a_contains(ledger_path, SENTINEL) is False


def test_falsification_removing_the_log_gate_lets_the_sentinel_leak_RED(tmp_path, monkeypatch):
    """Sensitivity control (mandatory falsification, matching
    test_login_redaction.py's own convention): temporarily patches
    `TelnetConnection.send_bytes` back to the exact PRE-FIX body (secret
    accepted but never consulted) and confirms the SAME scenario that
    was green above now goes RED -- a green test that can't be made to
    fail this way would prove nothing."""

    def _leaky_send_bytes(self, data, secret=False):
        if self.logger:
            self.logger.log_raw("TX", data)
        self._sock.sendall(data)

    monkeypatch.setattr(TelnetConnection, "send_bytes", _leaky_send_bytes)

    session = _make_session(tmp_path, b"Password:")
    ledger_path = tmp_path / "ledger.jsonl"
    server = _FakeLedgerServer(LedgerWriter(path=ledger_path))

    _type_sentinel_via_attach(session, server, SENTINEL)
    session.logger.close()

    log_content = open(session.logger.path, encoding="utf-8").read()
    # RED: with the log-gate bypassed, the FULL sentinel reconstructs
    # from the raw per-keystroke lines -- the leak is caught.
    assert _typed_content_from_log(log_content) == SENTINEL


def test_falsification_confirms_default_send_bytes_still_redacts(tmp_path):
    """Sanity bookend to the RED test above: with NO monkeypatch, the
    identical scenario is green again in the SAME test module/process --
    proving the RED result above was caused by the monkeypatch, not by
    process-wide state the previous test left behind."""
    session = _make_session(tmp_path, b"Password:")
    ledger_path = tmp_path / "ledger.jsonl"
    server = _FakeLedgerServer(LedgerWriter(path=ledger_path))

    _type_sentinel_via_attach(session, server, SENTINEL)
    session.logger.close()

    log_content = open(session.logger.path, encoding="utf-8").read()
    assert SENTINEL not in log_content
    assert "secret input redacted" in log_content


# -- broadened secret anchor: PIN, not "password" ---------------------------


def test_pin_prompt_sentinel_never_leaks_fail_safe_broadened_anchor(tmp_path):
    """cipher's second finding: `Enter PIN:` has no "password" substring
    at all -- the narrow `login_password` anchor alone would have missed
    it. `is_probable_secret_prompt()`'s broadened, fail-safe anchor
    catches it."""
    session = _make_session(tmp_path, b"Enter PIN:")
    ledger_path = tmp_path / "ledger.jsonl"
    server = _FakeLedgerServer(LedgerWriter(path=ledger_path))
    pin_sentinel = "13375ENTINEL"

    _type_sentinel_via_attach(session, server, pin_sentinel)
    session.logger.close()

    log_content = open(session.logger.path, encoding="utf-8").read()
    assert pin_sentinel not in log_content
    entries = read_entries(path=ledger_path)
    assert all(e["input"] == "<redacted>" for e in entries)


def test_ordinary_command_prompt_sentinel_is_not_redacted_sensitivity_control(tmp_path):
    """Sensitivity control for both tests above: an ORDINARY screen must
    NOT be redacted -- proving the green results are a real signal keyed
    on the screen's shape, not a check that always redacts."""
    session = _make_session(tmp_path, b"Command [TL=00:00:00]:[1] (?=Help)? :")
    ledger_path = tmp_path / "ledger.jsonl"
    server = _FakeLedgerServer(LedgerWriter(path=ledger_path))
    plain_text = "HELLO"

    _type_sentinel_via_attach(session, server, plain_text)
    session.logger.close()

    log_content = open(session.logger.path, encoding="utf-8").read()
    # NOT redacted -- an ordinary keystroke stream reconstructs in full.
    assert _typed_content_from_log(log_content) == plain_text
    entries = read_entries(path=ledger_path)
    assert all(e["input"] != "<redacted>" for e in entries)


# -- documented residual: a secret-entry prompt with no keyword at all ------


def test_documented_residual_a_prompt_with_no_secret_keyword_is_not_redacted(tmp_path):
    """The KNOWN, DOCUMENTED gap (classify.is_probable_secret_prompt()'s
    own docstring): a secret-entry prompt phrased with none of this
    predicate's keywords has no signal it can key on. Pinned down here,
    not silently assumed complete -- this is a real, accepted residual of
    a best-effort, fail-safe-biased heuristic, not a regression."""
    session = _make_session(tmp_path, b"Speak, friend, and enter:")
    ledger_path = tmp_path / "ledger.jsonl"
    server = _FakeLedgerServer(LedgerWriter(path=ledger_path))
    riddle_answer = "MELLON"

    _type_sentinel_via_attach(session, server, riddle_answer)
    session.logger.close()

    log_content = open(session.logger.path, encoding="utf-8").read()
    # The documented gap -- not redacted, reconstructs in full.
    assert _typed_content_from_log(log_content) == riddle_answer


# -- staleness: the screen becomes secret DURING the fence-wait ------------


def test_staleness_screen_becomes_secret_during_the_fence_wait_still_redacted(tmp_path):
    """mack's staleness finding, proven end-to-end through the REAL log
    file (not just a mocked send_bytes call, unlike tests/test_session.py's
    own unit-level version of this same scenario): the screen transitions
    from ordinary to a secret prompt WHILE send_raw() is still blocked in
    its fence-wait -- the eventual send must reflect the screen AS OF the
    moment the wait resolves, never the stale pre-wait snapshot."""
    session = _make_session(tmp_path, b"Command [TL=00:00:00]:[1] (?=Help)? :")
    ledger_path = tmp_path / "ledger.jsonl"
    server = _FakeLedgerServer(LedgerWriter(path=ledger_path))
    lock = ControlLock()
    lock.acquire_driver()
    lock.take_human()  # fences the in-flight "dispatch"

    pre_text = session.render_text(session.render())
    result = {}

    def send_call():
        session.send_raw(SENTINEL[0].encode("latin-1"), control_lock=lock)
        result["done"] = True

    t = threading.Thread(target=send_call)
    t.start()
    time.sleep(0.15)  # still fenced -- the screen is still the ORDINARY one
    assert "done" not in result

    # The screen transitions to a genuine secret prompt WHILE still fenced.
    session.terminal.feed(b"\x1b[2J\x1b[HPassword:")
    lock.release_driver()  # NOW the fence clears -- send_raw's render() happens after this
    t.join(timeout=2.0)
    assert result.get("done") is True

    protocol.record_attach_keystroke(server, session, pre_text, session.last_sent, session.last_sent_secret)
    session.logger.close()

    # The decision reflects the POST-transition screen, not the stale
    # pre-wait one (which would have wrongly read secret=False) --
    # checked at every layer this decision reaches: the session's own
    # exposed flag, the transcript log's redaction marker (never the
    # raw keystroke line `log_raw` would have written), and the ledger.
    assert session.last_sent_secret is True
    log_content = open(session.logger.path, encoding="utf-8").read()
    assert "secret input redacted" in log_content
    assert "TX (1 bytes)" not in log_content  # the shape log_raw() would have used instead
    entries = read_entries(path=ledger_path)
    assert entries[0]["input"] == "<redacted>"


# -- the THIRD sink: `last_sent` -> build_response()'s `sent_input` field
# (tw watch/tw spectate's TX-channel, and any build_response-based verb) ---


def test_secret_attach_keystroke_redacts_last_sent_so_sent_input_never_leaks(tmp_path):
    """The third sink cipher's own repro didn't originally target but the
    hub caught: `session.last_sent` feeds `build_response()`'s
    `sent_input` field directly (`protocol.py`) -- the same field
    `watch.py`'s `WatchHub` reads via `build_response(self.session)` for
    every `tw watch`/`tw spectate` TX-channel event. Redacting
    `last_sent` at the SOURCE (send_raw()) closes this without touching
    watch.py/interactive_app.py/spectate at all -- proven here by driving
    the REAL `protocol.dispatch(..., "screen", ...)` verb (the one-shot
    CLI equivalent of the same `build_response()` chokepoint) after a
    secret keystroke."""
    session = _make_session(tmp_path, b"Password:")
    server = _FakeLedgerServer(LedgerWriter(path=tmp_path / "ledger.jsonl"))

    session.send_raw(SENTINEL[0].encode("latin-1"))

    assert session.last_sent == "<redacted>"
    resp = protocol.dispatch(session, "screen", {}, server)
    assert resp["ok"] is True
    assert resp["sent_input"] == "<redacted>"
    assert SENTINEL[0] != resp["sent_input"]


def test_ordinary_attach_keystroke_leaves_last_sent_unredacted_sensitivity_control(tmp_path):
    """Sensitivity control for the test above: an ORDINARY screen must
    leave `last_sent`/`sent_input` as the real character -- proving the
    green result above is a real signal keyed on the screen's shape, not
    a check that always redacts."""
    session = _make_session(tmp_path, b"Command [TL=00:00:00]:[1] (?=Help)? :")
    server = _FakeLedgerServer(LedgerWriter(path=tmp_path / "ledger.jsonl"))

    session.send_raw(b"H")

    assert session.last_sent == "H"
    resp = protocol.dispatch(session, "screen", {}, server)
    assert resp["ok"] is True
    assert resp["sent_input"] == "H"
