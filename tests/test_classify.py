"""Screen classifier tests: synthetic anchor coverage + a real captured
TWGS screen fixture (see tests/fixtures/, captured live; see canon session-engine / screen-understanding)."""

import os
import re

import pytest

from tw2002_aiclient.session import classify as classify_module
from tw2002_aiclient.session.classify import (
    _BLOCK_TITLE_SPECS,
    _CONTENT_ANCHORS,
    _GATE_ANCHORS,
    NEVER_AUTO_ACTION_CLASSES,
    _TWGS_MAIN_MENU_SECTOR_RE,
    _is_exclusive_closed_block,
    _is_main_command,
    _is_money_prompt,
    classify,
    classify_screen,
    is_probable_secret_prompt,
)

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name):
    path = os.path.join(FIXTURE_DIR, name)
    with open(path, encoding="utf-8") as f:
        return f.read()


def _fixture_with_prompt(name):
    """A fixture plus the prompt line the live path would hand
    `classify_screen` (`session.classify()` passes `rows[-1].strip()`)."""
    text = _load_fixture(name)
    rows = text.splitlines()
    return text, (rows[-1].strip() if rows else "")


def _block_spec(class_name):
    """The (header_re, footer_re) pair `classify` anchors for `class_name`.
    Reaching into the private table deliberately: several tests below need
    to prove the BLOCK was recognized on a screen whose final class is
    something else (a live gate anchor legitimately outranks it), and
    there is no public surface that reports that distinction."""
    for name, header_re, footer_re in _BLOCK_TITLE_SPECS:
        if name == class_name:
            return header_re, footer_re
    raise AssertionError(f"no block-title spec anchored for {class_name!r}")


def _cargo_hold_block_recognized(text):
    """Does the cargo-hold quote's block anchor actually fire on `text`?

    The question every exclusivity vector below is really asking. Those
    vectors used to ask it indirectly, via `classify_screen(...) ==
    "unknown"`, which worked only while their terminal purchase prompt
    anchored to nothing. `money_prompt` now claims that prompt, so the
    indirect form would answer "money_prompt" whether the exclusivity
    check worked or not -- a green test pinning nothing. Asking the
    predicate directly is both immune to that and strictly more
    specific: it names the property under test instead of a side effect
    of it."""
    header_re, footer_re = _block_spec("stardock_cargo_hold_quote")
    return _is_exclusive_closed_block(text, header_re, footer_re)


def test_main_command_prompt():
    assert classify("Command [TL=00753:0/0/0/850] (?=Help)? :") == "main_command"


# -- WO-CLASSIFY-MAIN-COMMAND-VS-TWGS-MENU --------------------------------


def test_twgs_door_main_menu_prompt_is_not_main_command():
    """Accept #1 (WO-CLASSIFY-MAIN-COMMAND-VS-TWGS-MENU).

    The TWGS outer-door ``[Main Menu]`` prompt must NOT classify as
    ``main_command``. Before the fix, ``ensure`` reported
    ``ok:true · classification=main_command`` for this exact string and
    the Play ladder drove a door menu as if it were an in-game sector
    prompt (live false-positive 2026-07-27)."""
    prompt = "Command [TL=00:00:00]:[Main Menu] :"
    assert classify_screen("", prompt) != "main_command"
    assert classify(prompt) != "main_command"
    # Hub ruling: prefer ``unknown`` (no new screen_class).
    assert classify_screen("", prompt) == "unknown"
    assert classify(prompt) == "unknown"


def test_twgs_door_main_menu_mutation_pin():
    """Mutation pin: ``_TWGS_MAIN_MENU_SECTOR_RE`` is the load-bearing guard.

    If the refuse regex is removed (or changed to never match), the prompt
    reverts to ``main_command`` because ``_COMMAND_ECHO_LINE_RE`` still
    matches the shared prefix. This proves the pin is not vacuous -- both
    halves of ``_is_main_command`` are necessary."""
    prompt = "Command [TL=00:00:00]:[Main Menu] :"
    # The refuse guard fires on the exact live false-positive string.
    assert _TWGS_MAIN_MENU_SECTOR_RE.search(prompt) is not None, (
        "refuse guard did not match — pin is vacuous"
    )
    # Without the guard, the TL prefix alone would match main_command.
    from tw2002_aiclient.session.classify import _COMMAND_ECHO_LINE_RE
    assert _COMMAND_ECHO_LINE_RE.search(prompt) is not None, (
        "TL prefix did not match — test is against wrong string"
    )
    # _is_main_command combines both: TL prefix YES, Main Menu guard FIRES → False.
    assert _is_main_command(prompt) is False


def test_in_game_sector_prompt_is_still_main_command():
    """Accept #2 (WO-CLASSIFY-MAIN-COMMAND-VS-TWGS-MENU).

    The real in-game sector prompt (integer sector number) must remain
    ``main_command`` after the fix — ``ensure`` depends on this."""
    in_game = "Command [TL=00:00:00]:[54] (?=Help)? :"
    assert classify_screen("", in_game) == "main_command"
    assert classify(in_game) == "main_command"
    assert _is_main_command(in_game) is True


def test_twgs_door_main_menu_stale_above_real_sector_prompt_does_not_poison():
    """Stale-scrollback guard (WO-CLASSIFY-MAIN-COMMAND-VS-TWGS-MENU).

    TWGS door chrome with ``[Main Menu]`` sitting above a real in-game
    sector prompt (e.g. after game selection and login) must not prevent
    ``main_command`` from being the correct classification for the live
    sector prompt. The gate anchor is checked against the prompt line
    only in ``classify_screen``."""
    stale_menu = "Command [TL=00:00:00]:[Main Menu] :"
    live_sector = "Command [TL=00:00:00]:[54] (?=Help)? :"
    text = stale_menu + "\n" + live_sector
    assert classify_screen(text, live_sector) == "main_command"


def test_real_sector_prompt_above_stale_main_menu_chrome_still_wins():
    """Mirror stale-scrollback guard: a later ``[Main Menu]`` left unclaimed
    in the pyte grid (e.g. on a TUI screen transition) above a real sector
    prompt must not steal the live gate. The current prompt is the live
    signal; stale content above it is scrollback noise."""
    live_sector = "Command [TL=00:00:00]:[54] (?=Help)? :"
    stale_menu = "Command [TL=00:00:00]:[Main Menu] :"
    # live prompt above, stale menu in scrollback below
    text = live_sector + "\n" + stale_menu
    # classify_screen uses the live prompt line — stale menu in body is irrelevant.
    assert classify_screen(text, live_sector) == "main_command"
    # NOTE: classify() (whole-text, no prompt discipline) sees BOTH lines;
    # _is_main_command checks the FULL text for [Main Menu] and would refuse.
    # This is a known, intentional difference — the stale-scrollback discipline
    # (gate anchors against prompt line only) is classify_screen's job, not
    # the content of classify().
    # For classify(), the live prompt's ``[54]`` is also present in the text;
    # since ``_TWGS_MAIN_MENU_SECTOR_RE`` fires on the stale line, classify()
    # returns ``unknown`` — the safe direction, never falsely ``main_command``
    # on a door menu screen.
    # Pinned both outcomes:
    assert classify(text) == "unknown"  # safe: stale menu in text → refuse wins


# -- end WO-CLASSIFY-MAIN-COMMAND-VS-TWGS-MENU ----------------------------


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


def test_login_password_real_prompts_still_classify():
    """WO-CLASSIFY-LOGIN-PASSWORD-NARROW Accept 2 — FakeTWGS / login
    automaton shapes must keep classifying as login_password after the
    bare-substring gate was tightened."""
    for prompt in (
        "Password:",
        "Password?",
        "Please enter a password for this game account.",
        "Please enter your password:",
        "Enter your password:",
        "Repeat password to verify.",
        "Your password?",
    ):
        assert classify_screen("", prompt) == "login_password", prompt
        assert classify(prompt) == "login_password", prompt


