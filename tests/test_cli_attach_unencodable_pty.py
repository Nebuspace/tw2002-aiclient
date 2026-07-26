"""WO-AUDIT-KEYDROP-HONESTY (session-audit F2), Accept #3 — an unencodable
keystroke must NOT end the pilot's attach session.

End-to-end on a REAL pty against a REAL daemon over a REAL unix socket: a
child ``tw attach`` process, its stdin a genuine terminal, talking to an
actual ``ThreadingUnixServer`` + ``CommandHandler``. Nothing between the
keystroke and ``session.send_raw`` is faked, because the claim under test
spans every one of those layers — ``sys.stdin``'s UTF-8 decode, ``cmd_attach``'s
encode, ``AttachInputConn``'s JSON frame, the socket, and the daemon's own
encode. A unit test of any single layer cannot see it.

This is the counterpart to the constraint that shapes the whole WO. Two
conditions must never share a handler:

* **transport failure** — the wire is dead. ``WO-AUDIT-ATTACH-SEND-KEY-BOOL``
  (7e13b7d) correctly ends attach with rc 1. Its proofs live in
  tests/test_cli_attach_interactive_send_failure.py and are untouched.
* **unencodable key** — the wire is fine; one character has no 8-bit form.
  Ending the pilot's session over a pasted em-dash would be the worse harm.
  That is what this file proves, by running the session PAST the refusal.

Timing note (learned the hard way, do not "simplify" this): ``tty.setcbreak``
defaults to ``when=termios.TCSAFLUSH``, which DISCARDS input already received
but not yet read. Keys injected before ``cmd_attach`` enters cbreak are
silently flushed and the child then blocks forever. The child therefore spies
``tty.setcbreak`` and prints ``CBREAK-READY`` only after the real call
returns; injection is gated on that marker. Gating on the program's own
``ATTACHED`` banner would NOT work — the banner is printed before
``setcbreak``, so keys sent on it land inside the flush window.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path

import pytest

pytestmark = pytest.mark.pty_ui


from tw2002_aiclient.session import env
from tw2002_aiclient.session.control_lock import ControlLock
from tw2002_aiclient.session.daemon import CommandHandler, ThreadingUnixServer

from .conftest import FakeAttachSession
from .pty_helpers import capture_pty_with_keys

DETACH_KEYS = bytes([29])  # Ctrl-]

# U+2192 RIGHTWARDS ARROW: no latin-1 form, and the audit's own reproduction
# character. Injected as the UTF-8 bytes a real terminal would deliver.
ARROW_UTF8 = "→".encode("utf-8")

# The marker is the CODEPOINT, not the sentence around it. What the operator
# must learn is *which* key was refused; the surrounding wording is prose and
# may be reworded without breaking this proof.
REFUSAL_MARKER = b"U+2192"

# Runs the real ``cmd_attach`` with only ONE thing added: a spy that announces
# when the real ``tty.setcbreak`` has returned. ``cmd_attach`` does its
# ``import tty`` inside the function body, so patching the module attribute
# out here is picked up at call time. Everything read from the environment,
# so no operator-home path is ever baked into this file.
_CHILD = """
import os, sys
sys.path.insert(0, os.environ["TW_REPO_ROOT"])
import tty
from argparse import Namespace

_real_setcbreak = tty.setcbreak

def _spy(fd, *a, **k):
    _real_setcbreak(fd, *a, **k)
    # cbreak touches LFLAG/CC only -- ONLCR is still on, so this prints as a
    # proper line on the pty.
    print("CBREAK-READY", flush=True)

tty.setcbreak = _spy

from tw2002_aiclient.session import cli

