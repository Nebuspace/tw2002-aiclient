"""F2-client — ``tw attach``'s interactive loop must not silently discard a
keystroke it cannot encode.

The loop encoded the operator's keypress with
``ch.encode("latin-1", errors="ignore")``. Anything above U+00FF became
``b""``, which travelled to the daemon as ``{"key": ""}`` and was answered
``{"ok": true}`` -- so the keystroke vanished with *every* surface reporting
success: no message, live ``ATTACHED`` session, rc 0.

The fix is local and pre-wire: encode strictly, catch ``UnicodeEncodeError``,
tell the operator, send nothing, and **keep the session alive**.

That last clause is the whole design, and it is why these tests exist beside
tests/test_cli_attach_interactive_send_failure.py rather than inside it.
``WO-AUDIT-ATTACH-SEND-KEY-BOOL`` (7e13b7d) made a ``send_key() -> False``
end the attach with rc 1, correctly: a dead wire will never carry anything.
An unencodable key is the opposite condition -- the wire is fine and exactly
one character cannot be represented. Ending an operator's session because
they pasted an em-dash would be a worse harm than the drop being fixed, and
on this product the human is the sovereign pilot. So the two conditions must
NOT share a handler, and the tests below pin both halves of that split:
the new path must not become fatal, and the old path must not stop being.
"""

from __future__ import annotations

from argparse import Namespace

import pytest

from tests.attach_helpers import FakeAttachConn as _FakeAttachConn
from tests.attach_helpers import terminal_mode
from tw2002_aiclient.session import attach_client, cli, env

DETACH_CH = chr(29)  # Ctrl-] — the documented interactive detach key

# Characters with no latin-1 encoding — the ones the old `errors="ignore"`
# turned into an empty payload. Spread deliberately across the BMP and one
# astral char, since `ord(ch)` and the message's `U+%04X` both have to cope.
UNENCODABLE = ["→", "—", "“", "\U0001f600"]  # → — “ 😀


class _ScriptedTtyStdin:
    """A real tty fd (so termios/cbreak run for real) with a scripted
    ``read(1)``. Counts reads, which is how "the session is still alive"
    becomes an observation rather than an inference."""

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


# -- the defect: an unencodable key must be reported, never silently dropped --

@pytest.mark.parametrize("ch", UNENCODABLE)
def test_unencodable_key_is_reported_to_the_operator(
    monkeypatch, tmp_path, tty_fd, capsys, ch
):
    """The operator must LEARN the key was not sent, not discover it later by
    the game not responding. The codepoint identifies which key; the glyph is
    deliberately not echoed (ECHO is off in cbreak, and this session may be
    sitting on a game password prompt)."""
    rc, _fake, _stdin, _before, _after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=[ch, DETACH_CH], send_ok=True
    )
    out = capsys.readouterr().out

    assert rc == 0
    assert "NOT SENT" in out, out
    notice = [line for line in out.splitlines() if line.startswith("NOT SENT")]
    assert len(notice) == 1, out
    assert f"U+{ord(ch):04X}" in notice[0], notice[0]
    # Scoped to the notice line, and asserted as pure-ASCII rather than as
    # `ch not in out`: the ATTACHED banner legitimately carries an em-dash of
    # its own, so a whole-output check would be confounded for exactly the
    # character an operator is most likely to paste. Pure-ASCII is the
    # stronger claim anyway -- it cannot be echoing ANY unencodable key.
    assert notice[0].isascii(), notice[0]


@pytest.mark.parametrize("ch", UNENCODABLE)
def test_unencodable_key_never_reaches_the_wire(
    monkeypatch, tmp_path, tty_fd, capsys, ch
):
    """Not "an empty payload was sent and acked" -- nothing is sent at all.
    ``send_key`` must not be called for that character."""
    rc, fake, _stdin, _before, _after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=[ch, DETACH_CH], send_ok=True
    )
    capsys.readouterr()

    assert rc == 0
    assert fake.sent == [], f"nothing may go on the wire for U+{ord(ch):04X}"
    assert b"" not in fake.sent


