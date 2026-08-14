"""D2 -- an 8-bit key the terminal could not DECODE is deliverable, and
must be delivered.

`cmd_attach` read `sys.stdin.read(1)`, which decodes bytes to `str` before
any of attach's own encoding logic runs. Under the default stdio setup
(utf-8 with `surrogateescape`) a raw byte `0xFF` therefore arrives as the
lone surrogate U+DCFF, `encode("latin-1")` raises, and the operator was
told:

    NOT SENT: key U+DCFF has no 8-bit encoding for this game connection

Wrong twice. `0xFF` HAS a perfect 8-bit form -- it is exactly the byte class
an 8-bit TradeWars wire is made of (an 8-bit Meta terminal, a latin-1 host,
a pasted latin-1 blob) -- and U+DCFF is a codepoint that exists on no
keyboard and that the operator never pressed. Under a *strict* stdin the
same byte instead raised `UnicodeDecodeError` and killed attach outright.

The fix is PEP 383's own definition read backwards: U+DC80-U+DCFF *is* byte
0x80-0xFF, so recover the byte and send it. What must NOT change is the
neighbouring behaviour -- a genuine unencodable CHARACTER (a real arrow) is
still refused, still non-fatal; a dead wire still ends attach with rc 1.
Both are pinned below, because a fix that widened into either would be a
regression dressed as a feature.
"""

from __future__ import annotations

import io
import os
import pty
from argparse import Namespace

import pytest

from tests.attach_helpers import FakeAttachConn as _FakeAttachConn
from tests.attach_helpers import terminal_mode
from tests.attach_terminal_harness import (  # noqa: F401  (fixture import)
    attach_daemon,
    run_attach_on_terminal,
)
from tw2002_aiclient.session import attach_client, cli, env

DETACH_CH = chr(29)
DETACH = bytes([29])


class _ScriptedTtyStdin:
    """A real tty fd with a scripted `read(1)`, matching the harness in
    tests/test_cli_attach_unencodable_key.py. Deliberately has NO
    `reconfigure` and no `errors`, which is also what makes it the natural
    probe for `_arm_lossless_stdin`'s can't-reconfigure path."""

    def __init__(self, fd, chars):
        self._fd = fd
        self._chars = list(chars)
        self.reads = 0

    def isatty(self):
        return True

    def fileno(self):
        return self._fd

    def read(self, n=1):
        self.reads += 1
        return self._chars.pop(0) if self._chars else ""


class _RaisingTtyStdin(_ScriptedTtyStdin):
    """Raises `UnicodeDecodeError` on the Nth read -- what a strict stdin
    does when handed a byte it cannot decode."""

    def __init__(self, fd, chars, raise_on_read):
        super().__init__(fd, chars)
        self._raise_on_read = raise_on_read

    def read(self, n=1):
        self.reads += 1
        if self.reads == self._raise_on_read:
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        return self._chars.pop(0) if self._chars else ""


def _attach(monkeypatch, tmp_path, tty_fd, *, stdin, send_ok=True):
    env.socket_path(tmp_path).touch()
    fake = _FakeAttachConn(send_ok=send_ok)
    monkeypatch.setattr(attach_client, "AttachInputConn", lambda sock_path: fake)
    monkeypatch.setattr(cli.sys, "stdin", stdin)
    before = terminal_mode(tty_fd)
    rc = cli.cmd_attach(Namespace(run_dir=str(tmp_path), keys=None))
    after = terminal_mode(tty_fd)
    return rc, fake, before, after


# -- the defect: a recovered byte is SENT, not refused ---------------------

@pytest.mark.parametrize("byte_value", [0x80, 0x9B, 0xA0, 0xE9, 0xFE, 0xFF])
def test_a_surrogate_escaped_byte_is_delivered_as_that_byte(
    monkeypatch, tmp_path, tty_fd, capsys, byte_value
):
    """U+DC80-U+DCFF -> 0x80-0xFF, sent verbatim. Spread across the range
    including both ends, so an off-by-one at either boundary shows up."""
    ch = chr(0xDC00 + byte_value)
    stdin = _ScriptedTtyStdin(tty_fd, [ch, DETACH_CH])
    rc, fake, _before, _after = _attach(monkeypatch, tmp_path, tty_fd, stdin=stdin)
    out = capsys.readouterr().out

    assert rc == 0
    assert fake.sent == [bytes([byte_value])], (
        f"U+{ord(ch):04X} is byte 0x{byte_value:02X} and the wire is 8-bit"
    )
    assert "NOT SENT" not in out, out