rc = cli.cmd_attach(Namespace(run_dir=os.environ["TW_RUN_DIR"], keys=None))
print("RC=%d" % rc, flush=True)
"""


class _PtyDaemon:
    """Real server + ``FakeAttachSession``, listening on the canonical
    ``<run_dir>/twd.sock`` so the child's ``tw attach`` resolves it the same
    way the product does."""

    def __init__(self, run_dir):
        self.run_dir = Path(run_dir)
        self.session = FakeAttachSession()
        self.control_lock = ControlLock()
        self.server = ThreadingUnixServer(str(env.socket_path(self.run_dir)), CommandHandler)
        self.server.session = self.session
        self.server.control_lock = self.control_lock
        self.server.watch_hub = None
        self.server.request_stop = lambda: None
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def pty_daemon():
    # mkdtemp, not tmp_path: pytest's tmp_path routinely overflows AF_UNIX's
    # ~104-byte sun_path limit.
    run_dir = tempfile.mkdtemp(prefix="twd-f2pty-")
    daemon = _PtyDaemon(run_dir)
    try:
        yield daemon
    finally:
        daemon.stop()


def _run_attach(tmp_path, pty_daemon, steps, stop_condition):
    child = tmp_path / "attach_child.py"
    child.write_text(_CHILD, encoding="utf-8")
    child_env = dict(
        os.environ,
        TW_REPO_ROOT=str(Path(__file__).resolve().parents[1]),
        TW_RUN_DIR=str(pty_daemon.run_dir),
        # Pin the child's stdin/stdout codec: under LC_ALL=C a real terminal
        # would hand `sys.stdin.read(1)` an ASCII decoder and the arrow would
        # fail to DECODE before ever reaching the encode under test. A real
        # operator's terminal is UTF-8; this makes that explicit rather than
        # inherited from whatever locale the suite happens to run under.
        PYTHONIOENCODING="utf-8",
    )
    return capture_pty_with_keys(
        [sys.executable, str(child)],
        steps=steps,
        stop_condition=stop_condition,
        env=child_env,
        detach_keys=DETACH_KEYS,
        timeout=20.0,
    )


def test_unencodable_key_is_reported_and_the_session_keeps_flying(tmp_path, pty_daemon):
    """The whole WO in one run: type an unencodable character, get told,
    stay attached, type a normal one and watch it reach the game, detach
    clean with rc 0.

    ``rc == 0`` is load-bearing twice over. It proves the refusal did not
    take the ``send_failed`` exit (which returns 1), and — because the daemon
    now refuses a zero-byte key too — it proves no empty payload was quietly
    forwarded in the arrow's place. An empty forward would have come back
    ``{"ok": false, "error": "empty_key"}``, tripped ``send_failed``, and
    ended this run at rc 1.
    """
    captured = _run_attach(
        tmp_path,
        pty_daemon,
        steps=[
            (b"CBREAK-READY", ARROW_UTF8),   # only safe AFTER the real cbreak
            (REFUSAL_MARKER, b"x"),          # ... the session is still alive?
        ],
        stop_condition=lambda data: REFUSAL_MARKER in data,
    )

    assert b"ATTACHED" in captured, "the child never got as far as attaching"
    assert REFUSAL_MARKER in captured, (
        "the operator was never told which key was refused:\n" + captured.decode(errors="replace")
    )
    assert pty_daemon.session.raw_sent == [b"x"], (
        "the keystroke typed AFTER the refusal must still reach the game, and "
        "the refused one must leave nothing behind it: "
        f"{pty_daemon.session.raw_sent!r}"
    )
    assert b"RC=0" in captured, (
        "an unencodable key must not end attach:\n" + captured.decode(errors="replace")
    )
    assert b"send_failed" not in captured, (
        "an unencodable key must never be reported as a transport failure"
    )


def test_an_ordinary_key_needs_no_notice(tmp_path, pty_daemon):
    """Control run on the same harness. Without it, the test above could pass
    against a build that printed a refusal notice for every keystroke."""
    captured = _run_attach(
        tmp_path,
        pty_daemon,
        steps=[(b"CBREAK-READY", b"d")],
        stop_condition=lambda data: b"CBREAK-READY" in data,
    )

    assert pty_daemon.session.raw_sent == [b"d"]
    assert b"U+" not in captured, "no refusal notice may appear for an ordinary key"
    assert b"RC=0" in captured
