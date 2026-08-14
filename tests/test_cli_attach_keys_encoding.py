"""D3/D4 -- `tw attach --keys` must put on the wire exactly what it was
asked for, or say it did not. THE SCRIPTED HALF, which had no tests at all.

The root defect was a DOUBLE ENCODE, not a drop. The chain was
`utf-8 -> unicode_escape -> latin-1(errors="ignore")`, and `unicode_escape`
is a latin-1-based codec: it decodes one codepoint per BYTE. So the utf-8
re-encoding came back as one character per byte, each of them
latin-1-representable, and all of them were shipped:

    --keys with a raw U+00FF   ->  wire b"\\xc3\\xbf"   (two bytes)
    the same key interactively ->  wire b"\\xff"       (one byte)

`errors="ignore"` therefore almost never fired. The branch was not dropping
non-ASCII input, it was MANGLING it -- silently, with rc 0, on exactly the
byte class an 8-bit TradeWars wire is made of, with the two halves of one
verb disagreeing about it.

The drops were the visible symptom of the same chain, in two shapes that
also exited 0:

    --keys ''            rc 0, sent []       "you asked for nothing"
    --keys '<esc arrow>' rc 0, sent []       "everything was thrown away"
    --keys 'a<esc>b'     rc 0, sent b"ab"    DIFFERENT bytes than asked for

The first two were indistinguishable; the third was worse than a drop,
because a caller reading rc 0 had every reason to believe the wire carried
what it asked for.

Why this file exists at all, stated plainly: a commit message on origin
described this fix in detail, and the fix was not in the tree. The
interactive twenty lines below was real; `errors="ignore"` here was
byte-identical from `af62889` to HEAD. What let that stand for as long as
it did was that `tests/test_cli_attach_unencodable_key.py` passes
`keys=None` in every single case -- a fully green suite proving nothing
about this branch. So: `--keys` tests.

`032bc12`'s deliberate pin survives and is asserted here as well as in its
own file: `--keys ""` still exits 0, so "you asked for nothing" stays
distinguishable from "everything you asked for was thrown away".
"""

from __future__ import annotations

from argparse import Namespace

import pytest

from tests.attach_helpers import FakeAttachConn as _FakeAttachConn
from tests.attach_terminal_harness import attach_daemon  # noqa: F401  (fixture)
from tw2002_aiclient.session import attach_client, cli, env

# Built from chr(92) rather than written as a backslash escape: this file is
# ABOUT escape sequences, and a source-level escape here would be resolved by
# Python before `--keys` ever saw it -- the argv the operator types contains a
# literal backslash character.
BS = chr(92)

ESC_ARROW = BS + "u2192"           # -> U+2192, the 4-hex form
ESC_NAMED = BS + "N{RIGHTWARDS ARROW}"  # -> U+2192, the named form
ESC_ASTRAL = BS + "U0001F600"      # -> U+1F600, the 8-hex form
ESC_OCTAL_OVER = BS + "777"        # -> U+01FF, octal overflow
ESC_OCTAL_FIRST_OVER = BS + "400"  # -> U+0100, first octal overflow
ESC_OCTAL_MAX_OK = BS + "377"      # -> U+00FF, last octal still encodable
ESC_HEX_MAX_OK = BS + "xff"        # -> U+00FF


def _run_keys(monkeypatch, tmp_path, keys, *, send_ok=True):
    env.socket_path(tmp_path).touch()
    fake = _FakeAttachConn(send_ok=send_ok)
    monkeypatch.setattr(attach_client, "AttachInputConn", lambda sock_path: fake)
    rc = cli.cmd_attach(Namespace(run_dir=str(tmp_path), keys=keys))
    return rc, fake


class _ScriptedTtyStdin:
    """Minimal scripted stdin over a real tty fd -- same shape as the one in
    tests/test_cli_attach_unencodable_key.py. Present here only so the two
    halves of `tw attach` can be compared in one assertion."""

    def __init__(self, fd, chars):
        self._fd = fd
        self._chars = list(chars)

    def isatty(self):
        return True

    def fileno(self):
        return self._fd

    def read(self, n=1):
        return self._chars.pop(0) if self._chars else ""