def test_the_operator_is_never_told_about_a_codepoint_they_did_not_press(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """The naming half of the defect, pinned separately from the delivery
    half: 'U+DCFF' must not appear in any operator-facing line, because no
    keyboard produces it."""
    stdin = _ScriptedTtyStdin(tty_fd, [chr(0xDCFF), DETACH_CH])
    rc, _fake, _before, _after = _attach(monkeypatch, tmp_path, tty_fd, stdin=stdin)
    out = capsys.readouterr().out

    assert rc == 0
    assert "DCFF" not in out.upper(), out


def test_a_run_of_undecodable_bytes_all_reach_the_wire_in_order(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """A pasted latin-1 blob is the realistic case. Order and interleaving
    with ordinary keys both matter -- this is a keystroke stream."""
    chars = [chr(0xDCE9), "a", chr(0xDCFF), "\r", chr(0xDC80), "b", DETACH_CH]
    stdin = _ScriptedTtyStdin(tty_fd, chars)
    rc, fake, _before, _after = _attach(monkeypatch, tmp_path, tty_fd, stdin=stdin)
    capsys.readouterr()

    assert rc == 0
    assert fake.sent == [b"\xe9", b"a", b"\xff", b"\r\n", b"\x80", b"b"]


# -- the boundary: do not over-recover -------------------------------------

def test_a_genuine_unencodable_character_is_still_refused_and_survivable(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """The shipped behaviour this fix must not weaken. A real arrow is a
    CHARACTER the wire cannot carry, not a byte the terminal could not
    decode -- it is still refused, still named, still non-fatal, and the
    next ordinary key still flies."""
    stdin = _ScriptedTtyStdin(tty_fd, ["→", "x", DETACH_CH])
    rc, fake, _before, _after = _attach(monkeypatch, tmp_path, tty_fd, stdin=stdin)
    out = capsys.readouterr().out

    assert rc == 0
    assert "NOT SENT" in out and "U+2192" in out, out
    assert fake.sent == [b"x"], "the arrow never flew; the next key did"


@pytest.mark.parametrize("code", [0xD800, 0xDBFF, 0xDC00, 0xDC7F, 0xDD00, 0xDFFF])
def test_surrogates_outside_the_pep383_range_are_not_treated_as_bytes(
    monkeypatch, tmp_path, tty_fd, capsys, code
):
    """PEP 383 uses U+DC80-U+DCFF and nothing else. A high surrogate, or a
    low one below DC80 or above DCFF, is NOT an escaped byte -- inventing a
    byte for it would put a character on the wire the operator never typed.
    These stay on the refusal path. Pins both edges of the recovery window
    from the outside; the parametrized delivery test pins them from within.
    """
    stdin = _ScriptedTtyStdin(tty_fd, [chr(code), DETACH_CH])
    rc, fake, _before, _after = _attach(monkeypatch, tmp_path, tty_fd, stdin=stdin)
    out = capsys.readouterr().out

    assert rc == 0
    assert fake.sent == [], f"U+{code:04X} is not a PEP 383 escaped byte"
    assert "NOT SENT" in out and f"U+{code:04X}" in out, out


def test_ordinary_keys_enter_and_the_detach_key_are_completely_unmoved(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """The explicit condition on changing anything about how stdin is read:
    the ordinary path must behave exactly as before -- printable keys byte
    for byte, Enter as CRLF, Ctrl-] intercepted and never forwarded."""
    stdin = _ScriptedTtyStdin(tty_fd, ["h", "i", "\r", "\n", "\x00", "\x7f", DETACH_CH, "z"])
    rc, fake, before, after = _attach(monkeypatch, tmp_path, tty_fd, stdin=stdin)
    out = capsys.readouterr().out

    assert rc == 0
    assert fake.sent == [b"h", b"i", b"\r\n", b"\r\n", b"\x00", b"\x7f"]
    assert stdin.reads == 7, "Ctrl-] ended the loop; 'z' was never read"
    assert "NOT SENT" not in out
    assert after == before, "terminal restored"


def test_a_dead_wire_still_ends_the_session_with_rc_1(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """Regression guard for 7e13b7d, re-pinned here because this WO adds a
    new branch directly in that key's path. A recovered byte is sent through
    the SAME `send_key` check, so a transport failure on one must still be
    fatal."""
    stdin = _ScriptedTtyStdin(tty_fd, [chr(0xDCFF), "a"])
    rc, fake, _before, _after = _attach(
        monkeypatch, tmp_path, tty_fd, stdin=stdin, send_ok=False
    )
    out = capsys.readouterr().out

    assert rc == 1
    assert "send_failed" in out, out
    assert fake.sent == [b"\xff"], "the recovered byte was attempted, then the wire died"


# -- _arm_lossless_stdin ---------------------------------------------------

def test_arm_lossless_stdin_reconfigures_a_strict_stream(monkeypatch):
    """A strict TextIOWrapper over a real tty -- the exact shape `sys.stdin`
    has -- becomes surrogateescape."""
    master_fd, slave_fd = pty.openpty()
    try:
        stream = io.TextIOWrapper(
            io.BufferedReader(io.FileIO(os.dup(slave_fd), "rb")),
            encoding="utf-8", errors="strict",
        )
        monkeypatch.setattr(cli.sys, "stdin", stream)
        assert stream.errors == "strict"
        assert cli._arm_lossless_stdin() is True
        assert stream.errors == "surrogateescape"
    finally:
        for fd in (master_fd, slave_fd):
            try:
                os.close(fd)
            except OSError:
                pass


def test_arm_lossless_stdin_is_a_no_op_when_already_lossless(monkeypatch):
    class _Already:
        errors = "surrogateescape"

        def reconfigure(self, **kwargs):  # pragma: no cover - must not run
            raise AssertionError("must not reconfigure an already-lossless stream")

    monkeypatch.setattr(cli.sys, "stdin", _Already())
    assert cli._arm_lossless_stdin() is True


def test_arm_lossless_stdin_reports_false_instead_of_raising(monkeypatch):
    """A stdin that cannot be reconfigured -- a test double, or a stream
    something already read -- must not take attach down with it."""
    class _NoReconfigure:
        errors = "strict"

    class _Refuses:
        errors = "strict"

        def reconfigure(self, **kwargs):
            raise io.UnsupportedOperation(
                "It is not possible to set the encoding or newline of stream "
                "after the first read"
            )

    monkeypatch.setattr(cli.sys, "stdin", _NoReconfigure())
    assert cli._arm_lossless_stdin() is False

    monkeypatch.setattr(cli.sys, "stdin", _Refuses())
    assert cli._arm_lossless_stdin() is False


def test_attach_still_runs_when_stdin_cannot_be_armed(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """`_arm_lossless_stdin` returning False must not be fatal -- the
    scripted-stdin fixtures used by every sibling attach test are exactly
    that case, and they still attach normally."""
    stdin = _ScriptedTtyStdin(tty_fd, ["a", DETACH_CH])
    assert not hasattr(stdin, "reconfigure")
    rc, fake, _before, _after = _attach(monkeypatch, tmp_path, tty_fd, stdin=stdin)

    assert rc == 0
    assert fake.sent == [b"a"]


def test_an_undecodable_stdin_ends_attach_honestly_instead_of_tracebacking(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """The backstop for a stdin that could not be armed. It ENDS the session
    -- measured, a strict decode error also discards the rest of the chunk
    the wrapper had already buffered, so 'report and keep going' would
    silently swallow keys the operator already typed. An honest ERROR plus a
    restored terminal beats a traceback."""
    stdin = _RaisingTtyStdin(tty_fd, ["a", "b"], raise_on_read=2)
    rc, fake, before, after = _attach(monkeypatch, tmp_path, tty_fd, stdin=stdin)
    out = capsys.readouterr().out

    assert rc == 1
    assert "Traceback" not in out
    assert "ERROR" in out and "8-bit key" in out, out
    assert "utf-8" in out, "name the codec, since that is what must change"
    assert fake.sent == [b"a"], "keys before the failure still went out"
    assert fake.closed
    assert after == before, "terminal restored on the backstop path too"


# -- end to end: a real byte, a real terminal, a real daemon ---------------

REAL_TERMINALS = [
    pytest.param({}, id="default-inherited"),
    pytest.param({"PYTHONIOENCODING": "utf-8"}, id="strict-utf-8"),
    pytest.param({"PYTHONIOENCODING": "utf-8:surrogateescape"}, id="surrogateescape"),
    pytest.param({"LC_ALL": "en_US.ISO8859-1"}, id="iso8859-1-locale"),
]


@pytest.mark.parametrize("env_overrides", REAL_TERMINALS)
def test_a_raw_8_bit_byte_reaches_a_real_daemon_from_a_real_terminal(
    attach_daemon, tmp_path, env_overrides
):
    """The claim that actually matters, proven end to end rather than
    against a fake stdin: byte 0xFF typed on a real pty arrives at a real
    daemon over a real unix socket as byte 0xFF.

    RED before the fix: under `strict-utf-8` this was rc 1 and a
    `UnicodeDecodeError` traceback; under the others the byte was refused
    and never sent.
    """
    rc, out, armed = run_attach_on_terminal(
        attach_daemon, tmp_path, env_overrides=env_overrides,
        keys=b"\xff" + DETACH,
    )

    assert armed, out
    assert "Traceback" not in out, out
    assert rc == 0, out
    assert attach_daemon.session.raw_sent == [b"\xff"], out
    assert "NOT SENT" not in out, out
