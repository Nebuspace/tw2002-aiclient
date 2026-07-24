"""Session-side redacted transcript ring buffer (WO-P3-041 LOGS band).

Proves `tw2002_aiclient/session/transcript_tail.py` in three layers:
  1. The module in isolation -- ring bounds, the redacted marker, snapshot
     isolation (`TestTranscriptTailUnit` below).
  2. The real wiring seams -- `Session.send()`/`Session.send_raw()`
     (`session.py`) append at the exact same `secret` decision already
     threaded into the real transcript logger's `log_raw`/`log_redacted`
     sink, and `protocol.py`'s `status` verb serves the snapshot
     additively as `log_tail`.
  3. An end-to-end proof, driving the REAL login automaton
     (`tw2002_aiclient/session/login.py`) against a scripted fake TWGS
     server (`tests/fake_twgs.py`) with a sentinel password, then reading
     it back off the REAL `status` verb response -- the sentinel must
     appear nowhere in that response while the redaction marker does.

Session-level tests reuse the same real-`Session`-plus-stub-socket shape
`tests/test_attach_redaction.py` already established (a real `Session`
object, `session.conn._sock` swapped for a discard-only stub so no actual
network I/O happens) -- not a hand-mocked approximation of the send path.
"""

from __future__ import annotations

import json

from tw2002_aiclient.session import login, protocol
from tw2002_aiclient.session.session import Session
from tw2002_aiclient.session.transcript_tail import TAIL_MAX, TranscriptTail

from .conftest import FAKE_HOST, FAKE_PORT
from .fake_twgs import FakeTWGS

SENTINEL = "SENTINEL-hunter2-SENTINEL"


class _StubSocket:
    """Discards every byte instead of touching a real network socket --
    matches tests/test_attach_redaction.py's own `_StubSocket`."""

    def sendall(self, data):
        pass


def _make_session(tmp_path, screen_bytes=b"Command [TL=00:00:00]:[1] (?=Help)? :"):
    session = Session(FAKE_HOST, FAKE_PORT, None, str(tmp_path))
    session.conn._sock = _StubSocket()
    session.terminal.feed(screen_bytes)
    return session


# -- 1. TranscriptTail in isolation ------------------------------------------


class TestTranscriptTailUnit:
    def test_ring_bounds_overflow_drops_oldest_order_preserved_newest_last(self):
        tail = TranscriptTail(maxlen=3)
        for i in range(5):
            tail.append_line(f"line-{i}")
        assert tail.snapshot() == ["line-2", "line-3", "line-4"]

    def test_default_maxlen_matches_tail_max_constant(self):
        tail = TranscriptTail()
        for i in range(TAIL_MAX + 10):
            tail.append_line(f"line-{i}")
        snap = tail.snapshot()
        assert len(snap) == TAIL_MAX
        assert snap[0] == f"line-{10}"  # oldest 10 dropped
        assert snap[-1] == f"line-{TAIL_MAX + 9}"

    def test_append_redacted_inserts_marker_mirroring_logging_util_wording(self):
        tail = TranscriptTail()
        tail.append_redacted()
        assert tail.snapshot() == ["<<secret input redacted>>"]

    def test_append_redacted_custom_note_still_only_a_note_no_payload_param(self):
        tail = TranscriptTail()
        tail.append_redacted(note="custom marker")
        assert tail.snapshot() == ["<<custom marker>>"]

    def test_falsification_append_line_is_not_itself_the_guard(self):
        """`append_line()` has no notion of "secret" -- it stores exactly
        what it's handed. This is the mandatory falsification for the
        marker test above: if `Session` ever mistakenly called
        `append_line(secret_text)` instead of `append_redacted()`, THIS
        module would happily store the payload -- proving the redaction
        guarantee lives in the CALLER'S branch choice (see the Session-
        level tests below), not in some magic inside this class."""
        tail = TranscriptTail()
        tail.append_line(SENTINEL)
        assert tail.snapshot() == [SENTINEL]

    def test_snapshot_isolation_mutating_returned_list_does_not_touch_ring(self):
        tail = TranscriptTail()
        tail.append_line("a")
        snap = tail.snapshot()
        snap.append("b")
        snap[0] = "mutated"
        assert tail.snapshot() == ["a"]


# -- 2. Session.send() / Session.send_raw() wiring ---------------------------


def test_session_send_non_secret_appends_direction_and_sender_tagged_line(tmp_path):
    session = _make_session(tmp_path)
    session.send("BUY", sender="app")
    assert session.tail.snapshot() == ["app> BUY"]


def test_session_send_secret_appends_only_the_marker_never_the_text(tmp_path):
    session = _make_session(tmp_path)
    session.send(SENTINEL, secret=True, sender="app")
    snap = session.tail.snapshot()
    assert snap == ["<<secret input redacted>>"]
    assert SENTINEL not in snap[0]


