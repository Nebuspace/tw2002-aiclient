"""Pure profile/character-strip composer for the trainer-cockpit row-1 band
(PWO-032, ``workorders/WO-P3-030-033-cockpit-frame-PREP.md``).

No ``curses`` import here on purpose — this module composes plain strings
only; ``tw2002_aiclient/screens.py`` (curses-side) draws them in a later WO.
"""

from __future__ import annotations

import re

# Per canon (`canon/surfaces/visual-language.md` — "Glyph / status-marker
# vocabulary" table, ~lines 117-131), `·` and `—` are both explicit NO-SWAP
# rows: they render identically in ASCII mode. Only some glyphs in that table
# (`✦`→`*`, the spinner, heartbeat, bars, …) actually swap; `·`/`—` do not,
# and a fabricated ASCII substitute for the em dash is explicitly what the
# canon row for `—` calls out as wrong ("in place of a fabricated `-`"). So
# these are single unconditional constants, not unicode/ascii pairs.
SEP = "·"

# Fallback glyphs for missing/broken fields. This mirrors the launcher's
# existing per-field-type convention rather than one single glyph everywhere:
#   - identity strings (host, handle) fall back to "?"
#     (``screens.py:231`` — ``host = row.host or row.server or "?"``).
#   - the single-character game-letter slot falls back to an em dash
#     (``screens.py:232`` — ``letter = (row.game_letter or "—")[:1]``).
# Reusing this split (instead of inventing a new single glyph) keeps the
# cockpit strip visually consistent with the launcher row it is extending.
MISSING_IDENTITY = "?"
MISSING_GAME_LETTER = "—"  # — (canon: no ASCII swap)


# Any run of control characters (incl. newline/tab, C0 \x00-\x1f/\x7f, and
# C1 \x80-\x9f — the 8-bit CSI introducer \x9b lives in that C1 range and
# reaching the terminal raw is escape-injection, not just a display glitch)
# or ordinary whitespace collapses to one space — keeps an embedded
# "\n"/"\t"/C1-control from ever reaching the curses draw layer.
_CONTROL_OR_WHITESPACE_RUN = re.compile(r"[\s\x00-\x1f\x7f-\x9f]+")


def _clean(value: object) -> str:
    """Normalize a raw field for display — never raises on a bad input type.

    ``None`` collapses to ``""``. A non-``str`` value (e.g. an ``int``/
    ``float`` from a malformed ``profiles.toml`` field) is coerced with
    ``str()`` rather than crashing — an int host renders as its digits, an
    honest display of whatever is actually in the profile. Embedded control
    characters/newlines/tabs collapse to a single space each, then the
    result is edge-stripped.
    """
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    return _CONTROL_OR_WHITESPACE_RUN.sub(" ", text).strip()


def compose_profile_strip(
    *,
    host: str | None,
    game_letter: str | None,
    handle: str | None,
    width: int,
    unicode_ok: bool = True,
) -> str:
    """Compose the row-1 ``host · game-letter · handle`` cockpit strip.

    Never raises, regardless of how broken or mistyped the inputs are (see
    ``_clean``). A missing/blank ``host`` or ``handle`` falls back to
    ``"?"``; a missing/blank ``game_letter`` falls back to ``"—"`` — see the
    module-level glyph comments for why the fallback differs by field.
    ``game_letter`` is truncated to its first character (after fallback
    substitution — the launcher's own convention, ``screens.py:232``:
    ``(row.game_letter or "—")[:1]``), so a malformed multi-character value
    never widens the strip.

    ``unicode_ok`` is accepted for uniformity with the rest of the chrome's
    ``glyph_set()`` convention and any future strip glyph that *does* have an
    ASCII twin, but today's glyph set (``·``, ``—``) is unconditionally
    unicode-safe per canon (`canon/surfaces/visual-language.md` glyph table)
    — so it currently has no effect on the output.

    The result is **always** ``len(result) <= width`` (``width <= 0`` returns
    ``""``). At minimal widths the composed line is hard-truncated at its
    tail — excess characters dropped from the end, no ellipsis inserted —
    so the strip always fits on one line and never wraps or h-scrolls.

    ``width`` is a **code-point** budget, not a terminal-**cell** budget: an
    operator-supplied host/handle containing wide characters (CJK, emoji,
    …) can occupy roughly two terminal cells per code point, so the actual
    on-screen width may exceed ``width`` for such input. Cell-accurate
    (wcwidth-aware) truncation is out of scope here — the curses draw layer
    provides the real backstop via its own bounded ``addnstr`` calls.
    """
    if width <= 0:
        return ""

    host_s = _clean(host) or MISSING_IDENTITY
    letter_s = (_clean(game_letter) or MISSING_GAME_LETTER)[:1]
    handle_s = _clean(handle) or MISSING_IDENTITY

    line = f"{host_s} {SEP} {letter_s} {SEP} {handle_s}"
    return line[:width]