def test_login_password_refuses_help_utility_mentions():
    """WO-CLASSIFY-LOGIN-PASSWORD-NARROW Accept 1 + WO-CLASSIFY-PASSWORD-
    LENGTH-UNKNOWN — bare ``password`` in non-login chrome must not steal
    login_password, and password-length / help-about-password chrome must
    not land on incidental money_prompt either. Honest class: unknown
    (halt by unknown-is-first-class, not NEVER_AUTO money_prompt breadth)."""
    helpish = "How many characters in your password?"
    assert classify_screen("", helpish) != "login_password"
    assert classify(helpish) != "login_password"
    assert classify_screen("", helpish) != "money_prompt"
    assert classify(helpish) != "money_prompt"
    assert classify_screen("", helpish) == "unknown"
    assert classify(helpish) == "unknown"

    utility = "Utility Menu — password recovery tools (? for help):"
    assert classify_screen("", utility) != "login_password"
    assert classify(utility) != "login_password"
    assert classify_screen("", utility) != "money_prompt"
    assert classify_screen("", utility) == "unknown"

    chrome = "See the password section of the help file:"
    assert classify_screen("", chrome) != "login_password"
    assert classify_screen("", chrome) != "money_prompt"
    assert classify_screen("", chrome) == "unknown"


def test_sector_display():
    assert classify("Sector  : 1234\r\nWarps to Sector(s):  1 - 2 - 3") == "sector_display"


def test_warp_confirm_gate_wins_over_sector_display_body():
    """WO-CLASSIFY-WARP-CONFIRM: live stall mis-classed as sector_display
    because Sector: still sat above the Y/N — gate on the prompt line must
    win."""
    text = _load_fixture("warp_confirm_prompt.txt").rstrip("\n")
    prompt = text.splitlines()[-1].strip()
    assert prompt.startswith("Do you really want to warp there?")
    assert classify_screen(text, prompt) == "warp_confirm"
    assert classify(text) == "warp_confirm"


def test_warp_confirm_stale_in_scrollback_does_not_poison_main_command():
    """Prompt-line gate only — Y/N left in scrollback above Command must
    not steal the live classification."""
    text = (
        "Sector  : 100 in uncharted space.\n"
        "Do you really want to warp there? (Y/N)\n"
        "Command [TL=00:00:00]:[100] (?=Help)? :"
    )
    prompt = "Command [TL=00:00:00]:[100] (?=Help)? :"
    assert classify_screen(text, prompt) == "main_command"


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


def test_real_captured_boxed_game_select_menu_variant_fixture():
    """A structurally DIFFERENT live TWGS game-select shape: no "select a
    game" text anywhere on screen (the original anchor above never
    fires), just a bracket-style menu under a boxed "Game" header,
    ending in the generic "Selection (? for menu):" prompt. Promotes
    this shape to `game_select` too via `_is_twgs_boxed_game_select_menu`
    (classify.py), so login.py's existing `game_select` handler --
    sending `profile.game_letter` -- fires here exactly as it does for
    the "select a game" wording."""
    text = _load_fixture("game_select_menu_boxed_variant.txt")
    rows = text.splitlines()
    prompt = rows[-1].strip() if rows else ""
    assert classify(text) == "game_select"
    assert classify_screen(text, prompt) == "game_select"


def test_boxed_game_select_prompt_without_game_header_is_still_a_plain_menu():
    """Precision guard: a DIFFERENT TWGS menu (e.g. a server's main lobby)
    can share the exact same generic bracket style AND the exact same
    "Selection (? for menu):" prompt -- but without the boxed "Game"
    header, it must NOT be misclassified as `game_select` (that would
    send the configured game LETTER as a keystroke on the wrong screen).
    It must still land on the generic `menu` classification."""
    text = (
        "┌──────────────────────┐\n"
        "│      Main Menu        │\n"
        "├──────────────────────┤\n"
        "│ <A> Page News          │\n"
        "│ <B> Read Mail          │\n"
        "│ <Q> Quit               │\n"
        "└──────────────────────┘\n"
        "Selection (? for menu):"
    )
    rows = text.splitlines()
    prompt = rows[-1].strip()
    assert classify(text) == "menu"
    assert classify_screen(text, prompt) == "menu"


def test_real_captured_banner_game_select_menu_variant_fixture():
    """A THIRD, structurally different live TWGS game-select shape: no
    box-drawing at all (unlike the boxed variant above) -- just a plain
    bracket list ending in the same generic "Selection (? for menu):"
    prompt, distinguished only by the TWGS server startup banner printed
    above it ("TradeWars Game Server" / "TWGS v<version>" / "Server
    registered to <host>"). Before this fix, this shape fell all the way
    through to the generic `menu` classification (confirmed live) since
    it has neither "select a game" text nor a boxed "Game" header --
    `_is_twgs_server_banner_game_select_menu` (classify.py) is the third
    signal-path that catches it, so login.py's existing `game_select`
    handler fires here too."""
    text = _load_fixture("game_select_menu_banner_variant.txt")
    rows = text.splitlines()
    prompt = rows[-1].strip() if rows else ""
    assert classify(text) == "game_select"
    assert classify_screen(text, prompt) == "game_select"


def test_anet_boxed_title_banner_game_select_fixture():
    """Fourth TWGS game-select layout (WO-ANET-BANNER-LAYOUT): digit-token
    title embedded in ANSI art ~13 rows below the plain version/registered
    pair. Regex alone is insufficient — proximity must admit art-embedded
    titles without raising the raw line ceiling."""
    text = _load_fixture("game_select_menu_banner_anet_boxed_title.txt")
    rows = text.splitlines()
    prompt = rows[-1].strip() if rows else ""
    assert classify(text) == "game_select"
    assert classify_screen(text, prompt) == "game_select"


def test_anet_live_chrome_footer_game_select_fixture():
    """Live a-net step-5 door (WO-ANET-STEP5-LIVE-BYTES): same banner+art
    title+#/! options as the boxed-title layout, but Selection never
    appears on the grid — last line is box-drawing chrome. Fixture derived
    from hub capture 185955Z (sanitized). Must not invent a new class."""
    text = _load_fixture("game_select_menu_banner_anet_live_chrome.txt")
    rows = text.splitlines()
    prompt = rows[-1].strip() if rows else ""
    assert "Selection" not in text
    assert classify(text) == "game_select"
    assert classify_screen(text, prompt) == "game_select"


def test_anet_banner_with_textual_non_selection_prompt_is_not_game_select():
    """Adversarial: chrome-footer carve-out must not fire when the last line
    is a real textual prompt other than Selection (e.g. Enter your choice)."""
    text = (
        "TWGS v2.20b\n"
        "\n"
        "Server registered to Example Net Online\n"
        "\n"
        "▐═▐ Trade Wars 2002 Game Server ▐\n"
        "▐·▐   <A> Sample Alpha     <F> Sample Foxtrot\n"
        "▐≡▐   <B> Sample Bravo     <G> Sample Golf\n"
        "▐╗▐   <C> Sample Charlie   <#> View Players Online\n"
        "▐╝▐   <D> Sample Delta     <!> View Game Descriptions\n"
        "▐╦▐   <E> Sample Echo      <Q> Quit / Logoff\n"
        "Enter your choice:\n"
    )
    assert classify_screen(text, "Enter your choice:") == "menu"


def test_digit_token_title_in_prose_far_from_banner_pair_is_not_game_select():
    """Adversarial for WO-ANET-BANNER-LAYOUT: fixing the digit-token regex
    must NOT admit a title quoted in plain prose 13 rows below the
    version/registered pair (no box/block art on the title line)."""
    text = (
        "TWGS v2.20b\n"
        "\n"
        "Server registered to twgs.test.example\n"
        "\n"
        "HELP: Connecting to a TWGS server\n"
        "When you connect you'll see a title like:\n"
        "\n"
        "\n"
        "\n"
        "\n"
        "\n"
        "\n"
        "\n"
        "Trade Wars 2002 Game Server\n"
        "That's just documentation.\n"
        "\n"
        "<A> Next help topic\n"
        "<B> Previous help topic\n"
        "<#> View Players Online\n"
        "<!> View Game Descriptions\n"
        "Selection (? for menu):"
    )
    rows = text.splitlines()
    prompt = rows[-1].strip()
    assert classify(text) == "menu"
    assert classify_screen(text, prompt) == "menu"


def test_banner_game_select_with_timed_out_as_current_prompt_stays_game_select():
    """WO-CLASSIFY-TIMED-OUT: TWGS appends ``Timed out...`` as the live
    last line while Selection is still on screen — must stay game_select
    so login retries the letter (not wedge as plain menu/unknown)."""
    text = (
        "TradeWars Game Server\n"
        "TWGS v2.20b\n"
        "Server registered to twgs.test.example\n"
        "<A> Sample Game One\n"
        "<#> Players Online\n"
        "<!> View game descriptions\n"
        "<Q> Quit\n"
        "Selection (? for menu):\n"
        "Timed out..."
    )
    assert classify_screen(text, "Timed out...") == "game_select"
    assert classify(text) == "game_select"


