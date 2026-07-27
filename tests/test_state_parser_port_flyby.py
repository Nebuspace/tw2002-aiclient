"""`read_port_from_sector_status` — the turn-free port flyby (E2).

Fixture provenance matters here, so it is stated: the primary shapes are
**column-0**, matching the real captured screens in the pre-rebirth live-run
ledger (`archive/…/runtime/state/ledger.jsonl`, `seraph_run` 2026-07-19,
e.g. `"prompt": "Warps to Sector(s) :  1"` with `"warps": [1]` parsed). Canon's
worked example in `canon/engine/screen-understanding.md` §"Examples" is
INDENTED — that is markdown code-block formatting, not a screen fact, and a
future WO that lifts it verbatim as a fixture would be testing against
something the game does not send. Indented variants are pinned separately as
robustness, never as the reference shape.

The tri-state is the point. "Nothing on screen" and "this sector has no port"
are different claims that write the world model in opposite directions.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.session.state_parser import (
    PortRead,
    read_port_from_sector_status as read_port,
)


# Real-shape (column-0) sector status, as captured live.
LIVE = (
    "Sector  : 158 in uncharted space.\n"
    "Ports   : Aegis, Class 1 (BBS)\n"
    "Warps to Sector(s) :  231 - 4309\n"
    "\n"
    "Command [TL=00:00:00]:[158] (?=Help)? :\n"
)
LIVE_NO_PORT = (
    "Sector  : 158 in uncharted space.\n"
    "Warps to Sector(s) :  231 - 4309\n"
    "\n"
    "Command [TL=00:00:00]:[158] (?=Help)? :\n"
)


# ------------------------------------------------------------------ the read

def test_reads_the_buy_sell_triple_from_a_live_shaped_screen():
    assert read_port(LIVE) == PortRead(observed=True, port={"class": "BBS"})


def test_the_class_is_the_letter_triple_never_the_digit():
    """Canon stores `"class": "BSB"`; the digit is display only."""
    text = LIVE.replace("Class 1 (BBS)", "Class 2 (BSB)")
    assert read_port(text).port == {"class": "BSB"}
    assert "2" not in (read_port(text).port or {}).get("class", "")


def test_a_warps_only_screen_is_UNOBSERVED_not_no_port():
    """The distinction the world model depends on: a render that never
    mentions ports states nothing, so the caller must omit the key and let a
    previously-learned port survive."""
    got = read_port(LIVE_NO_PORT)
    assert got.observed is False
    assert got.port is None


def test_ports_none_is_a_POSITIVE_no_port():
    text = LIVE.replace("Ports   : Aegis, Class 1 (BBS)", "Ports   : None")
    got = read_port(text)
    assert got.observed is True
    assert got.port is None


def test_a_special_port_is_present_but_classless_never_invented():
    """`Class 0 (Special)` is not a buy/sell posture. Recording it as one
    would put a fabricated commodity claim into the model; recording presence
    without a class lets `write_from_state` preserve a class learned
    elsewhere (e.g. a CIM report)."""
    text = LIVE.replace("Class 1 (BBS)", "Class 0 (Special)")
    got = read_port(text)
    assert got.observed is True
    assert got.port == {}
    assert "class" not in got.port


def test_case_is_normalised_upward():
    text = LIVE.replace("(BBS)", "(sbs)")
    assert read_port(text).port == {"class": "SBS"}


@pytest.mark.parametrize("triple", ["BBS", "BSB", "SBB", "SSB", "SBS", "BSS", "SSS", "BBB"])
def test_every_real_class_triple_reads(triple):
    text = LIVE.replace("(BBS)", f"({triple})")
    assert read_port(text).port == {"class": triple}


# ------------------------------------------------------- the provenance gate

def test_narrative_text_split_from_the_sector_line_is_not_ingested():
    """Canon's gate: the `Ports :` marker must be a SIBLING of the
    `Sector : N` line, before the next blank line. Prose that reproduces the
    shape across a paragraph break is not sector data."""
    narrative = (
        "The ancient log reads:\n"
        "\n"
        "Sector  : 999\n"
        "\n"
        "Ports   : Liar's Rest, Class 1 (BBS)\n"
    )
    assert read_port(narrative).observed is False


def test_a_ports_line_with_no_sector_anchor_is_not_ingested():
    assert read_port("Ports   : Orphan, Class 1 (BBS)\n").observed is False


def test_the_last_block_wins_on_a_scrolled_screen():
    """Same last-match discipline as `read_warps_from_sector_status` and
    `parse_state`: after a warp, the newest block is the true one."""
    scrolled = (
        "Sector  : 1\n"
        "Ports   : Old, Class 1 (BBS)\n"
        "Warps to Sector(s) : 2\n"
        "\n"
        "Sector  : 2\n"
        "Ports   : New, Class 8 (SSS)\n"
        "Warps to Sector(s) : 1\n"
    )
    assert read_port(scrolled).port == {"class": "SSS"}


# ------------------------------------------------------------- hardening

def test_never_raises_on_junk():
    for bogus in (None, 7, b"bytes", [], {}, object()):
        assert read_port(bogus) == PortRead(observed=False)


def test_an_empty_screen_is_unobserved():
    assert read_port("").observed is False


def test_indentation_is_tolerated_as_robustness_not_as_the_reference_shape():
    """Canon's markdown example is indented; real captures are not. Tolerated
    so a differently-rendered server does not silently stop feeding the world
    model — but the fixtures above stay column-0 deliberately."""
    indented = (
        "  Sector  : 5678\n"
        "  Ports   : Hammurabi Annex, Class 2 (BSB)\n"
        "  Warps to Sector(s) :  (379) - (597) - (1302)\n"
    )
    assert read_port(indented).port == {"class": "BSB"}
