"""Screen classifier tests: synthetic anchor coverage + a real captured
TWGS screen fixture (see tests/fixtures/, captured live per DESIGN.md §12)."""

import os

from twclient.classify import classify, classify_screen

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name):
    path = os.path.join(FIXTURE_DIR, name)
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_main_command_prompt():
    assert classify("Command [TL=00753:0/0/0/850] (?=Help)? :") == "main_command"


def test_computer_command_prompt_wins_over_main_command():
    """Regression: 'Computer command [TL=...]' is a superset of the plain
    'Command [TL=...]' ship prompt -- main_command's pattern always
    matches it too, so ordering (computer checked first) is what makes
    the more specific classification win. Caught live against
    twgs.test.example's on-board computer subsystem."""
    text = "Computer command [TL=00:00:00]:[22825] (?=Help)?"
    assert classify(text) == "computer"
    assert classify_screen(text, text) == "computer"


def test_pause_key():
    assert classify("  [Pause]") == "pause_key"
    assert classify("Press any key to continue...") == "pause_key"


def test_login_name():
    assert classify("What is your name, Trader?") == "login_name"


def test_login_password():
    assert classify("Password:") == "login_password"


def test_sector_display():
    assert classify("Sector  : 1234\r\nWarps to Sector(s):  1 - 2 - 3") == "sector_display"


def test_port_trade():
    assert classify("Fuel Ore   Buying   50%\r\nOrganics   Selling  20%") == "port_trade"


def test_unknown_fallback():
    assert classify("this matches nothing we know about") == "unknown"


def test_pause_key_takes_priority_over_other_anchors_on_same_screen():
    text = "Sector  : 1234\r\n[Pause]"
    assert classify(text) == "pause_key"


def test_real_captured_opening_screen_fixture():
    fixture_path = os.path.join(FIXTURE_DIR, "opening_screen.txt")
    if not os.path.exists(fixture_path):
        import pytest

        pytest.skip("no live-captured fixture present yet")
    text = _load_fixture("opening_screen.txt")
    result = classify(text)
    assert result == "login_name", f"live-captured opening screen misclassified as {result!r}:\n{text}"


def test_real_captured_game_select_menu_fixture():
    """Live TWGS server-level menu uses <A>/<B>/... bullets (not TW2002's
    classic (A)/(B) style) — caught by driving the real server. v2 B1
    promotes this from the generic bracket-style `menu` anchor to the
    dedicated `game_select` gate anchor (checked before `menu` in
    _GATE_ANCHORS) so the login automaton can auto-select the configured
    game letter specifically on this screen shape, distinct from any
    other menu."""
    fixture_path = os.path.join(FIXTURE_DIR, "game_select_menu.txt")
    if not os.path.exists(fixture_path):
        import pytest

        pytest.skip("no live-captured fixture present yet")
    text = _load_fixture("game_select_menu.txt")
    assert classify(text) == "game_select"


def test_inline_same_line_bracket_confirmation_is_not_a_menu():
    """Regression: 'Use (N)ew Name or (B)BS Name [B] ?' has two bracket
    pairs on ONE line -- an inline confirmation, not a genuine multi-line
    options list. Must not classify as menu (whole-text or via
    classify_screen), and must not poison later unrelated prompts once it
    scrolls into stale-but-still-on-screen buffer content. Caught live:
    it falsely classified 'Stardrift is what you want?' and 'One moment
    please' as menu (tests/fixtures/stale_bracket_false_positive.txt)."""
    line = "Use (N)ew Name or (B)BS Name [B] ?"
    assert classify(line) == "unknown"

    fixture_path = os.path.join(FIXTURE_DIR, "stale_bracket_false_positive.txt")
    if not os.path.exists(fixture_path):
        import pytest

        pytest.skip("no live-captured fixture present yet")
    text = _load_fixture("stale_bracket_false_positive.txt")
    rows = text.splitlines()
    prompt = rows[-1].strip() if rows else ""
    assert classify_screen(text, prompt) == "unknown"


