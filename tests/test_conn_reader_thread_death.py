"""WO-CONN-READER-THREAD-DEATH-HONESTY -- audit I-02.

A reader thread that dies must not leave the connection advertising itself
as live. These pins cover the four Accept criteria plus the two failure
modes a careless fix would introduce: a false disconnect on clean traffic,
and a stale failure reason surviving a reconnect.
"""

from __future__ import annotations

import threading
import time

import pytest

from tw2002_aiclient.session.connection import (
    READER_FAILURE_PREFIX,
    TelnetConnection,
)


class _Terminal:
    def __init__(self): self.fed = bytearray()
    def feed(self, data): self.fed.extend(data)


class _CleanNegotiator:
    def feed(self, data): return data
    def pop_pending_output(self): return b""


class _RaisingNegotiator:
    """Stands in for a `TelnetHandler` whose `feed()` raises -- exactly what
    a >255-column NAWS dimension produces today (audit I-03), and what ANY
    future negotiation bug would produce."""

    def __init__(self, exc=None): self.exc = exc or ValueError("bytes must be in range(0, 256)")
    def feed(self, data): raise self.exc
    def pop_pending_output(self): return b""


class _Sock:
    """Yields the given chunks, then blocks so the loop cannot exit by
    running out of data -- the thread must exit for the reason under test."""

    def __init__(self, chunks): self.chunks = list(chunks); self.sent = []
    def recv(self, n):
        if self.chunks:
            return self.chunks.pop(0)
        time.sleep(0.02)
        return b"\x00"
    def sendall(self, b): self.sent.append(b)
    def settimeout(self, t): pass
    def close(self): pass


class _ClosingSock(_Sock):
    """Peer closes cleanly after the chunks run out."""
    def recv(self, n):
        return self.chunks.pop(0) if self.chunks else b""


def _run_loop(conn, timeout=2.0):
    """Run `_reader_loop` to completion in a thread, swallowing the
    re-raised exception the way the real thread runner does."""
    def _target():
        try:
            conn._reader_loop()
        except Exception:
            pass
    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout=timeout)
    return t


def _conn(negotiator, sock, logger=None):
    c = TelnetConnection("h", 1, _Terminal(), negotiator, logger=logger)
    c._sock = sock
    c.connected = True
    return c


# --------------------------------------------------------------------------
# Accept #1 and #3 -- the bug itself.
# --------------------------------------------------------------------------

def test_raising_negotiator_kills_thread_and_clears_connected() -> None:
    c = _conn(_RaisingNegotiator(), _Sock([b"hello"]))
    t = _run_loop(c)
    assert not t.is_alive(), "reader thread should be gone"
    assert c.connected is False, "connection still advertises itself as live"


@pytest.mark.parametrize(
    "exc",
    [ValueError("range"), TypeError("bad"), KeyError("k"), RuntimeError("boom"),
     AttributeError("attr"), ZeroDivisionError("div")],
)
def test_any_unexpected_exception_marks_down(exc: Exception) -> None:
    """The blast radius is "any future exception in the loop body", not one
    known bug -- so the guarantee is pinned against a family, not a case."""
    c = _conn(_RaisingNegotiator(exc), _Sock([b"x"]))
    _run_loop(c)
    assert c.connected is False


def test_failure_is_recorded_with_the_exception_type() -> None:
    c = _conn(_RaisingNegotiator(TypeError("nope")), _Sock([b"x"]))
    _run_loop(c)
    assert c.reader_failure == f"{READER_FAILURE_PREFIX}TypeError"


def test_recorded_failure_never_carries_the_exception_message() -> None:
    """Secret discipline: this loop handles server bytes that may be a
    password prompt, and an exception message can embed the payload that
    caused it. Type name only -- `guardian.py`'s own idiom."""
    secret = "hunter2-SUPERSECRET"
    c = _conn(_RaisingNegotiator(ValueError(secret)), _Sock([b"x"]))
    _run_loop(c)
    assert secret not in (c.reader_failure or "")
    assert c.reader_failure == f"{READER_FAILURE_PREFIX}ValueError"


# --------------------------------------------------------------------------
# Accept #2 -- the failure surfaces, distinctly from an ordinary drop.
# --------------------------------------------------------------------------

class _Logger:
    def __init__(self): self.raw = []; self.redacted = []
    def log_raw(self, direction, data): self.raw.append((direction, data))
    def log_redacted(self, direction, note="secret input redacted"):
        self.redacted.append((direction, note))


def test_failure_reaches_the_log() -> None:
    log = _Logger()
    c = _conn(_RaisingNegotiator(), _Sock([b"x"]), logger=log)
    _run_loop(c)
    assert any("reader thread died" in note for _d, note in log.redacted)


def test_failure_note_goes_through_the_redaction_sink_not_log_raw() -> None:
    """`log_raw` persists content; this note must never travel that path."""
    log = _Logger()
    c = _conn(_RaisingNegotiator(), _Sock([b"x"]), logger=log)
    _run_loop(c)
    assert not any("reader thread died" in str(d) for d, _ in log.raw)
    assert log.redacted


