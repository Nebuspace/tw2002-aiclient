"""Best-effort state-extraction tests — no network involved."""

import os

from twclient.state_parser import is_genuine_sector_status, parse_haggle, parse_port_report, parse_state

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name):
    path = os.path.join(FIXTURE_DIR, name)
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_extracts_sector():
    assert parse_state("Sector  : 4321")["sector"] == 4321


def test_sector_anchors_to_last_match_not_a_stale_pre_warp_line():
    """Regression (DESIGN-v2 §8 root-fix): parse_state() used to
    re.search() the WHOLE rendered buffer, so a stale pre-warp 'Sector :
    1234' line still sitting in pyte's unclaimed scrollback (pyte
    doesn't clear cells the server never overwrites) outranked the
    true, current post-warp sector. The LAST match in the buffer is the
    current one."""
    text = "Sector : 1234\n(scrolled game text in between)\nSector : 5678"
    assert parse_state(text)["sector"] == 5678


# -- _SECTOR_RE line-anchoring (mack's F2 carve-out, closed 2026-07-19) -----
#
# Finding 2's original fix gated the BATCH parse_port_report() path on
# classify_screen; the single-sector write_from_state() path was
# explicitly left unconditional ("fine to keep unconditional"). mack's
# fresh-eyes pass found that carve-out IS exploitable: parse_state()'s
# unanchored `sector\s*:?\s*(\d+)` matches "Sector: N" ANYWHERE,
# including mid-sentence inside chat/narrative text, and the LAST-match
# discipline needed for the real stale-scrollback case then lets a
# same-screen phantom mention outrank the bot's true current sector.


def test_a_chat_line_mentioning_sector_mid_sentence_is_not_extracted():
    """Adapted from mack's probe_f2_carveout.py: the ONLY "sector"
    mention on this screen is embedded in ordinary narrative text, not a
    genuine system status line -- parse_state() must not manufacture a
    phantom sector out of it."""
    forged_narrative_screen = (
        "Incoming transmission from Rival Trader:\n"
        '"Meet me in Sector: 8675 with 50000 credits, I have a great deal!"\n'
        "\n"
        "You have 50,000 credits.\n"
        "Turns left : 199\n"
        "\n"
        "Command [TL=00:12:34]:[1000] (?=Help) ?"
    )
    assert parse_state(forged_narrative_screen).get("sector") is None


def test_a_genuine_status_line_still_extracts_correctly():
    """The real system status line ('Sector : N', its own line) must
    still extract exactly as before -- the fix narrows the anchor to
    the genuine shape, it doesn't disable extraction."""
    screen = "Sector : 100\nPorts   : Terran (Class 0)\nCommand [TL=00:12:34]:[1000] (?=Help) ?"
    assert parse_state(screen)["sector"] == 100


def test_real_sector_wins_over_a_same_screen_phantom_chat_mention():
    """Adapted from mack's probe_f2_combined.py: the bot is REALLY in
    sector 100 at a real port; a chat line mentioning "Sector: 8675"
    mid-sentence arrives on the SAME screen, textually AFTER the real
    status line. Before the fix, the last-match discipline picked the
    phantom 8675; the real sector must win now."""
    screen = (
        "Sector : 100\n"
        "Ports   : Terran (Class 0)\n"
        "\n"
        "Fuel Ore   Buying     1200    75%\n"
        "Organics   Selling     800    40%\n"
        "Equipment  Buying      300    90%\n"
        "\n"
        "Incoming transmission from Rival Trader:\n"
        '"Great deals waiting in Sector: 8675, come check it out!"\n'
        "\n"
        "Command [TL=00:12:34]:[1000] (?=Help) ?"
    )
    state = parse_state(screen)
    assert state["sector"] == 100
    assert state["port"]["commodities"][0]["name"] == "Fuel Ore"


# -- `is_genuine_sector_status()` (mack round-3 residual, closed 2026-07-19) -
#
# Round 2's line-anchoring only required the forged "Sector : N" be
# alone on ITS line, not alone on the SCREEN -- a line-isolated forgery
# inside an otherwise-narrative block still reproduces that shape and
# still wins parse_state()'s last-match-wins rule. These tests cover the
# new WORLD-MODEL-WRITE-ONLY provenance gate; parse_state()'s own
# `sector` field is asserted UNCHANGED throughout (see module docstring
# -- other consumers still need it).