def _safe_chip(value: object) -> tuple[str, str | None]:
    """Best-effort coercion of a caller-supplied ``(text, tone)`` chip pair
    to a usable ``(str, str|None)``, degrading any unusable shape to
    ``("", None)`` -- mirrors ``cockpit.control_seat._safe_arm_chip``'s
    own contract verbatim (this module intentionally does not import that
    one, to keep the pure-composer/pure-composer boundary a plain
    duplication rather than a new cross-module dependency for two lines
    of logic). Never raises regardless of ``value``'s type."""
    try:
        text, tone = value  # a 2-element unpack; anything else raises
    except Exception:  # noqa: BLE001 -- an unusable chip must not crash the row
        return "", None
    if not isinstance(text, str) or not text:
        return "", None
    if tone is not None and not isinstance(tone, str):
        return text, None
    return text, tone


def compose_profile_strip_segments(
    *,
    host: str | None,
    game_letter: str | None,
    handle: str | None,
    width: int,
    unicode_ok: bool = True,
    conn_chip: "tuple[str, str | None] | None" = None,
) -> "list[tuple[str, str | None]]":
    """``compose_profile_strip``'s row, as ``(text, tone)`` segments so the
    CONN chip (WO-PLAY-STRIP-TRAINER-CHROME / DECISION
    `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 3: "CONN -- top
    line beside server/host") can carry its own color distinct from the
    plain identity text around it -- the same segments-vs-flat-string
    split ``cockpit.control_seat.compose_control_strip_segments`` already
    uses for the row below.

    ``conn_chip=None`` (the default) degrades to the exact
    ``compose_profile_strip`` string wrapped as one plain ``(text, None)``
    segment -- byte-identical output, so this is a strict additive
    extension and every pre-existing caller of the flat-string composer
    is unaffected by this function's existence.

    When a usable ``conn_chip`` is supplied, it is placed immediately
    beside the host (``"{host} {chip} · {letter} · {handle}"``), each
    piece truncated left-to-right against ``width`` exactly like
    ``control_seat._compose_segments``'s own sequential-budget rule: the
    identity fields never lose a character to the chip and the chip is
    never split mid-token (an empty remaining budget simply drops it
    whole, honest-absence rather than a mangled ``CO``).

    Never raises regardless of any argument's type or content.
    """
    if width <= 0:
        return []
    if conn_chip is None:
        text = compose_profile_strip(
            host=host, game_letter=game_letter, handle=handle,
            width=width, unicode_ok=unicode_ok,
        )
        return [(text, None)] if text else []

    host_s = _clean(host) or MISSING_IDENTITY
    letter_s = (_clean(game_letter) or MISSING_GAME_LETTER)[:1]
    handle_s = _clean(handle) or MISSING_IDENTITY
    chip_text, chip_tone = _safe_chip(conn_chip)

    pieces: list[tuple[str, str | None]] = [(host_s, None)]
    if chip_text:
        pieces.append((f" {chip_text}", chip_tone))
    pieces.append((f" {SEP} {letter_s} {SEP} {handle_s}", None))

    out: list[tuple[str, str | None]] = []
    used = 0
    for text, tone in pieces:
        if used >= width:
            break
        clipped = text[: width - used]
        if clipped:
            out.append((clipped, tone))
            used += len(clipped)
    return out


def compose_profile_strip_from_row(row: object, *, width: int, unicode_ok: bool = True) -> str:
    """Convenience wrapper over a duck-typed profile row.

    Accepts anything exposing ``host``/``server``/``game_letter``/``handle``
    attributes (e.g. ``screens.ProfileRow``) without importing ``screens.py``
    (which pulls ``curses``) — mirrors the launcher's own host-fallback,
    ``row.host or row.server or "?"`` (``screens.py:231``). Missing
    attributes degrade to ``None`` fields rather than raising.
    """
    host = getattr(row, "host", None) or getattr(row, "server", None)
    return compose_profile_strip(
        host=host,
        game_letter=getattr(row, "game_letter", None),
        handle=getattr(row, "handle", None),
        width=width,
        unicode_ok=unicode_ok,
    )


def compose_profile_strip_segments_from_row(
    row: object,
    *,
    width: int,
    unicode_ok: bool = True,
    conn_chip: "tuple[str, str | None] | None" = None,
) -> "list[tuple[str, str | None]]":
    """``compose_profile_strip_segments``'s duck-typed row wrapper --
    mirrors ``compose_profile_strip_from_row``'s own host-fallback
    convention verbatim, plus the optional ``conn_chip`` segment."""
    host = getattr(row, "host", None) or getattr(row, "server", None)
    return compose_profile_strip_segments(
        host=host,
        game_letter=getattr(row, "game_letter", None),
        handle=getattr(row, "handle", None),
        width=width,
        unicode_ok=unicode_ok,
        conn_chip=conn_chip,
    )