def test_a_raising_logger_does_not_mask_the_original_failure() -> None:
    class _BadLogger(_Logger):
        def log_redacted(self, direction, note="x"): raise OSError("log is gone")

    c = _conn(_RaisingNegotiator(), _Sock([b"x"]), logger=_BadLogger())
    _run_loop(c)
    assert c.connected is False
    assert c.reader_failure == f"{READER_FAILURE_PREFIX}ValueError"


def test_clean_close_is_distinguishable_from_a_crash() -> None:
    """The point of `reader_failure`: without it, flipping `connected` would
    make a real defect render as an ordinary network drop, and the guardian
    would reconnect around the bug forever."""
    c = _conn(_CleanNegotiator(), _ClosingSock([b"hello"]))
    _run_loop(c)
    assert c.connected is False          # both paths mark down ...
    assert c.reader_failure is None      # ... only one names a fault


# --------------------------------------------------------------------------
# Accept #4 -- the fix must not invent disconnects.
# --------------------------------------------------------------------------

def test_clean_traffic_reaches_the_terminal_and_stays_connected() -> None:
    term = _Terminal()
    c = TelnetConnection("h", 1, term, _CleanNegotiator())
    c._sock = _Sock([b"hello", b" world"])
    c.connected = True
    t = threading.Thread(target=c._reader_loop, daemon=True)
    t.start()
    time.sleep(0.2)
    assert c.connected is True, "false disconnect on clean traffic"
    assert b"hello" in bytes(term.fed)
    assert c.reader_failure is None
    c._stop.set()
    t.join(timeout=2)
    assert c.connected is False          # and a requested stop still marks down


def test_stop_event_exit_marks_down_without_a_failure() -> None:
    c = _conn(_CleanNegotiator(), _Sock([b"x"]))
    c._stop.set()
    _run_loop(c)
    assert c.connected is False
    assert c.reader_failure is None


def test_oserror_from_recv_is_an_ordinary_drop_not_a_fault() -> None:
    """`recv` raising OSError is the peer going away -- the pre-existing
    `break`. It must NOT be relabelled as a reader-loop bug."""
    class _DeadSock(_Sock):
        def recv(self, n): raise OSError("connection reset")

    c = _conn(_CleanNegotiator(), _DeadSock([]))
    _run_loop(c)
    assert c.connected is False
    assert c.reader_failure is None


# --------------------------------------------------------------------------
# The mirror-image bug a careless fix introduces.
# --------------------------------------------------------------------------

def test_reconnect_clears_a_stale_failure_reason(monkeypatch) -> None:
    """A reconnected link must not still be reporting the last death."""
    c = _conn(_RaisingNegotiator(), _Sock([b"x"]))
    _run_loop(c)
    assert c.reader_failure is not None

    monkeypatch.setattr(
        "tw2002_aiclient.session.connection.socket.create_connection",
        lambda *a, **k: _Sock([]),
    )
    started = []
    monkeypatch.setattr(
        "tw2002_aiclient.session.connection.threading.Thread",
        lambda **kw: type("T", (), {"start": lambda s: started.append(1)})(),
    )
    c.connect()
    assert c.reader_failure is None, "stale failure survived a reconnect"
    assert c.connected is True


def test_a_dying_old_reader_cannot_mark_a_new_connection_down(monkeypatch) -> None:
    """Accept #3 -- no race with the shutdown/reconnect path.

    `close()` does not join the reader thread, so a dying reader can outlive
    its own connection: close -> reconnect -> the OLD thread's `finally`
    fires and marks the NEW, live connection down. The generation guard is
    what prevents it.

    (The race predates this WO: the original `connected = False` sat after
    the loop with the same exposure. Widening the clear to fire on exception
    paths too would have widened the window rather than leaving it as found,
    which is why the guard ships with the fix rather than after it.)

    Drives the REAL `_reader_loop` rather than re-implementing its `finally`
    in the test: an earlier draft did the latter and was vacuous -- removing
    the product guard left it green, because the test was exercising its own
    copy of the logic. Caught by mutation-testing the pin.
    """

    class _ReconnectingNegotiator:
        """A reconnect lands while THIS thread is mid-failure -- the exact
        interleaving, made deterministic."""

        def __init__(self): self.conn = None
        def feed(self, data):
            self.conn._reader_generation += 1   # a new connect() bumps it ...
            self.conn.connected = True          # ... and declares itself live
            raise ValueError("the old thread's failure")
        def pop_pending_output(self): return b""

    neg = _ReconnectingNegotiator()
    c = _conn(neg, _Sock([b"x"]))
    neg.conn = c

    _run_loop(c)

    assert c.connected is True, (
        "a dead OLD reader marked the live NEW connection down"
    )
    assert c.reader_failure is not None, "the old thread's failure still records"


def test_generation_guard_still_clears_for_the_current_reader() -> None:
    """The guard must not become an excuse never to clear the flag -- the
    ordinary case still marks down."""
    c = _conn(_RaisingNegotiator(), _Sock([b"x"]))
    _run_loop(c)
    assert c.connected is False


def test_a_fresh_connection_reports_no_failure() -> None:
    c = TelnetConnection("h", 1, _Terminal(), _CleanNegotiator())
    assert c.reader_failure is None
    assert c.connected is False