def test_session_send_raw_non_secret_appends_per_keystroke_sender_tagged_line(tmp_path):
    session = _make_session(tmp_path, screen_bytes=b"Command [TL=00:00:00]:[1] (?=Help)? :")
    session.send_raw(b"H", sender="human")
    session.send_raw(b"I", sender="human")
    assert session.tail.snapshot() == ["human> H", "human> I"]


def test_session_send_raw_secret_prompt_appends_only_markers_never_cleartext(tmp_path):
    session = _make_session(tmp_path, screen_bytes=b"Password:")
    for ch in SENTINEL:
        session.send_raw(ch.encode("latin-1"), sender="human")
    snap = session.tail.snapshot()
    assert snap == ["<<secret input redacted>>"] * len(SENTINEL)
    assert all(SENTINEL not in line for line in snap)


def test_falsification_broken_secret_classifier_would_leak_into_tail(tmp_path, monkeypatch):
    """Mandatory falsification for the send_raw() secret path: patches
    `is_probable_secret_prompt` (as imported into session.py's own
    namespace -- the exact name `send_raw()` calls) to always report
    "not a secret prompt", simulating a broken/bypassed classifier, and
    confirms the SAME password-prompt scenario that was green above now
    leaks the sentinel into the tail. A green test that can't be made to
    fail this way would prove nothing. `monkeypatch` reverts automatically
    at teardown."""
    from tw2002_aiclient.session import session as session_module

    monkeypatch.setattr(session_module, "is_probable_secret_prompt", lambda _prompt: False)
    session = _make_session(tmp_path, screen_bytes=b"Password:")
    session.send_raw(SENTINEL[0].encode("latin-1"), sender="human")
    snap = session.tail.snapshot()
    assert snap == [f"human> {SENTINEL[0]}"]  # RED: the leak is caught


# -- 3. protocol.py `status` verb: additive `log_tail` -----------------------


class _BareServer:
    """No `control_lock`/`watch_hub` -- protocol.py's status branch reads
    both via `getattr(..., None)`, matching test_ensure_no_auto_arm.py's
    own bare `FakeServer` convention."""


class _TailLessFakeSession:
    """Just enough surface for `build_response()` -- deliberately has NO
    `.tail` attribute, standing in for a pre-WO-P3-041 test double (e.g.
    tests/test_watch.py's own `FakeSession`) -- proves the `status` verb's
    `log_tail` wiring is additive-safe against callers that predate it."""

    def __init__(self):
        self.conn = type("C", (), {"connected": True})()
        self.last_rx = 0.0
        self.last_sent = None
        self.host = "127.0.0.1"
        self.port = 23
        self.name = "twd"

    def render(self):
        return ["Command [TL=1000]"]

    def render_text(self, rows=None):
        return "\n".join(rows if rows is not None else self.render())


def test_status_verb_carries_log_tail_from_a_real_session(tmp_path):
    session = _make_session(tmp_path)
    session.send("N", sender="app")
    resp = protocol.dispatch(session, "status", {}, _BareServer())
    assert resp["ok"] is True
    assert resp["log_tail"] == ["app> N"]


def test_status_verb_log_tail_defaults_empty_list_without_a_tail_attribute():
    session = _TailLessFakeSession()
    resp = protocol.dispatch(session, "status", {}, _BareServer())
    assert resp["ok"] is True
    assert resp["log_tail"] == []
    # Existing fields untouched -- additive-only.
    assert resp["connected"] is True
    assert resp["host"] == "127.0.0.1"


# -- 4. End-to-end: real login automaton against a fake TWGS server ---------


def test_end_to_end_sentinel_password_never_reaches_status_response(tmp_path):
    handle, game_letter = "AEGIS", "F"
    fake = FakeTWGS(handle=handle, game_letter=game_letter, password=SENTINEL, mode="returning")

    with fake:
        session = Session("127.0.0.1", fake.port, "wo-p3-041", str(tmp_path))
        session.start(timeout=10)
        try:
            profile = login.LoginProfile(
                name="wo-p3-041", handle=handle, game_letter=game_letter, allow_register=False
            )
            saved = {"wo-p3-041": SENTINEL}
            cls, _steps = login.run_login(
                session,
                profile,
                get_password=lambda n: saved.get(n),
                save_password=lambda n, pw: None,
            )
            assert cls == "main_command"

            resp = protocol.dispatch(session, "status", {}, _BareServer())
        finally:
            session.close()

    assert not fake.errors, fake.errors
    assert resp["ok"] is True

    # Positive signal first -- the redaction marker actually fired, so an
    # "absence" assertion below can't be vacuously true because nothing
    # was ever redacted at all.
    assert "<<secret input redacted>>" in resp["log_tail"]

    # Sentinel absent from the tail specifically...
    assert all(SENTINEL not in line for line in resp["log_tail"])
    # ...and from the WHOLE status response (the exact shape the cockpit
    # composer / CLI JSON encoder will actually see over the wire).
    dumped = json.dumps(resp)
    assert SENTINEL not in dumped