def test_plain_game_select_with_timed_out_as_current_prompt_stays_game_select():
    """WO-PLAY-GAME-LETTER-AUTOSELECT: the PLAIN ``Select a game :`` variant
    (no TWGS box, no TWGS server banner) when TWGS appends ``Timed out...`` as
    the live last line must still classify as ``game_select`` so the login
    automaton sends ``profile.game_letter`` rather than wedging as ``menu``.

    Mirror of ``test_banner_game_select_with_timed_out_as_current_prompt_stays_game_select``
    for the plain variant. Root-cause pin: before the fix, classify_screen()
    returned ``menu`` here (gate anchor fired against the prompt only; ``Timed
    out...`` doesn't match ``select a game``), causing the login automaton to
    stagnate and hand Manual to the operator without ever sending the letter."""
    text = (
        "<A> Alien Retribution [20kS, 25kT]\n"
        "<B> Star Control II   [20kS, 10kT]\n"
        "<F> Bob the Builder   [30kS, 30kT, NO PVP]\n"
        "<!> Description menu  <Q> Quit (Disconnect)\n"
        "Select a game :\n"
        "Timed out..."
    )
    assert classify_screen(text, "Timed out...") == "game_select"
    # classify() full-text scan already worked (gate anchor fires on whole text);
    # this is the regression pin for the classify_screen() prompt-line path only.
    # WO-CLASSIFY-API-PARITY-PLAIN-TIMEOUT (ratified "enforce"): this is the
    # coincidental agreement classify()'s own docstring now documents explicitly --
    # not evidence classify() is generally safe to call on live screen text; see
    # the stale-scrollback negative just below for the case where it disagrees.
    assert classify(text) == "game_select"


def test_plain_game_select_timed_out_alternate_wording():
    """``Timed out waiting for input.`` is the longer TWGS timeout phrase —
    same root cause, same fix (``_TWGS_TIMED_OUT_PROMPT_RE`` already matches
    both wordings; this confirms the plain-variant timed-out handler sees it)."""
    text = (
        "<A> Game Alpha\n"
        "<F> Bob the Builder\n"
        "<Q> Quit\n"
        "Select a game :\n"
        "Timed out waiting for input."
    )
    assert classify_screen(text, "Timed out waiting for input.") == "game_select"


def test_stale_plain_game_select_bleeding_into_module_entry_menu_with_timed_out_is_not_game_select():
    """Stale-scrollback precision guard for the plain variant
    (WO-PLAY-GAME-LETTER-AUTOSELECT, mirrors the boxed/banner negative fixtures).

    A stale ``Select a game :`` left in the pyte buffer from an EARLIER login
    step can sit above the genuine CURRENT screen (the module-entry menu:
    ``T - Play Trade Wars 2002``) which itself then receives a ``Timed out...``
    prompt.  The plain-variant timed-out helper must NOT mistake the stale
    phrase for a live game-select prompt -- the dash-style menu option between
    the stale ``Select a game :`` line and the ``Timed out...`` line is the
    tell.  This would send the configured letter as an unintended keystroke on
    the wrong screen if it misfired as ``game_select``.

    WO-CLASSIFY-API-PARITY-PLAIN-TIMEOUT (ratified "enforce" over "align",
    audit/session-classify-audit-coverage-20260726.md C-01, amended per the
    2026-07-26T21:17Z CC probe): this is the load-bearing evidence for that
    ruling. ``classify()``'s own gate-anchor loop scans the WHOLE text with
    no prompt-line discipline at all, so it misreads the stale ``Select a
    game :`` line as ``game_select`` below -- a structurally BIGGER hole
    than the audit's one-line finding (a missing
    ``_is_plain_timed_out_game_select`` pre-pass), and not something that
    pre-pass could have fixed. See ``classify()``'s own docstring
    (classify.py) and tests/test_classify_api_parity.py's structural sweep,
    which fails the whole suite if any PRODUCT-TREE caller ever reaches for
    this bare function instead of ``classify_screen()``."""
    text = (
        "<A> Alien Retribution [20kS, 25kT]\n"  # stale game-select body
        "<F> Bob the Builder   [30kS, 30kT]\n"   # stale game-select body
        "Select a game :\n"                        # stale prompt -- must NOT vouch
        "T - Play Trade Wars 2002\n"              # CURRENT module-entry menu (dash-style)
        "I - Introduction & Help\n"
        "Enter your choice:\n"
        "Timed out..."
    )
    # Must be ``menu`` (the current screen's own content anchor), never ``game_select``.
    assert classify_screen(text, "Timed out...") == "menu"
    # classify() scans whole text, no prompt discipline -- this is the KNOWN,
    # intentional divergence WO-CLASSIFY-API-PARITY-PLAIN-TIMEOUT documents and
    # structurally refuses to let spread to any product-tree caller (see
    # tests/test_classify_api_parity.py).
    assert classify(text) == "game_select"


def test_banner_game_select_lookalike_without_the_twgs_banner_is_still_a_plain_menu():
    """Precision guard, mirroring the boxed-variant negative test above:
    a DIFFERENT TWGS lobby menu can share the exact same bracket style
    AND the exact same "Selection (? for menu):" prompt -- but without
    the TWGS server startup banner (title + version + "registered to"),
    it must NOT be misclassified as `game_select` (that would send the
    configured game LETTER as a keystroke on the wrong screen). It must
    still land on the generic `menu` classification."""
    text = (
        "Welcome to a different TWGS lobby\n"
        "\n"
        "<A> Sample Game One                    <B> Stock 5,000 Sectors\n"
        "<C> Stock 10,000 Sector Gold           <D> Stock 5,000 Sector SOLO\n"
        "<#> Players Online\n"
        "<Q> Quit\n"
        "\n"
        "Selection (? for menu):"
    )
    rows = text.splitlines()
    prompt = rows[-1].strip()
    assert classify(text) == "menu"
    assert classify_screen(text, prompt) == "menu"


# -- stale-scrollback / adversarial precision hardening (cipher review,
# 2026-07-20) -------------------------------------------------------------
#
# The FIRST versions of both game_select variant checks above scanned
# their header/banner signal against the WHOLE screen with no tie to the
# CURRENT prompt -- so a STALE header/banner left over from an earlier
# game-select screen could combine with a LATER, unrelated menu sharing
# the same generic "Selection (? for menu):" prompt and still misfire
# game_select (which would send the configured game LETTER on the wrong
# screen). These five vectors (adapted from the adversarial review's own
# probe script) each construct exactly that shape a different way; all
# five must classify as the generic `menu`, never `game_select`.


def test_stale_boxed_door_select_bleeding_into_a_later_module_entry_menu_is_not_game_select():
    """Vector 1: a genuine boxed door-select screen (real "Game" header
    + bracket menu) painted on an EARLIER screen is never cleared from
    the pyte grid; the NEXT real screen in the same login flow (the
    module-entry menu, a totally different step) only overwrites the
    bottom rows and legitimately also ends in the generic prompt."""
    text = (
        "+------------------+--------------------------+\n"
        "| Game             | Note: Multi-playing on   |\n"
        "+------------------+--------------------------+\n"
        "| <A> Vanilla TW2002: The Original              |\n"
        "| <Q> Quit                                      |\n"
        "+------------------------------------------------+\n"
        "\n"
        "\n"
        "T - Play Trade Wars 2002\n"
        "E - Exit\n"
        "Selection (? for menu):"
    )
    rows = text.splitlines()
    prompt = rows[-1].strip()
    assert classify(text) == "menu"
    assert classify_screen(text, prompt) == "menu"


def test_stale_twgs_banner_bleeding_into_a_later_unrelated_utility_menu_is_not_game_select():
    """Vector 2: the TWGS connect-time banner (printed once) never
    scrolls off / clears; a LATER, unrelated generic-prompt menu (e.g. a
    sysop/utility menu reached deep in the flow) still has it sitting
    above."""
    text = (
        "TradeWars Game Server\n"
        "TWGS v2.20b\n"
        "Server registered to twgs.test.example\n"
        "\n"
        "\n"
        "<A> Read System Notices\n"
        "<B> Change Terminal Options\n"
        "Selection (? for menu):"
    )
    rows = text.splitlines()
    prompt = rows[-1].strip()
    assert classify(text) == "menu"
    assert classify_screen(text, prompt) == "menu"


