"""Layer-A tests for ``tw2002_aiclient.watchfeed.WatchFeed`` (WO-P4-050,
lane 1: the adapter). No pty, no real daemon socket -- every test drives a
real in-kernel ``socket.socketpair()`` as the "fake daemon" end, wrapped in
a local spy transport so writes can be asserted on directly. Never touches
``run/twd.sock``.
"""

from __future__ import annotations

import json
import socket
import threading
import time

from tw2002_aiclient.watchfeed import WatchFeed

_EXPECTED_SUBSCRIBE_LINE = (json.dumps({"verb": "subscribe", "args": {}}) + "\n").encode("utf-8")


class _SpyTransport:
    """Wraps one real socketpair endpoint, recording every ``sendall()``
    call so a test can assert on the FULL write log -- WatchFeed's
    no-sends Accept criterion, made hostile per the WO-P4-050 dispatch."""

    def __init__(self, sock):
        self._sock = sock
        self.writes: list[bytes] = []

    def sendall(self, data):
        self.writes.append(bytes(data))
        return self._sock.sendall(data)

    def makefile(self, mode):
        return self._sock.makefile(mode)

    def shutdown(self, how):
        return self._sock.shutdown(how)

    def close(self):
        return self._sock.close()


def _make_feed_pair():
    """Returns ``(feed, spy, server_sock)``: ``feed``'s ``connect_fn``
    hands back a spy-wrapped end of a real in-kernel AF_UNIX socketpair
    (no filesystem path involved); ``server_sock`` is the test's own
    "fake daemon" end -- write scripted NDJSON lines to it, close it for
    EOF."""
    client_sock, server_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    spy = _SpyTransport(client_sock)
    feed = WatchFeed(connect_fn=lambda: spy)
    return feed, spy, server_sock


def _send_event(server_sock, event: dict):
    server_sock.sendall((json.dumps(event) + "\n").encode("utf-8"))


