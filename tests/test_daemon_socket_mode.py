"""WO-AUDIT-DAEMON-SOCKET-MODE (phase 1, MODE ONLY) — the daemon's listen
socket must be owner-only, re-asserted, never left to the operator's umask.

``ThreadingUnixServer`` inherited whatever ``socket.bind()`` produced, which
on AF_UNIX is ``0o777 & ~umask``. Measured against a REAL spawned ``twd``
before the fix:

===========  ==============  ==================================
umask        ``twd.sock``    who else could reach it
===========  ==============  ==================================
``0o022``    ``0o755``       other r-x — no connect (no write bit)
``0o002``    ``0o775``       **group rwx — group could connect**
``0o000``    ``0o777``       **other rwx — anyone could connect**
===========  ==============  ==================================

That matters because the wire has no authentication of any kind: reaching
the socket *is* the authorization. Any process that connects can send any
verb — ``do``/``send``/``attach``/``stop`` — onto the operator's live game
session.

**Why these tests are not merely cosmetic.** Asserting "the mode is 0600"
proves nothing on its own unless the platform actually enforces socket modes
on ``connect()``, so ``test_mode_bits_are_enforced_on_connect_on_this_platform``
proves that link by execution instead of assuming it, and pins the detail
that the governing bit is **write** (which is exactly why the ``0o755`` red
above still denied ``other`` while ``0o775`` did not). And a mode on a socket
that no longer serves would be a perfect, useless score — so
``test_the_hardened_socket_still_serves`` round-trips a real request through
one.

The mode literal is asserted as ``0o600`` rather than imported from
``daemon.SOCK_MODE`` on purpose: a test that reads the constant it is meant
to guard passes just as happily when someone widens the constant.

**Out of scope, deliberately (phase 1 is MODE ONLY).** No peer-credential
check (``SO_PEERCRED`` / ``getpeereid``) — that is a platform fork plus a
policy question about *which* uids may drive, not a mode assertion. Nothing
here touches the run-dir's own mode or the pidfile's.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import stat
import tempfile
import threading
from pathlib import Path

import pytest

from tw2002_aiclient.session.daemon import CommandHandler, ThreadingUnixServer

# The three umasks the audit measured. 0o002 (group-writable) is the one that
# actually let a stranger in on a shared-group box; 0o000 is the worst case.
UMASKS = [0o000, 0o002, 0o022]


@pytest.fixture
def sock_dir():
    """A SHORT socket dir — pytest's `tmp_path` is long enough to blow
    AF_UNIX's ~104-byte address limit."""
    d = tempfile.mkdtemp(prefix="twd-mode-")
    try:
        yield Path(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


@pytest.mark.parametrize("umask_val", UMASKS, ids=[oct(u) for u in UMASKS])
def test_the_listen_socket_is_owner_only_whatever_the_umask(sock_dir, umask_val):
    """`os.umask()` is process-global, which is safe here because pytest runs
    tests sequentially within a process (xdist splits across processes, not
    within one) and the original value is restored in `finally` even on a
    failed assertion."""
    path = sock_dir / f"s{umask_val:03o}.sock"
    old_umask = os.umask(umask_val)
    try:
        server = ThreadingUnixServer(str(path), CommandHandler)
    finally:
        os.umask(old_umask)
    try:
        mode = _mode(path)
        assert mode == 0o600, f"umask {umask_val:#o} left the control socket at {mode:#o}"
        # Named separately because *write* is the bit `connect()` checks --
        # see test_mode_bits_are_enforced_on_connect_on_this_platform.
        assert mode & 0o070 == 0, "group must have no bits at all"
        assert mode & 0o007 == 0, "other must have no bits at all"

        # The load-bearing half of "re-asserted, not umask-dependent": under a
        # permissive umask the inherited mode would have been WIDER, so this
        # is a real change of state and not the umask agreeing with us by luck.
        umask_derived = 0o777 & ~umask_val
        if umask_derived != 0o600:
            assert mode != umask_derived, (
                f"mode {mode:#o} is just the umask default -- nothing was re-asserted"
            )
    finally:
        server.server_close()


def test_the_hardened_socket_still_serves(sock_dir):
    """A 0600 socket that stopped answering would be a vacuous pass. Drive a
    real request through one, under the most permissive umask, so the mode is
    proven on a LIVE socket rather than an inert file."""
    path = sock_dir / "live.sock"
    old_umask = os.umask(0o000)
    try:
        server = ThreadingUnixServer(str(path), CommandHandler)
    finally:
        os.umask(old_umask)

    class _Session:
        history = [("do", {}, "p", "main_command", "prompt")]

    server.session = _Session()
    server.request_stop = lambda: None
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        assert _mode(path) == 0o600

        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c.settimeout(5.0)
        c.connect(str(path))
        try:
            c.sendall(b'{"verb": "history", "args": {"n": 1}}\n')
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = c.recv(65536)
                assert chunk, "hardened socket accepted the connection then went silent"
                buf += chunk
        finally:
            c.close()
        assert json.loads(buf.decode())["ok"] is True
    finally:
        server.shutdown()
        server.server_close()
        t.join(timeout=5)


def test_mode_bits_are_enforced_on_connect_on_this_platform(sock_dir):
    """The link that makes the mode assertion mean something.

    Same uid throughout, so the OWNER class matches every time -- clearing
    the owner bits is the only way to observe enforcement without a second
    user account. If the owner class is enforced, group and other are
    enforced by the same permission check, and 0o600 leaves both with no
    bits at all.

    Also pins WHICH bit governs: `connect()` needs **write**. That is why
    the pre-fix `0o755` still denied `other` (r-x) while `0o775` handed the
    whole group a working control channel.
    """
    path = sock_dir / "probe.sock"
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(path))
    srv.listen(5)
    threading.Thread(target=lambda: _accept_until_closed(srv), daemon=True).start()

    def connects(mode):
        os.chmod(path, mode)
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c.settimeout(2.0)
        try:
            c.connect(str(path))
            return True
        except PermissionError:
            return False
        finally:
            c.close()

    try:
        assert connects(0o600) is True, "the mode this WO installs must still work for its owner"
        assert connects(0o200) is True, "write alone is sufficient -- write is the governing bit"
        assert connects(0o400) is False, "read without write must NOT be able to connect"
        assert connects(0o000) is False, "no bits must not be able to connect"
        # Class matching is first-match, not most-permissive: a wide-open
        # group+other cannot rescue an owner with no bits.
        assert connects(0o077) is False, "owner class is matched first and denies"
    finally:
        srv.close()


def _accept_until_closed(srv):
    while True:
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        conn.close()


def test_the_pidfile_mode_is_deliberately_unchanged(sock_dir):
    """Disclosure pinned as a test rather than left in a report.

    `_claim_pidfile` opens with an explicit `0o644` and this WO did not touch
    it: a pid is not a secret, and the file's real job is the atomic
    `O_EXCL` claim behind the single-connection invariant, which its mode
    does not affect. Note it is still umask-MASKED (an operator at umask
    0o077 gets 0o600), i.e. inherited behavior rather than a decision -- if
    that ever needs to become a decision, this test is where it fails first.
    """
    from tw2002_aiclient.session.daemon import _claim_pidfile

    pidfile = sock_dir / "twd.pid"
    old_umask = os.umask(0o022)
    try:
        _claim_pidfile(pidfile)
    finally:
        os.umask(old_umask)

    assert _mode(pidfile) == 0o644
    assert pidfile.read_text() == str(os.getpid())