def test_help_screen_quoting_the_banner_verbatim_plus_an_unrelated_menu_is_not_game_select():
    """Vector 3: no stale scrollback needed at all -- just a help/manual
    screen that QUOTES the banner as documentation, plus an unrelated
    bracket menu of its own, ending in the same generic prompt by
    coincidence."""
    text = (
        "HELP: Connecting to a TWGS server\n"
        "When you connect you'll see a banner like:\n"
        "  TradeWars Game Server\n"
        "  TWGS v2.20b\n"
        "  Server registered to twgs.test.example\n"
        "That's just version info, nothing to act on.\n"
        "\n"
        "<A> Next help topic\n"
        "<B> Previous help topic\n"
        "Selection (? for menu):"
    )
    rows = text.splitlines()
    prompt = rows[-1].strip()
    assert classify(text) == "menu"
    assert classify_screen(text, prompt) == "menu"


def test_game_as_a_table_column_header_is_not_a_boxed_game_select_header():
    """Vector 4: a "who's playing what" status box with a real column
    header literally "Game", plus a genuine unrelated bracket menu below
    it (utility/options menu), ending in the same generic prompt."""
    text = (
        "+--------+----------+--------+\n"
        "| Player | Game     | Status |\n"
        "+--------+----------+--------+\n"
        "| Alice  | TWGS-1   | Active |\n"
        "+--------+----------+--------+\n"
        "\n"
        "<A> Refresh\n"
        "<B> Message a player\n"
        "Selection (? for menu):"
    )
    rows = text.splitlines()
    prompt = rows[-1].strip()
    assert classify(text) == "menu"
    assert classify_screen(text, prompt) == "menu"


def test_chat_lines_mimicking_bracket_menu_shape_plus_a_game_box_is_not_game_select():
    """Vector 5: two players with single-letter handles chatting, whose
    lines happen to look like bracket menu options, on a screen that
    (independently) has a "Game" box AND ends in the generic prompt --
    the hardest vector since there's no blank-line gap at all between
    the box and the chat lines."""
    text = (
        "+------+\n"
        "| Game |\n"
        "+------+\n"
        "Lobby chat:\n"
        "<A> hey anyone want to play\n"
        "<B> sure invite me\n"
        "Selection (? for menu):"
    )
    rows = text.splitlines()
    prompt = rows[-1].strip()
    assert classify(text) == "menu"
    assert classify_screen(text, prompt) == "menu"


# -- ROUND 2 stale-scrollback hardening (cipher re-attack, same day) -------
#
# The round-1 fix above (vectors 1-5) proves ADJACENCY -- the header/banner
# and the qualifying body sit in the same range -- but never proves the
# qualifying body is the LAST menu content before the prompt. A STALE, never-
# cleared copy of a FULL game-select body (markers included) can itself sit
# in that range ahead of a genuinely CURRENT, actually-different bracket-
# style menu (not dash-style, so `_range_has_no_dash_style_menu` misses it),
# and the round-1 fix alone still misfires `game_select`. Both vectors below
# must classify as the generic `menu`, never `game_select`.


def test_stale_boxed_game_select_body_bleeding_into_a_live_utility_menu_is_not_game_select():
    """The boxed variant's own game-select body (header, game list, BOTH
    markers, "<Q> Quit") never clears from the pyte grid; a REAL, actually-
    current "Utility Menu" with its own unrelated bracket options sits
    directly above the prompt. Before the round-2 fix, the stale markers
    higher up in the same range still vouched for `game_select` here."""
    text = (
        "┌──────────────────────────────────────┐\n"
        "│                Game                 │\n"
        "├──────────────────────────────────────┤\n"
        "│ <A> Vanilla TW2002: Mostly default  │\n"
        "│ <#> Players Online                  │\n"
        "│ <!> View Game Descriptions          │\n"
        "│ <Q> Quit                            │\n"
        "└──────────────────────────────────────┘\n"
        "\n"
        "Utility Menu\n"
        "\n"
        "<A> Refresh\n"
        "<B> Message a player\n"
        "\n"
        "Selection (? for menu):"
    )
    rows = text.splitlines()
    prompt = rows[-1].strip()
    assert classify(text) == "menu"
    assert classify_screen(text, prompt) == "menu"


def test_stale_banner_game_select_body_bleeding_into_a_live_utility_menu_is_not_game_select():
    """Same shape as the boxed vector above, applied to the non-boxed
    banner variant: the TWGS connect-time banner plus its own full
    game-select body (game list, BOTH markers, "<Q> Quit") is stale
    scrollback; a REAL, actually-current "Utility Menu" sits directly
    above the prompt."""
    text = (
        "TradeWars Game Server\n"
        "TWGS v2.20b\n"
        "Server registered to twgs.test.example\n"
        "\n"
        "<A> Sample Game One\n"
        "<#> Players Online\n"
        "<!> View game descriptions\n"
        "<Q> Quit\n"
        "\n"
        "Utility Menu\n"
        "\n"
        "<A> Refresh\n"
        "<B> Message a player\n"
        "\n"
        "Selection (? for menu):"
    )
    rows = text.splitlines()
    prompt = rows[-1].strip()
    assert classify(text) == "menu"
    assert classify_screen(text, prompt) == "menu"


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


# -- WO-CLASSIFY-BLOCK-TITLES: the OTHER `-=-=- <Title> -=-=-` blocks ------
#
# `Port Report (CIM)` was the only system block classify.py anchored, even
# though the captured corpus carries eight distinct block headers. The
# generalization is deliberately narrow, because on this product a
# CONFIDENTLY WRONG class is worse than `unknown` (which routes to
# escalate-to-the-human -- canon engine/screen-understanding.md, "The
# Unknown Is First-Class"). Three properties carry that narrowness, and
# each has its own tests below:
#
#   1. exclusivity, reused wholesale from `_is_genuine_cim_report` -- a
#      screen that merely QUOTES a block is never the block;
#   2. an explicit header+footer PAIR per entry, because TW2002's footers
#      are not derived from its headers ("StarDock Shipyard - Cargo Hold
#      Upgrade" closes with "End of Cargo Hold Upgrade Quote");
#   3. an ALLOWLIST, not a shape -- an unanchored title classifies as
#      nothing at all and the screen stays `unknown`.
#
# Anchored: `Port Report (CIM)` (pre-existing), `StarDock Shipyard - Cargo
# Hold Upgrade`, `StarDock Shipyard - Ship Registration`. NOT anchored,
# with reasons, in `_BLOCK_TITLE_SPECS`' own comment in classify.py.

_HOLDS_PROMPT = "How many holds would you like to buy [0-20] ?"


def test_real_captured_stardock_cargo_hold_quote_classifies():
    """The acceptance case, in its final shape. A real captured StarDock
    PURCHASE screen: the cargo-hold upgrade quote. Two things are true
    about it at once and the order between them is the whole point.

    The exclusive closed block above the prompt IS recognized -- asserted
    directly against the shared predicate, so this is a claim about the
    block anchor and not about whatever `classify_screen` happens to
    answer. But the live prompt is a BUY QUESTION, and DECISIONS §A.2
    pins that shape never-auto-action, so the `money_prompt` gate
    outranks the content anchor and is what the app is told.

    That precedence is deliberate and is the safety of the whole WO. The
    losing answer, `stardock_cargo_hold_quote`, is a benign screen
    IDENTITY -- exactly the kind of label a taught rule may be recorded
    against. Handing it back while the server sits blocked on "how many
    holds would you like to buy" is the hole DECISIONS §A.2 exists to
    close. Nothing is lost: the block still identifies the screen for
    anyone who asks the predicate, and the at-max sibling capture below
    still classifies by its block on the no-prompt path."""
    text, prompt = _fixture_with_prompt("stardock_cargo_hold_quote.txt")
    header_re, footer_re = _block_spec("stardock_cargo_hold_quote")
    assert prompt == _HOLDS_PROMPT
    assert _is_exclusive_closed_block(text, header_re, footer_re) is True
    assert classify_screen(text, prompt) == "money_prompt"
    # ... and with no live prompt line the block IS the answer: the gate
    # never fires, because a gate is a claim about what the server is
    # blocked on right now.
    assert classify_screen(text, "") == "stardock_cargo_hold_quote"


