"""Settle-edge push-stream engine for `tw watch` / `tw spectate`.

`WatchHub` runs a small background thread that watches the session's
already-rendered screen and detects "settle edges": moments where the
screen has both (a) stopped changing (idle >= debounce) and (b) actually
changed since the last edge it announced. Each edge is broadcast, as a
protocol.build_response()-shaped event, to every currently-subscribed
queue. This is deliberately separate from settle.wait_for_settle(), which
answers "has THIS specific send settled yet" for a single synchronous
`do`/`read` call — WatchHub instead answers "what's the game doing right
now", continuously, for however many passive spectators are attached.
Both read the same session state through the same lock; they don't
interact and don't need to.

Nuisance auto-handling (e.g. auto-dismissing repeated pauses) is
explicitly NOT this module's job — it streams every settle-edge as-is.

Ported from archive `twclient/watch.py` (WO-P2-WATCHHUB-PORT). Read-only:
never takes control_lock / never sends game input.
"""

import threading
import time

from .protocol import build_response

_DEFAULT_DEBOUNCE_MS = 350
_DEFAULT_POLL_INTERVAL_S = 0.05


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _screen_hash(session):
    return hash(tuple(session.render()))


class WatchHub:
    def __init__(self, session, debounce_ms=_DEFAULT_DEBOUNCE_MS, poll_interval_s=_DEFAULT_POLL_INTERVAL_S):
        self.session = session
        self.debounce_ms = debounce_ms
        self.poll_interval_s = poll_interval_s
        self._subscribers = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        # Seeded at construction so the first background emit is a real
        # change, not a re-announcement of whatever's already on screen.
        self._last_emitted_hash = _screen_hash(session)
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def subscriber_count(self):
        with self._lock:
            return len(self._subscribers)

    def subscribe(self, queue_cls):
        """Register a new subscriber queue (caller supplies the Queue
        class/instance so this module has no hard queue.Queue import
        dependency for tests), seeded with the CURRENT settled screen as
        its first event so a spectator tuning in mid-session isn't
        staring at nothing until the next real change."""
        q = queue_cls()
        snapshot = build_response(self.session)
        snapshot["ts"] = _now_iso()
        q.put(snapshot)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            self._subscribers.discard(q)

    def broadcast_extra(self, event: dict):
        """Push an arbitrary event dict to every current subscriber,
        bypassing the settle-edge screen-change detection entirely --
        for events that aren't "the screen changed" at all (e.g. future
        AUTO-LOOP progress). Stamps `ts` the same way settle-edge events
        do, so a consumer can't tell the two apart by shape alone."""
        event = dict(event)
        event.setdefault("ts", _now_iso())
        self._broadcast(event)

    def _loop(self):
        while not self._stop.is_set():
            time.sleep(self.poll_interval_s)
            with self._lock:
                has_subscribers = bool(self._subscribers)
            if not has_subscribers:
                continue
            self._maybe_emit()

    def _maybe_emit(self):
        idle_for_ms = (time.monotonic() - self.session.last_rx) * 1000
        if idle_for_ms < self.debounce_ms:
            return
        current_hash = _screen_hash(self.session)
        if current_hash == self._last_emitted_hash:
            return
        event = build_response(self.session, settled_reason="idle")
        event["ts"] = _now_iso()
        self._broadcast(event)
        self._last_emitted_hash = current_hash

    def _broadcast(self, event):
        with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            q.put(event)
