"""Operator-TTY encode honesty (DECISIONS §B / WO-ASCII-ENCODE-HONESTY).

Prefer a documented substitute over a silent content hole. When stdout (or
another text stream) cannot encode a glyph, apply the TW-safe substitute
table and retry; if the result is still unencodable, fail loud with a typed
ERROR -- never ``errors="ignore"`` / never a successful-looking write that
dropped characters.
"""

from __future__ import annotations

import sys
from typing import TextIO

# ord -> replacement. Keep twins short and TW-terminal-safe (no box-drawing
# inventiveness here -- only glyphs that already reach CLI report/help paths).
_TTY_SUBSTITUTES: dict[int, str] = {
    0x2014: "--",  # em dash —
    0x2013: "-",  # en dash –
    0x2026: "...",  # ellipsis …
    0x2605: "*",  # black star ★ (you-are-here)
    0x00B7: ".",  # middle dot ·
    0x22C5: ".",  # dot operator ⋅
}


def substitute_for_tty(text: str) -> str:
    """Return ``text`` with non-ASCII operator glyphs replaced by ASCII twins."""
    return text.translate(_TTY_SUBSTITUTES)


def encode_for_tty(text: str, encoding: str) -> str:
    """Return a form of ``text`` that ``encoding`` can encode.

    Tries the original first; on ``UnicodeEncodeError`` applies
    :func:`substitute_for_tty` and retries. Still failing raises
    ``UnicodeEncodeError`` (caller turns that into a loud CLI ERROR).
    """
    try:
        text.encode(encoding)
        return text
    except UnicodeEncodeError:
        substituted = substitute_for_tty(text)
        substituted.encode(encoding)  # may raise -- intentional
        return substituted


def print_tty(
    text: str = "",
    *,
    file: TextIO | None = None,
    end: str = "\n",
    flush: bool = False,
) -> None:
    """``print`` with §B substitute-or-loud encode discipline."""
    stream = sys.stdout if file is None else file
    enc = getattr(stream, "encoding", None) or "utf-8"
    try:
        out = encode_for_tty(text, enc)
    except UnicodeEncodeError as exc:
        print(
            f"ERROR: output_not_encodable:{exc.reason}",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    print(out, file=stream, end=end, flush=flush)