def test_cargo_hold_quote_at_max_keeps_main_command_because_the_live_gate_wins():
    """The SAME block on the sibling real capture (the ship is already at
    max holds, so the server printed the quote and went straight back to
    the ship command prompt). The block IS recognized -- proven directly
    against the shared predicate -- but the block anchors are CONTENT
    anchors, so the live `main_command` gate correctly outranks them: the
    server is blocked at the command prompt, and that is what the app must
    be told. Getting this precedence backwards would silently break
    `ensure`/`guardian`/`login`, all of which drive to a verified
    `main_command`."""
    text, prompt = _fixture_with_prompt("stardock_cargo_hold_quote_at_max.txt")
    header_re, footer_re = _block_spec("stardock_cargo_hold_quote")
    assert _is_exclusive_closed_block(text, header_re, footer_re) is True
    assert classify_screen(text, prompt) == "main_command"


def test_real_captured_shipyard_listing_block_is_recognized_and_the_live_gate_wins():
    """The second anchored title, on its own real capture. Same shape as
    the at-max case above: an exclusive closed `StarDock Shipyard - Ship
    Registration` block whose live prompt is the ship command prompt, so
    `main_command` wins. This title is anchored anyway -- the block is what
    identifies the screen, and the class is what a taught rule would have
    to match on the day a capture arrives with a question below it instead
    of the command prompt."""
    text, prompt = _fixture_with_prompt("stardock_shipyard_listing.txt")
    header_re, footer_re = _block_spec("stardock_shipyard_listing")
    assert _is_exclusive_closed_block(text, header_re, footer_re) is True
    assert classify_screen(text, prompt) == "main_command"


# -- exclusivity: a screen that QUOTES a block is never that block --------
#
# Every vector below ends in the real purchase prompt. When these were
# written that prompt anchored to NOTHING, which is what made
# `classify_screen(...) == "unknown"` a meaningful assertion: with no gate
# to hide behind, the block anchor was the only thing that could have
# classified them.
#
# `money_prompt` took that property away -- the purchase prompt is now a
# gate, and a gate answers before any content anchor is consulted. Left
# alone, every one of these would assert "money_prompt" and pass no matter
# what the exclusivity check did. So each now asserts the exclusivity
# predicate DIRECTLY (`_cargo_hold_block_recognized`), which no gate can
# stand in front of, and keeps the class assertion as corroboration that
# the block never reaches the answer either. The vectors themselves are
# untouched: the attack each encodes is unchanged, only the question asked
# of it is sharper.


def test_help_screen_quoting_the_cargo_hold_quote_as_a_worked_example_is_not_classified():
    """The `_is_genuine_cim_report` probe, re-aimed: a help screen can
    reproduce the block's punctuation byte-for-byte, but it needs a lead-in
    ("...looks like this:") and a trailing remark that real system output
    never carries."""
    text = (
        "Command [TL=00:00:00]:[1000] (?=Help) ? u\n"
        "\n"
        "HELP: buying cargo holds\n"
        "The upgrade quote StarDock prints looks like this:\n"
        "\n"
        "-=-=-        StarDock Shipyard - Cargo Hold Upgrade        -=-=-\n"
        "Your ship can hold up to 20 additional cargo holds.\n"
        "-=-=-        End of Cargo Hold Upgrade Quote        -=-=-\n"
        "\n"
        "Holds are only ever sold at StarDock.\n"
        f"{_HOLDS_PROMPT}"
    )
    assert _cargo_hold_block_recognized(text) is False
    assert classify_screen(text, _HOLDS_PROMPT) == "money_prompt"
    assert classify(text) != "stardock_cargo_hold_quote"


def test_forged_transmission_quoting_the_cargo_hold_quote_is_not_classified():
    """A forged/griefing broadcast reproducing the identical block, with
    its own "Incoming transmission from..." label directly above the
    header -- which a genuine block (immediately preceded by only the
    triggering command's echo) never has."""
    text = (
        "Incoming transmission from Rival Trader:\n"
        "-=-=-        StarDock Shipyard - Cargo Hold Upgrade        -=-=-\n"
        "Holds cost 1 credit each, for a total of 20 credits to fill them all.\n"
        "-=-=-        End of Cargo Hold Upgrade Quote        -=-=-\n"
        "\n"
        f"{_HOLDS_PROMPT}"
    )
    assert _cargo_hold_block_recognized(text) is False
    assert classify_screen(text, _HOLDS_PROMPT) == "money_prompt"


def test_cargo_hold_quote_still_printing_is_not_classified():
    """Header seen, no footer yet -- the same "never trust a block
    mid-arrival" discipline the CIM report already obeys."""
    text = (
        "Command [TL=00:00:00]:[1000] (?=Help) ? u\n"
        "\n"
        "-=-=-        StarDock Shipyard - Cargo Hold Upgrade        -=-=-\n"
        "Your ship can hold up to 20 additional cargo holds.\n"
        f"{_HOLDS_PROMPT}"
    )
    assert _cargo_hold_block_recognized(text) is False
    assert classify_screen(text, _HOLDS_PROMPT) == "money_prompt"


def test_narrative_after_the_cargo_hold_quote_footer_is_not_classified():
    """Exclusivity is checked on BOTH sides of the block: a trailing
    remark between the footer and the prompt is narrative framing, so the
    block is not the screen's sole content."""
    text = (
        "Command [TL=00:00:00]:[1000] (?=Help) ? u\n"
        "\n"
        "-=-=-        StarDock Shipyard - Cargo Hold Upgrade        -=-=-\n"
        "Your ship can hold up to 20 additional cargo holds.\n"
        "-=-=-        End of Cargo Hold Upgrade Quote        -=-=-\n"
        "\n"
        "Prices are re-quoted daily; this one may be out of date.\n"
        f"{_HOLDS_PROMPT}"
    )
    assert _cargo_hold_block_recognized(text) is False
    assert classify_screen(text, _HOLDS_PROMPT) == "money_prompt"


def test_stale_cargo_hold_quote_above_a_later_one_anchors_to_the_LATEST_block():
    """Stale-scrollback discipline, inherited from the CIM anchor: an
    older closed quote sitting higher in the never-cleared pyte grid, with
    intervening game text, must not be what gets classified -- the freshest
    block printed after it is."""
    text = (
        "-=-=-        StarDock Shipyard - Cargo Hold Upgrade        -=-=-\n"
        "Holds cost 900 credits each, for a total of 18,000 credits.\n"
        "-=-=-        End of Cargo Hold Upgrade Quote        -=-=-\n"
        "(intervening scrolled game text)\n"
        "Command [TL=00:00:00]:[1000] (?=Help) ? u\n"
        "\n"
        "-=-=-        StarDock Shipyard - Cargo Hold Upgrade        -=-=-\n"
        "Holds cost 1,468 credits each, for a total of 29,360 credits.\n"
        "-=-=-        End of Cargo Hold Upgrade Quote        -=-=-\n"
        "\n"
        f"{_HOLDS_PROMPT}"
    )
    assert _cargo_hold_block_recognized(text) is True
    assert classify_screen(text, _HOLDS_PROMPT) == "money_prompt"


# -- the asymmetric footer: headers do NOT derive their own closers -------


def test_the_naive_symmetric_end_of_header_title_footer_is_not_accepted():
    """The trap this WO exists around. TW2002's footer title is NOT
    "End of <header title>": the real captured block closes with "End of
    Cargo Hold Upgrade Quote". A screen carrying the *derived* footer a
    naive rule would have looked for is not a block this module knows, so
    it stays `unknown` -- and the paired assertion proves the anchored,
    genuinely captured footer is what does close it, so this test can
    never pass merely because the header regex is broken."""
    derived_footer = "-=-=-        End of StarDock Shipyard - Cargo Hold Upgrade        -=-=-"
    real_footer = "-=-=-        End of Cargo Hold Upgrade Quote        -=-=-"
    body = (
        "Command [TL=00:00:00]:[1000] (?=Help) ? u\n"
        "\n"
        "-=-=-        StarDock Shipyard - Cargo Hold Upgrade        -=-=-\n"
        "Your ship can hold up to 20 additional cargo holds.\n"
        "{footer}\n"
        "\n"
        f"{_HOLDS_PROMPT}"
    )
    assert _cargo_hold_block_recognized(body.format(footer=derived_footer)) is False
    assert _cargo_hold_block_recognized(body.format(footer=real_footer)) is True