def test_genuine_status_line_with_ports_sibling_is_trusted():
    screen = "Sector : 100\nPorts   : Terran (Class 0)\nCommand [TL=00:12:34]:[1000] (?=Help) ?"
    assert is_genuine_sector_status(screen) is True


def test_genuine_status_line_with_warps_to_sector_sibling_is_trusted():
    screen = "Sector : 100\nWarps to Sector(s) :  12 - 45 - 99\nCommand [TL=00:12:34]:[1000] (?=Help) ?"
    assert is_genuine_sector_status(screen) is True


def test_bare_sector_line_with_no_sibling_at_all_is_not_trusted():
    """A line-start "Sector : N" with nothing status-shaped immediately
    beneath it (just the command prompt) is not enough on its own --
    the genuine in-game display always carries at least one sibling
    status field alongside it."""
    screen = "Sector : 100\nCommand [TL=00:12:34]:[1000] (?=Help) ?"
    assert is_genuine_sector_status(screen) is False


def test_mid_sentence_phantom_with_no_line_start_match_is_not_trusted():
    screen = 'Incoming transmission: "Meet me in Sector: 8675, come see!"\nCommand [TL=00:12:34]:[1000] (?=Help) ?'
    assert is_genuine_sector_status(screen) is False


def test_residual_line_isolated_forgery_in_a_narrative_block_is_not_trusted():
    """mack round-3's confirmed repro (probe_residual_line_anchor.py):
    a real "Sector : 100" / "Ports : ..." block, followed later on the
    SAME screen by a planet-comment block whose only line-isolated
    "Sector : 8675" has no sibling status marker around it at all. The
    genuine block earlier in the screen must not vouch for this later,
    unrelated, line-isolated forgery -- the gate is evaluated against
    the LAST-match line specifically (the one parse_state()'s `sector`
    field itself would report), not "does a sibling exist anywhere on
    the screen"."""
    screen = (
        "Sector : 100\n"
        "Ports   : Terran (Class 0)\n"
        "\n"
        "-- Planet comment --\n"
        "Great deals waiting here!\n"
        "Sector : 8675\n"
        "Come check it out!\n"
        "\n"
        "Command [TL=00:12:34]:[1000] (?=Help) ?"
    )
    assert parse_state(screen)["sector"] == 8675  # unchanged -- parse_state()'s own extraction
    assert is_genuine_sector_status(screen) is False


def test_extracts_turns_left_from_command_prompt():
    state = parse_state("Command [TL=00753:0/0/0/850] (?=Help)? :")
    assert state["turns_left"] == 753


def test_tl_hhmmss_timer_shape_is_not_misread_as_zero_turns():
    """Regression: this live server's MBBS Gold build uses TL= for a
    HH:MM:SS countdown timer, not a turn count. Caught live against
    twgs.test.example's main command prompt
    ('Command [TL=00:00:00]:[22825] (?=Help)? :'); naively matching
    digits after 'TL=' produced a misleading turns_left=0."""
    state = parse_state("Command [TL=00:00:00]:[22825] (?=Help)? :")
    assert "turns_left" not in state
    assert state["turn_timer"] == "00:00:00"


def test_extracts_turns_left_plain_phrasing():
    """This live server never actually shows TL= as a turn count (see
    above) — the real number shows up post-dock instead: '29990 turns
    left.' Caught live against twgs.test.example."""
    assert parse_state("One turn deducted, 29990 turns left.")["turns_left"] == 29990


def test_extracts_credits_label_first_shape():
    assert parse_state("Credits: 12,345")["credits"] == 12345


def test_extracts_credits_amount_first_shape():
    """Regression: the real screen format is amount-first ('You have
    100,000 credits'), not label-first ('Credits: N') — the original
    label-first-only regex never matched this live shape at all. Caught
    live against twgs.test.example's port trade screen."""
    assert parse_state("You have 100,000 credits and 50 empty cargo holds.")["credits"] == 100000


