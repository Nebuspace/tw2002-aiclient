"""WO-AUDIT-ATTACH-SEND-KEY-BOOL — ``tw attach``'s INTERACTIVE loop must
not swallow the pilot's keystrokes while still claiming ``ATTACHED``.

``cmd_attach``'s interactive branch discarded ``AttachInputConn.send_key()``'s
bool at BOTH call sites (the ``\\r\\n`` one and the general one), looped on,
and returned 0 -- so a dead wire looked exactly like a live one to the human
holding the keyboard. This is the sibling of WO-AUDIT-CLI-KEYS-IGNORE-RETURN,
which fixed the scripted ``--keys`` branch twenty lines above and left this
half untouched (see tests/test_cli_attach_keys_exit_code.py).

The interactive path needs a real tty fd -- ``sys.stdin.isatty()`` gates
entry and ``termios.tcgetattr/tcsetattr`` need a terminal -- so these tests
pair a real ``pty.openpty()`` slave (for ``fileno()``) with a scripted
``read(1)``. That combination keeps the terminal-state assertions honest
(the cbreak switch and its restore really happen on a real tty) while the
keystroke sequence stays deterministic, with no reliance on injection
timing. The end-to-end real-pty exit-code run lives in the WO's proof.
"""

from __future__ import annotations

import ast
import builtins
from argparse import Namespace
from pathlib import Path

import pytest

from tests.attach_helpers import FakeAttachConn as _FakeAttachConn
from tests.attach_helpers import terminal_mode
from tw2002_aiclient.session import attach_client, cli, env

DETACH_CH = chr(29)  # Ctrl-] — the documented interactive detach key

CLI_SRC_PATH = Path(cli.__file__)


class _ScriptedTtyStdin:
    """A real tty fd (so termios/cbreak are exercised for real) with a
    scripted ``read(1)``. Snapshots the terminal attrs on every keystroke,
    which is when the code under test is provably inside cbreak."""

    def __init__(self, fd, chars):
        self._fd = fd
        self._chars = list(chars)
        self.attrs_while_reading = []

    def isatty(self):
        return True

    def fileno(self):
        return self._fd

    def read(self, n=1):
        self.attrs_while_reading.append(terminal_mode(self._fd))
        return self._chars.pop(0) if self._chars else ""  # "" == EOF


def _attach(monkeypatch, tmp_path, tty_fd, *, chars, send_ok):
    """Run the real interactive ``cmd_attach`` against a scripted tty.
    Returns ``(rc, fake_conn, fake_stdin, attrs_before, attrs_after)``."""
    env.socket_path(tmp_path).touch()
    fake = _FakeAttachConn(send_ok=send_ok)
    monkeypatch.setattr(attach_client, "AttachInputConn", lambda sock_path: fake)
    stdin = _ScriptedTtyStdin(tty_fd, chars)
    monkeypatch.setattr(cli.sys, "stdin", stdin)

    before = terminal_mode(tty_fd)
    rc = cli.cmd_attach(Namespace(run_dir=str(tmp_path), keys=None))
    after = terminal_mode(tty_fd)
    return rc, fake, stdin, before, after


# -- the defect: a failed send must be visible, and must stop the loop ------

@pytest.mark.parametrize(
    "ch, expected_bytes",
    [
        ("\r", b"\r\n"),   # the CR call site
        ("\n", b"\r\n"),   # ... and its LF twin, same call site
        ("x", b"x"),       # the general call site
    ],
)
def test_failed_send_is_reported_and_exits_non_zero(
    monkeypatch, tmp_path, tty_fd, capsys, ch, expected_bytes
):
    """Both call sites: send_key() -> False ends the session with a visible
    error and a non-zero rc. No detach key is scripted, so the only thing
    that can end this loop is the failed send itself."""
    rc, fake, _stdin, _before, _after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=[ch], send_ok=False
    )

    assert rc == 1, "a session whose keystrokes were dropped must not exit 0"
    out = capsys.readouterr().out
    assert "ERROR" in out and "send_failed" in out, out
    assert fake.sent == [expected_bytes]


