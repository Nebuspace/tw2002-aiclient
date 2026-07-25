"""WatchHub settle-edge detection + subscriber fan-out — no network, no
real threading: `_maybe_emit()` is called directly rather than starting the
background thread, matching the fake-clock style used for settle.py.

WO-P2-WATCHHUB-PORT: greenfield rewrite of the archive suite (imports
`tw2002_aiclient.session.watch`). CLI `tw watch` not wired yet.
"""

from __future__ import annotations

import queue
import time

from tw2002_aiclient.session.watch import WatchHub


class FakeSession:
    """Just enough surface for protocol.build_response(): .render(),
    .render_with_color(), .render_text(rows), .last_rx."""

    def __init__(self, rows, last_rx):
        self._rows = rows
        self.last_rx = last_rx
        self.last_sent = None

    def render(self):
        return list(self._rows)

    def render_with_color(self):
        # WO-P4-053: build_response's bare-rows path now takes both from
        # here in one call -- no color fixture is exercised by this
        # module's settle-edge tests, so an empty color map is enough.
        return self.render(), []

    def render_text(self, rows=None):
        return "\n".join(rows if rows is not None else self._rows)


def test_subscribe_seeds_current_screen_immediately():
    session = FakeSession(["current screen"], last_rx=time.monotonic())
    hub = WatchHub(session)
    q = hub.subscribe(queue.Queue)
    seed = q.get_nowait()
    assert seed["screen"] == ["current screen"]
    assert "ts" in seed
    assert seed["ok"] is True


def test_no_emit_while_still_receiving_bytes():
    session = FakeSession(["hello"], last_rx=time.monotonic())  # just now
    hub = WatchHub(session, debounce_ms=350)
    q = hub.subscribe(queue.Queue)
    q.get_nowait()  # drain the seed
    hub._maybe_emit()
    assert q.empty()


def test_emits_on_settle_when_screen_changed():
    session = FakeSession(["hello"], last_rx=time.monotonic() - 1.0)  # long idle
    hub = WatchHub(session, debounce_ms=350)
    q = hub.subscribe(queue.Queue)
    q.get_nowait()
    session._rows = ["goodbye"]
    hub._maybe_emit()
    event = q.get_nowait()
    assert event["screen"] == ["goodbye"]
    assert event["settled_reason"] == "idle"
    assert "ts" in event


def test_does_not_re_emit_an_unchanged_screen():
    session = FakeSession(["hello"], last_rx=time.monotonic() - 1.0)
    hub = WatchHub(session, debounce_ms=350)
    q = hub.subscribe(queue.Queue)
    q.get_nowait()
    session._rows = ["goodbye"]
    hub._maybe_emit()
    q.get_nowait()  # the one real emit
    hub._maybe_emit()  # screen hasn't changed since -> nothing new
    assert q.empty()


def test_fan_out_to_multiple_subscribers():
    session = FakeSession(["hello"], last_rx=time.monotonic() - 1.0)
    hub = WatchHub(session, debounce_ms=350)
    q1 = hub.subscribe(queue.Queue)
    q2 = hub.subscribe(queue.Queue)
    q1.get_nowait()
    q2.get_nowait()
    session._rows = ["broadcast me"]
    hub._maybe_emit()
    e1 = q1.get_nowait()
    e2 = q2.get_nowait()
    assert e1["screen"] == e2["screen"] == ["broadcast me"]


def test_unsubscribe_stops_further_delivery():
    session = FakeSession(["hello"], last_rx=time.monotonic() - 1.0)
    hub = WatchHub(session, debounce_ms=350)
    q = hub.subscribe(queue.Queue)
    q.get_nowait()
    hub.unsubscribe(q)
    session._rows = ["changed"]
    hub._maybe_emit()
    assert q.empty()


def test_subscriber_count_tracks_subscribe_and_unsubscribe():
    session = FakeSession(["hello"], last_rx=time.monotonic())
    hub = WatchHub(session)
    assert hub.subscriber_count() == 0
    q = hub.subscribe(queue.Queue)
    assert hub.subscriber_count() == 1
    hub.unsubscribe(q)
    assert hub.subscriber_count() == 0


def test_broadcast_extra_bypasses_settle_edge():
    session = FakeSession(["hello"], last_rx=time.monotonic())
    hub = WatchHub(session, debounce_ms=350)
    q = hub.subscribe(queue.Queue)
    q.get_nowait()
    hub.broadcast_extra({"ok": True, "kind": "extra", "n": 1})
    event = q.get_nowait()
    assert event["kind"] == "extra"
    assert "ts" in event


