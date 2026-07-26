"""Pins for session.tty_encode — §B substitute-or-loud."""

from __future__ import annotations

import io

import pytest

from tw2002_aiclient.session.tty_encode import (
    encode_for_tty,
    print_tty,
    substitute_for_tty,
)


def test_substitute_table_covers_help_and_report_glyphs():
    raw = "here ★ Root — coverage · joins …/game"
    assert substitute_for_tty(raw) == "here * Root -- coverage . joins .../game"
    assert substitute_for_tty(raw).isascii()


def test_encode_for_tty_passes_through_when_codec_accepts():
    text = "here ★ Root"
    assert encode_for_tty(text, "utf-8") == text


def test_encode_for_tty_substitutes_under_ascii():
    text = "here ★ Root — dead"
    assert encode_for_tty(text, "ascii") == "here * Root -- dead"


def test_encode_for_tty_loud_when_no_substitute_helps():
    # U+2603 snowman has no twin in the table -- must not silent-drop.
    with pytest.raises(UnicodeEncodeError):
        encode_for_tty("snowman \u2603", "ascii")


def test_print_tty_substitutes_on_ascii_stream(capsys):
    stream = io.TextIOWrapper(io.BytesIO(), encoding="ascii", write_through=True)
    print_tty("MAP — / here ★ X", file=stream)
    stream.seek(0)
    assert stream.buffer.getvalue() == b"MAP -- / here * X\n"


def test_print_tty_exits_loud_when_unsubstitutable(capsys):
    stream = io.TextIOWrapper(io.BytesIO(), encoding="ascii", write_through=True)
    with pytest.raises(SystemExit) as exc:
        print_tty("no twin \u2603", file=stream)
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "ERROR: output_not_encodable:" in err
