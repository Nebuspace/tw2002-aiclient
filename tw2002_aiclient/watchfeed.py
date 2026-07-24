"""``WatchFeed`` -- the product-side lifetime subscribe CLIENT (WO-P4-050,
lane 1: the adapter). Play-shell counterpart to ``tw watch``
(``session/cli.py::cmd_watch``): opens the daemon's ``subscribe`` stream and
keeps only the LATEST settle-edge event + a running count, for a UI thread
to poll via ``snapshot()`` on its own draw cadence -- never blocks the
caller waiting on the network, and never buffers a backlog of stale events.

Wire shape mirrors ``cmd_watch`` / ``session/daemon.py::_handle_subscribe``
exactly: connect the unix socket, write ONE ``{"verb": "subscribe", "args":
{}}`` line, then read a lifetime stream of newline-delimited JSON events,
each a ``protocol.build_response()``-shaped dict (``WatchHub`` seeds the
current screen immediately on subscribe, then one event per settle edge --
see ``session/watch.py``). This class never re-derives that shape; it just
records whatever dict arrives.

D5 (spectator-only, read-only): this class exposes NO send/do API of any
kind. The only bytes it ever writes to the transport are the one subscribe
line, written once inside ``start()`` -- never repeated, never anything
else, for the lifetime of the instance (proven by
``tests/test_watchfeed.py``'s write-capture assert). The background reader
thread only records (count + latest event, under a lock); it never draws,
never calls UI code, and never raises out of the thread -- a malformed/
non-JSON line (or valid JSON that isn't a dict, matching
``daemon.py``'s own "valid JSON but not a request object" containment) is
silently dropped, not surfaced as a placeholder or a crash.

Hardening family (matches ``cockpit/logsband.py``'s tone): every public
method is never-raises. ``start()`` records any connect/write failure as
``running=False`` in the snapshot rather than propagating; ``stop()`` is
idempotent, safe before ``start()``, safe mid-stream, and bounded (~2s
join) regardless of how the reader thread got stuck. The transport's
``.shutdown(SHUT_RDWR)``-before-``.close()`` idiom (mirroring
``session/attach_client.py::AttachInputConn.close()``) is what reliably
unblocks a reader thread parked in a blocking ``readline()`` -- a bare
``close()`` from another thread is a known POSIX race, ``shutdown()``
first is not.
"""

from __future__ import annotations

import json
import socket
import threading
from dataclasses import dataclass

from .session import env

# The one and only line this class ever writes to the wire -- built once so
# every start() sends byte-identical bytes, mirroring cmd_watch's own
# literal (session/cli.py::cmd_watch).
_SUBSCRIBE_REQUEST = (json.dumps({"verb": "subscribe", "args": {}}) + "\n").encode("utf-8")

# Bounded join wait for the reader thread on stop() -- see the module
# docstring's shutdown-before-close note for why this is expected to
# resolve well under this bound rather than actually needing it.
_STOP_JOIN_TIMEOUT_S = 2.0


@dataclass(frozen=True)
class WatchFeedSnapshot:
    """Thread-safe point-in-time read of a ``WatchFeed``'s state -- exactly
    the three fields a UI draw loop needs, no more: how many events have
    arrived so far, the most recent one (or ``None`` before the first
    arrives / after a connect failure), and whether the feed is still
    actively subscribed."""

    events_received: int
    latest_event: dict | None
    running: bool


def _default_connect_fn(run_dir):
    """The real daemon transport: a unix-domain ``SOCK_STREAM`` connect to
    ``env.socket_path(run_dir)``, mirroring ``cmd_watch``'s own connect
    (``session/cli.py``) -- same socket family, same path resolution
    (honors ``run_dir``/``TW_RUN_DIR`` the same way every other caller
    does, via ``env.py``, never reimplemented here). Deliberately does NOT
    pre-check ``sock_path.exists()`` the way ``cmd_watch`` does for a
    friendlier CLI error message -- ``WatchFeed`` has no error-message
    field in its contract (only ``events_received``/``latest_event``/
    ``running``), so a missing socket simply fails ``connect()`` the same
    as any other connect failure, contained the same way by ``start()``."""

    def _connect():
        sock_path = env.socket_path(run_dir)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(str(sock_path))
        return s

    return _connect


def _close_transport(transport):
    """``shutdown(SHUT_RDWR)`` before ``close()`` -- see the module
    docstring. Both steps are individually best-effort (a transport that's
    already shut down / already closed raises ``OSError`` on either call,
    swallowed here) so this is safe to call twice, matching ``stop()``'s
    own idempotence contract. ``shutdown`` is optional on the transport
    duck-type (a test fake need not implement it) -- ``close()`` alone is
    still attempted either way."""
    shutdown = getattr(transport, "shutdown", None)
    if callable(shutdown):
        try:
            shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    try:
        transport.close()
    except OSError:
        pass


