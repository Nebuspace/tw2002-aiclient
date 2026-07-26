"""WO-WEDGED-SEND-FENCE-STICKS — wedged sendall must not leave the fence forever.

Generation-token coverage (explicit, per WO Accept): the fence revision's
generation set correctly *preserves* a wedged predecessor's fence across a
fresh ``enter_auto_loop`` (see ``test_enter_auto_loop_does_not_erase_…``).
That does **not** reduce this hazard — it prevents a later run from
laundering the fence away. Clearing still requires the wedged run's own
``leave_auto_loop`` in ``finally``, which never runs while ``sendall``
blocks. This WO unblocks the socket so ``finally`` can run; it does not
clear the fence from outside.

CC pin (hub 18:15:03Z): a fix that let a *fresh* generation clear a wedged
predecessor's fence would break ``_ReplayPort.is_driver_fenced`` /
``is_auto_loop_held``'s coarse "any hold" premise (safe only under
one-generation-at-a-time). **This tip does not do that** — no outside
fence clear, no second concurrent generation; the one-runner discipline
and the docstring premise are re-proved, not inherited as stale.
"""

from __future__ import annotations

import threading
import time

import pytest

from tw2002_aiclient.session import session as session_mod
from tw2002_aiclient.session.connection import TelnetConnection
from tw2002_aiclient.session.control_lock import ControlLock
from tw2002_aiclient.session.session import Session

from .conftest import FAKE_HOST, FAKE_PORT


class _BlockingSocket:
    """``sendall`` blocks until ``release`` is set or ``shutdown`` forces OSError."""

    def __init__(self):
        self._release = threading.Event()
        self._in_send = threading.Event()
        self.sent = []
        self.shutdown_calls = 0

    def sendall(self, data):
        self._in_send.set()
        # Poll: shutdown must raise (not complete the send). Explicit
        # ``_release`` without shutdown is for clean-path tests only.
        while True:
            if self.shutdown_calls:
                raise OSError("forced unblock")
            if self._release.wait(timeout=0.05):
                if self.shutdown_calls:
                    raise OSError("forced unblock")
                self.sent.append(data)
                return

    def shutdown(self, _how):
        self.shutdown_calls += 1
        # Wake the waiter so it can observe shutdown_calls and raise.
        self._release.set()

    def close(self):
        self._release.set()

    def settimeout(self, _value):
        return None

    def gettimeout(self):
        return None


def _session_with_blocking_sock(tmp_path):
    sess = Session(FAKE_HOST, FAKE_PORT, "wedge", str(tmp_path))
    sock = _BlockingSocket()
    sess.conn._sock = sock
    sess.conn.connected = True
    return sess, sock


def test_force_unblock_sends_wakes_blocked_sendall(tmp_path):
    sess, sock = _session_with_blocking_sock(tmp_path)
    errors = []

    def _blocked():
        try:
            sess.conn.send_bytes(b"Q")
        except OSError as exc:
            errors.append(exc)

    t = threading.Thread(target=_blocked)
    t.start()
    assert sock._in_send.wait(timeout=1.0)
    sess.conn.force_unblock_sends()
    t.join(timeout=1.0)
    assert not t.is_alive()
    assert sock.shutdown_calls >= 1
    assert errors and isinstance(errors[0], OSError)


def test_wedged_autoloop_send_fence_clears_after_send_raw_courtesy_bound(
    tmp_path, monkeypatch
):
    """Human attach keystrokes stop paying the full fence tax once the
    wedged auto-loop send is unblocked and its ``finally`` releases."""
    monkeypatch.setattr(session_mod, "_FENCE_WAIT_TIMEOUT_S", 0.15)
    monkeypatch.setattr(session_mod, "_FENCE_UNBLOCK_WAIT_S", 0.5)

    sess, sock = _session_with_blocking_sock(tmp_path)
    lock = ControlLock()
    generation = lock.enter_auto_loop()
    leave_calls = []

    def _wedged_run():
        try:
            sess.conn.send_bytes(b"macro-step")
        except OSError:
            pass
        finally:
            lock.leave_auto_loop(generation)
            leave_calls.append(generation)

    t = threading.Thread(target=_wedged_run, name="tw-autoloop-wedge")
    t.start()
    assert sock._in_send.wait(timeout=1.0)

    lock.take_human()
    assert lock.is_driver_fenced() is True

    # First keystroke: waits the (patched) courtesy bound, force-unblocks,
    # absorbs leave_auto_loop, then attempts its own send on the dead sock.
    with pytest.raises(OSError):
        sess.send_raw(b"x", control_lock=lock, sender="human")

    t.join(timeout=1.0)
    assert not t.is_alive()
    assert leave_calls == [generation]
    assert lock.is_driver_fenced() is False

    # Subsequent keystroke must not sit out another courtesy bound.
    # Replace sock with a non-blocking stub so the send can complete.
    class _Ok:
        def sendall(self, data):
            self.last = data

        def shutdown(self, _how):
            pass

        def close(self):
            pass

    ok = _Ok()
    sess.conn._sock = ok
    sess.conn.connected = True
    t0 = time.monotonic()
    sess.send_raw(b"y", control_lock=lock, sender="human")
    elapsed = time.monotonic() - t0
    assert elapsed < 0.15, f"still paying fence tax: {elapsed:.3f}s"
    assert ok.last == b"y"


def test_generation_token_does_not_clear_wedged_predecessor_fence():
    """Restate the Accept note: generation tokens preserve, they do not heal."""
    lock = ControlLock()
    token_a = lock.enter_auto_loop()
    lock.take_human()
    lock.release_human()
    # A never leaves -- standing in for wedged sendall.
    lock.enter_auto_loop()
    assert lock.is_driver_fenced() is True
    assert token_a in lock.outstanding_auto_loop_generations()