def test_credits_anchors_to_you_have_line_over_a_stale_offer_mention():
    """Regression (DESIGN-v2 §8 root-fix -- corrupted one live reward
    delta by +90,661cr): a lingering 'We'll sell them for 132 credits.'
    offer sentence, still sitting in pyte's unclaimed scrollback from
    the PRIOR trade round, used to outrank the real 'You have N
    credits' balance line under first-match-wins re.search(). The
    unambiguous balance phrasing wins regardless of position now (this
    correction used to live only in ledger.py's snapshot_state())."""
    text = (
        "We'll sell them for 132 credits.\n"
        "Your offer [132] ?\n"
        "You have 100,485 credits and 50 empty cargo holds."
    )
    assert parse_state(text)["credits"] == 100485


def test_credits_takes_the_last_you_have_line_when_printed_twice():
    """Regression: a completed-transaction screen prints 'You have N
    credits' TWICE on one screen -- once mid-screen as the port's
    pre-transaction status context, once at the very end as the actual
    post-transaction result. The LAST one is current."""
    text = (
        "You have 100,101 credits and 40 empty cargo holds.\n"
        "We'll buy them for 384 credits.\n"
        "Your offer [384] ? 384\n"
        "Very well, we'll buy them.\n"
        "You have 100,485 credits and 50 empty cargo holds."
    )
    assert parse_state(text)["credits"] == 100485


def test_credits_label_first_fallback_also_anchors_to_last_match():
    """The fallback shapes (no 'you have' phrasing anywhere in the
    buffer) get the same last-match-wins treatment, closing the root
    defect for every credits shape, not just the balance phrasing."""
    text = "Credits: 1,000\nCredits: 2,000"
    assert parse_state(text)["credits"] == 2000


def test_extracts_warps():
    state = parse_state("Warps to Sector(s) :  12 - 45 - 99")
    assert state["warps"] == [12, 45, 99]


def test_extracts_port_commodities():
    """Real port-trade table shape: NAME STATUS TRADING %-OF-MAX ONBOARD
    -- three numbers per row, not one."""
    text = (
        "Fuel Ore   Buying    2650    100%       0\r\n"
        "Organics   Selling   2970     40%      12\r\n"
        "Equipment  Buying    1220    100%       0"
    )
    state = parse_state(text)
    names = {c["name"]: c for c in state["port"]["commodities"]}
    assert names["Fuel Ore"]["status"] == "buying"
    assert names["Fuel Ore"]["amount"] == 2650
    assert names["Fuel Ore"]["pct"] == 100
    assert names["Organics"]["status"] == "selling"
    assert names["Organics"]["pct"] == 40
    assert names["Equipment"]["pct"] == 100


def test_real_captured_port_trade_screen_fixture():
    """Regression: the naive single-number commodity regex misread the
    'Trading' amount column (2650) as a percentage instead of the actual
    '% of max' column (100). Caught live against twgs.test.example's
    Adipocere Primus port (tests/fixtures/port_trade_screen.txt)."""
    fixture_path = os.path.join(FIXTURE_DIR, "port_trade_screen.txt")
    if not os.path.exists(fixture_path):
        import pytest

        pytest.skip("no live-captured fixture present yet")
    text = _load_fixture("port_trade_screen.txt")
    state = parse_state(text)
    assert state["turns_left"] == 29990
    assert state["credits"] == 100000
    commodities = {c["name"]: c for c in state["port"]["commodities"]}
    for name in ("Fuel Ore", "Organics", "Equipment"):
        assert commodities[name]["status"] == "buying"
        assert commodities[name]["pct"] == 100  # the real % of max column
    assert commodities["Fuel Ore"]["amount"] == 2650


def test_missing_fields_are_simply_absent():
    state = parse_state("nothing recognizable here")
    assert state == {}


# -- parse_haggle: DESIGN-v2 §9, seeded from real captured port-haggle
# dialogues against twgs.test.example (2026-07-19) -----------------------


def test_parse_haggle_no_active_dialogue_is_empty():
    assert parse_haggle("Command [TL=00753:0/0/0/850] (?=Help)? :") == {}


