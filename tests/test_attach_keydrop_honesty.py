"""WO-AUDIT-KEYDROP-HONESTY (session-audit F2) — the ``attach`` verb must
never answer ``{"ok": true}`` for a keystroke that did not reach the wire.

``daemon.py::_handle_attach`` encoded the incoming key with
``key.encode("latin-1", errors="ignore")``. Every character above U+00FF
became ``b""``; ``send_raw(b"")`` reached ``sendall(b"")`` (a no-op) and the
daemon still answered ``{"ok": true}``. Three surfaces then disagreed about
that same non-event, which is what makes it a lie rather than merely a drop:

* the transcript log stayed **silent** — nothing was written,
* ``last_sent`` (served to every spectator via ``build_response``) reported
  an **empty send**,
* the LOGS tail gained a **phantom** ``human> `` row.

Both refusals are proven over a REAL ``ThreadingUnixServer`` +
``CommandHandler`` on a REAL unix socket — the same standard the audit used
to find the defect — because the claim under test ("the daemon answers X")
is a claim about the wire protocol, not about a function's return value.

Two client shapes matter and only one of them is the shipped client:

* ``AttachInputConn.send_key()`` takes *bytes* and latin-1-decodes them, so
  it structurally cannot put a non-latin-1 string on the wire. Reaching the
  ``unencodable_key`` branch therefore requires a raw frame, which is why
  ``_AttachWire`` below exists rather than reusing the production client.
* The shipped client refuses the character before the wire
  (``cli.py::cmd_attach``), so these errors are its belt-and-braces backstop
  — the contract *any other* client gets. That is a deliberate second layer,
  not dead code, and the tests say so rather than implying coverage of a
  path the product cannot take.
"""

from __future__ import annotations

import json
import socket
import tempfile
import threading
import time
from pathlib import Path

import pytest

from tw2002_aiclient.session.control_lock import MODE_HUMAN
from tw2002_aiclient.session.daemon import CommandHandler, ThreadingUnixServer
from tw2002_aiclient.session.session import Session

from .conftest import FAKE_HOST, FAKE_PORT

# The latin-1 boundary itself, pinned as data rather than described in prose:
# U+00FF is the last character with an 8-bit form, U+0100 the first without.
LAST_ENCODABLE = "ÿ"       # ÿ  -> b"\xff"
FIRST_UNENCODABLE = "Ā"    # Ā  -> no 8-bit form
RIGHTWARDS_ARROW = "→"     # →  the audit's own reproduction character


class _AttachWire:
    """A minimal raw ``attach`` client: one JSON frame in, one out.

    Deliberately NOT ``AttachInputConn`` — that class takes ``bytes`` and
    latin-1-decodes them, so it cannot express ``{"key": "→"}`` at all.
    This stands in for any other client of the daemon's wire protocol.
    """

    def __init__(self, sock_path):
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.settimeout(5.0)
        self._sock.connect(str(sock_path))
        self._file = self._sock.makefile("rwb")
        self.ack = self._frame({"verb": "attach", "args": {}})

    def _frame(self, obj):
        self._file.write((json.dumps(obj) + "\n").encode("utf-8"))
        self._file.flush()
        line = self._file.readline()
        assert line, "daemon closed the attach connection instead of replying"
        return json.loads(line.decode("utf-8"))

    def key(self, text):
        return self._frame({"key": text})

    def close(self):
        try:
            self._file.close()
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass


# -- the defect: a refusal, never a delivery claim -------------------------

@pytest.mark.parametrize(
    "text, expected_error",
    [
        (RIGHTWARDS_ARROW, "unencodable_key"),
        (FIRST_UNENCODABLE, "unencodable_key"),
        ("\U0001f680", "unencodable_key"),   # an emoji — the pasted case
        ("a→b", "unencodable_key"),     # PARTIAL: refuse, never send "ab"
        ("", "empty_key"),                   # present, well-formed, zero bytes
    ],
)
def test_a_key_that_cannot_reach_the_wire_is_refused(fake_daemon, text, expected_error):
    """No ``{"ok": true}`` for a non-delivery, and nothing forwarded.

    The partial case is the sharpest of these: ``errors="ignore"`` would have
    delivered ``b"ab"`` — not nothing, but *different bytes than the operator
    asked for* — and still called it success.
    """
    wire = _AttachWire(fake_daemon.sock_path)
    try:
        assert wire.ack["ok"] is True, wire.ack

        resp = wire.key(text)

        assert resp["ok"] is False, f"delivery claimed for {text!r}"
        assert resp["error"] == expected_error, resp
        assert fake_daemon.session.raw_sent == [], (
            "a refused key must not reach send_raw at all — an empty forward is "
            "what produces the phantom LOGS row and the empty last_sent"
        )
    finally:
        wire.close()


def test_the_encodable_boundary_still_goes_through(fake_daemon):
    """The refusal is scoped to what genuinely has no 8-bit form. U+00FF is
    the last character that does, so it must still be forwarded — a fix that
    also refused it would be an over-correction that silently narrows what
    the pilot can type."""
    wire = _AttachWire(fake_daemon.sock_path)
    try:
        resp = wire.key(LAST_ENCODABLE)

        assert resp["ok"] is True, resp
        assert fake_daemon.session.raw_sent == [b"\xff"]
    finally:
        wire.close()