def _run_interactive(monkeypatch, tmp_path, tty_fd, chars):
    """Drive the INTERACTIVE branch with the same characters, so the two
    paths can be compared directly rather than against two hand-written
    expectations that could both be wrong."""
    env.socket_path(tmp_path).touch()
    fake = _FakeAttachConn(send_ok=True)
    monkeypatch.setattr(attach_client, "AttachInputConn", lambda sock_path: fake)
    monkeypatch.setattr(cli.sys, "stdin", _ScriptedTtyStdin(tty_fd, list(chars) + [chr(29)]))
    cli.cmd_attach(Namespace(run_dir=str(tmp_path), keys=None))
    return fake


# -- the defect: a drop must fail visibly ----------------------------------

@pytest.mark.parametrize(
    "keys,codepoint",
    [
        (ESC_ARROW, "U+2192"),
        (ESC_NAMED, "U+2192"),
        (ESC_ASTRAL, "U+1F600"),
        (ESC_OCTAL_OVER, "U+01FF"),
        (ESC_OCTAL_FIRST_OVER, "U+0100"),
    ],
)
def test_a_full_drop_is_reported_and_exits_non_zero(
    monkeypatch, tmp_path, capsys, keys, codepoint
):
    """All FOUR escape forms that can exceed U+00FF, not the two the
    original note enumerated: the 4-hex, the named, the 8-hex, and octal
    overflow (which spans \\400-\\777, i.e. U+0100-U+01FF)."""
    rc, fake = _run_keys(monkeypatch, tmp_path, keys)
    out = capsys.readouterr().out

    assert rc == 1, out
    assert fake.sent == []
    assert "ERROR" in out and codepoint in out, out
    assert fake.closed


@pytest.mark.parametrize("keys", [ESC_ARROW, ESC_NAMED, ESC_ASTRAL, ESC_OCTAL_OVER])
def test_a_full_drop_is_distinguishable_from_asking_for_nothing(
    monkeypatch, tmp_path, capsys, keys
):
    """The whole point of the fix, as one comparison. Before, both were
    `rc 0, sent []` and a caller could not tell them apart."""
    rc_dropped, fake_dropped = _run_keys(monkeypatch, tmp_path, keys)
    out_dropped = capsys.readouterr().out
    rc_empty, fake_empty = _run_keys(monkeypatch, tmp_path, "")
    out_empty = capsys.readouterr().out

    assert fake_dropped.sent == fake_empty.sent == []  # identical on the wire
    assert (rc_dropped, "ERROR" in out_dropped) != (rc_empty, "ERROR" in out_empty), (
        "an all-dropped payload is still indistinguishable from --keys ''"
    )
    assert rc_dropped == 1 and rc_empty == 0


def test_a_partial_drop_sends_nothing_rather_than_different_bytes(
    monkeypatch, tmp_path, capsys
):
    """The sharpest shape: `a<arrow>b` used to put b"ab" on the wire and
    exit 0. Sending a truncated payload is worse than sending none -- the
    caller asked for three keys and the game would have received two, with
    every surface reporting success."""
    rc, fake = _run_keys(monkeypatch, tmp_path, "a" + ESC_ARROW + "b")
    out = capsys.readouterr().out

    assert rc == 1, out
    assert fake.sent == [], "a partial payload must NOT reach the wire"
    assert b"ab" not in fake.sent
    assert "U+2192" in out and "index 1" in out, out


def test_the_reported_index_points_at_the_offending_key(monkeypatch, tmp_path, capsys):
    """The index is into the escape-DECODED key sequence, which is the
    operator's model of 'which keystroke'. Two different positions, so the
    test cannot pass on a hardcoded zero."""
    rc, _ = _run_keys(monkeypatch, tmp_path, ESC_ARROW + "xyz")
    assert "index 0" in capsys.readouterr().out

    rc2, _ = _run_keys(monkeypatch, tmp_path, "abcd" + ESC_ARROW)
    assert "index 4" in capsys.readouterr().out
    assert rc == rc2 == 1


def test_the_refusal_names_the_codepoint_and_never_the_glyph(
    monkeypatch, tmp_path, capsys
):
    """Same rule as the interactive notice, and the same reasons. Asserted
    as pure-ASCII rather than 'the arrow is absent', which is the stronger
    claim: the line cannot be echoing ANY unencodable character."""
    _rc, _fake = _run_keys(monkeypatch, tmp_path, "a" + ESC_ARROW + "b")
    out = capsys.readouterr().out

    assert out.isascii(), out
    assert "→" not in out
    assert "U+2192" in out