def test_dash_style_menu_anchor():
    """TWGS module-entry menu style: 'T - Play Trade Wars 2002', no brackets."""
    text = "==-- Trade Wars 2002 --==\r\nT - Play Trade Wars 2002\r\nI - Introduction & Help\r\nX - Exit"
    assert classify(text) == "menu"


def test_classify_screen_prefers_prompt_line_over_stale_body_text():
    """Regression: a settled screen can still show an earlier decorative
    '[Pause]' marker above an already-active menu prompt. Whole-screen
    classify() misfires 'pause_key' here; classify_screen() must prefer
    the live prompt line and correctly land on 'menu' instead. Caught
    live against twgs.test.example (tests/fixtures/rules_and_menu_screen.txt)."""
    fixture_path = os.path.join(FIXTURE_DIR, "rules_and_menu_screen.txt")
    if not os.path.exists(fixture_path):
        import pytest

        pytest.skip("no live-captured fixture present yet")
    text = _load_fixture("rules_and_menu_screen.txt")
    rows = text.splitlines()
    prompt = rows[-1].strip() if rows else ""

    # The bug: naive whole-screen classify() is fooled by the stale
    # "[Pause]" text still visible higher up the screen.
    assert classify(text) == "pause_key"

    # The fix: classify_screen() only trusts a gate anchor (pause_key,
    # login_name/password, main_command) against the CURRENT prompt line;
    # the stale "[Pause]" match higher up the screen is correctly ignored,
    # and the content-anchor pass finds the real dash-style menu instead.
    assert classify_screen(text, prompt) == "menu"


def test_classify_screen_ignores_stale_gate_text_from_a_prior_prompt():
    """Regression: after answering a login-name prompt, the echoed
    'What is your name? ZEPHYR' line lingers above the NEXT prompt
    ('Vantage is what you want?' — the ship-name confirmation, which has
    no anchor of its own). Whole-text classify() misfires 'login_name';
    classify_screen() must not, since neither line legitimately anchors
    on that stale gate hit and the current prompt is unrelated."""
    text = "What is your name? ZEPHYR\r\nVantage is what you want?"
    prompt = "Vantage is what you want?"
    assert classify(text) == "login_name"  # the naive whole-text bug
    assert classify_screen(text, prompt) == "unknown"  # honest, not misleading


def test_classify_screen_falls_back_to_full_text_when_prompt_line_unanchored():
    # A body-only anchor (sector_display) with a prompt line that itself
    # anchors to nothing should still be found via the full-text fallback.
    text = "Sector  : 1234\r\nWarps to Sector(s):  1 - 2 - 3\r\n>"
    assert classify_screen(text, ">") == "sector_display"


def test_classify_screen_empty_prompt_uses_full_text():
    assert classify_screen("Password:", "") == "login_password"


# -- v2 B1 anchors (auto-login automaton) --------------------------------


def test_ansi_prompt():
    assert classify("Use ANSI graphics?") == "ansi_prompt"


def test_game_select():
    assert classify("Select a game :") == "game_select"


def test_char_create():
    text = "Would you like to start a new character in this game?  (Type Y or N)"
    assert classify(text) == "char_create"


def test_char_create_gate_checked_against_current_prompt_line():
    text = "You were not found in the player database.\r\nWould you like to start a new character in this game?  (Type Y or N)"
    prompt = "Would you like to start a new character in this game?  (Type Y or N)"
    assert classify_screen(text, prompt) == "char_create"


# -- cim_report (mack Finding 2, 2026-07-19 adversarial review) -------------
#
# parse_port_report() used to run with zero provenance check -- any
# screen merely REPRODUCING the report's header/footer punctuation got
# ingested as real sector data. These probes (adapted from mack's
# probe_poison.py) prove the new `cim_report` anchor tells a genuine
# system-generated report apart from a quoted example or forged
# transmission that reproduces the identical text.