def test_session_survives_and_the_next_real_key_still_reaches_the_game(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """The Accept, in one test: unencodable key -> told, still alive, the
    NEXT ordinary keystroke is delivered, then a clean detach with rc 0."""
    rc, fake, stdin, before, after = _attach(
        monkeypatch, tmp_path, tty_fd,
        chars=["—", "x", "\r", DETACH_CH], send_ok=True,
    )
    out = capsys.readouterr().out

    assert rc == 0, "an unencodable key must not end the operator's session"
    assert "NOT SENT" in out
    assert fake.sent == [b"x", b"\r\n"], "the keys that CAN be encoded still fly"
    assert stdin.reads == 4, "the loop kept reading -- it did not bail on the em-dash"
    assert fake.closed
    assert after == before, "terminal restored on the survive-and-continue path"


def test_a_run_of_unencodable_keys_reports_each_one_and_still_survives(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """Pasting a line of smart-quoted text is the realistic case: several
    unencodable characters in a row, none of them fatal."""
    rc, fake, stdin, _before, _after = _attach(
        monkeypatch, tmp_path, tty_fd,
        chars=["“", "—", "”", "y", DETACH_CH], send_ok=True,
    )
    out = capsys.readouterr().out

    assert rc == 0
    assert out.count("NOT SENT") == 3, out
    assert fake.sent == [b"y"]
    assert stdin.reads == 5


# -- the boundary: do not over-fix ------------------------------------------

@pytest.mark.parametrize("code", [0x00, 0x41, 0x7F, 0x80, 0xA0, 0xFE, 0xFF])
def test_every_latin_1_representable_key_is_still_sent_unchanged(
    monkeypatch, tmp_path, tty_fd, capsys, code
):
    """U+00FF is the last encodable codepoint; U+0100 is the first that is
    not. Everything at or below the boundary must go out byte-for-byte, so
    the fix cannot quietly widen into "drop anything non-ASCII"."""
    ch = chr(code)
    rc, fake, _stdin, _before, _after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=[ch, DETACH_CH], send_ok=True
    )
    out = capsys.readouterr().out

    assert rc == 0
    assert fake.sent == [bytes([code])]
    assert "NOT SENT" not in out


def test_the_first_unencodable_codepoint_is_the_one_just_past_the_boundary(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """U+0100 -- the codepoint immediately above latin-1's range. Pins the
    split at exactly 0xFF/0x100 from the other side, so a fix that used a
    narrower or wider cut than the codec's own would be caught."""
    rc, fake, _stdin, _before, _after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=["Ā", DETACH_CH], send_ok=True
    )
    out = capsys.readouterr().out

    assert rc == 0
    assert fake.sent == []
    assert "U+0100" in out


def test_detach_key_still_detaches_and_is_never_forwarded(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """Ctrl-] is latin-1-encodable, so the new try/except sits directly in its
    path; it must still be intercepted before any encode happens."""
    rc, fake, stdin, _before, _after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=[DETACH_CH, "z"], send_ok=True
    )
    capsys.readouterr()

    assert rc == 0
    assert fake.sent == []
    assert stdin.reads == 1, "Ctrl-] must end the loop, not be encoded and sent"


# -- the split: unencodable and transport-dead must NOT share a handler -------

def test_transport_failure_still_ends_the_session_with_rc_1(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """Direct regression guard for 7e13b7d. Nothing in this lane may weaken
    it: a dead wire still ends attach, still reports, still rc 1."""
    rc, fake, _stdin, _before, _after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=["a", "b"], send_ok=False
    )
    out = capsys.readouterr().out

    assert rc == 1
    assert "ERROR" in out and "send_failed" in out, out
    assert fake.sent == [b"a"]


def test_the_two_conditions_are_distinguishable_in_one_session(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """Both happen, in order, in a single attach: the unencodable key is
    reported and survived; the later dead-wire send ends the session. If the
    two ever collapse into one handler this test fails, whichever way they
    collapse -- a shared fatal handler kills rc 0 on the first key, a shared
    non-fatal one leaves rc 0 at the end."""
    rc, fake, stdin, _before, _after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=["→", "a", "b"], send_ok=False
    )
    out = capsys.readouterr().out

    assert "NOT SENT" in out and "U+2192" in out, out
    assert "send_failed" in out, out
    assert rc == 1, "the transport failure decides the exit code, not the drop"
    assert fake.sent == [b"a"], "the arrow never flew; 'b' was never reached"
    assert stdin.reads == 2, "survived the arrow, stopped at the dead wire"


def test_the_unencodable_notice_is_not_dressed_as_a_session_ending_error(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """Vocabulary is the operator's only cue here. ``ERROR:`` is this file's
    established prefix for "this run is over" (daemon_not_running, not a tty,
    attach_failed, send_failed) -- a survivable drop must not wear it, or the
    operator reads a live session as a dead one."""
    rc, _fake, _stdin, _before, _after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=["—", DETACH_CH], send_ok=True
    )
    out = capsys.readouterr().out

    assert rc == 0
    assert "NOT SENT" in out
    assert "ERROR" not in out, out
    assert "still attached" in out, "the message must say the session survived"


def test_unencodable_path_leaves_no_empty_payload_anywhere_in_the_session(
    monkeypatch, tmp_path, tty_fd, capsys
):
    """Sweep-shaped rather than case-shaped: across a mixed session, no
    ``send_key`` call anywhere received an empty ``bytes``. That is the exact
    artifact the daemon used to answer ``{"ok": true}``."""
    chars = ["→", "a", "—", "\r", "\U0001f600", "b", DETACH_CH]
    rc, fake, _stdin, _before, _after = _attach(
        monkeypatch, tmp_path, tty_fd, chars=chars, send_ok=True
    )
    capsys.readouterr()

    assert rc == 0
    assert fake.sent == [b"a", b"\r\n", b"b"]
    assert all(payload for payload in fake.sent), fake.sent