# -- the pin that must not break -------------------------------------------

def test_empty_keys_still_exits_zero_and_sends_nothing(monkeypatch, tmp_path, capsys):
    """`032bc12`'s deliberate pin, re-asserted from inside the lane that
    changes this branch. `send_ok=False` so a `send_key` call that should
    never happen would be caught by the rc as well as by `sent`."""
    rc, fake = _run_keys(monkeypatch, tmp_path, "", send_ok=False)
    out = capsys.readouterr().out

    assert rc == 0
    assert fake.sent == []
    assert "ERROR" not in out, out
    assert fake.closed


# -- the boundary: do not over-fix -----------------------------------------

@pytest.mark.parametrize(
    "keys,expected",
    [
        ("hi", b"hi"),
        (ESC_HEX_MAX_OK, b"\xff"),
        (ESC_OCTAL_MAX_OK, b"\xff"),
        ("a" + BS + "r", b"a\r"),
        ("a" + BS + "n", b"a\n"),
        ("a" + BS + BS + "b", b"a" + BS.encode() + b"b"),
    ],
)
def test_everything_encodable_still_goes_out_unchanged(
    monkeypatch, tmp_path, capsys, keys, expected
):
    """`\\377` and `\\xff` both land on U+00FF, the last encodable
    codepoint; `\\400` is the first that is not. Pins the split at exactly
    the codec's own boundary from the encodable side."""
    rc, fake = _run_keys(monkeypatch, tmp_path, keys)
    out = capsys.readouterr().out

    assert rc == 0, out
    assert fake.sent == [expected]
    assert "ERROR" not in out


@pytest.mark.parametrize(
    "char,expected_byte",
    [("ÿ", b"\xff"), ("é", b"\xe9"), ("\x80", b"\x80"), ("\xa0", b"\xa0")],
)
def test_a_raw_latin1_character_is_sent_as_its_ONE_byte(
    monkeypatch, tmp_path, capsys, char, expected_byte
):
    """THE ROOT DEFECT, and the one that is not an edge case at all.

    The old chain encoded argv to UTF-8 before handing it to
    `unicode_escape`, which is a latin-1-based codec and decodes one
    codepoint per BYTE. A plain latin-1 character therefore came back as
    two characters, both encodable, and both were shipped: `--keys 'y with
    diaeresis'` put `b"\\xc3\\xbf"` on the wire where interactive attach
    puts `b"\\xff"`. Not a drop -- a silent double encode, rc 0, and the two
    halves of one verb disagreeing about exactly the byte class an 8-bit
    TradeWars wire is made of.

    A fix that only made unencodable input fail loudly would have left this
    running.
    """
    rc, fake = _run_keys(monkeypatch, tmp_path, char)
    out = capsys.readouterr().out

    assert rc == 0, out
    assert fake.sent == [expected_byte], (
        f"{char!r} is one 8-bit key; two bytes on the wire is the double encode"
    )
    assert len(fake.sent[0]) == 1
    assert "ERROR" not in out


@pytest.mark.parametrize("char", ["ÿ", "é", "\x80", "\xff", "a"])
def test_the_scripted_and_interactive_paths_agree_byte_for_byte(
    monkeypatch, tmp_path, tty_fd, capsys, char
):
    """The two halves of `tw attach` must put the SAME bytes on the wire for
    the same key. Stated as an equality between the paths rather than as two
    separate expectations, so neither can drift without this failing --
    which is how the double encode survived: each half looked fine alone.
    """
    _rc_s, fake_scripted = _run_keys(monkeypatch, tmp_path, char)
    capsys.readouterr()
    fake_interactive = _run_interactive(monkeypatch, tmp_path, tty_fd, [char])
    capsys.readouterr()

    assert fake_scripted.sent == fake_interactive.sent, (
        f"--keys and interactive attach disagree on {char!r}: "
        f"{fake_scripted.sent} vs {fake_interactive.sent}"
    )


