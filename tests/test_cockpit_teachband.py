"""WO-P5-066 -- the standing A/R/T teach band on the control strip.

Layer-A: composition, canon wording, placement, width degradation, and the
labels-are-not-wired separation that is the WO's second Accept criterion.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from tw2002_aiclient.cockpit import control_seat, stopbanner, teachband

CANON = (
    Path(__file__).resolve().parents[1]
    / "canon" / "surfaces" / "mode-line-and-teach-controls.md"
)


# --------------------------------------------------------------------------
# Canon wording -- the Accept criterion that a naive "are A, R, T present?"
# check cannot see.
# --------------------------------------------------------------------------

def test_band_is_canon_standing_spelling() -> None:
    """WO-P5-071 adds `P panic`; WO-PLAY-REFLEX-AFFORDANCE adds `V)reflex`.

    `P panic` is spelled with a SPACE, not a paren. Canon's prose at
    `mode-line-and-teach-controls.md:235` says "every token uses the uniform
    `KEY)verb` shape", which would make this `P)anic` -- but the band
    literal canon actually prints is `P panic`, identically at `:136`,
    `:220` and `visual-language.md:306`. Three consistent cross-file
    literals beat one generalisation that overlooks its own last token, so
    the literal is what ships and the conflict is reported to the hub.
    Kept as an inline literal, NOT derived from `TEACH_TOKENS`: an
    expectation built from the product's own constant would follow any
    change to it and pin nothing.

    WO-PLAY-HELP-AUTONOMY-KEYS adds `H)old?` / `O)ffer?`
    (`?` = confirm-not-auto) immediately before `L)chains`.
    """
    assert teachband.compose_teach_band() == (
        "A)nalyze  R)ecord  T)rigger  V)reflex  U)rules  "
        "H)old?  O)ffer?  L)chains  P panic"
    )


def test_band_imports_reflex_token_spelling() -> None:
    """Single source of truth with the key-handler module (Accept #2)."""
    from tw2002_aiclient.cockpit import autonomy_keys
    from tw2002_aiclient.cockpit import chains
    from tw2002_aiclient.cockpit import reflex_controls
    from tw2002_aiclient.cockpit import rules_library

    assert reflex_controls.REFLEX_TOKEN == "V)reflex"
    assert reflex_controls.REFLEX_TOKEN in teachband.TEACH_TOKENS
    assert "V)reflex" in teachband.compose_teach_band()
    assert rules_library.RULES_TOKEN == "U)rules"
    assert rules_library.RULES_TOKEN in teachband.TEACH_TOKENS
    assert "U)rules" in teachband.compose_teach_band()
    assert autonomy_keys.HOLD_TOKEN == "H)old?"
    assert autonomy_keys.OFFER_TOKEN == "O)ffer?"
    assert autonomy_keys.HOLD_TOKEN in teachband.TEACH_TOKENS
    assert autonomy_keys.OFFER_TOKEN in teachband.TEACH_TOKENS
    assert "H)old?" in teachband.compose_teach_band()
    assert "O)ffer?" in teachband.compose_teach_band()
    # E stays on HELP one-liners (width) — still discoverable beside O/H/L.
    assert autonomy_keys.EXPLORE_TOKEN == "E)xplore"
    assert autonomy_keys.EXPLORE_TOKEN not in teachband.TEACH_TOKENS
    assert chains.CHAINS_TOKEN == "L)chains"
    assert chains.CHAINS_TOKEN in teachband.TEACH_TOKENS
    assert "L)chains" in teachband.compose_teach_band()
    assert teachband.TEACH_TOKENS[-2] is chains.CHAINS_TOKEN
    assert teachband.compose_teach_band().endswith("P panic")


def test_autonomy_help_one_liners_confirm_not_auto() -> None:
    """WO-PLAY-HELP-AUTONOMY-KEYS Accept: O/H carry confirm-not-auto wording."""
    from tw2002_aiclient.cockpit import autonomy_keys

    lines = autonomy_keys.compose_autonomy_help_lines()
    assert lines == (
        autonomy_keys.EXPLORE_HELP,
        autonomy_keys.HOLD_HELP,
        autonomy_keys.OFFER_HELP,
        autonomy_keys.CHAINS_HELP,
    )
    assert "confirm" in autonomy_keys.HOLD_HELP
    assert "not auto" in autonomy_keys.HOLD_HELP
    assert "confirm" in autonomy_keys.OFFER_HELP
    assert "not auto" in autonomy_keys.OFFER_HELP
    assert "O)ffer?" in autonomy_keys.OFFER_HELP
    assert "H)old?" in autonomy_keys.HOLD_HELP
    assert "E)xplore" in autonomy_keys.EXPLORE_HELP
    assert "L)chains" in autonomy_keys.CHAINS_HELP


def test_band_uses_trigger_not_the_banner_s_assign() -> None:
    """The whole point of the WO's wording criterion.

    Canon spells the T token TWO ways on purpose: `T)rigger` on the calm
    standing band, `T)assign` on the STOP banner's promoted teach line.
    Reusing `stopbanner.TEACH_LINE` here would still contain an A, an R and
    a T -- and would still be wrong.
    """
    band = teachband.compose_teach_band()
    assert "T)rigger" in band
    assert "T)assign" not in band
    assert "T)assign" in stopbanner.TEACH_LINE  # the other register, unchanged


def test_both_registers_are_grounded_in_canon_verbatim() -> None:
    """Neither spelling is this repo's invention -- both appear in canon."""
    text = CANON.read_text(encoding="utf-8")
    assert "A)nalyze  R)ecord  T)rigger" in text     # standing band, :136
    assert "A)nalyze  R)ecord  T)assign" in text     # STOP banner, :271


def test_band_does_not_carry_other_wos_tokens() -> None:
    """Still guarding scope creep — `^A)ode` stays foreign (ADR-002).

    `P panic` joined in WO-P5-071; `L)chains` joins in WO-TEACHBAND-L-CHAINS
    now that the modal ships. Mode chord remains out of this band.
    """
    band = teachband.compose_teach_band()
    assert "^A)ode" not in band
    assert "L)chains" in band


def test_tokens_are_pure_ascii_no_unicode_twin() -> None:
    """`visual-language.md:156`: `KEY)verb` -> `KEY)verb` (no swap)."""
    assert teachband.compose_teach_band(unicode_ok=True) == \
        teachband.compose_teach_band(unicode_ok=False)
    assert teachband.compose_teach_band().isascii()


@pytest.mark.parametrize("hostile", [None, 0, object(), b"x", [], 3.5])
def test_compose_never_raises_on_hostile_unicode_ok(hostile: object) -> None:
    assert teachband.compose_teach_band(unicode_ok=hostile) == (
        "A)nalyze  R)ecord  T)rigger  V)reflex  U)rules  "
        "H)old?  O)ffer?  L)chains  P panic"
    )


# --------------------------------------------------------------------------
# Placement on the control strip.
# --------------------------------------------------------------------------

def _line(width: int, **kw: object) -> str:
    segs = control_seat.compose_control_strip_segments(
        spectating=False, attached=True, liveness_text="RX 2s",
        width=width, **kw,
    )
    return "".join(text for text, _tone in segs)


def test_band_renders_on_a_wide_row() -> None:
    line = _line(120, teach_band=teachband.compose_teach_band())
    assert "A)nalyze  R)ecord  T)rigger" in line


def test_band_is_absent_when_not_passed() -> None:
    """Opt-in: every pre-066 caller keeps its exact previous row."""
    assert "A)nalyze" not in _line(120)


def test_band_does_not_disturb_the_row_width() -> None:
    for width in range(1, 160):
        line = _line(width, teach_band=teachband.compose_teach_band())
        assert len(line) == width, f"width {width} produced {len(line)}"


def test_band_never_abuts_chips_or_liveness() -> None:
    """>=1 blank column on each side, at every width the band renders at."""
    band = teachband.compose_teach_band()
    for width in range(1, 200):
        line = _line(width, teach_band=band)
        idx = line.find(band)
        if idx == -1:
            continue
        assert idx >= 1 and line[idx - 1] == " ", f"abuts left at width {width}"
        end = idx + len(band)
        assert end < len(line) and line[end] == " ", f"abuts right at width {width}"


def test_liveness_survives_every_width_the_band_renders_at() -> None:
    """The band is the lowest-priority element; it must never cost the
    load-bearing freeze signal a single column."""
    band = teachband.compose_teach_band()
    for width in range(1, 200):
        with_band = _line(width, teach_band=band)
        if band not in with_band:
            continue
        assert with_band.endswith("RX 2s"), f"liveness lost at width {width}"
        # And the chips on the left are byte-identical to the no-band row --
        # the band may only ever consume BLANK columns, never a chip's.
        assert with_band[: with_band.find(band)].rstrip() == \
            _line(width)[: with_band.find(band)].rstrip(), \
            f"band displaced left-side content at width {width}"


def test_band_drops_whole_never_truncated() -> None:
    """All-or-nothing: no proper prefix of the band may ever appear."""
    band = teachband.compose_teach_band()
    # From 2 chars up. A 1-char prefix is "A", which collides with any
    # unrelated chip that happens to contain the letter (the truncated
    # MANUAL chip renders "MA" at width 8) -- that is a coincidence, not a
    # truncated band. "A)" onward cannot occur except as this band.
    prefixes = [band[:n] for n in range(2, len(band))]
    for width in range(1, 200):
        line = _line(width, teach_band=band)
        if band in line:
            continue
        for prefix in prefixes:
            assert prefix not in line, (
                f"width {width} rendered truncated band {prefix!r}"
            )


def test_narrow_row_is_byte_identical_to_no_band() -> None:
    """Where the band cannot fit, the row is exactly what it was pre-066."""
    band = teachband.compose_teach_band()
    for width in range(1, 200):
        line = _line(width, teach_band=band)
        if band not in line:
            assert line == _line(width), f"width {width} changed without a band"


@pytest.mark.parametrize("hostile", [0, object(), b"bytes", [], 3.5, ""])
def test_hostile_band_renders_as_absent_not_invented(hostile: object) -> None:
    assert _line(120, teach_band=hostile) == _line(120)


# --------------------------------------------------------------------------
# The two composers must not drift.
# --------------------------------------------------------------------------

def test_segments_join_byte_identical_to_line() -> None:
    band = teachband.compose_teach_band()
    for width in range(1, 200):
        segs = control_seat.compose_control_strip_segments(
            spectating=False, attached=True, liveness_text="RX 2s",
            width=width, teach_band=band,
        )
        assert "".join(t for t, _ in segs) == _line(width, teach_band=band)


def test_band_segment_carries_the_chrome_tone() -> None:
    band = teachband.compose_teach_band()
    segs = control_seat.compose_control_strip_segments(
        spectating=False, attached=True, liveness_text="RX 2s",
        width=120, teach_band=band,
    )
    tones = [tone for text, tone in segs if text == band]
    assert tones == [teachband.TEACH_TONE]


def test_chrome_tone_is_distinct_from_every_badge_tone() -> None:
    """If TEACH_TONE ever collided with "ok"/"warn"/"danger" the band would
    silently acquire the reverse-video badge treatment."""
    assert teachband.TEACH_TONE not in ("ok", "warn", "danger", None)


# --------------------------------------------------------------------------
# Accept #2 -- labels only. Nothing behind them.
# --------------------------------------------------------------------------

def test_teach_keys_are_not_bound_in_the_cockpit_handler() -> None:
    """A, R and T are all now wired.

    R is wired by WO-P5-067; T by WO-P5-068; A by WO-P5-069 (Analyze
    on-demand).  All three are bound in the cockpit handler.

    Read structurally from the cockpit handler's source so a future
    removal of any binding goes red here immediately.
    """
    from tw2002_aiclient import screens

    src = inspect.getsource(screens.PlayShellScreen.handle_key)
    for key in ("A", "a", "R", "r", "T", "t"):
        assert re.search(rf"""ord\(["']{key}["']\)""", src), (
            f"cockpit handle_key no longer binds {key!r} — teach-band wire broken"
        )


def test_teachband_module_sends_nothing() -> None:
    """The band composes text. It must never acquire a send path."""
    src = inspect.getsource(teachband)
    for forbidden in ("send", "write", "socket", "subprocess", "os.system"):
        assert forbidden not in src, f"teachband references {forbidden!r}"
