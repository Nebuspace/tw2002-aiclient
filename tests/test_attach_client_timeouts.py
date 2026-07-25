"""AttachInputConn socket-op timeouts (HARDEN-ATTACH).

Cipher's WO-P4-056 audit finding: ``AttachInputConn`` performed unbounded
socket reads (no ``settimeout``) -- worst case, the play cockpit hangs
forever mid-keystroke on a wedged daemon. Proves the fix by driving each
blocking op against a deliberately-wedged fake unix-socket server in a
watchdog thread and asserting the op RETURNS (with the existing honest
failure result) within a bound comfortably above ``_SOCKET_TIMEOUT_S`` --
never by letting the test itself hang.

Red-first evidence (recorded, not re-run here -- this file only proves the
POST-fix bound): against the exact pre-fix git blob
(``git show HEAD:tw2002_aiclient/session/attach_client.py`` at
e243bc2fc1becb6af9b8c43ccefd338ad03f5246, before this WO's commit),

    connect() vs fully-silent daemon:       still_alive=True elapsed=10.01s (bound=10.0s)
    connect() vs acks-then-wedges daemon:   succeeded=True
    send_key() vs acks-then-wedges daemon:  still_alive=True elapsed=10.00s (bound=10.0s)

i.e. both operations were still blocked at a 10s bound (double the fix's
5.0s timeout) with no way to return.
"""

from __future__ import annotations

import json
import socket
import tempfile
import threading
import time

import pytest

from tw2002_aiclient.session.attach_client import _SOCKET_TIMEOUT_S, AttachInputConn

# Comfortably above the real timeout so a passing test isn't a coin-flip on
# scheduler jitter, while still being tight enough to prove a bound exists
# (not just "eventually finishes").
_WATCHDOG_BOUND_S = _SOCKET_TIMEOUT_S + 5.0


class _FullySilentServer:
    """Accepts a connection, then never reads and never writes -- wedges
    ``connect()``'s own ack-read (and, if it were unbounded, the write/
    flush too, though a one-line JSON message never blocks on a local
    socket's send buffer)."""

    def __init__(self, sock_path):
        self.sock_path = str(sock_path)
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.sock_path)
        self._server.listen(1)
        self._stop = threading.Event()
        self._conns = []
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        self._server.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
                self._conns.append(conn)  # accepted, then deliberately silent forever
            except socket.timeout:
                continue
            except OSError:
                return

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
        for c in self._conns:
            try:
                c.close()
            except OSError:
                pass
        try:
            self._server.close()
        except OSError:
            pass


class _ConnectsThenWedgesServer:
    """Acks the initial ``{"verb": "attach"}`` request (so ``connect()``
    succeeds and the control-lock handshake completes), then goes silent
    forever -- wedges ``send_key()``'s own ack-read."""

    def __init__(self, sock_path):
        self.sock_path = str(sock_path)
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.sock_path)
        self._server.listen(1)
        self._stop = threading.Event()
        self._conns = []
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        self._server.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self._conns.append(conn)
            try:
                f = conn.makefile("rwb")
                line = f.readline()
                if line:
                    f.write((json.dumps({"ok": True}) + "\n").encode("utf-8"))
                    f.flush()
                # One ack only -- silent forever after.
            except OSError:
                pass

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
        for c in self._conns:
            try:
                c.close()
            except OSError:
                pass
        try:
            self._server.close()
        except OSError:
            pass


@pytest.fixture
def sock_path():
    """Short /tmp dir -- pytest's tmp_path overflows AF_UNIX's ~104-byte
    sun_path limit (same pattern as conftest.py's fake_daemon fixture)."""
    sock_dir = tempfile.mkdtemp(prefix="twd-wedge-")
    try:
        yield f"{sock_dir}/s.sock"
    finally:
        import shutil

        shutil.rmtree(sock_dir, ignore_errors=True)


def _run_with_watchdog(fn, bound_s):
    """Drives ``fn`` in a daemon thread, waits up to ``bound_s``. Returns
    ``(still_blocked, result_holder, elapsed_s)`` -- never itself blocks
    past ``bound_s``, so a regression here fails fast instead of hanging
    the suite."""
    result = {}

    def _target():
        result["value"] = fn()
        result["completed"] = True

    t = threading.Thread(target=_target, daemon=True)
    start = time.monotonic()
    t.start()
    t.join(timeout=bound_s)
    elapsed = time.monotonic() - start
    return t.is_alive(), result, elapsed


def test_connect_returns_within_bound_against_a_fully_silent_daemon(sock_path):
    server = _FullySilentServer(sock_path)
    server.start()
    try:
        conn = AttachInputConn(sock_path)
        still_blocked, result, elapsed = _run_with_watchdog(conn.connect, _WATCHDOG_BOUND_S)

        assert not still_blocked, (
            f"connect() still blocked after {elapsed:.1f}s (bound={_WATCHDOG_BOUND_S}s) "
            "-- the socket op has no timeout"
        )
        # Same honest failure shape connect() already produces for a dead
        # socket -- no new exception type, no silent success.
        assert result.get("value") is False
        assert conn.error  # a reason is always surfaced, never blank
    finally:
        server.stop()


def test_send_key_returns_within_bound_after_daemon_goes_silent_post_connect(sock_path):
    server = _ConnectsThenWedgesServer(sock_path)
    server.start()
    try:
        conn = AttachInputConn(sock_path)
        assert conn.connect() is True  # handshake still succeeds -- only the NEXT op wedges

        still_blocked, result, elapsed = _run_with_watchdog(
            lambda: conn.send_key(b"d"), _WATCHDOG_BOUND_S
        )

        assert not still_blocked, (
            f"send_key() still blocked after {elapsed:.1f}s (bound={_WATCHDOG_BOUND_S}s) "
            "-- the socket op has no timeout"
        )
        # send_key()'s existing contract: a failed send returns False, no
        # exception crosses the API boundary, no retry.
        assert result.get("value") is False
    finally:
        server.stop()


def test_close_is_safe_after_a_timed_out_connect(sock_path):
    server = _FullySilentServer(sock_path)
    server.start()
    try:
        conn = AttachInputConn(sock_path)
        still_blocked, _result, _elapsed = _run_with_watchdog(conn.connect, _WATCHDOG_BOUND_S)
        assert not still_blocked  # guard: don't mask a hang as a close() pass

        conn.close()  # must not raise on a timed-out/half-dead socket
        conn.close()  # idempotent -- a second close() is also safe
    finally:
        server.stop()


def test_close_is_safe_after_a_timed_out_send_key(sock_path):
    server = _ConnectsThenWedgesServer(sock_path)
    server.start()
    try:
        conn = AttachInputConn(sock_path)
        assert conn.connect() is True

        still_blocked, _result, _elapsed = _run_with_watchdog(
            lambda: conn.send_key(b"d"), _WATCHDOG_BOUND_S
        )
        assert not still_blocked

        conn.close()  # must not raise
    finally:
        server.stop()


def test_timeout_armed_happy_path_still_attaches_and_sends_normally(fake_daemon):
    """Regression: the timeout must not slow down or break the real
    request/response flow against a responsive daemon."""
    conn = AttachInputConn(fake_daemon.sock_path)
    start = time.monotonic()
    assert conn.connect() is True
    assert conn.send_key(b"d") is True
    elapsed = time.monotonic() - start

    # A local unix-socket round trip is sub-millisecond; this is a loose
    # sanity bound, not a precision timing assertion.
    assert elapsed < 2.0
    assert fake_daemon.session.raw_sent == [b"d"]
    conn.close()