# -- Accept #3 at the daemon layer: a refusal must not end anything --------

def test_a_refused_key_does_not_end_the_attach_session(fake_daemon):
    """The operator keeps flying. After a refusal the SAME connection still
    carries the next real keystroke — proving the refusal is a per-frame
    answer, not a connection-level failure.

    This is the daemon-side half of "an unencodable keystroke does not end
    attach"; the client-side half is proven end-to-end on a real pty in
    tests/test_cli_attach_unencodable_pty.py.
    """
    wire = _AttachWire(fake_daemon.sock_path)
    try:
        assert wire.key(RIGHTWARDS_ARROW)["ok"] is False
        assert wire.key("")["ok"] is False

        resp = wire.key("d")

        assert resp["ok"] is True, resp
        assert fake_daemon.session.raw_sent == [b"d"], (
            "the keystroke after a refusal must still reach the game"
        )
    finally:
        wire.close()


def test_a_refused_key_does_not_release_the_human_control_lock(fake_daemon):
    """A refusal must not hand the seat back to the App. ``_handle_attach``'s
    ``finally: lock.release_human()`` runs on ANY exit from that loop, so a
    refusal that returned instead of continuing would silently drop MODE_HUMAN
    while the operator still believed they held the keyboard."""
    wire = _AttachWire(fake_daemon.sock_path)
    try:
        assert wire.key(RIGHTWARDS_ARROW)["ok"] is False

        assert fake_daemon.control_lock.mode == MODE_HUMAN
    finally:
        wire.close()


# -- the three surfaces, against a REAL Session ---------------------------

class _StubSocket:
    """Records what actually reached the wire. Mirrors the stub in
    tests/test_attach_redaction.py."""

    def __init__(self):
        self.sent = []

    def sendall(self, data):
        self.sent.append(data)


class _RealSessionDaemon:
    """Real ``ThreadingUnixServer`` + ``CommandHandler`` in front of a REAL
    ``Session`` whose socket is stubbed.

    ``fake_daemon``'s ``FakeAttachSession`` cannot prove this: the phantom
    ``human> `` row and the silent transcript are produced by the real
    ``Session.send_raw`` (session.py), so only the real one can show they are
    gone. No network — the stub socket is the wire.
    """

    def __init__(self, sock_path, log_dir):
        from tw2002_aiclient.session.control_lock import ControlLock

        self.session = Session(FAKE_HOST, FAKE_PORT, None, str(log_dir))
        self.wire = _StubSocket()
        self.session.conn._sock = self.wire
        self.session.terminal.feed(b"Command [TL=00:00:00]:[1] (?=Help)? : ")

        self.sock_path = str(sock_path)
        self.server = ThreadingUnixServer(self.sock_path, CommandHandler)
        self.server.session = self.session
        self.server.control_lock = ControlLock()
        self.server.watch_hub = None
        self.server.request_stop = lambda: None
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.session.logger.close()


@pytest.fixture
def real_session_daemon(tmp_path):
    # mkdtemp, not tmp_path: pytest's tmp_path routinely overflows AF_UNIX's
    # ~104-byte sun_path limit.
    sock_dir = tempfile.mkdtemp(prefix="twd-f2-")
    daemon = _RealSessionDaemon(Path(sock_dir) / "s.sock", tmp_path)
    try:
        yield daemon
    finally:
        daemon.stop()


def test_refused_key_leaves_all_three_surfaces_agreeing_nothing_happened(
    real_session_daemon,
):
    """The audit's actual finding, closed: wire, ``last_sent`` and the LOGS
    tail must all report the same non-event.

    Pre-fix these three disagreed — ``sendall(b"")`` (nothing), ``last_sent``
    ``""`` (an empty send), and a ``human> `` row (something happened). The
    transcript's silence was the only honest one of the three.
    """
    wire = _AttachWire(real_session_daemon.sock_path)
    try:
        resp = wire.key(RIGHTWARDS_ARROW)
        assert resp == {"ok": False, "error": "unencodable_key"}, resp

        session = real_session_daemon.session
        assert real_session_daemon.wire.sent == [], "nothing may reach the wire"
        assert session.last_sent is None, (
            "last_sent is served to every spectator — it must not report an "
            "empty send for a keystroke that never left the client"
        )
        assert session.tail.snapshot() == [], (
            "no phantom 'human> ' row: the LOGS tail must not show a keystroke "
            "the game never received"
        )
    finally:
        wire.close()


def test_a_delivered_key_still_marks_all_three_surfaces(real_session_daemon):
    """The other half of the same claim: when a key IS delivered, all three
    surfaces must say so. Without this, 'the surfaces agree' would be
    satisfiable by a fix that simply stopped recording anything at all."""
    wire = _AttachWire(real_session_daemon.sock_path)
    try:
        assert wire.key("d")["ok"] is True

        session = real_session_daemon.session
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not real_session_daemon.wire.sent:
            time.sleep(0.02)

        assert real_session_daemon.wire.sent == [b"d"]
        assert session.last_sent == "d"
        assert session.tail.snapshot() == ["human> d"]
    finally:
        wire.close()