def test_failed_send_stops_the_loop_on_the_first_failure(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """Three keys are queued but the wire is dead: the loop leaves after the
    FIRST failure instead of grinding through the rest into a black hole."""
    rc, fake, stdin, _before, _after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=["a", "b", "c"], send_ok=False
    )
    capsys.readouterr()

    assert rc == 1
    assert fake.sent == [b"a"], "must not keep sending after a failed send"
    assert len(stdin.attrs_while_reading) == 1, "must not keep reading keystrokes either"


def test_failure_path_restores_the_terminal_and_closes_the_connection(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """The new early exit must not skip either ``finally:``. A fix that
    leaves the operator's terminal in cbreak is worse than the bug."""
    rc, fake, stdin, before, after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=["x"], send_ok=False
    )
    capsys.readouterr()

    assert rc == 1
    assert stdin.attrs_while_reading, "the loop never read a key -- test proves nothing"
    assert stdin.attrs_while_reading[0] != before, (
        "cbreak never actually changed the terminal, so 'restored' is untestable here"
    )
    assert after == before, "termios.tcsetattr must restore the terminal on the failure path"
    assert fake.closed, "conn.close() must still run (outer finally:) on the failure path"


def test_failure_is_reported_after_the_terminal_is_restored(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """Ordering, not just occurrence: the terminal is already restored when
    the operator's error line is printed, so the message lands on a sane
    terminal rather than inside cbreak."""
    seen_at_print = {}
    real_print = builtins.print

    def _spy_print(*args, **kwargs):
        if args and "send_failed" in str(args[0]):
            seen_at_print["attrs"] = terminal_mode(tty_fd)
        return real_print(*args, **kwargs)

    monkeypatch.setattr(cli, "print", _spy_print, raising=False)
    rc, _fake, _stdin, before, _after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=["x"], send_ok=False
    )
    capsys.readouterr()

    assert rc == 1
    assert "attrs" in seen_at_print, "the error line was never printed"
    assert seen_at_print["attrs"] == before


# -- the happy path stays untouched ---------------------------------------

def test_successful_sends_still_loop_until_detach_and_exit_zero(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """Regression guard for the fix itself: with a live wire every key is
    forwarded and only Ctrl-] ends the session, still exit 0, still silent."""
    rc, fake, _stdin, before, after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=["a", "\r", "b", DETACH_CH, "z"], send_ok=True
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "ERROR" not in out
    assert fake.sent == [b"a", b"\r\n", b"b"], "Ctrl-] must detach without being forwarded"
    assert fake.closed
    assert after == before


def test_eof_still_exits_zero(monkeypatch, tmp_path, tty_fd, capsys):
    """Pre-existing behavior, preserved: an empty ``read(1)`` (EOF) leaves
    the loop with rc 0 -- nothing was dropped, so nothing is reported."""
    rc, fake, _stdin, _before, _after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=[], send_ok=False
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "ERROR" not in out
    assert fake.sent == []
    assert fake.closed


# -- tripwire: the return value can never be discarded again ---------------

def test_no_send_key_call_discards_its_return_value():
    """Mechanical guard, not prose: a ``send_key(...)`` call that stands
    alone as an expression statement is a discarded bool by definition.
    That exact shape is what created this WO and its scripted-branch twin,
    at three call sites over two commits -- so it is banned outright rather
    than re-reviewed by eye."""
    tree = ast.parse(CLI_SRC_PATH.read_text(encoding="utf-8"))

    discarded = [
        f"cli.py:{node.lineno}: {ast.unparse(node)}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "send_key"
    ]

    assert not discarded, (
        "send_key() returns False on a dead wire; these call sites throw it away:\n  "
        + "\n  ".join(discarded)
    )


def test_tripwire_would_catch_the_original_defect():
    """The guard above only means something if it can go red -- pinned
    against the exact pre-fix source shape rather than trusted."""
    pre_fix_shape = (
        "def cmd_attach(args):\n"
        "    if ch in ('\\n', '\\r'):\n"
        "        conn.send_key(b'\\r\\n')\n"
        "    else:\n"
        "        conn.send_key(ch.encode('latin-1', errors='ignore'))\n"
    )
    tree = ast.parse(pre_fix_shape)

    discarded = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "send_key"
    ]

    assert len(discarded) == 2, "the tripwire must flag BOTH original call sites"