def _wait_until(predicate, timeout=2.0, interval=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_settle_events_recorded_latest_wins():
    feed, _spy, server_sock = _make_feed_pair()
    feed.start()
    try:
        events = [{"ok": True, "screen": [f"frame {i}"], "n": i} for i in range(5)]
        for event in events:
            _send_event(server_sock, event)
        assert _wait_until(lambda: feed.snapshot().events_received == 5)
        snap = feed.snapshot()
        assert snap.events_received == 5
        assert snap.latest_event == events[-1]
        assert snap.running is True
    finally:
        feed.stop()
        server_sock.close()


def test_subscribe_line_is_the_only_write_ever():
    """Hostile write-capture assert: the ONE subscribe line, and nothing
    else -- across repeated snapshot() calls and repeated stop() calls."""
    feed, spy, server_sock = _make_feed_pair()
    feed.start()
    try:
        _send_event(server_sock, {"ok": True, "screen": ["hi"]})
        assert _wait_until(lambda: feed.snapshot().events_received == 1)
        for _ in range(10):
            feed.snapshot()
        feed.stop()
        for _ in range(10):
            feed.snapshot()
        feed.stop()  # stop twice -- still no new writes
        assert spy.writes == [_EXPECTED_SUBSCRIBE_LINE]
    finally:
        server_sock.close()


def test_malformed_line_dropped_mid_stream():
    feed, _spy, server_sock = _make_feed_pair()
    feed.start()
    try:
        _send_event(server_sock, {"ok": True, "screen": ["one"]})
        assert _wait_until(lambda: feed.snapshot().events_received == 1)

        server_sock.sendall(b"not valid json at all\n")
        server_sock.sendall(b"[1, 2, 3]\n")  # valid JSON, not a dict -- also dropped

        _send_event(server_sock, {"ok": True, "screen": ["two"]})
        assert _wait_until(lambda: feed.snapshot().events_received == 2)
        snap = feed.snapshot()
        assert snap.events_received == 2
        assert snap.latest_event == {"ok": True, "screen": ["two"]}
        assert snap.running is True
    finally:
        feed.stop()
        server_sock.close()


def test_eof_ends_stream_gracefully():
    feed, _spy, server_sock = _make_feed_pair()
    feed.start()
    try:
        _send_event(server_sock, {"ok": True, "screen": ["one"]})
        assert _wait_until(lambda: feed.snapshot().events_received == 1)
        server_sock.close()  # EOF from the "daemon" side
        assert _wait_until(lambda: feed.snapshot().running is False)
        snap = feed.snapshot()
        assert snap.running is False
        assert snap.events_received == 1
        assert snap.latest_event == {"ok": True, "screen": ["one"]}
    finally:
        feed.stop()


def test_stop_idempotent_before_and_mid_stream():
    feed, _spy, server_sock = _make_feed_pair()

    # Safe before start() -- pure no-op.
    feed.stop()
    assert feed.snapshot().running is False

    feed.start()
    try:
        _send_event(server_sock, {"ok": True, "screen": ["mid"]})
        assert _wait_until(lambda: feed.snapshot().events_received == 1)

        reader_thread = feed._thread
        assert reader_thread is not None and reader_thread.is_alive()

        started = time.monotonic()
        feed.stop()  # mid-stream: thread is parked in a blocking readline()
        elapsed = time.monotonic() - started

        assert not reader_thread.is_alive()  # join proves the thread is dead
        assert feed.snapshot().running is False

        feed.stop()  # idempotent -- no raise, no hang, no re-write
        assert feed.snapshot().running is False

        # Join-budget canary LAST — never mask the behavioural asserts above.
        assert elapsed < 2.5  # bounded well within the ~2s join budget
    finally:
        server_sock.close()


def test_start_with_raising_connect_fn_is_contained():
    def _boom():
        raise OSError("connection refused")

    feed = WatchFeed(connect_fn=_boom)
    feed.start()  # must not raise
    snap = feed.snapshot()
    assert snap.running is False
    assert snap.events_received == 0
    assert snap.latest_event is None
    feed.stop()  # also must not raise -- still a no-op, nothing was ever spawned


def test_start_with_write_failure_after_connect_is_contained():
    """Same fd-leak shape as the raced-stop regression below, different
    trigger: a connect that succeeds but whose write then fails must not
    leak the transport either -- every early-exit path out of start()
    either publishes the transport (happy path) or closes it."""

    class _BrokenAfterConnect:
        def __init__(self):
            self.closed = False

        def sendall(self, data):
            raise BrokenPipeError("broken")

        def makefile(self, mode):  # pragma: no cover -- must never be reached
            raise AssertionError("read loop must never start after a failed write")

        def shutdown(self, how):
            pass

        def close(self):
            self.closed = True

    transport = _BrokenAfterConnect()
    feed = WatchFeed(connect_fn=lambda: transport)
    feed.start()
    snap = feed.snapshot()
    assert snap.running is False
    assert transport.closed is True  # the fresh transport must not leak on a write failure
    feed.stop()


def test_stop_during_blocked_connect_closes_fresh_transport_no_send():
    """Mack adversarial-review regression (HIGH, WO-P4-050 in-wave fix):
    a stop() landing while start() is still blocked inside connect_fn()
    has nothing to close yet (self._transport/_thread are both still
    None) -- start() must recheck the stop flag once connect_fn() finally
    returns, before ever writing the subscribe line, or the late-arriving
    transport + reader thread get published with no one left to close
    them. Every wait below is a bounded Event.wait, not a sleep-and-hope,
    so a regression hangs this test rather than passing silently."""
    connect_entered = threading.Event()
    connect_may_proceed = threading.Event()
    transport_holder: dict = {}

    class _CloseTrackingTransport:
        def __init__(self, sock):
            self._sock = sock
            self.writes: list[bytes] = []
            self.closed = False

        def sendall(self, data):
            self.writes.append(bytes(data))
            return self._sock.sendall(data)

        def makefile(self, mode):  # pragma: no cover -- must never be reached
            raise AssertionError("reader thread must never spawn on a raced stop()")

        def shutdown(self, how):
            return self._sock.shutdown(how)

        def close(self):
            self.closed = True
            return self._sock.close()

    client_sock, server_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

    def _blocking_connect():
        connect_entered.set()
        assert connect_may_proceed.wait(timeout=5.0), "test setup stalled -- connect never released"
        transport = _CloseTrackingTransport(client_sock)
        transport_holder["transport"] = transport
        return transport

    feed = WatchFeed(connect_fn=_blocking_connect)

    start_thread = threading.Thread(target=feed.start, daemon=True)
    start_thread.start()
    try:
        assert connect_entered.wait(timeout=5.0)  # start() is now blocked inside connect_fn()
        feed.stop()  # races the still-blocked connect -- nothing yet for it to close

        connect_may_proceed.set()
        start_thread.join(timeout=5.0)
        assert not start_thread.is_alive()

        assert "transport" in transport_holder
        transport = transport_holder["transport"]
        assert transport.writes == []  # subscribe line NEVER sent
        assert transport.closed is True  # the fresh (raced) transport got closed
        assert feed.snapshot().running is False
        assert feed._thread is None  # no reader thread was ever spawned
    finally:
        server_sock.close()


def test_default_connect_fn_failure_is_contained(tmp_path):
    """Exercises the REAL default daemon-socket connect path (not a test
    fake) against a run_dir with no socket present -- proves it fails
    closed the same way, without ever touching run/twd.sock."""
    feed = WatchFeed(run_dir=tmp_path)
    feed.start()
    snap = feed.snapshot()
    assert snap.running is False
    feed.stop()


def test_snapshot_thread_safety_smoke():
    feed, _spy, server_sock = _make_feed_pair()
    feed.start()
    try:
        stop_feeding = threading.Event()

        def _feeder():
            i = 0
            while not stop_feeding.is_set():
                try:
                    _send_event(server_sock, {"ok": True, "screen": [f"f{i}"]})
                except OSError:
                    return
                i += 1
                time.sleep(0.001)

        feeder_thread = threading.Thread(target=_feeder, daemon=True)
        feeder_thread.start()

        last_count = -1
        deadline = time.monotonic() + 1.0
        try:
            while time.monotonic() < deadline:
                snap = feed.snapshot()
                assert snap.events_received >= last_count  # monotonically nondecreasing
                last_count = snap.events_received
        finally:
            stop_feeding.set()
            feeder_thread.join(timeout=2.0)
    finally:
        feed.stop()
        server_sock.close()
    assert last_count > 0  # actually observed real growth, not a no-op loop
