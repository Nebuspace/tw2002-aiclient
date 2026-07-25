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
