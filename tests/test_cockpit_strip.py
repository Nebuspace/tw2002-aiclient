"""Pure profile/character-strip composer tests (PWO-032, Layer-A).

No curses/terminal involved — asserts the composed string directly, per the
tests/test_spectate_layout.py pure-function convention this ports.
"""

from types import SimpleNamespace

import pytest

from tw2002_aiclient.cockpit.strip import (
    MISSING_GAME_LETTER,
    MISSING_IDENTITY,
    SEP,
    compose_profile_strip,
    compose_profile_strip_segments,
    compose_profile_strip_segments_from_row,
)


# ---------------------------------------------------------------------------
# Healthy fixture profile
# ---------------------------------------------------------------------------


def test_healthy_profile_composes_exact_string():
    result = compose_profile_strip(
        host="tw2002.example.net",
        game_letter="A",
        handle="Captain",
        width=80,
    )
    assert result == "tw2002.example.net · A · Captain"
    assert len(result) <= 80


def test_healthy_profile_ascii_mode_is_identical_to_unicode_mode():
    # Canon (visual-language.md glyph table): `·` is an explicit NO-SWAP
    # glyph — ASCII mode must not change this strip's output at all.
    unicode_result = compose_profile_strip(
        host="tw2002.example.net", game_letter="A", handle="Captain", width=80
    )
    ascii_result = compose_profile_strip(
        host="tw2002.example.net",
        game_letter="A",
        handle="Captain",
        width=80,
        unicode_ok=False,
    )
    assert ascii_result == unicode_result == "tw2002.example.net · A · Captain"
    assert len(ascii_result) <= 80


# ---------------------------------------------------------------------------
# Broken profile — each field missing individually, then all missing
# ---------------------------------------------------------------------------


def test_missing_host_falls_back_to_question_mark():
    result = compose_profile_strip(host=None, game_letter="A", handle="Captain", width=80)
    assert result == f"{MISSING_IDENTITY} {SEP} A {SEP} Captain"


def test_blank_host_falls_back_to_question_mark():
    result = compose_profile_strip(host="   ", game_letter="A", handle="Captain", width=80)
    assert result.startswith(MISSING_IDENTITY)


def test_missing_game_letter_falls_back_to_em_dash():
    result = compose_profile_strip(host="host", game_letter=None, handle="Captain", width=80)
    assert result == f"host {SEP} {MISSING_GAME_LETTER} {SEP} Captain"


def test_missing_game_letter_ascii_mode_is_identical_no_fabricated_hyphen():
    # Regression guard: canon forbids a fabricated "-" standing in for the
    # em dash in ASCII mode — the em dash itself is the NO-SWAP glyph.
    # NOTE: "host"/"Captain" are deliberately hyphen-free fixtures here — the
    # "-" not in ascii_result assert below depends on that; don't swap in a
    # hyphenated host/handle without updating or dropping that assert.
    unicode_result = compose_profile_strip(host="host", game_letter=None, handle="Captain", width=80)
    ascii_result = compose_profile_strip(
        host="host", game_letter=None, handle="Captain", width=80, unicode_ok=False
    )
    assert ascii_result == unicode_result == f"host {SEP} {MISSING_GAME_LETTER} {SEP} Captain"
    assert "-" not in ascii_result


def test_missing_handle_falls_back_to_question_mark():
    result = compose_profile_strip(host="host", game_letter="A", handle=None, width=80)
    assert result.endswith(MISSING_IDENTITY)


def test_all_fields_missing_no_crash_all_fallbacks():
    result = compose_profile_strip(host=None, game_letter=None, handle=None, width=80)
    assert result == (
        f"{MISSING_IDENTITY} {SEP} {MISSING_GAME_LETTER} " f"{SEP} {MISSING_IDENTITY}"
    )
    assert len(result) <= 80


def test_all_fields_missing_ascii_mode_no_crash_no_fabricated_glyphs():
    # NOTE: all-``None`` input is inherently hyphen-free (fallback glyphs are
    # "?"/"—" only) — the "-"/"|" not-in asserts below rely on that; this
    # test must stay all-fallback, never a mix with real hyphenated data.
    unicode_result = compose_profile_strip(host=None, game_letter=None, handle=None, width=80)
    ascii_result = compose_profile_strip(
        host=None, game_letter=None, handle=None, width=80, unicode_ok=False
    )
    # Canon (·/— are both NO-SWAP): ASCII mode must be byte-identical here.
    assert ascii_result == unicode_result
    # Regression guard against exactly the fabricated-glyph drift this WO
    # revise fixed: no invented "-" or "|" standing in for a NO-SWAP glyph.
    assert "-" not in ascii_result
    assert "|" not in ascii_result


def test_empty_strings_treated_same_as_none():
    result = compose_profile_strip(host="", game_letter="", handle="", width=80)
    assert result == compose_profile_strip(host=None, game_letter=None, handle=None, width=80)


