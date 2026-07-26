"""Shared harness for the `tw attach` TERMINAL-ENCODING proofs.

Why a subprocess at all, when the sibling attach tests drive `cmd_attach`
in-process with a scripted stdin: the defects these tests cover live in
``sys.stdout``/``sys.stdin``'s *codec*, and a process cannot honestly
choose its own stdio codec after it has started. ``LC_ALL`` / ``LANG`` /
``PYTHONIOENCODING`` are read by the interpreter at startup, so the only
way to prove "attach survives on an 8-bit or ascii terminal" is to launch
a real interpreter with that environment, on a real pty, against a real
daemon on a real unix socket.

**The injection gate is a ``tty.setcbreak`` spy, never the banner.**
``tty.setcbreak`` defaults to ``termios.TCSAFLUSH``, which DISCARDS input
already queued on the tty. Keys written before that call are silently
thrown away -- so a test that waits for the ``ATTACHED`` banner and then
injects would prove nothing while appearing to pass, because the banner is
printed *before* ``setcbreak`` runs. Worse, on exactly the terminals these
tests target the banner may never print at all: printing it was itself one
of the defects. The driver below therefore wraps ``tty.setcbreak``, calls
through to the real one FIRST, and only then emits ``CBREAK_MARKER``. That
marker is the single safe moment to write a key.
"""

from __future__ import annotations

import os
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from tests.conftest import _FAKE_DAEMON_IMPORTS_OK, _FakeDaemon
from tests.pty_helpers import terminate_session_group

REPO_ROOT = Path(__file__).resolve().parents[1]

CBREAK_MARKER = "<<CBREAK-ARMED>>"

# Runs in the CHILD. Wraps `tty.setcbreak` before `cmd_attach` can look it
# up (cli.py imports `tty` inside the function, so the module attribute is
# resolved at call time and this patch is seen). Pure ASCII on purpose --
# it has to survive the very ascii/latin-1 stdout under test.
_DRIVER_SRC = f'''\
import sys
import tty

from tw2002_aiclient.session import cli

_real_setcbreak = tty.setcbreak


def _spy(fd, when=None):
    if when is None:
        _real_setcbreak(fd)
    else:
        _real_setcbreak(fd, when)
    # AFTER the real call: TCSAFLUSH has now discarded anything queued, so
    # this is the first instant at which a written key can survive.
    sys.stdout.write("{CBREAK_MARKER}\\n")
    sys.stdout.flush()


tty.setcbreak = _spy
raise SystemExit(cli.main(["attach", "--run-dir", sys.argv[1]]))
'''


@pytest.fixture
def attach_daemon(tmp_path):
    """A REAL daemon on a REAL unix socket, at the `twd.sock` name
    `env.socket_path()` resolves to, under a SHORT /tmp dir (pytest's
    `tmp_path` overflows AF_UNIX's ~104-byte sun_path limit -- same
    reason as conftest.py's own `fake_daemon`)."""
    if not _FAKE_DAEMON_IMPORTS_OK:
        pytest.skip("needs tw2002_aiclient.session.{control_lock,watch,daemon}")
    run_dir = Path(tempfile.mkdtemp(prefix="twd-term-", dir="/tmp"))
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    daemon.run_dir = run_dir
    try:
        deadline = time.monotonic() + 5.0
        while not (run_dir / "twd.sock").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        yield daemon
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


def _child_env(overrides):
    env = dict(os.environ)
    for var in ("LC_ALL", "LANG", "PYTHONIOENCODING", "PYTHONUTF8",
                "PYTHONCOERCECLOCALE"):
        env.pop(var, None)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env.update(overrides)
    return env


def run_attach_on_terminal(daemon, tmp_path, *, env_overrides, keys,
                           timeout=25.0):
    """Launch a real `tw attach` on a real pty under `env_overrides`.

    Waits for the ``setcbreak`` spy's marker before writing ``keys``.
    Returns ``(rc, output_str, cbreak_armed)``. ``cbreak_armed`` False
    means attach died before ever taking the keyboard -- which is exactly
    what the banner crash looked like.
    """
    driver = tmp_path / "attach_driver.py"
    driver.write_text(_DRIVER_SRC, encoding="utf-8")

    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        [sys.executable, str(driver), str(daemon.run_dir)],
        stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
        cwd=str(REPO_ROOT), env=_child_env(env_overrides),
        start_new_session=True,
    )
    os.close(slave_fd)

    out = bytearray()
    armed = False
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master_fd], [], [], 0.1)
            if ready:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break  # slave closed -- child exited
                if not chunk:
                    break
                out += chunk
            if not armed and CBREAK_MARKER.encode() in bytes(out):
                armed = True
                try:
                    os.write(master_fd, keys)
                except OSError:
                    pass  # child already gone
            if proc.poll() is not None and not ready:
                break
        # grace_s=5.0 restores the voluntary-exit window the old
        # `proc.wait(timeout=5)` gave a real `tw attach` process before any
        # kill (this is the one call site that had one -- the other two
        # `terminate_session_group` sites in this suite killed immediately
        # even before this helper existed, so they are unchanged).
        terminate_session_group(proc, grace_s=5.0)
        # Drain whatever the child wrote just before exiting.
        drain_until = time.monotonic() + 1.0
        while time.monotonic() < drain_until:
            ready, _, _ = select.select([master_fd], [], [], 0.1)
            if not ready:
                break
            try:
                chunk = os.read(master_fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
    finally:
        os.close(master_fd)

    # `replace` so a test can always SEE what the child emitted, including
    # a mojibake or partial-write failure it is asserting about.
    return proc.returncode, bytes(out).decode("utf-8", "replace"), armed