def test_parse_haggle_opening_quote_buy_direction():
    """Real capture: a 'buy' dialogue (the port buys from us -- we want a
    HIGHER price) opens with a plain restatement + the same number as
    the offer default."""
    text = "We'll buy them for 2,214 credits.\nYour offer [2,214] ? "
    haggle = parse_haggle(text)
    assert haggle["direction"] == "buy"
    assert haggle["baseline"] == 2214
    assert haggle["latest_quote"] == 2214
    assert haggle["current_default"] == 2214


def test_parse_haggle_opening_quote_sell_direction():
    """Real capture: a 'sell' dialogue (the port sells to us -- we want
    a LOWER price)."""
    text = "We'll sell them for 758 credits.\nYour offer [758] ? "
    haggle = parse_haggle(text)
    assert haggle["direction"] == "sell"
    assert haggle["baseline"] == 758
    assert haggle["current_default"] == 758


def test_parse_haggle_round_two_anchors_to_the_latest_requote_not_the_opening_one():
    """Real captured round-2: countering the opening 2,214 quote with
    2450 got a re-quote ('We'll buy them for 2,216 credits.') using the
    SAME restatement wording as round 1 -- baseline must stay the
    ORIGINAL opening quote (the fair-value reference), while
    latest_quote/current_default track the live round-2 number."""
    text = (
        "We'll buy them for 2,214 credits.\n"
        "Your offer [2,214] ? 2450\n"
        "We'll buy them for 2,216 credits.\n"
        "Your offer [2,216] ? "
    )
    haggle = parse_haggle(text)
    assert haggle["direction"] == "buy"
    assert haggle["baseline"] == 2214  # unchanged -- the fair-value anchor
    assert haggle["latest_quote"] == 2216
    assert haggle["current_default"] == 2216


def test_parse_haggle_final_offer_phrasing_variant_also_anchors_to_last():
    """Real captured second port used 'Our final offer is N credits.'
    for its round-2 counter instead of restating 'We'll buy/sell...' --
    a different phrasing for the same live/current-quote concept, still
    anchored to the LAST one in the buffer."""
    text = (
        "We'll sell them for 3,700 credits.\n"
        "Your offer [3,700] ? 3700\n"
        "Our final offer is 3,372 credits.\n"
        "Your offer [3,372] ? "
    )
    haggle = parse_haggle(text)
    assert haggle["direction"] == "sell"
    assert haggle["baseline"] == 3700
    assert haggle["latest_quote"] == 3372
    assert haggle["current_default"] == 3372


def test_parse_haggle_current_default_absent_once_the_offer_prompt_is_gone():
    """The structural "resolved" signal haggle.py relies on: once the
    'Your offer [...]?' prompt is no longer the live tail of the screen
    (deal closed, in ANY of the several real acceptance phrasings --
    "Done, we'll take the lot.", "Cheapskate...", "You insult my
    intelligence...", "You will put me out of business..." were all
    observed live), current_default is absent."""
    text = (
        "We'll buy them for 2,216 credits.\n"
        "Your offer [2,216] ? 2216\n"
        "Done, we'll take the lot.\n\n"
        "You have 112,940 credits and 50 empty cargo holds.\n\n"
        "Command [TL=00:00:00]:[27584] (?=Help)? : "
    )
    haggle = parse_haggle(text)
    assert "current_default" not in haggle


# -- parse_port_report: batch-ingest for the world-model's `bulk_upsert`
# (knowledge/architecture/world-model.md). PROVENANCE CAVEAT: the CIM
# report grammar exercised below is CONSTRUCTED from documented TW2002
# conventions (the three-letter Buy/Sell port-class code is
# independently verified real; the header/footer/row punctuation is
# this project's own -- no live-captured multi-sector report exists
# yet). Expect a refinement pass once the daemon sees a real one. -----