# ---------------------------------------------------------------------------
# Hardening (Mack attack-round): mistyped fields, oversized game_letter,
# embedded control characters — a malformed profiles.toml value can reach
# any of these paths, and none of them may raise or break the one-line
# guarantee.
# ---------------------------------------------------------------------------


def test_non_str_host_coerces_instead_of_raising():
    result = compose_profile_strip(host=12345, game_letter="A", handle="Captain", width=80)
    assert result == f"12345 {SEP} A {SEP} Captain"


def test_non_str_handle_float_coerces_instead_of_raising():
    result = compose_profile_strip(host="host", game_letter="A", handle=3.5, width=80)
    assert result == f"host {SEP} A {SEP} 3.5"


def test_non_str_game_letter_coerces_and_still_truncates_to_one_char():
    # An int game_letter would str()-coerce to a multi-digit string in the
    # pathological case; the [:1] truncation must still apply after coercion.
    result = compose_profile_strip(host="host", game_letter=42, handle="Captain", width=80)
    assert result == f"host {SEP} 4 {SEP} Captain"


def test_all_fields_non_str_no_crash():
    # Every field mistyped at once — must still compose, never raise.
    result = compose_profile_strip(host=1, game_letter=2.0, handle=False, width=80)
    assert "\n" not in result
    assert len(result) <= 80


def test_multi_char_game_letter_truncates_to_first_char():
    result = compose_profile_strip(host="host", game_letter="AB", handle="Captain", width=80)
    assert result == f"host {SEP} A {SEP} Captain"


def test_multi_char_game_letter_ascii_mode_still_truncates():
    result = compose_profile_strip(
        host="host", game_letter="ZZ", handle="Captain", width=80, unicode_ok=False
    )
    assert result == f"host {SEP} Z {SEP} Captain"


def test_embedded_newline_collapses_to_single_space():
    result = compose_profile_strip(host="abc\ndef", game_letter="A", handle="Captain", width=80)
    assert "\n" not in result
    assert "abc def" in result


def test_embedded_tab_collapses_to_single_space():
    result = compose_profile_strip(host="host", game_letter="A", handle="cap\ttain", width=80)
    assert "\t" not in result
    assert "cap tain" in result


def test_embedded_control_char_stripped_no_raw_control_bytes():
    # A raw ASCII control byte that isn't classic whitespace (e.g. BEL, ESC).
    result = compose_profile_strip(host="ab\x07cd\x1bef", game_letter="A", handle="Captain", width=80)
    assert "\x07" not in result
    assert "\x1b" not in result
    assert "ab cd ef" in result


def test_embedded_c1_control_stripped_no_escape_injection():
    # \x9b is the 8-bit CSI introducer (C1 control range \x80-\x9f) — a raw
    # one reaching the terminal is escape-injection, not just a glitch.
    result = compose_profile_strip(host="abc\x9bdef", game_letter="A", handle="Captain", width=80)
    assert "\x9b" not in result
    assert "abc def" in result


def test_multiple_embedded_newlines_collapse_to_one_space_each():
    result = compose_profile_strip(
        host="line1\n\n\nline2", game_letter="A", handle="Captain", width=80
    )
    assert "\n" not in result
    assert "line1 line2" in result


# ---------------------------------------------------------------------------
# Width-truncation sweep: the ≤width invariant and no-wrap (single line)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("width", list(range(0, 6)) + [10, 20, 33, 50, 80, 200])
def test_width_invariant_never_exceeded(width):
    result = compose_profile_strip(
        host="a-fairly-long-hostname.example.net",
        game_letter="A",
        handle="SomeLongHandleName",
        width=width,
    )
    assert len(result) <= width
    assert "\n" not in result  # never wraps


def test_zero_width_returns_empty_string():
    assert compose_profile_strip(host="host", game_letter="A", handle="Captain", width=0) == ""


def test_negative_width_returns_empty_string():
    assert compose_profile_strip(host="host", game_letter="A", handle="Captain", width=-5) == ""


def test_minimal_width_truncates_at_tail_never_raises():
    full = compose_profile_strip(host="host", game_letter="A", handle="Captain", width=80)
    truncated = compose_profile_strip(host="host", game_letter="A", handle="Captain", width=5)
    assert len(truncated) <= 5
    assert truncated == full[:5]


def test_broken_profile_at_minimal_width_no_exception():
    # Must never raise, even with every field missing at a pathological width.
    for width in range(0, 4):
        result = compose_profile_strip(host=None, game_letter=None, handle=None, width=width)
        assert len(result) <= width if width > 0 else result == ""


# ---------------------------------------------------------------------------
# compose_profile_strip_segments_from_row — duck-typed row wrapper
# (product callers use this; the string-only from_row helper was retired)
# ---------------------------------------------------------------------------


def _joined(segments):
    return "".join(text for text, _tone in segments)


