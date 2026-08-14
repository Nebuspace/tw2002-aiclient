"""Shared fixtures/helpers for in-process ``tw attach`` CLI tests.

WO-CLEANUP-DEDUP-ATTACH-TEST-FIXTURES — extract the STRUCT-DUP harness that
was hand-copied across ``test_cli_attach_*.py`` (``_FakeAttachConn``,
``terminal_mode``, ``tty_fd``). Behavior-preserving only; scripted-stdin
classes stay per-file (they diverge on purpose).

Registered via ``pytest_plugins`` in ``tests/conftest.py`` so ``tty_fd`` is
available by name without redefining it in each module.
"""

from __future__ import annotations

import os
import pty
import termios

import pytest

_LFLAG = 3  # index of lflag in a termios.tcgetattr() list


def terminal_mode(fd):
    """``tcgetattr(fd)`` with the transient ``PENDIN`` status bit masked off.

    ``PENDIN`` ("input is pending re-print") is set by the kernel behind the
    caller's back during a cbreak round trip -- it is not part of the mode
    ``cmd_attach`` saved and restored. Comparing it would fail restore
    assertions for a reason that has nothing to do with the restore; every
    flag cbreak actually clears stays unmasked and compared.
    """
    attrs = list(termios.tcgetattr(fd))
    attrs[_LFLAG] &= ~getattr(termios, "PENDIN", 0)
    return attrs


class FakeAttachConn:
    """Stands in for ``AttachInputConn`` -- ``cmd_attach`` only ever calls
    ``connect()``, ``send_key(data)``, and ``close()`` on it."""

    def __init__(self, sock_path=None, *, send_ok=True):
        self.sock_path = sock_path
        self._send_ok = send_ok
        self.error = None
        self.sent = []
        self.closed = False

    def connect(self):
        return True

    def send_key(self, data):
        self.sent.append(data)
        return self._send_ok

    def close(self):
        self.closed = True


@pytest.fixture
def tty_fd():
    master_fd, slave_fd = pty.openpty()
    try:
        yield slave_fd
    finally:
        for fd in (master_fd, slave_fd):
            try:
                os.close(fd)
            except OSError:
                pass