def test_parse_port_report_clean_multi_sector_fixture():
    """The representative shape: a header, three sector rows (one with
    both port and warps, one warps-only, one port-only), a footer."""
    text = _load_fixture("cim_port_report.txt")
    records = parse_port_report(text)
    by_sector = {r["sector_id"]: r for r in records}
    assert set(by_sector) == {1234, 5001, 5678}

    full = by_sector[1234]
    assert full["warps"] == [2235, 2100, 1999]
    assert full["port"]["class"] == "BBS"
    commodities = {c["name"]: c for c in full["port"]["commodities"]}
    assert commodities["Fuel Ore"] == {"name": "Fuel Ore", "status": "buying", "pct": 100}
    assert commodities["Organics"] == {"name": "Organics", "status": "buying", "pct": 40}
    assert commodities["Equipment"] == {"name": "Equipment", "status": "selling", "pct": 60}

    warps_only = by_sector[5001]
    assert warps_only["warps"] == [5002, 5003]
    assert "port" not in warps_only

    port_only = by_sector[5678]
    assert "warps" not in port_only
    assert port_only["port"]["class"] == "SSB"


def test_parse_port_report_no_report_on_screen_returns_empty_list():
    assert parse_port_report("Command [TL=00753:0/0/0/850] (?=Help)? :") == []


def test_parse_port_report_anchors_to_the_latest_report_not_a_stale_one_in_scrollback():
    """Regression-shaped (same discipline as parse_state()'s stale-sector
    test): a stale, already-closed report sitting higher in the buffer
    must not shadow a genuinely fresher one printed after it."""
    text = (
        "-=-=-        Port Report (CIM)        -=-=-\n"
        "Sector 111  Class: BBB  F:10% O:20% E:30%\n"
        "-=-=-        End of Report        -=-=-\n"
        "(intervening scrolled game text)\n"
        "-=-=-        Port Report (CIM)        -=-=-\n"
        "Sector 222  Class: SSS  F:90% O:80% E:70%\n"
        "-=-=-        End of Report        -=-=-\n"
    )
    records = parse_port_report(text)
    assert [r["sector_id"] for r in records] == [222]


def test_parse_port_report_skips_a_malformed_row_without_crashing():
    """A row with an unparseable sector token is dropped conservatively
    -- never a guessed/garbage record into the world-model -- while its
    well-formed sibling rows still parse."""
    text = (
        "-=-=-        Port Report (CIM)        -=-=-\n"
        "Sector ABCD  Class: BBS  F:100% O:40% E:60%\n"
        "Sector 333  Class: BBS  F:100% O:40% E:60%\n"
        "-=-=-        End of Report        -=-=-\n"
    )
    records = parse_port_report(text)
    assert [r["sector_id"] for r in records] == [333]


def test_parse_port_report_drops_a_bare_sector_row_with_no_usable_data():
    """A sector number alone, with neither a port nor warps segment,
    carries no content worth writing to the world-model."""
    text = (
        "-=-=-        Port Report (CIM)        -=-=-\n"
        "Sector 444\n"
        "-=-=-        End of Report        -=-=-\n"
    )
    assert parse_port_report(text) == []


def test_parse_port_report_rejects_out_of_range_percentages():
    """mack's cheap-orthogonal-hardening suggestion (2026-07-19 follow-
    up): F/O/E percentages are bounded 0-100 -- a careless forgery with
    an out-of-range value ("F:150%") must be rejected rather than
    silently accepted as real port data. The row's warps segment is
    independent and still parses."""
    text = (
        "-=-=-        Port Report (CIM)        -=-=-\n"
        "Sector 555  Class: BBS  F:150% O:20% E:30%  Warps: 1-2-3\n"
        "-=-=-        End of Report        -=-=-\n"
    )
    records = parse_port_report(text)
    assert len(records) == 1
    assert "port" not in records[0]
    assert records[0]["warps"] == [1, 2, 3]


def test_parse_port_report_accepts_boundary_percentages_0_and_100():
    text = (
        "-=-=-        Port Report (CIM)        -=-=-\n"
        "Sector 556  Class: BBS  F:0% O:100% E:50%\n"
        "-=-=-        End of Report        -=-=-\n"
    )
    records = parse_port_report(text)
    commodities = {c["name"]: c for c in records[0]["port"]["commodities"]}
    assert commodities["Fuel Ore"]["pct"] == 0
    assert commodities["Organics"]["pct"] == 100
    assert commodities["Equipment"]["pct"] == 50