def test_from_row_uses_host_over_server():
    row = SimpleNamespace(host="resolved.example.net", server="catalog-key", game_letter="B", handle="Nav")
    result = _joined(compose_profile_strip_segments_from_row(row, width=80))
    # Exact host token (not startswith) — CodeQL py/incomplete-url-substring-sanitization
    assert result.split(f" {SEP} ", 1)[0] == "resolved.example.net"
    assert "catalog-key" not in result


def test_from_row_falls_back_to_server_when_host_missing():
    row = SimpleNamespace(host="", server="catalog-key", game_letter="B", handle="Nav")
    result = _joined(compose_profile_strip_segments_from_row(row, width=80))
    assert result.split(f" {SEP} ", 1)[0] == "catalog-key"


def test_from_row_missing_attributes_no_crash():
    row = SimpleNamespace()  # nothing set at all
    result = _joined(compose_profile_strip_segments_from_row(row, width=80))
    assert result == compose_profile_strip(host=None, game_letter=None, handle=None, width=80)


def test_from_row_ascii_mode_propagates():
    row = SimpleNamespace(host="host", server="", game_letter="A", handle="Captain")
    result = _joined(
        compose_profile_strip_segments_from_row(row, width=80, unicode_ok=False)
    )
    # unicode_ok still threads through to the underlying call even though
    # today's glyph set (NO-SWAP ·/—) makes it a no-op on the output.
    assert result == compose_profile_strip(
        host="host", game_letter="A", handle="Captain", width=80, unicode_ok=False
    )
    assert result == compose_profile_strip(
        host="host", game_letter="A", handle="Captain", width=80, unicode_ok=True
    )


# ---------------------------------------------------------------------------
# compose_profile_strip_segments — the CONN chip is all-or-nothing
# (WO-PLAY-STRIP-TRAINER-CHROME REVISE, hub 2026-07-31: the STATUS-DONE cut
# mid-truncated the chip at tight widths — `clipped = text[: width - used]`
# on the chip piece itself — producing readable-but-wrong prefixes like
# "CO"/"CON". Fixed to drop the whole chip rather than clip it, mirroring
# ``control_seat._compose_segments``'s own all-or-nothing chip rule.)
# ---------------------------------------------------------------------------


def test_conn_chip_absent_is_byte_identical_to_the_flat_composer():
    segs = compose_profile_strip_segments(
        host="host", game_letter="A", handle="Captain", width=80, conn_chip=None,
    )
    assert "".join(t for t, _ in segs) == compose_profile_strip(
        host="host", game_letter="A", handle="Captain", width=80,
    )


def test_conn_chip_renders_full_text_with_room():
    segs = compose_profile_strip_segments(
        host="host", game_letter="A", handle="Captain", width=80,
        conn_chip=("●", "ok"),
    )
    joined = "".join(t for t, _ in segs)
    assert " ● " in joined
    chip_segments = [text for text, tone in segs if tone == "ok"]
    assert chip_segments == [" ●"]


@pytest.mark.parametrize("width", list(range(0, 45)))
def test_conn_chip_is_all_or_nothing_never_a_partial_prefix(width):
    """THE pin this REVISE exists for: at every width, the chip segment is
    either the exact full ``" ●"`` text or entirely absent — never a
    truncated ``" CO"``/``" CON"`` fragment that reads as a plausible but
    wrong claim."""
    segs = compose_profile_strip_segments(
        host="a-fairly-long-hostname.example.net", game_letter="A",
        handle="SomeLongHandleName", width=width, conn_chip=("●", "ok"),
    )
    joined = "".join(t for t, _ in segs)
    assert len(joined) <= width
    chip_segments = [text for text, tone in segs if tone == "ok"]
    assert chip_segments in ([], [" ●"]), (
        f"width {width} produced a partial/mangled ● chip: {chip_segments!r}"
    )


def test_conn_chip_dropping_never_costs_the_identity_fields_a_character():
    """Where the chip does not fit, the row must be byte-identical to the
    no-chip composition (only the chip's own room is given up)."""
    for width in range(0, 45):
        with_chip = compose_profile_strip_segments(
            host="a-fairly-long-hostname.example.net", game_letter="A",
            handle="SomeLongHandleName", width=width, conn_chip=("●", "ok"),
        )
        joined = "".join(t for t, _ in with_chip)
        if " ●" in joined:
            continue
        without_chip = compose_profile_strip(
            host="a-fairly-long-hostname.example.net", game_letter="A",
            handle="SomeLongHandleName", width=width,
        )
        assert joined == without_chip, f"width {width} lost identity chars when dropping the chip"


def test_conn_chip_focused_brackets_are_also_all_or_nothing():
    """The focused ``"[●]"`` variant (one char longer) must obey the
    same rule — never clip to ``"[CON"`` or similar."""
    for width in range(0, 45):
        segs = compose_profile_strip_segments(
            host="host", game_letter="A", handle="Captain", width=width,
            conn_chip=("[●]", "ok"),
        )
        chip_segments = [text for text, tone in segs if tone == "ok"]
        assert chip_segments in ([], [" [●]"]), (
            f"width {width} produced a partial focused chip: {chip_segments!r}"
        )