def test_a_real_footer_from_a_different_block_never_closes_this_header():
    """The looser repair for the asymmetry -- "accept any `End of ...`
    line" -- is worse than the naive one: it pairs one block's header with
    a DIFFERENT block's closer. Both titles here are real captured
    strings; the PAIR is not, so nothing classifies."""
    text = (
        "Command [TL=00:00:00]:[1000] (?=Help) ? u\n"
        "\n"
        "-=-=-        StarDock Shipyard - Cargo Hold Upgrade        -=-=-\n"
        "Your ship can hold up to 20 additional cargo holds.\n"
        "-=-=-        End of Shipyard Listing        -=-=-\n"
        "\n"
        f"{_HOLDS_PROMPT}"
    )
    assert _cargo_hold_block_recognized(text) is False
    assert classify_screen(text, _HOLDS_PROMPT) == "money_prompt"


# -- allowlist, not shape -------------------------------------------------


def test_an_unanchored_block_title_stays_unknown_even_when_perfectly_exclusive():
    """The single most important property of the generalization: the table
    is an ALLOWLIST of captured title pairs, not a `-=-=- <Title> -=-=-`
    shape. This screen is synthetic and gives a REAL but unanchored title
    pair (from tests/fixtures/stardock_equipment_listing.txt, where it
    only ever appears mid-listing) the most favourable framing possible --
    perfectly exclusive, triggering echo above, nothing but the prompt
    below. It must still be `unknown`, because naming a screen nobody has
    captured in this shape is exactly the confident-wrong-answer this
    module refuses to give."""
    text = (
        "Command [TL=00:00:00]:[1000] (?=Help) ? e\n"
        "\n"
        "-=-=-        Density & Holographic Scanners        -=-=-\n"
        "Scanner Type                  Cost        Notes\n"
        "Fixture Density Scanner      50,000      Reveals adjacent signatures\n"
        "-=-=-        End of Scanner Listing        -=-=-\n"
        "\n"
        "Enter your selection:"
    )
    assert classify_screen(text, "Enter your selection:") == "unknown"


def test_a_one_word_mutation_of_an_anchored_title_stays_unknown():
    """Same allowlist property, attacked from the other side: the real
    captured purchase screen with ONE word changed in its header title.
    Everything else -- framing, footer, live prompt -- is the genuine
    capture, so only the exact-title match stands between this and a
    confident wrong answer."""
    text, prompt = _fixture_with_prompt("stardock_cargo_hold_quote.txt")
    assert _cargo_hold_block_recognized(text) is True
    mutated = text.replace("Cargo Hold Upgrade        -=-=-", "Cargo Bay Upgrade        -=-=-")
    assert "Cargo Bay Upgrade" in mutated
    assert _cargo_hold_block_recognized(mutated) is False
    # The live money gate answers for both, which is exactly why the
    # title claim has to be asserted against the predicate above.
    assert classify_screen(mutated, prompt) == "money_prompt"


def test_multi_block_equipment_listing_anchors_nothing_new():
    """The real StarDock equipment screen carries FOUR block headers and
    THREE footers, none of them a matching pair by title and none of them
    exclusive (each inner block has the previous block's output above it).
    It is not anchored, it does not become anchored by accident, and its
    live `main_command` gate remains its correct class."""
    text, prompt = _fixture_with_prompt("stardock_equipment_listing.txt")
    for _name, header_re, footer_re in _BLOCK_TITLE_SPECS:
        assert _is_exclusive_closed_block(text, header_re, footer_re) is False
    assert classify_screen(text, prompt) == "main_command"


def test_with_no_prompt_line_the_block_outranks_the_whole_text_gate_fallback():
    """A real behavior change worth stating outright. `classify_screen`'s
    last resort, when there is no prompt line at all, is to scan gate
    anchors against the WHOLE text -- and the whole text of these screens
    still holds the stale `Command [TL=…]` echo that triggered the block.
    Content anchors are checked BEFORE that fallback (pre-existing
    precedent, unchanged by this WO: `port_trade_screen.txt` with an empty
    prompt already answers `port_trade`, not `main_command`), so these two
    screens now answer with their block instead of `main_command`.

    That is the honest answer: with no live prompt line, `main_command`
    would be a claim that the server is blocked at the ship prompt, sourced
    from nothing but stale unclaimed grid content -- exactly the
    false-gate-on-scrollback failure this module's prompt-line discipline
    exists to prevent. The live path reaches this shape whenever the last
    rendered row is blank (`session.classify()` passes `rows[-1].strip()`).
    """
    for fixture, expected in (
        ("stardock_shipyard_listing.txt", "stardock_shipyard_listing"),
        ("stardock_cargo_hold_quote_at_max.txt", "stardock_cargo_hold_quote"),
    ):
        text = _load_fixture(fixture)
        assert classify_screen(text, "") == expected
        # ... and with the real prompt line present, the live gate still wins.
        assert classify_screen(text, text.splitlines()[-1].strip()) == "main_command"


def test_an_anchored_stardock_block_never_becomes_a_cim_report():
    """The CIM anchor and the new ones now share one structural predicate;
    this pins that sharing the STRUCTURE never means sharing the TITLE."""
    for name in ("stardock_cargo_hold_quote.txt", "stardock_shipyard_listing.txt"):
        text, prompt = _fixture_with_prompt(name)
        assert classify_screen(text, prompt) != "cim_report"
        assert classify_screen(text, "") != "cim_report"
        assert classify(text) != "cim_report"


# -- money_prompt: the class that FORBIDS ---------------------------------
#
# WO-CLASSIFY-BLOCK-TITLES / canon DECISIONS.md §A.2 (Accepted
# 2026-07-26), aligning canon's P-QTY. Every other class in this module is
# a licence: canon (engine/screen-understanding.md, "The Unknown Is First-
# Class") makes `unknown` the escalate trigger, so naming a screen is what
# allows a taught rule to match it. `money_prompt` is the one label that
# runs the other way -- it is named AND forbidden, so it SUBTRACTS its
# screens from the teachable set. Tests below pin both halves: that it
# claims the shapes P-QTY names, and that claiming them never hands any
# consumer a new screen to act on.


def test_the_real_captured_purchase_prompt_is_a_money_prompt():
    """P-QTY's own worked example, from the real capture. This exact line
    is why the class exists: `[0-20]` is a RANGE HINT, while the sibling
    `[12]` / `[100]` quantity prompts are DEFAULTS a bare Enter accepts,
    and nothing in the shape distinguishes them."""
    assert classify_screen("", _HOLDS_PROMPT) == "money_prompt"


@pytest.mark.parametrize(
    "prompt",
    [
        # Range hint -- the real capture (tests/fixtures/…quote.txt).
        "How many holds would you like to buy [0-20] ?",
        # Enter-accepts-default siblings, both recorded in canon's P-QTY
        # anchor probe. Before this class they matched no gate at all.
        "How many holds of Fuel Ore do you want to buy [12]?",
        "How many fighters would you like to deploy [100]?",
        # canon/engine/trace-ledger.md's own worked example of an app
        # keystroke answering a quantity question.
        "How many holds?",
        # "how much", the money-side wording of the same question.
        "How much are you willing to spend?",
        # Bank transfer -- named by DECISIONS §A.2, tagged HYPOTHESIS in
        # classify.py until a real bank capture lands.
        "How many credits do you wish to transfer?",
        "Transfer how many credits to the vault:",
        "Withdraw 5,000 credits:",
    ],
)
def test_money_prompt_claims_the_quantity_and_transfer_shapes(prompt):
    assert classify_screen("", prompt) == "money_prompt"