def _wait_until(predicate, timeout=3.0, interval=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class _HostileQueue:
    """Subscriber-shaped double whose ``.put()`` explodes -- proves
    ``_broadcast()``'s per-subscriber containment
    (WO-AUDIT-WATCHHUB-LOOP-CONTAIN). The seed put (``subscribe()``'s
    first call) is let through so construction via ``hub.subscribe()``
    succeeds cleanly; every put after that raises."""

    def __init__(self, message="hostile put"):
        self._message = message
        self._real = queue.Queue()
        self._n = 0

    def put(self, item):
        self._n += 1
        if self._n == 1:
            self._real.put(item)
            return
        raise RuntimeError(self._message)

    def get_nowait(self):
        return self._real.get_nowait()


def test_loop_survives_a_raising_tick():
    """WO-AUDIT-WATCHHUB-LOOP-CONTAIN, proof 1. Pre-fix (HEAD blob, see
    the WO's red-first evidence), a raising tick killed the background
    thread outright and there was no ``last_loop_error`` field at all."""
    session = FakeSession(["hello"], last_rx=time.monotonic() - 1.0)
    hub = WatchHub(session, debounce_ms=50, poll_interval_s=0.01)
    q = hub.subscribe(queue.Queue)
    q.get_nowait()  # drain seed

    real_maybe_emit = hub._maybe_emit
    calls = {"n": 0}

    def flaky_maybe_emit():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real_maybe_emit()

    hub._maybe_emit = flaky_maybe_emit
    hub.start()
    try:
        assert _wait_until(lambda: hub.last_loop_error is not None)
        assert hub.last_loop_error == "RuntimeError"
        assert hub._thread.is_alive()  # the loop kept going past the raise

        session._rows = ["goodbye"]  # a subsequent, real emit still reaches the subscriber
        event = q.get(timeout=3.0)
        assert event["screen"] == ["goodbye"]
    finally:
        hub.stop()
        hub._thread.join(timeout=3.0)


def test_bad_subscriber_does_not_starve_the_rest():
    """WO-AUDIT-WATCHHUB-LOOP-CONTAIN, proof 2. Pre-fix, the hostile
    queue's raise propagated straight out of ``_maybe_emit()`` and the
    good subscriber got nothing at all -- see the WO's red-first
    evidence."""
    session = FakeSession(["hello"], last_rx=time.monotonic() - 1.0)
    hub = WatchHub(session, debounce_ms=50)
    hostile_q = hub.subscribe(_HostileQueue)
    good_q = hub.subscribe(queue.Queue)
    hostile_q.get_nowait()  # drain seed
    good_q.get_nowait()

    session._rows = ["goodbye"]
    hub._maybe_emit()  # must not raise despite the hostile subscriber

    event = good_q.get_nowait()
    assert event["screen"] == ["goodbye"]
    assert hub.last_loop_error == "RuntimeError"


def test_loop_tick_exception_text_never_leaks_into_last_loop_error():
    """WO-AUDIT-WATCHHUB-LOOP-CONTAIN, proof 3 (Cipher rule): only the
    exception's TYPE NAME is ever observable -- never its message text,
    which could embed server-echoed screen content."""
    fake_secret = "FAKE-SECRET-SENTINEL-XYZ"
    session = FakeSession(["hello"], last_rx=time.monotonic() - 1.0)
    hub = WatchHub(session, debounce_ms=50, poll_interval_s=0.01)
    q = hub.subscribe(queue.Queue)
    q.get_nowait()

    def hostile_maybe_emit():
        raise RuntimeError(fake_secret)

    hub._maybe_emit = hostile_maybe_emit
    hub.start()
    try:
        assert _wait_until(lambda: hub.last_loop_error is not None)
        assert hub.last_loop_error == "RuntimeError"
        assert fake_secret not in hub.last_loop_error
    finally:
        hub.stop()
        hub._thread.join(timeout=3.0)


def test_broadcast_exception_text_never_leaks_into_error_or_event():
    """Same Cipher pin as above, at the ``_broadcast()`` containment
    site: the sentinel must be absent from both ``last_loop_error`` and
    the event delivered to the surviving subscriber."""
    fake_secret = "FAKE-SECRET-SENTINEL-XYZ"
    session = FakeSession(["hello"], last_rx=time.monotonic() - 1.0)
    hub = WatchHub(session, debounce_ms=50)
    hostile_q = hub.subscribe(lambda: _HostileQueue(fake_secret))
    good_q = hub.subscribe(queue.Queue)
    hostile_q.get_nowait()
    good_q.get_nowait()

    session._rows = ["goodbye"]
    hub._maybe_emit()

    event = good_q.get_nowait()
    assert hub.last_loop_error == "RuntimeError"
    assert fake_secret not in hub.last_loop_error
    assert fake_secret not in str(event)


def test_stop_returns_promptly_even_with_a_long_poll_interval():
    """WO-AUDIT-WATCHHUB-LOOP-CONTAIN, proof 4. Pre-fix ``stop()``
    blocked for the full ``poll_interval_s`` (a plain ``time.sleep``
    loop can't be woken early) -- see the WO's red-first evidence
    (~2.0s observed at ``poll_interval_s=2.0``). The ``wait()``-based
    loop must return in well under that."""
    session = FakeSession(["hello"], last_rx=time.monotonic())
    hub = WatchHub(session, poll_interval_s=2.0)
    hub.start()
    try:
        assert _wait_until(lambda: hub._thread.is_alive())
        t0 = time.monotonic()
        hub.stop()
        hub._thread.join(timeout=5.0)
        elapsed = time.monotonic() - t0
        assert not hub._thread.is_alive()
        assert elapsed < 1.0  # far under poll_interval_s -- proves the wait() is interruptible
    finally:
        hub.stop()
        hub._thread.join(timeout=5.0)


def test_status_reports_subscriber_count():
    from tw2002_aiclient.session import protocol

    class _Conn:
        connected = True

    class _Session(FakeSession):
        def __init__(self):
            super().__init__(["Command [?]"], last_rx=time.monotonic())
            self.conn = _Conn()
            self.host = "127.0.0.1"
            self.port = 23
            self.name = "test"

    class _Server:
        def __init__(self, hub):
            self.watch_hub = hub
            self.control_lock = None

    session = _Session()
    hub = WatchHub(session)
    hub.subscribe(queue.Queue)
    resp = protocol.dispatch(session, "status", {}, _Server(hub))
    assert resp["ok"] is True
    assert resp["subscribers"] == 1