class WatchFeed:
    """Product-side subscribe client. One instance = one lifetime
    subscribe connection; call ``start()`` once, poll ``snapshot()`` from
    the UI thread on its own cadence, call ``stop()`` on Esc/back or
    shutdown.

    ``connect_fn``: a no-arg callable returning an already-connected
    socket-like transport (must support ``sendall(bytes)``,
    ``makefile("rb")``, ``close()``, and MAY support
    ``shutdown(how)``). Defaults to a real daemon connect
    (``_default_connect_fn(run_dir)``). Tests always pass a fake transport
    here -- this class never touches a real socket on its own initiative
    beyond what ``connect_fn`` gives it.

    Lifecycle single-owner assumption: ``start()``/``stop()`` are expected
    to be called by one owning thread (the play-shell flow that owns this
    instance) -- only ``snapshot()`` is proven thread-safe against the
    background reader; concurrent ``start()``/``stop()`` calls from
    multiple threads are neither guarded nor tested. One specific case IS
    handled despite that: a ``stop()`` that lands while ``start()`` is
    mid-connect is nonetheless honored -- checked once ``connect_fn()``
    returns, before the subscribe line is ever written; the fresh
    transport is closed and no subscribe line is sent (Mack
    adversarial-review fix, HIGH, WO-P4-050). General concurrent
    ``start()``/``stop()`` beyond that one race remains undocumented
    territory.
    """

    def __init__(self, *, connect_fn=None, run_dir=None):
        self._connect_fn = connect_fn if connect_fn is not None else _default_connect_fn(run_dir)
        self._lock = threading.Lock()
        self._events_received = 0
        self._latest_event = None
        self._running = False
        self._transport = None
        self._thread = None
        self._stop_requested = threading.Event()

    def start(self) -> None:
        """Connect, write the one subscribe line, spawn the daemon reader
        thread. Never raises: a connect or write failure is recorded as
        ``running=False`` and ``start()`` simply returns -- there is no
        exception surface and no error-detail field for a caller to
        inspect (matches the frozen contract's three snapshot fields).
        A ``start()`` while a previous subscribe is still alive is a
        no-op (never opens a second connection out from under itself).

        A ``stop()`` that lands while ``start()`` is still blocked inside
        ``connect_fn()`` is honored, not lost: rechecked once
        ``connect_fn()`` returns, before the subscribe line is ever
        written (Mack adversarial-review fix, HIGH, WO-P4-050 -- see
        class docstring). Without this recheck a late-returning connect
        would publish a transport (and spawn a reader thread) that
        ``stop()`` already ran past and would never get another chance
        to close."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_requested.clear()
        try:
            transport = self._connect_fn()
        except Exception:
            with self._lock:
                self._running = False
            return
        if self._stop_requested.is_set():
            _close_transport(transport)
            with self._lock:
                self._running = False
            return
        try:
            transport.sendall(_SUBSCRIBE_REQUEST)
        except Exception:
            # Connected, but the write itself failed (e.g. broken pipe
            # right after connect) -- same fd-leak shape as the raced-stop
            # case above: the transport was never published, so nothing
            # else will ever close it unless start() does so here.
            _close_transport(transport)
            with self._lock:
                self._running = False
            return
        self._transport = transport
        with self._lock:
            self._running = True
        self._thread = threading.Thread(target=self._read_loop, args=(transport,), daemon=True)
        self._thread.start()

    def _read_loop(self, transport) -> None:
        """Reader-thread body: record-only, never draws, never raises out
        of the thread. Each line is independently contained -- a
        malformed/non-JSON line, or JSON that decodes but isn't a dict
        (mirrors ``daemon.py``'s own "valid JSON but not a request
        object" containment), is dropped without touching the count.
        EOF (``readline()`` returns ``b""``) or any transport-level
        ``OSError`` (broken pipe, reset, or the ``shutdown()``-induced
        unblock from ``stop()``) ends the loop the same way: quietly,
        ``running`` flips to ``False``, thread exits."""
        try:
            f = transport.makefile("rb")
        except Exception:
            with self._lock:
                self._running = False
            return
        try:
            while not self._stop_requested.is_set():
                try:
                    line = f.readline()
                except OSError:
                    break
                if not line:
                    break
                try:
                    event = json.loads(line.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if not isinstance(event, dict):
                    continue
                with self._lock:
                    self._events_received += 1
                    self._latest_event = event
        except Exception:
            # Never raise out of a background thread -- an uncaught
            # exception here would be silently swallowed by the thread
            # machinery anyway, but the explicit catch keeps the intent
            # visible and guarantees the finally below still runs.
            pass
        finally:
            with self._lock:
                self._running = False
            try:
                f.close()
            except Exception:
                pass

    def stop(self) -> None:
        """Idempotent, bounded, never raises. Safe to call before
        ``start()`` (no-op) and safe to call twice (the second call's
        already-closed transport / already-finished thread are both
        no-ops). Unblocks a reader thread parked mid-``readline()`` via
        ``_close_transport``'s shutdown-before-close (see module
        docstring) rather than relying on ``_stop_requested`` alone,
        which the reader thread only re-checks between lines."""
        self._stop_requested.set()
        transport = self._transport
        if transport is not None:
            _close_transport(transport)
        thread = self._thread
        if thread is not None:
            thread.join(timeout=_STOP_JOIN_TIMEOUT_S)
        with self._lock:
            self._running = False

    def snapshot(self) -> WatchFeedSnapshot:
        """Thread-safe point-in-time read -- see ``WatchFeedSnapshot``.
        Safe to call at any point in the lifecycle (before ``start()``,
        mid-stream, after ``stop()``), any number of times, from any
        thread."""
        with self._lock:
            return WatchFeedSnapshot(
                events_received=self._events_received,
                latest_event=self._latest_event,
                running=self._running,
            )