@pytest.mark.parametrize(
    "prompt",
    [
        # DELIBERATE NON-CLAIM 1. `Your offer [N]?` is unambiguously a
        # money prompt, and is unambiguously owned by a DIFFERENT
        # Accepted canon concept: canon/engine/auto-haggle.md
        # prescribes a built-in guarded rule that answers exactly this
        # prompt under its own parser and STOP-on-desync contract.
        # Claiming it here would silently overrule that concept, so it
        # is escalated instead of decided in code.
        "We'll buy them for 158 credits. Your offer [158]?",
        "Your offer [158]?",
        # DELIBERATE NON-CLAIM 2. The bare free-input solicitation. The
        # crawler matches this on purpose (a false "unsafe" there only
        # under-explores a graph); a false CLASS here would be this
        # module claiming to know a screen it does not.
        "Enter your selection:",
        "Enter your choice:",
        # Ordinary driven prompts -- pinned so a widening of the money
        # patterns cannot quietly eat one.
        "Command [TL=00753:0/0/0/850] (?=Help)? :",
        "Computer command [TL=00753:0/0/0/850] (?=Help)? :",
        # "how many" as ordinary informational prose, not a solicitation:
        # no terminal ? or :, so the line-anchored pattern declines.
        "You have no idea how many sectors are out there",
        # DELIBERATE NON-CLAIM 3 (WO-CLASSIFY-PASSWORD-LENGTH-UNKNOWN).
        # Quantity-shaped but about a password — post-C-02 residual that
        # used to halt via incidental money_prompt; now honest unknown.
        "How many characters in your password?",
    ],
)
def test_money_prompt_declines_what_it_deliberately_does_not_claim(prompt):
    assert classify_screen("", prompt) != "money_prompt"


def test_money_prompt_is_the_last_gate_so_no_driven_class_can_lose_a_screen():
    """Position, not just presence. Everything above `money_prompt` in
    `_GATE_ANCHORS` answers a screen some part of this app DRIVES --
    login.py's automaton, guardian.py's keepalive, protocol.py's `ensure`
    each act on a specific named class. Appended last, `money_prompt` can
    only ever take screens that were going to fall through to a content
    anchor or to `unknown`, and nothing drives either of those. Promote it
    up the list and this pin goes red."""
    assert _GATE_ANCHORS[-1][0] == "money_prompt"
    assert [name for name, _m in _GATE_ANCHORS].count("money_prompt") == 1


@pytest.mark.parametrize(
    "prompt, driven_class",
    [
        ("How many holds? Command [TL=00751:0/0/0/850]:", "main_command"),
        # login_password used to collide here via bare ``password`` on
        # "How many characters in your password?" — that false positive
        # is refused by WO-CLASSIFY-LOGIN-PASSWORD-NARROW; no remaining
        # money∩login_password shape is a real login gate, so the
        # driven-gate pin covers main_command + pause_key only.
        ("How many? Press any key to continue:", "pause_key"),
    ],
)
def test_a_money_shaped_line_never_outranks_a_gate_the_app_actually_drives(prompt, driven_class):
    """The behavioural half of the ordering pin, for the case where
    someone reorders the list and updates the index assertion above along
    with it. Every prompt here is deliberately AMBIGUOUS -- the money
    patterns genuinely match it (asserted, so the case cannot degrade into
    a tautology about a line money never claimed) AND so does a gate some
    consumer drives. The driven class must win, or the login automaton and
    the keepalive lose screens they are built to recognize."""
    assert _is_money_prompt(prompt) is True
    assert classify_screen("", prompt) == driven_class


def test_money_prompt_needs_a_whole_line_not_a_fragment_in_stale_scrollback():
    """`classify_screen`'s last resort, with no prompt line at all, scans
    gate anchors against the WHOLE text -- where a never-cleared pyte grid
    routinely still holds old output. The money patterns are line-anchored
    (`re.MULTILINE`) precisely so that fallback still requires a whole
    LINE to be a money question. A screen whose only money wording is
    embedded mid-sentence is not a money prompt."""
    embedded = "The clerk asks how many holds you want: consult the manual before deciding\nSome other line"
    assert classify_screen(embedded, "") != "money_prompt"
    whole_line = "-- Cargo Bay --\nHow many holds would you like to buy [0-20] ?\n"
    assert classify_screen(whole_line, "") == "money_prompt"


def test_never_auto_action_classes_is_exactly_the_ruled_set():
    """A closed vocabulary decision, pinned as one. DECISIONS §A.2 named
    `money_prompt` and nothing else; a class quietly joining or leaving
    this set changes what the App is permitted to automate, which is a
    canon change, not a refactor."""
    assert NEVER_AUTO_ACTION_CLASSES == frozenset({"money_prompt"})


def test_never_auto_action_only_names_classes_an_anchor_can_actually_return():
    """The pin fails OPEN if it is misspelled -- a class nothing ever
    returns forbids nothing at all, and every consumer keeps looking
    green. classify.py asserts this at import; asserting it again here is
    what makes the failure a named test rather than a collection error
    somebody re-runs and shrugs at."""
    returnable = {name for name, _m in _GATE_ANCHORS} | {name for name, _m in _CONTENT_ANCHORS}
    assert NEVER_AUTO_ACTION_CLASSES <= returnable


def test_money_prompt_only_ever_takes_screens_that_nothing_drives(monkeypatch):
    """The WO's load-bearing direction, proven as a differential rather
    than argued: adding this class must make the app do LESS.

    Classify the whole captured corpus twice -- once as shipped, once with
    the `money_prompt` anchor lifted back out -- and inspect every screen
    that moved. Two things must hold. The set must be NON-EMPTY, or the
    anchor is dead code and every other test here is theatre. And every
    moved screen's OLD class must be one that no consumer acts on, so the
    move can only ever have taken a screen out of reach, never put one
    within it."""
    # Every class any consumer branches on, with its site. Sourced by
    # reading the four `classify_screen` decision call sites, not guessed:
    #   login._decide          -- pause_key, login_name, ansi_prompt,
    #                             game_select, menu, char_create,
    #                             login_password, main_command (target)
    #   guardian._maybe_keepalive -- main_command (and ONLY that)
    #   protocol.ensure        -- main_command (the `cls == target` check)
    #   crawler.screen_state   -- _NON_MENU_GATE_CLASSES, a REFUSAL list
    driven = {
        "pause_key",
        "login_name",
        "login_password",
        "ansi_prompt",
        "game_select",
        "char_create",
        "menu",
        "main_command",
    }

    without_money = [entry for entry in _GATE_ANCHORS if entry[0] != "money_prompt"]
    assert len(without_money) == len(_GATE_ANCHORS) - 1

    corpus = {name: _fixture_with_prompt(name) for name in _EXPECTED_FIXTURE_CLASSES}
    after = {name: classify_screen(text, prompt) for name, (text, prompt) in corpus.items()}
    monkeypatch.setattr(classify_module, "_GATE_ANCHORS", without_money)
    before = {name: classify_screen(text, prompt) for name, (text, prompt) in corpus.items()}
    monkeypatch.undo()

    moved = {name: (before[name], after[name]) for name in corpus if before[name] != after[name]}
    assert moved, "money_prompt classified no captured screen at all -- dead anchor"
    for fixture, (before, after) in moved.items():
        assert after == "money_prompt", (fixture, before, after)
        assert before not in driven, (
            f"{fixture} moved a DRIVEN class {before!r} into money_prompt -- "
            "that is a consumer losing a screen it acts on, not a refusal being added"
        )


# -- nothing silently re-classed -----------------------------------------


# Frozen expectations for every captured screen in tests/fixtures/, both
# entry points. A generalized anchor that quietly re-classes an existing
# screen is a defect, not an improvement, and a per-screen assertion buried
# in its own test does not catch it across the whole corpus. Deliberately
# NOT exhaustive over the directory: a sibling lane adding a fixture should
# not be red-gated by this file. Add a row when you add a fixture.
#
# `classify()` (whole text, gate anchors scanned everywhere) legitimately
# disagrees with `classify_screen()` (gate anchors scoped to the live
# prompt) on three of these -- that divergence is the documented reason
# classify_screen is the canonical live path, and it is pinned here rather
# than left to be rediscovered.
_EXPECTED_FIXTURE_CLASSES = {
    # fixture: (classify(text), classify_screen(text, prompt))
    "been_on_today_reenter_screen.txt": ("unknown", "unknown"),
    "cim_port_report.txt": ("cim_report", "cim_report"),
    "game_select_menu.mojibake-before.txt": ("game_select", "game_select"),
    "game_select_menu.txt": ("game_select", "game_select"),
    "game_select_menu_banner_variant.txt": ("game_select", "game_select"),
    "game_select_menu_banner_anet_boxed_title.txt": ("game_select", "game_select"),
    "game_select_menu_banner_anet_live_chrome.txt": ("game_select", "game_select"),
    "game_select_menu_boxed_variant.txt": ("game_select", "game_select"),
    "opening_screen.txt": ("login_name", "login_name"),
    "pause_key_prompt.txt": ("pause_key", "pause_key"),
    "port_commerce_report_gorram_primus.txt": ("main_command", "main_command"),
    "port_trade_screen.txt": ("main_command", "main_command"),
    # stale "[Pause]" above a live menu prompt -- the naive whole-text bug.
    "rules_and_menu_screen.txt": ("pause_key", "menu"),
    "stale_bracket_false_positive.txt": ("unknown", "unknown"),
    # The one screen this WO moves (was ("main_command", "unknown")). Its
    # live prompt is the purchase question, so the `money_prompt` gate
    # answers -- DECISIONS §A.2, never-auto-action. The exclusive block
    # above it is still recognized and still names the screen on the
    # no-prompt path; see
    # test_real_captured_stardock_cargo_hold_quote_classifies for both
    # halves. classify()'s whole-text scan still finds the STALE command
    # echo on line 1 and answers main_command -- unchanged, and the same
    # naive-path bug as rules_and_menu_screen above.
    "stardock_cargo_hold_quote.txt": ("main_command", "money_prompt"),
    "stardock_cargo_hold_quote_at_max.txt": ("main_command", "main_command"),
    "stardock_equipment_listing.txt": ("main_command", "main_command"),
    "stardock_shipyard_listing.txt": ("main_command", "main_command"),
    "warp_confirm_prompt.txt": ("warp_confirm", "warp_confirm"),
}