def test_real_cim_report_fixture_classifies_as_cim_report():
    text = _load_fixture("cim_port_report.txt")
    rows = text.splitlines()
    prompt = rows[-1].strip() if rows else ""
    assert classify_screen(text, prompt) == "cim_report"


def test_help_screen_quoting_a_cim_report_as_a_worked_example_is_not_cim_report():
    """mack's probe_poison.py Scenario A: a help/tutorial screen quoting
    the report format as a worked example reproduces the exact
    header/footer punctuation, but carries narrative framing both
    before ("...looks like this:") and after ("Use it to scan...") the
    report that real system output never does."""
    text = (
        "Command [TL=00:00:00]:[1000] (?=Help) ? cim\n"
        "\n"
        "The Continuous Information Manifest (CIM) report looks like this:\n"
        "\n"
        "-=-=- Port Report (CIM) -=-=-\n"
        "Sector 999  Class: BBS F:10% O:20% E:30%  Warps: 1-2-3\n"
        "-=-=- End of Report -=-=-\n"
        "\n"
        "Use it to scan multiple sectors at once.\n"
        "Command [TL=00:00:01]:[1000] (?=Help) ?"
    )
    rows = text.splitlines()
    prompt = rows[-1].strip()
    assert classify_screen(text, prompt) != "cim_report"


def test_forged_chat_broadcast_quoting_a_cim_report_is_not_cim_report():
    """mack's probe_poison.py Scenario B: a forged/griefing chat
    broadcast reproducing the identical report punctuation, with no
    game-generated framing distinguishing it from a real report -- but
    it DOES carry its own "Incoming transmission from..." label directly
    above the header, which a genuine report (immediately preceded by
    only the triggering command's own echo) never has."""
    text = (
        "Incoming transmission from Rival Trader:\n"
        "-=-=- Port Report (CIM) -=-=-\n"
        "Sector 42  Class: SSB F:1% O:1% E:1%  Warps: 66-77-88\n"
        "-=-=- End of Report -=-=-\n"
        "\n"
        "Command [TL=00:00:05]:[1000] (?=Help) ?"
    )
    rows = text.splitlines()
    prompt = rows[-1].strip()
    assert classify_screen(text, prompt) != "cim_report"


def test_cim_report_not_yet_closed_is_not_trusted():
    """A report still printing (header seen, no footer yet) must not be
    classified as a genuine closed report -- same "don't parse mid-
    arrival" discipline as state_parser's own report parser."""
    text = "-=-=- Port Report (CIM) -=-=-\nSector 1  Class: BBB F:1% O:1% E:1%\nCommand [TL=00:00:00]:[1] (?=Help) ?"
    rows = text.splitlines()
    prompt = rows[-1].strip()
    assert classify_screen(text, prompt) != "cim_report"


def test_cim_report_anchors_to_the_latest_report_in_scrollback():
    """A stale, already-closed report sitting higher in the buffer, with
    intervening narrative text, must not itself get classified as the
    live report -- classify_screen() must land on the genuinely fresh
    one printed after it."""
    text = (
        "-=-=-        Port Report (CIM)        -=-=-\n"
        "Sector 111  Class: BBB  F:10% O:20% E:30%\n"
        "-=-=-        End of Report        -=-=-\n"
        "(intervening scrolled game text)\n"
        "Command [TL=00:00:00]:[1] (?=Help) ? v\n"
        "\n"
        "-=-=-        Port Report (CIM)        -=-=-\n"
        "Sector 222  Class: SSS  F:90% O:80% E:70%\n"
        "-=-=-        End of Report        -=-=-\n"
        "\n"
        "Command [TL=00:00:01]:[1] (?=Help) ?"
    )
    rows = text.splitlines()
    prompt = rows[-1].strip()
    assert classify_screen(text, prompt) == "cim_report"


def test_classify_whole_text_also_recognizes_a_genuine_cim_report():
    """The naive whole-text classify() must agree with classify_screen()
    on a genuine report -- both call the same structural check, just
    with different arguments."""
    text = _load_fixture("cim_port_report.txt")
    assert classify(text) == "cim_report"
