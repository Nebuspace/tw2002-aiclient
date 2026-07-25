"""Pin: FakeTWGS stop() during an active script must not poison `.errors`.

Under pytest-xdist, worker teardown races the accept-thread mid-send/recv
and historically recorded `OSError: Bad file descriptor` into `.errors`,
failing unrelated `assert not fake.errors` Accept checks (WO-TEST-FAKE-SERVER-SOCKET-FLAKE).
"""

from __future__ import annotations

import socket
import threading
import time

from .fake_twgs import FakeTWGS


def test_stop_during_hold_leaves_errors_empty():
    fake = FakeTWGS(handle="AEGIS", game_letter="F", password="pw-not-used", mode="returning")
    fake.start()
    # Connect but send nothing — server blocks in outer_name expect_line.
    client = socket.create_connection(("127.0.0.1", fake.port), timeout=2)
    time.sleep(0.05)  # let accept + first _send complete
    fake.stop()
    client.close()
    assert fake.errors == [], fake.errors


def test_stop_while_client_half_open_leaves_errors_empty():
    """Client gone; stop() must not record EBADF from the hold/recv path."""
    fake = FakeTWGS(handle="AEGIS", game_letter="F", password="secret-ok", mode="returning")
    with fake:
        client = socket.create_connection(("127.0.0.1", fake.port), timeout=2)
        # Drive just far enough that the server is in a recv wait, then abort.
        # outer_name expects blank line.
        client.sendall(b"\r\n")
        time.sleep(0.05)
        client.close()
        time.sleep(0.05)
    assert fake.errors == [], fake.errors