@pytest.mark.parametrize("keys,codepoint", [("→", "U+2192"), ("Ā", "U+0100"),
                                            ("a→b", "U+2192")])
def test_a_raw_character_the_wire_cannot_carry_is_refused_not_mangled(
    monkeypatch, tmp_path, capsys, keys, codepoint
):
    """The other face of the double encode. A raw arrow used to be shipped
    as its three UTF-8 bytes with rc 0 -- bytes the operator never asked
    for, on a wire that has no such character. It is now refused, exactly as
    interactive attach refuses it.

    This is the row the WO's own summary table had backwards (it listed a
    raw arrow as `sent []`); it was never dropped, it was transmitted wrong.
    """
    rc, fake = _run_keys(monkeypatch, tmp_path, keys)
    out = capsys.readouterr().out

    assert rc == 1, out
    assert fake.sent == [], "mangled bytes must not reach the wire"
    assert codepoint in out, out


@pytest.mark.parametrize("byte_value", [0x80, 0xE9, 0xFF])
def test_a_raw_8_bit_byte_in_argv_is_recovered_and_sent(
    monkeypatch, tmp_path, capsys, byte_value
):
    """`--keys $'\\xff'`: argv reaches Python already decoded with PEP 383
    surrogate-escape, so the byte arrives as a lone surrogate. It used to
    raise `UnicodeEncodeError` on the first encode and kill the verb with
    an uncaught traceback. Same recovery as the interactive path, so the
    two agree."""
    rc, fake = _run_keys(monkeypatch, tmp_path, chr(0xDC00 + byte_value))
    out = capsys.readouterr().out

    assert rc == 0, out
    assert fake.sent == [bytes([byte_value])]
    assert "ERROR" not in out


# -- malformed escapes: the other half of "cannot be turned into bytes" ----

@pytest.mark.parametrize(
    "keys",
    [BS, "a" + BS, "a" + BS + "x", "a" + BS + "u12", "a" + BS + "N", "a" + BS + "U00"],
)
def test_an_undecodable_escape_is_reported_instead_of_tracebacking(
    monkeypatch, tmp_path, capsys, keys
):
    """A trailing backslash or a truncated \\x \\u \\U \\N raises
    `UnicodeDecodeError` from `unicode_escape` -- a different failure from a
    drop (the argument cannot be turned into keys AT ALL) and, before this
    lane, an uncaught traceback."""
    rc, fake = _run_keys(monkeypatch, tmp_path, keys)
    out = capsys.readouterr().out

    assert rc == 1, out
    assert fake.sent == []
    assert "ERROR" in out and "could not be decoded" in out, out
    assert out.isascii(), out
    assert fake.closed


# -- the pre-existing exit-code contract still holds -----------------------

def test_a_transport_failure_is_still_the_reason_for_rc_1_when_bytes_are_valid(
    monkeypatch, tmp_path, capsys
):
    """`032bc12`'s other half: encodable keys that the wire refuses still
    report `send_failed`, distinct from an encoding refusal."""
    rc, fake = _run_keys(monkeypatch, tmp_path, "hi", send_ok=False)
    out = capsys.readouterr().out

    assert rc == 1
    assert "send_failed" in out, out
    assert fake.sent == [b"hi"], "the bytes were valid and were attempted"


# -- end to end against a real daemon on a real unix socket ----------------

def test_a_partial_drop_puts_nothing_on_a_real_daemons_wire(attach_daemon):
    """The in-process tests use a fake connection; this one proves the same
    claim through the real `AttachInputConn`, a real unix socket and the
    real daemon `attach` verb -- which is where "sent b'ab'" was actually
    observed."""
    rc = cli.cmd_attach(
        Namespace(run_dir=str(attach_daemon.run_dir), keys="a" + ESC_ARROW + "b")
    )

    assert rc == 1
    assert attach_daemon.session.raw_sent == []


def test_encodable_keys_still_reach_a_real_daemon(attach_daemon):
    """The other side of the same proof, so the test above cannot be passing
    because nothing reaches this daemon at all."""
    rc = cli.cmd_attach(
        Namespace(run_dir=str(attach_daemon.run_dir), keys="ab" + ESC_HEX_MAX_OK)
    )

    assert rc == 0
    assert attach_daemon.session.raw_sent == [b"ab\xff"]
