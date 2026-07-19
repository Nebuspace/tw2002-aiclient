"""Best-effort state-extraction tests — no network involved."""

import os

from twclient.state_parser import parse_haggle, parse_state

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