def test_every_captured_fixture_keeps_its_expected_classification():
    actual = {}
    for name in _EXPECTED_FIXTURE_CLASSES:
        text, prompt = _fixture_with_prompt(name)
        actual[name] = (classify(text), classify_screen(text, prompt))
    assert actual == _EXPECTED_FIXTURE_CLASSES


# -- WO-CLEANPREEMPT (secret sub-diff): is_probable_secret_prompt() -- the
# `tw attach` interactive keystroke path's own FAIL-SAFE secret detection,
# deliberately separate from (and broader than) the `login_password` gate
# anchor used by classify_screen()/login.py above. --------------------


def test_is_probable_secret_prompt_matches_password():
    assert is_probable_secret_prompt("Password?") is True


def test_is_probable_secret_prompt_matches_pin():
    assert is_probable_secret_prompt("Enter PIN:") is True
    assert is_probable_secret_prompt("PIN number:") is True


def test_is_probable_secret_prompt_matches_passcode_variants():
    assert is_probable_secret_prompt("Enter your passcode:") is True
    assert is_probable_secret_prompt("Enter your pass code:") is True


def test_is_probable_secret_prompt_matches_access_code():
    assert is_probable_secret_prompt("Access code:") is True


def test_is_probable_secret_prompt_matches_a_bare_code_prompt():
    assert is_probable_secret_prompt("Enter code:") is True


def test_is_probable_secret_prompt_matches_verify():
    assert is_probable_secret_prompt("Verify your identity:") is True


def test_is_probable_secret_prompt_matches_secret():
    assert is_probable_secret_prompt("Enter the secret word:") is True


def test_is_probable_secret_prompt_is_case_insensitive():
    assert is_probable_secret_prompt("PASSWORD?") is True
    assert is_probable_secret_prompt("pin:") is True


def test_is_probable_secret_prompt_word_boundary_avoids_pin_substring_false_positives():
    # "pin" is word-boundaried specifically so it doesn't fire on
    # ordinary words that merely CONTAIN it.
    assert is_probable_secret_prompt("Spin the wheel!") is False
    assert is_probable_secret_prompt("Pinpoint your location:") is False


def test_is_probable_secret_prompt_false_for_ordinary_command_prompt():
    assert is_probable_secret_prompt("Command [TL=00:00:00]:[1234] (?=Help)? :") is False


def test_is_probable_secret_prompt_false_for_empty_or_missing_prompt():
    assert is_probable_secret_prompt("") is False
    assert is_probable_secret_prompt(None) is False


def test_is_probable_secret_prompt_documented_residual_no_keyword_at_all():
    """The documented KNOWN RESIDUAL, pinned down rather than left
    implicit: a secret-entry prompt phrased with none of this
    predicate's keywords has no signal it can key on -- this is a
    best-effort heuristic over literal English text, not game-shape
    understanding. This test exists so a future reader can see the gap
    is real and intentional, not an oversight."""
    assert is_probable_secret_prompt("Speak, friend, and enter:") is False


# ---------------------------------------------------------------------------
# WO-XENO-GAME-SELECT -- the square-bracket door (Exiled / twgs.exiled.org).
#
# Max's actual block: this screen classified `unknown`, so `_decide` returned
# None and `tw ensure --profile xeno` stalled at
# LoginStalled(automaton_stuck, unknown). The letter path was already correct;
# only the classification was missing.
# ---------------------------------------------------------------------------

EXILED_FIXTURE = "game_select_menu_exiled_square_bracket.txt"


def test_exiled_square_bracket_menu_is_game_select():
    """Accept #1 -- the live capture must resolve to the EXISTING class."""
    text, prompt = _fixture_with_prompt(EXILED_FIXTURE)
    assert classify_screen(text, prompt) == "game_select"


def test_exiled_square_bracket_menu_is_game_select_via_classify_too():
    """Both public APIs. `classify()` has no separate prompt line, so a
    detector wired into only one of them is the standing parity trap here."""
    text = _load_fixture(EXILED_FIXTURE)
    assert classify("\n".join(text.splitlines())) == "game_select"


def test_exiled_fixture_still_carries_the_two_signals_it_is_teaching():
    """Guards the fixture itself: a later redaction/reflow that removed the
    bracket rows or the timed-out suffix would leave the positive tests
    passing for the wrong reason (or silently testing nothing)."""
    text = _load_fixture(EXILED_FIXTURE)
    rows = [l for l in text.splitlines() if re.match(r"^\s+\[[A-Za-z0-9]\]\s+\S+", l)]
    assert len(rows) >= 2, "fixture lost its bracketed game rows"
    assert re.search(r":\s*Timed\s+out\b", text.splitlines()[-1], re.I)


def test_exiled_fixture_carries_no_operator_contact():
    """Public repo: the live capture's sysop e-mail is redacted."""
    text = _load_fixture(EXILED_FIXTURE)
    found = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    assert found == ["sysop@example.org"], found


def test_stale_exiled_rows_under_a_live_command_prompt_are_not_game_select():
    """Accept #2 -- the stale-scrollback negative.

    The whole menu is still in scrollback, but the human has since reached a
    live game prompt. Classifying this `game_select` would make ensure send a
    game letter into a live Command prompt.
    """
    stale = _load_fixture(EXILED_FIXTURE).rstrip("\n")
    live_prompt = "Command [TL=00:00:00]:[10] (?=Help)? :"
    text = stale + "\n" + live_prompt
    assert classify_screen(text, live_prompt) != "game_select"
    assert classify(text) != "game_select"


def test_timed_out_chrome_without_game_rows_is_not_game_select():
    """Signal 1 alone is far too generic -- any host chrome ending in
    `:Timed out` would otherwise be read as a game door."""
    text = "Connecting to the server...\nPlease wait.\n[ Some Host ]:Timed out..."
    assert classify_screen(text, text.splitlines()[-1]) != "game_select"


def test_game_rows_without_the_timed_out_prompt_are_not_game_select():
    """Signal 2 alone: bracket rows under an unrelated live prompt."""
    text = " [A] Alpha Quadrant Invasion\n [B] Default Stock Game\nEnter your choice:"
    assert classify_screen(text, "Enter your choice:") != "game_select"


def test_the_prompt_line_cannot_satisfy_its_own_body_requirement():
    """The Exiled prompt itself carries `[A][B][C][D]...` at column 0. The
    detector's leading-indent requirement plus above-prompt scoping is what
    stops it counting itself -- without both, a bare prompt line with no menu
    would classify as a game door."""
    lone = "[ Exiled TW2002 ]:[A][B][C][D][E][X][Z][#]:Timed out..."
    assert classify_screen(lone, lone) != "game_select"


@pytest.mark.parametrize(
    "name",
    [
        "game_select_menu.txt",
        "game_select_menu_boxed_variant.txt",
        "game_select_menu_banner_variant.txt",
        "game_select_menu_banner_anet_boxed_title.txt",
        "game_select_menu_banner_anet_live_chrome.txt",
    ],
)
def test_existing_game_select_shapes_are_unaffected(name):
    """Accept #3 -- no collision. The three previously-taught shapes must
    still classify exactly as they did before this detector existed."""
    text, prompt = _fixture_with_prompt(name)
    assert classify_screen(text, prompt) == "game_select"
