"""Login Automaton tests (DESIGN-v2 B1/B3/B4) — no network.

FakeLoginSession drives an ORDERED script of (screen, expected-response)
steps, so tests assert the exact real-flow sequence captured live
against twgs.test.example (see login.py's module docstring) without
depending on literal password text (which is CSPRNG-random for a fresh
NEW-registration and must not be predictable/hardcoded in a test)."""

import random

import pytest

from twclient.login import LoginError, register_with_name_bank, run_login
from twclient.settle import wait_for_settle

from .conftest import FAKE_HOST, FAKE_PORT


class FakeLoginSession:
    """Walks an ordered list of steps: `{"screen": text, "expect": fn}`.
    On send(), validates `expect(text, secret)` (if given) against what
    the automaton sent, records it, and advances to the next step's
    screen. Once the script is exhausted, stays on the final screen
    (models a settled target screen that doesn't change further).

    The advance is DEFERRED to the next `sleep()` call rather than
    applied synchronously inside `send()` -- matching the more realistic
    async-response convention `test_settle.py`'s `StagedSession` already
    uses (a real Session's response bytes arrive later, over a separate
    reader path, never instantly at send()-time). This is load-bearing
    for `settle.send_and_confirm`'s idle-detection path (used by
    run_login for a step with no explicit wait_hint, TW-02):
    `wait_for_settle` can only see an "idle" settle if `session.rx_count`
    genuinely increases AFTER its own polling starts -- a synchronous
    same-call bump (the old convention) would already be reflected in
    the `start_rx_count` it captures at its own start, so it would never
    observe a NEW arrival and would spin to "timeout" every time."""

    def __init__(self, steps):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._steps = steps
        self._i = 0
        self.sent = []  # [(text, secret), ...]
        self._pending_advance = False

    # -- settle-detection protocol surface (matches Session) -------------
    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self._pending_advance:
            self._pending_advance = False
            if self._i < len(self._steps) - 1:
                self._i += 1
            self.rx_count += 1
            self.last_rx = self.t

    def render(self):
        return self._steps[self._i]["screen"].split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._steps[self._i]["screen"]

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350):
        result = wait_for_settle(self, wait_prompt=wait_prompt, timeout_s=timeout, debounce_ms=debounce_ms)
        # A step marked auto_advance models unsolicited server push that
        # arrives without the automaton sending anything (e.g. a
        # RETURNING welcome banner immediately followed by the sector
        # display) -- advance once the automaton has polled it, rather
        # than requiring a send() to move the script forward.
        step = self._steps[self._i]
        if step.get("auto_advance") and self._i < len(self._steps) - 1:
            self._i += 1
            self.rx_count += 1
            self.last_rx = self.t
        return result

    # -- driving -----------------------------------------------------------
    def send(self, text, enter=True, secret=False):
        self.sent.append((text, secret))
        step = self._steps[self._i]
        if step.get("expect") is not None:
            assert step["expect"](text, secret), f"step {self._i}: unexpected send {text!r} secret={secret!r}"
        self._pending_advance = True


class FakeProfile:
    def __init__(self, name="default", host=FAKE_HOST, port=FAKE_PORT, game_letter="F", handle="AEGIS",
                 ship_name="Vantage", planet_name="Anchorage", server=None, allow_register=True):
        self.name = name
        self.host = host
        self.port = port
        self.game_letter = game_letter
        self.handle = handle
        self.ship_name = ship_name
        self.planet_name = planet_name
        self.server = server  # optional catalog key (WO-MS-1/WO-MS-2); None = today's bare host/port shape
        # WO-MS-4: defaults True so every pre-existing NEW-registration
        # test in this file (none of which pass this kwarg) keeps
        # exercising the registration branch unmodified; the hard-gate
        # guard tests construct FakeProfile(allow_register=False)
        # explicitly to prove the refusal.
        self.allow_register = allow_register
        self.handle_explicit = handle is not None
        self.ship_name_explicit = ship_name is not None
        self.planet_name_explicit = planet_name is not None


def _is(expected):
    return lambda text, secret: text == expected and secret is False


def _is_secret(expected):
    return lambda text, secret: text == expected and secret is True


def _any(text, secret):
    return True


# -- NEW registration happy path -----------------------------------------

def _new_registration_steps(profile, password_screens=1):
    """Build the ordered screen script for a full NEW-registration run,
    matching the real captured flow. `password_screens` lets a test
    inject extra "didn't match" retry rounds before the real screen
    moves on (all sends in that run must be secret + identical, but we
    don't know the literal value ahead of time, so `expect` only checks
    secret=True and records the value via a closure)."""
    seen_password = {}

    def _expect_password_consistent(text, secret):
        if not secret:
            return False
        if "value" not in seen_password:
            seen_password["value"] = text
        return text == seen_password["value"]

    steps = [
        {"screen": "Please enter your name (ENTER for none):", "expect": _is("")},
        {"screen": "<F> Bob the Builder\nSelect a game :", "expect": _is(profile.game_letter)},
        {"screen": "T - Play Trade Wars 2002\nI - Introduction & Help\nEnter your choice:", "expect": _is("T")},
        {"screen": "What is your name?", "expect": _is(profile.handle)},
        {"screen": "Use ANSI graphics?", "expect": _is("Y")},
        {"screen": "Show today's log? (Y/N) [N]", "expect": _is("N")},
        {
            "screen": "You were not found in the player database.\nWould you like to start a new character in this game?  (Type Y or N)",
            "expect": _is("Y"),
        },
    ]
    for _ in range(password_screens):
        steps.append({"screen": "Please enter a password for this game account.\nPassword?", "expect": _expect_password_consistent})
        steps.append({"screen": "Repeat password to verify.\nPassword?", "expect": _expect_password_consistent})
    steps += [
        {
            "screen": f"Do you wish to make up a new Alias for your Trader Name,\nor would you rather use your BBS name of {profile.handle}?\nUse (N)ew Name or (B)BS Name [B] ?",
            "expect": _is("B"),
        },
        {"screen": "What do you want to name your ship? (30 letters)", "expect": _is(profile.ship_name)},
        {"screen": f"{profile.ship_name} is what you want?", "expect": _is("Y")},
        # The real captured bottom line here is an input-box marker, not
        # the "name your home planet" wording (which sits one line up).
        {
            "screen": "What do you want to name your home planet? (Class K-BE, Desert wasteland)\n[---------------------------------------]",
            "expect": _is(profile.planet_name),
        },
        {"screen": "Planet command (?=help) [D]", "expect": _is("Q")},
        {"screen": "Command [TL=00:00:00]:[24146] (?=Help)? :", "expect": None},
    ]
    return steps, seen_password


def test_new_registration_happy_path_reaches_main_command():
    profile = FakeProfile()
    saved = {}
    steps, seen_password = _new_registration_steps(profile, password_screens=1)
    session = FakeLoginSession(steps)

    cls, taken = run_login(
        session,
        profile,
        get_password=lambda name: saved.get(name),
        save_password=lambda name, pw: saved.__setitem__(name, pw),
        target="main_command",
    )

    assert cls == "main_command"
    # A password was generated, sent as secret, and saved BEFORE the
    # confirm round (recoverability -- DESIGN-v2 D9/the credential-mismatch fix).
    assert saved["default"] == seen_password["value"]
    assert len(seen_password["value"]) == 8
    assert seen_password["value"].isalnum()
    # Every secret-marked send used the identical value.
    secret_sends = [t for t, s in session.sent if s]
    assert secret_sends == [seen_password["value"]] * 2


def test_new_registration_survives_password_mismatch_retries():
    """The observed live flake: 'Passwords didn't match. Try again.'
    The automaton must resend the SAME generated value each time, not
    generate a new one, and not give up before _MAX_PASSWORD_RETRIES."""
    profile = FakeProfile()
    saved = {}
    # 3 create/repeat rounds = 6 password screens, simulating two
    # real-world mismatch bounces before success.
    steps, seen_password = _new_registration_steps(profile, password_screens=3)
    session = FakeLoginSession(steps)

    cls, taken = run_login(
        session, profile, get_password=lambda n: saved.get(n), save_password=lambda n, pw: saved.__setitem__(n, pw)
    )
    assert cls == "main_command"
    secret_sends = [t for t, s in session.sent if s]
    assert len(secret_sends) == 6
    assert len(set(secret_sends)) == 1  # always the identical value


def test_password_saved_before_confirm_round_even_if_run_later_fails():
    """Recoverability check: the credential is durably saved the moment
    it's generated, not after the whole flow completes."""
    profile = FakeProfile()
    saved = {}
    steps = [
        {"screen": "Please enter your name (ENTER for none):", "expect": _is("")},
        {"screen": "<F> Bob the Builder\nSelect a game :", "expect": _is(profile.game_letter)},
        {"screen": "T - Play Trade Wars 2002\nI - Introduction & Help\nEnter your choice:", "expect": _is("T")},
        {"screen": "What is your name?", "expect": _is(profile.handle)},
        {"screen": "Use ANSI graphics?", "expect": _is("Y")},
        {"screen": "Show today's log? (Y/N) [N]", "expect": _is("N")},
        {"screen": "start a new character?  (Type Y or N)", "expect": _is("Y")},
        {"screen": "Password?", "expect": _any},
        # Deliberately never advances past this second "Password?" (the
        # script runs out here), so the automaton keeps resending the
        # identical password until the retry cap fires -- proving the
        # save already happened well before that point.
        {"screen": "Password?", "expect": _any},
    ]
    session = FakeLoginSession(steps)
    with pytest.raises(LoginError, match="password_retries_exhausted"):
        run_login(session, profile, get_password=lambda n: saved.get(n), save_password=lambda n, pw: saved.__setitem__(n, pw))
    assert "default" in saved
    assert len(saved["default"]) == 8


# -- game_select classification variants -----------------------------------
#
# login.py's `_decide()` already sends `profile.game_letter` on ANY
# `game_select` classification -- these prove classify.py's second,
# structurally different boxed-menu TWGS variant (found live against a
# real TWGS server, no "select a game" text anywhere on screen) reaches
# that same existing handler, with zero changes needed in this module.

def test_boxed_game_select_menu_variant_sends_configured_game_letter():
    profile = FakeProfile()
    boxed_game_select_screen = (
        "twgs.test.example\n"
        "Game\n"
        "<A> Vanilla TW2002: Mostly default settings\n"
        "<#> Players Online\n"
        "<!> View Game Descriptions\n"
        "<Q> Quit\n"
        "Selection (? for menu):"
    )
    steps = [
        {"screen": boxed_game_select_screen, "expect": _is(profile.game_letter)},
        {"screen": "Command [TL=00:00:00]:[1] (?=Help)? :", "expect": None},
    ]
    session = FakeLoginSession(steps)
    cls, _ = run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert cls == "main_command"
    assert session.sent == [(profile.game_letter, False)]


def test_boxed_game_select_lookalike_without_game_header_does_not_send_letter():
    """Precision guard, applied through the automaton: a DIFFERENT menu
    sharing the exact same bracket style and 'Selection (? for menu):'
    prompt, but with no boxed 'Game' header, must NOT be misclassified as
    game_select -- that would send the configured game LETTER as a
    keystroke on the wrong screen. It must fail loud (automaton_stuck)
    rather than guess, same as any other unrecognized menu."""
    profile = FakeProfile()
    lookalike_menu_screen = (
        "Main Menu\n"
        "<A> Page News\n"
        "<B> Read Mail\n"
        "<Q> Quit\n"
        "Selection (? for menu):"
    )
    steps = [{"screen": lookalike_menu_screen, "expect": lambda text, secret: False}]
    session = FakeLoginSession(steps)
    with pytest.raises(LoginError, match="automaton_stuck"):
        run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert session.sent == []


def test_banner_game_select_menu_variant_sends_configured_game_letter():
    """A THIRD, non-boxed TWGS game-select shape (no box-drawing at all),
    distinguished only by the TWGS server startup banner above the
    bracket list -- proves `_is_twgs_server_banner_game_select_menu`
    (classify.py) reaches login.py's existing `game_select` handler too,
    with zero changes needed in this module."""
    profile = FakeProfile()
    banner_game_select_screen = (
        "TradeWars Game Server\n"
        "TWGS v2.20b\n"
        "Server registered to twgs.test.example\n"
        "<A> Sample Game One\n"
        "<#> Players Online\n"
        "<!> View game descriptions\n"
        "<Q> Quit\n"
        "Selection (? for menu):"
    )
    steps = [
        {"screen": banner_game_select_screen, "expect": _is(profile.game_letter)},
        {"screen": "Command [TL=00:00:00]:[1] (?=Help)? :", "expect": None},
    ]
    session = FakeLoginSession(steps)
    cls, _ = run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert cls == "main_command"
    assert session.sent == [(profile.game_letter, False)]


def test_banner_game_select_lookalike_without_the_twgs_banner_does_not_send_letter():
    """Precision guard, applied through the automaton: a DIFFERENT TWGS
    lobby menu sharing the exact same bracket style and
    'Selection (? for menu):' prompt, but with no TWGS server startup
    banner, must NOT be misclassified as game_select -- that would send
    the configured game LETTER as a keystroke on the wrong screen. It
    must fail loud (automaton_stuck) rather than guess, same as any
    other unrecognized menu."""
    profile = FakeProfile()
    lookalike_menu_screen = (
        "Welcome to a different TWGS lobby\n"
        "<A> Sample Game One\n"
        "<#> Players Online\n"
        "<Q> Quit\n"
        "Selection (? for menu):"
    )
    steps = [{"screen": lookalike_menu_screen, "expect": lambda text, secret: False}]
    session = FakeLoginSession(steps)
    with pytest.raises(LoginError, match="automaton_stuck"):
        run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert session.sent == []


# -- stale-scrollback precision guards, applied through the automaton
# (cipher adversarial review, 2026-07-20) -----------------------------------
#
# Both classify.py variant checks originally had no tie between their
# header/banner signal and the CURRENT prompt -- a stale header/banner
# left over from an EARLIER game-select screen could combine with a
# LATER, unrelated menu sharing the same generic prompt and still
# misfire game_select, which here would mean sending the configured
# game LETTER as a keystroke on the WRONG screen. Driven end-to-end
# through the automaton (not just classify.py directly) so this can't
# regress silently even if some future change only touches login.py's
# own dispatch table.


def test_stale_boxed_door_select_bleeding_into_module_entry_menu_answers_the_real_current_menu_not_the_stale_letter():
    """The stale boxed door-select box must NOT be treated as game_select
    (that would send the configured game LETTER, wrong for this screen)
    -- but the screen's REAL current content genuinely IS the
    module-entry menu ("T - Play Trade Wars 2002" is really the CURRENT
    prompt's own menu here, not stale), so the correct, already-existing
    `_MODULE_ENTRY_MENU_RE` handler correctly answers "T". The
    load-bearing assertion is what it does NOT send: never the
    configured game letter ("F")."""
    profile = FakeProfile()
    stale_boxed_then_module_entry = (
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
    steps = [
        {"screen": stale_boxed_then_module_entry, "expect": _is("T")},
        {"screen": "Command [TL=00:00:00]:[1] (?=Help)? :", "expect": None},
    ]
    session = FakeLoginSession(steps)
    cls, _ = run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert cls == "main_command"
    assert session.sent == [("T", False)]
    assert profile.game_letter not in [t for t, _s in session.sent]


def test_stale_twgs_banner_bleeding_into_unrelated_utility_menu_fails_loud_not_a_blind_letter_send():
    profile = FakeProfile()
    stale_banner_then_utility_menu = (
        "TradeWars Game Server\n"
        "TWGS v2.20b\n"
        "Server registered to twgs.test.example\n"
        "\n"
        "\n"
        "<A> Read System Notices\n"
        "<B> Change Terminal Options\n"
        "Selection (? for menu):"
    )
    steps = [{"screen": stale_banner_then_utility_menu, "expect": lambda text, secret: False}]
    session = FakeLoginSession(steps)
    with pytest.raises(LoginError, match="automaton_stuck"):
        run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert session.sent == []


# -- ROUND 2 stale-scrollback hardening (cipher re-attack, same day) -------
#
# The stale-scrollback guards above prove ADJACENCY -- the header/banner and
# the qualifying game-select body sit in the same range -- but never prove
# that body is the LAST menu content before the prompt. A STALE, never-
# cleared copy of a FULL game-select body (markers + "<Q> Quit" included)
# can itself sit ahead of a genuinely CURRENT, actually-different bracket-
# style "Utility Menu" -- a shape the dash-only exclusion above never
# covers. Before the round-2 fix (classify.py's
# `_range_has_no_menu_after_game_select_markers`), this misclassified as
# game_select and sent the configured game LETTER onto the real, live
# Utility Menu. Driven end-to-end through the automaton, same rationale as
# the round-1 guards above: this can't regress silently even if a future
# change only touches login.py's own dispatch table.


def test_stale_game_select_body_bleeding_into_a_live_utility_menu_fails_loud_not_a_blind_letter_send():
    profile = FakeProfile()
    stale_game_select_body_then_utility_menu = (
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
    steps = [{"screen": stale_game_select_body_then_utility_menu, "expect": lambda text, secret: False}]
    session = FakeLoginSession(steps)
    with pytest.raises(LoginError, match="automaton_stuck"):
        run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert session.sent == []


# -- RETURNING branch -----------------------------------------------------

def test_returning_login_uses_saved_password_and_skips_registration():
    profile = FakeProfile()
    saved = {"default": "sAvEd123"}
    steps = [
        {"screen": "Please enter your name (ENTER for none):", "expect": _is("")},
        {"screen": "<F> Bob the Builder\nSelect a game :", "expect": _is(profile.game_letter)},
        {"screen": "T - Play Trade Wars 2002\nI - Introduction & Help\nEnter your choice:", "expect": _is("T")},
        {"screen": "What is your name?", "expect": _is(profile.handle)},
        {"screen": "Use ANSI graphics?", "expect": _is("Y")},
        {"screen": "Show today's log? (Y/N) [N]", "expect": _is("N")},
        # No char_create prompt at all -- the handle WAS found.
        {"screen": "Password?", "expect": _is_secret("sAvEd123")},
        {"screen": f"Hello {profile.handle}, welcome to:", "expect": None, "auto_advance": True},
        {"screen": "Command [TL=00:00:00]:[24146] (?=Help)? :", "expect": None},
    ]
    session = FakeLoginSession(steps)
    save_calls = []
    cls, taken = run_login(
        session, profile, get_password=lambda n: saved.get(n), save_password=lambda n, pw: save_calls.append((n, pw))
    )
    assert cls == "main_command"
    # Never re-saves an already-known-good credential.
    assert save_calls == []
    secret_sends = [t for t, s in session.sent if s]
    assert secret_sends == ["sAvEd123"]


def test_returning_login_without_saved_password_raises_rather_than_guessing():
    profile = FakeProfile()
    steps = [
        {"screen": "What is your name?", "expect": _is(profile.handle)},
        {"screen": "Use ANSI graphics?", "expect": _is("Y")},
        {"screen": "Password?", "expect": None},
    ]
    session = FakeLoginSession(steps)
    with pytest.raises(LoginError, match="returning_no_saved_password"):
        run_login(session, profile, get_password=lambda n: None, save_password=lambda n, pw: None)


# -- D7 nuisances, interleaved at arbitrary points -------------------------

def test_pause_key_interstitial_is_dismissed_with_blank_enter():
    profile = FakeProfile()
    steps = [
        {"screen": "  [Pause]", "expect": _is("")},
        {"screen": "What is your name?", "expect": _is(profile.handle)},
        {"screen": "Command [TL=00:00:00]:[1] (?=Help)? :", "expect": None},
    ]
    session = FakeLoginSession(steps)
    cls, _ = run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert cls == "main_command"


def test_inactivity_warning_gets_a_keepalive_keystroke_not_a_crash():
    profile = FakeProfile()
    steps = [
        {"screen": "What is your name?", "expect": _is(profile.handle)},
        {"screen": "INACTIVITY WARNING:\n  Your session will be terminated in Sixty seconds.", "expect": _is("")},
        {"screen": "Command [TL=00:00:00]:[1] (?=Help)? :", "expect": None},
    ]
    session = FakeLoginSession(steps)
    cls, _ = run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert cls == "main_command"


def test_show_todays_log_prompt_declined():
    profile = FakeProfile()
    steps = [
        {"screen": "What is your name?", "expect": _is(profile.handle)},
        {"screen": "Show today's log? (Y/N) [N]", "expect": _is("N")},
        {"screen": "Command [TL=00:00:00]:[1] (?=Help)? :", "expect": None},
    ]
    session = FakeLoginSession(steps)
    cls, _ = run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert cls == "main_command"


# -- B4 idempotence / failure modes ----------------------------------------

def test_already_at_target_is_a_zero_step_noop():
    profile = FakeProfile()
    steps = [{"screen": "Command [TL=00:00:00]:[1] (?=Help)? :", "expect": None}]
    session = FakeLoginSession(steps)
    cls, taken = run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert cls == "main_command"
    assert taken == 0
    assert session.sent == []  # never sent a single keystroke


def test_unrecognized_screen_that_never_changes_raises_stuck_not_infinite_loop():
    profile = FakeProfile()
    steps = [{"screen": "This is a screen shape nothing in the automaton recognizes.", "expect": None}]
    session = FakeLoginSession(steps)
    with pytest.raises(LoginError, match="automaton_stuck"):
        run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)


def test_password_retries_exhausted_raises_rather_than_looping_forever():
    profile = FakeProfile()
    steps, _ = _new_registration_steps(profile, password_screens=10)
    session = FakeLoginSession(steps)
    saved = {}
    with pytest.raises(LoginError, match="password_retries_exhausted"):
        run_login(session, profile, get_password=lambda n: saved.get(n), save_password=lambda n, pw: saved.__setitem__(n, pw))


# -- stale-scrollback regression (caught live on this build's own cold
# auto-register proof against twgs.test.example) -------------------------

def test_ship_naming_survives_stale_scrollback_from_prior_prompts():
    """Live bug: pyte doesn't clear cells the server never overwrites, so
    'Use (N)ew Name or (B)BS Name' and 'What do you want to name your
    ship?' both linger a few lines above LATER prompts within the same
    25-row screen. A full-TEXT scan for these sub-steps re-fired on the
    stale lines: 'B' got resent as the ship name, and the ship name got
    resent at the confirm prompt (which the server read as declining,
    looping forever). The fix scopes these matches to the current PROMPT
    LINE only, same discipline as classify.py's gate anchors -- this
    reproduces the exact multi-line stale-scrollback shape observed live
    to prove it now resolves instead of looping."""
    profile = FakeProfile()
    steps = [
        # Screen shows the ALREADY-ANSWERED "(N)ew Name or (B)BS Name"
        # prompt still visible above the new ship-naming prompt -- must
        # send the ship name, not "B" again.
        {
            "screen": (
                "Do you wish to make up a new Alias for your Trader Name,\n"
                "or would you rather use your BBS name of AEGIS?\n"
                "Use (N)ew Name or (B)BS Name [B] ? B\n"
                "Your ship is being initialized.\n"
                "You must now christen your new Bofors Merchant Cruiser\n"
                "What do you want to name your ship? (30 letters)"
            ),
            "expect": _is(profile.ship_name),
        },
        # Screen shows the ALREADY-ANSWERED ship-name prompt still
        # visible above the confirm prompt -- must send "Y", not the
        # ship name again.
        {
            "screen": (
                "What do you want to name your ship? (30 letters)\n"
                f"{profile.ship_name}\n"
                f"{profile.ship_name} is what you want?"
            ),
            "expect": _is("Y"),
        },
        {"screen": "Command [TL=00:00:00]:[1] (?=Help)? :", "expect": None},
    ]
    session = FakeLoginSession(steps)
    cls, taken = run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert cls == "main_command"
    assert session.sent == [(profile.ship_name, False), ("Y", False)]


def test_planet_name_box_prompt_not_confused_by_stale_planet_wording():
    """Companion regression for the planet-name step, which uses a
    compound (box-marker prompt shape + 'name your home planet' in the
    wider text) match specifically because its real prompt line is a
    generic input-box marker, not planet-naming wording."""
    profile = FakeProfile()
    steps = [
        {
            "screen": (
                "What do you want to name your home planet? (Class K-BE, Desert wasteland)\n"
                "[---------------------------------------]"
            ),
            "expect": _is(profile.planet_name),
        },
        {"screen": "Planet command (?=help) [D]", "expect": _is("Q")},
        {"screen": "Command [TL=00:00:00]:[1] (?=Help)? :", "expect": None},
    ]
    session = FakeLoginSession(steps)
    cls, taken = run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert cls == "main_command"
    assert session.sent == [(profile.planet_name, False), ("Q", False)]


# -- TW-02: send/settle race, routed through settle.send_and_confirm --------
#
# _decide() never supplies an explicit wait_hint (every branch's third
# tuple element is None), so run_login always exercises send_and_confirm's
# confirm_prompt=None (idle+stability-recheck) fallback -- these two fakes
# model that path's own failure/recovery shapes directly, distinct from
# FakeLoginSession's simpler ordered-script convention.


class _NeverSettlesSession:
    """A prompt that keeps changing forever on a fixed fake-clock cadence
    (faster than the debounce window) -- models a persistently-glitching
    screen that never genuinely settles, no matter how many retry rounds
    run_login attempts. The PROMPT LINE itself never changes (still
    "What is your name?"), only trailing content above it, so
    classify_screen keeps recognizing the same login_name gate anchor
    every round."""

    def __init__(self, change_every_s=0.1):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._change_every_s = change_every_s
        self._next_change_at = change_every_s
        self._tick = 0
        self.sent = []

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        while self.t >= self._next_change_at:
            self._tick += 1
            self._next_change_at += self._change_every_s
            self.rx_count += 1
            self.last_rx = self.t

    def render(self):
        return f"(frame {self._tick})\nWhat is your name?".split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else f"(frame {self._tick})\nWhat is your name?"

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, secret))


def test_run_login_persistently_unconfirmed_send_raises_after_stagnation_cap():
    """TW-02: a screen that never genuinely settles must not retry
    forever -- a persistently failing confirm is folded into the SAME
    stagnant-round budget an unrecognized screen already uses, so it
    eventually raises a clean, distinctly-labeled LoginError instead of
    looping (the mid-animation/clean-halt shape, applied to login)."""
    profile = FakeProfile()
    session = _NeverSettlesSession()
    with pytest.raises(LoginError, match="automaton_send_unconfirmed"):
        run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)


class _RecoversAfterOneGlitchSession:
    """The FIRST send()'s confirm never settles within the per-step
    budget (a transient settle-race); a SECOND, identical retry send()
    (run_login re-sends the same input once a failed confirm loops back
    to the same classification) settles cleanly. Proves a transient
    settle-race gets a genuine second chance via the existing
    stagnant-round retry budget rather than aborting on the first failed
    confirm (the slow-settle/no-false-halt shape, applied to login)."""

    def __init__(self, glitch_text, final_text):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._text = glitch_text
        self._final_text = final_text
        self._glitching = False
        self._next_tick = None
        self._settle_at = None
        self.sent = []

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self._glitching:
            while self.t >= self._next_tick:
                self.rx_count += 1
                self.last_rx = self.t
                self._next_tick += 0.1
        elif self._settle_at is not None and self.t >= self._settle_at:
            self._text = self._final_text
            self.rx_count += 1
            self.last_rx = self.t
            self._settle_at = None

    def render(self):
        return self._text.split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._text

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, secret))
        if len(self.sent) == 1:
            self._glitching = True
            self._next_tick = self.t + 0.1
        else:
            self._glitching = False
            self._settle_at = self.t + 0.05


def test_run_login_recovers_from_a_transient_unconfirmed_send_via_retry():
    """TW-02 companion: the FIRST attempt's confirm never settles within
    budget, but the automaton's existing retry path (folding a failed
    confirm into the stagnant-round budget rather than aborting
    outright) gives it a genuine second chance -- the retried send
    settles cleanly and login proceeds to completion, proving this
    isn't a false halt on a merely-slow send."""
    profile = FakeProfile()
    session = _RecoversAfterOneGlitchSession(
        glitch_text="What is your name?", final_text="Command [TL=00:00:00]:[1] (?=Help)? :"
    )
    cls, _ = run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert cls == "main_command"
    assert session.sent == [(profile.handle, False), (profile.handle, False)]  # one failed attempt, one retry


# -- WO-MS-2: front_end catalog-driven adapter select ------------------------
#
# A profile may carry `server=<catalog key>` (twclient/servers.py, WO-MS-1);
# run_login resolves that key's `front_end` BEFORE driving anything. These
# tests write synthetic servers.toml fixtures rather than depending on the
# real catalog's contents (which today has zero `bbs` entries -- MS-3c
# pruned them -- so the `bbs` branch is a guard for future adds, proven here
# against a fixture that models one).

def _write_servers_toml(tmp_path, body):
    path = tmp_path / "servers.toml"
    path.write_text(body)
    return path


def _mask_secrets(sent):
    """Sent-list shape with any secret-marked value blanked out -- the
    CSPRNG-generated NEW-registration password differs run-to-run by
    design, so a 'byte-for-byte identical path' check must compare the
    SHAPE (order, which sends are secret) rather than the literal value."""
    return [(None if secret else text, secret) for text, secret in sent]


def test_front_end_bbs_raises_naming_direct_alternative_port(tmp_path):
    """BBS-menu navigation isn't implemented (declined Wave-2 item) --
    run_login must fail loudly before sending a single keystroke, and the
    error must name the catalog's TWGS-direct alternative port so an
    operator knows what to reach for instead."""
    catalog = _write_servers_toml(
        tmp_path,
        '[servers.bbs_host]\n'
        'hostname = "bbs.example.test"\n'
        "port = 23\n"
        'transport = "telnet"\n'
        'front_end = "bbs"\n'
        "aliases = []\n"
        'status = "online"\n'
        'sources = ["test"]\n'
        "\n"
        "[servers.bbs_host_direct_alt]\n"
        'hostname = "bbs.example.test"\n'
        "port = 2002\n"
        'transport = "telnet"\n'
        'front_end = "direct"\n'
        "aliases = []\n"
        'status = "online"\n'
        'sources = ["test"]\n',
    )
    profile = FakeProfile(server="bbs_host")
    session = FakeLoginSession([{"screen": "irrelevant -- never reached", "expect": None}])

    with pytest.raises(LoginError, match=r"front_end_bbs_unsupported.*bbs_host.*direct_alt_port=2002"):
        run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None, servers_path=catalog)
    assert session.sent == []  # no BBS navigation was ever attempted


def test_front_end_bbs_without_cataloged_alternative_still_fails_loudly(tmp_path):
    """No direct sibling cataloged for this host -- still fails loudly
    (never guesses/attempts BBS navigation), just without a port to cite."""
    catalog = _write_servers_toml(
        tmp_path,
        '[servers.lonely_bbs_host]\n'
        'hostname = "lonely.example.test"\n'
        "port = 23\n"
        'transport = "telnet"\n'
        'front_end = "bbs"\n'
        "aliases = []\n"
        'status = "online"\n'
        'sources = ["test"]\n',
    )
    profile = FakeProfile(server="lonely_bbs_host")
    session = FakeLoginSession([{"screen": "irrelevant -- never reached", "expect": None}])

    with pytest.raises(LoginError, match=r"front_end_bbs_unsupported.*no_cataloged_direct_alternative"):
        run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None, servers_path=catalog)
    assert session.sent == []


def test_front_end_auto_resolves_to_direct_behavior(tmp_path):
    catalog = _write_servers_toml(
        tmp_path,
        '[servers.auto_host]\n'
        'hostname = "auto.example.test"\n'
        "port = 23\n"
        'transport = "telnet"\n'
        'front_end = "auto"\n'
        "aliases = []\n"
        'status = "online"\n'
        'sources = ["test"]\n',
    )
    profile = FakeProfile(server="auto_host")
    saved = {}
    steps, seen_password = _new_registration_steps(profile, password_screens=1)
    session = FakeLoginSession(steps)

    cls, taken = run_login(
        session, profile, get_password=lambda n: saved.get(n), save_password=lambda n, pw: saved.__setitem__(n, pw),
        servers_path=catalog,
    )

    assert cls == "main_command"
    assert saved["default"] == seen_password["value"]


def test_front_end_direct_is_byte_for_byte_the_existing_path(tmp_path):
    """A profile whose catalog entry is explicitly front_end=direct must
    drive the exact same send sequence, in the exact same order, as a
    profile with no `server` at all (today's only real-world shape)."""
    catalog = _write_servers_toml(
        tmp_path,
        '[servers.direct_host]\n'
        'hostname = "direct.example.test"\n'
        "port = 23\n"
        'transport = "telnet"\n'
        'front_end = "direct"\n'
        "aliases = []\n"
        'status = "online"\n'
        'sources = ["test"]\n',
    )
    profile_catalog = FakeProfile(server="direct_host")
    profile_bare = FakeProfile()  # no server key at all

    saved_catalog, saved_bare = {}, {}
    steps_catalog, _ = _new_registration_steps(profile_catalog, password_screens=1)
    steps_bare, _ = _new_registration_steps(profile_bare, password_screens=1)
    session_catalog = FakeLoginSession(steps_catalog)
    session_bare = FakeLoginSession(steps_bare)

    cls_catalog, taken_catalog = run_login(
        session_catalog, profile_catalog, get_password=lambda n: saved_catalog.get(n),
        save_password=lambda n, pw: saved_catalog.__setitem__(n, pw), servers_path=catalog,
    )
    cls_bare, taken_bare = run_login(
        session_bare, profile_bare, get_password=lambda n: saved_bare.get(n),
        save_password=lambda n, pw: saved_bare.__setitem__(n, pw),
    )

    assert cls_catalog == cls_bare == "main_command"
    assert taken_catalog == taken_bare
    assert _mask_secrets(session_catalog.sent) == _mask_secrets(session_bare.sent)


def test_front_end_unrecognized_value_fails_loudly_never_guesses(monkeypatch):
    """Defensive belt-and-braces: servers.py's own catalog loader already
    constrains front_end to {direct, bbs, auto} at load time (a bad value
    raises ServerCatalogError there, well before login.py ever sees it) --
    this proves run_login still refuses to guess if an unrecognized value
    somehow reaches it, rather than silently falling through to direct."""
    from twclient import servers as servers_mod

    fake_rec = {"key": "weird_host", "hostname": "weird.example.test", "port": 23, "front_end": "carrier-pigeon"}
    monkeypatch.setattr(servers_mod, "get_server", lambda key, path=None: fake_rec)

    profile = FakeProfile(server="weird_host")
    session = FakeLoginSession([{"screen": "irrelevant -- never reached", "expect": None}])

    with pytest.raises(LoginError, match=r"front_end_unrecognized:server=weird_host:front_end='carrier-pigeon'"):
        run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert session.sent == []


# -- WO-MS-4: registration opt-in hard-gate ----------------------------------
#
# Auto-creating a character on a real server is a policy call: char_create's
# dispatch must refuse BEFORE sending the "Y" that starts registration
# unless the profile has explicitly opted in via `allow_register`.

_PRE_REGISTRATION_STEPS = [
    {"screen": "Please enter your name (ENTER for none):", "expect": _is("")},
    {"screen": "<F> Bob the Builder\nSelect a game :", "expect": _is("F")},
    {"screen": "T - Play Trade Wars 2002\nI - Introduction & Help\nEnter your choice:", "expect": _is("T")},
    {"screen": "What is your name?", "expect": _is("AEGIS")},
    {"screen": "Use ANSI graphics?", "expect": _is("Y")},
    {"screen": "Show today's log? (Y/N) [N]", "expect": _is("N")},
]


def _char_create_screen():
    return (
        "You were not found in the player database.\n"
        "Would you like to start a new character in this game?  (Type Y or N)"
    )


def test_allow_register_false_hard_fails_before_any_registration_keystroke():
    profile = FakeProfile(allow_register=False)
    steps = _PRE_REGISTRATION_STEPS + [
        # Must never be sent -- a send here fails this test's own
        # assertion inside FakeLoginSession, independent of the
        # LoginError assertion below.
        {"screen": _char_create_screen(), "expect": lambda text, secret: False},
    ]
    session = FakeLoginSession(steps)
    with pytest.raises(LoginError, match=r"registration_not_permitted:profile=default:set allow_register=true to opt in"):
        run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    # Exactly the 6 pre-registration sends landed; nothing for char_create.
    assert session.sent == [("", False), ("F", False), ("T", False), ("AEGIS", False), ("Y", False), ("N", False)]


class _ProfileWithoutAllowRegisterAttr:
    """Mimics a profile object that PREDATES the allow_register field
    entirely -- belt-and-braces proof of the `getattr(profile,
    "allow_register", False)` SAFE default, not just the
    attribute-present-and-False case above."""

    def __init__(self):
        self.name = "legacy"
        self.host = FAKE_HOST
        self.port = FAKE_PORT
        self.game_letter = "F"
        self.handle = "AEGIS"
        self.ship_name = "Vantage"
        self.planet_name = "Anchorage"
        self.server = None
        # deliberately no self.allow_register at all


def test_allow_register_missing_attribute_hard_fails_via_safe_default():
    profile = _ProfileWithoutAllowRegisterAttr()
    steps = _PRE_REGISTRATION_STEPS + [
        {"screen": _char_create_screen(), "expect": lambda text, secret: False},
    ]
    session = FakeLoginSession(steps)
    with pytest.raises(LoginError, match=r"registration_not_permitted:profile=legacy"):
        run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert session.sent == [("", False), ("F", False), ("T", False), ("AEGIS", False), ("Y", False), ("N", False)]


# -- WO-MS-4: NEW-branch prompt-coverage variety -----------------------------
#
# Both fixtures below are CONSTRUCTED (never captured live) -- MS-3's own
# live-probe LOE finding is that every TWGS front-end probed so far is
# byte-identical, so no modded-server registration prompt has actually been
# observed yet. These prove the _NEW_BRANCH_VARIANTS registry mechanism
# (one recognized entry dispatched correctly) and the fail-loud posture for
# anything NOT in it (never guessed/sent blind), same discipline as
# state_parser.py's own constructed-not-live fixtures.

def test_new_branch_variant_registry_recognized_prompt_is_answered():
    profile = FakeProfile()
    saved = {}
    steps = _PRE_REGISTRATION_STEPS + [
        {"screen": _char_create_screen(), "expect": _is("Y")},
        # CONSTRUCTED: a hypothetical modded server's extra registration
        # question, seeded into _NEW_BRANCH_VARIANTS to prove the
        # mechanism, not because any real server has been observed asking it.
        {"screen": "Enable the weekly news digest?", "expect": _is("N")},
        {"screen": "Please enter a password for this game account.\nPassword?", "expect": lambda t, s: s is True},
        {"screen": "Repeat password to verify.\nPassword?", "expect": lambda t, s: s is True},
        {
            "screen": (
                f"Do you wish to make up a new Alias for your Trader Name,\n"
                f"or would you rather use your BBS name of {profile.handle}?\n"
                f"Use (N)ew Name or (B)BS Name [B] ?"
            ),
            "expect": _is("B"),
        },
        {"screen": "What do you want to name your ship? (30 letters)", "expect": _is(profile.ship_name)},
        {"screen": f"{profile.ship_name} is what you want?", "expect": _is("Y")},
        {
            "screen": "What do you want to name your home planet? (Class K-BE, Desert wasteland)\n[---------------------------------------]",
            "expect": _is(profile.planet_name),
        },
        {"screen": "Planet command (?=help) [D]", "expect": _is("Q")},
        {"screen": "Command [TL=00:00:00]:[24146] (?=Help)? :", "expect": None},
    ]
    session = FakeLoginSession(steps)
    cls, _ = run_login(
        session, profile, get_password=lambda n: saved.get(n), save_password=lambda n, pw: saved.__setitem__(n, pw)
    )
    assert cls == "main_command"


def test_new_branch_unrecognized_variant_prompt_fails_loud_never_guesses():
    """CONSTRUCTED: a hypothetical modded-server question that IS
    gameplay-affecting (an alignment pick -- exactly the kind of choice
    _NEW_BRANCH_VARIANTS' own module comment says must never be guessed).
    Not in the registry -- must raise automaton_stuck rather than loop or
    send anything for it."""
    profile = FakeProfile()
    steps = _PRE_REGISTRATION_STEPS + [
        {"screen": _char_create_screen(), "expect": _is("Y")},
        {"screen": "Choose your alignment: (G)ood, (N)eutral, or (E)vil?", "expect": lambda text, secret: False},
    ]
    session = FakeLoginSession(steps)
    with pytest.raises(LoginError, match="automaton_stuck"):
        run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    # The 6 pre-registration sends plus char_create's "Y" landed; nothing
    # was ever sent for the unrecognized alignment prompt.
    assert session.sent == [("", False), ("F", False), ("T", False), ("AEGIS", False), ("Y", False), ("N", False), ("Y", False)]


# -- WO-MS-4: name-bank collision detection + bounded redraw -----------------

def _bank_collision_steps():
    """A drawn handle that turns out to already belong to an existing
    character: straight to the password gate with no char_create in
    between (the RETURNING shape), same as
    test_returning_login_without_saved_password_raises_rather_than_guessing
    above -- but here `bank_draw=True` must turn this into a distinct
    collision error instead of the generic returning_no_saved_password.
    Uses `_any` for the handle-echo step (not `_PRE_REGISTRATION_STEPS`'
    hardcoded "AEGIS") since a bank-drawn handle's exact value isn't known
    ahead of time."""
    return [
        {"screen": "Please enter your name (ENTER for none):", "expect": _is("")},
        {"screen": "<F> Bob the Builder\nSelect a game :", "expect": _is("F")},
        {"screen": "T - Play Trade Wars 2002\nI - Introduction & Help\nEnter your choice:", "expect": _is("T")},
        {"screen": "What is your name?", "expect": _any},
        {"screen": "Use ANSI graphics?", "expect": _is("Y")},
        {"screen": "Show today's log? (Y/N) [N]", "expect": _is("N")},
        {"screen": "Password?", "expect": lambda text, secret: False},  # never reached -- raises first
    ]


def test_run_login_bank_draw_collision_raises_distinct_error_and_sends_nothing_secret():
    profile = FakeProfile(handle="SomeoneElse")
    session = FakeLoginSession(_bank_collision_steps())
    with pytest.raises(LoginError, match=r"bank_draw_handle_collision:profile=default:handle=SomeoneElse"):
        run_login(session, profile, get_password=lambda n: None, save_password=lambda n, pw: None, bank_draw=True)
    assert all(not secret for _text, secret in session.sent)  # no password was ever sent


def _new_registration_steps_for_bank_draw(ship_name, planet_name):
    """Same shape as _new_registration_steps, but the handle-echo step
    accepts ANY value (`_any`) since the caller doesn't control which
    handle register_with_name_bank's rng draws."""
    seen_password = {}

    def _expect_password_consistent(text, secret):
        if not secret:
            return False
        if "value" not in seen_password:
            seen_password["value"] = text
        return text == seen_password["value"]

    return [
        {"screen": "Please enter your name (ENTER for none):", "expect": _is("")},
        {"screen": "<F> Bob the Builder\nSelect a game :", "expect": _is("F")},
        {"screen": "T - Play Trade Wars 2002\nI - Introduction & Help\nEnter your choice:", "expect": _is("T")},
        {"screen": "What is your name?", "expect": _any},
        {"screen": "Use ANSI graphics?", "expect": _is("Y")},
        {"screen": "Show today's log? (Y/N) [N]", "expect": _is("N")},
        {"screen": _char_create_screen(), "expect": _is("Y")},
        {"screen": "Please enter a password for this game account.\nPassword?", "expect": _expect_password_consistent},
        {"screen": "Repeat password to verify.\nPassword?", "expect": _expect_password_consistent},
        {
            "screen": "Do you wish to make up a new Alias for your Trader Name,\nor would you rather use your BBS name of X?\nUse (N)ew Name or (B)BS Name [B] ?",
            "expect": _is("B"),
        },
        {"screen": "What do you want to name your ship? (30 letters)", "expect": _is(ship_name)},
        {"screen": f"{ship_name} is what you want?", "expect": _is("Y")},
        {
            "screen": "What do you want to name your home planet? (Class K-BE, Desert wasteland)\n[---------------------------------------]",
            "expect": _is(planet_name),
        },
        {"screen": "Planet command (?=help) [D]", "expect": _is("Q")},
        {"screen": "Command [TL=00:00:00]:[24146] (?=Help)? :", "expect": None},
    ]


def _write_name_bank(tmp_path, handles):
    path = tmp_path / "name_bank.toml"
    handles_toml = ", ".join(f'"{h}"' for h in handles)
    path.write_text(f'[names]\nhandles = [{handles_toml}]\nships = ["Ship"]\nplanets = ["World"]\n')
    return path


def test_register_with_name_bank_redraws_after_collision_then_succeeds(tmp_path):
    """The name-bank rider's bounded retry: the first two drawn identities
    collide with an existing character; register_with_name_bank obtains a
    FRESH session (a collided session can never be resumed -- see its own
    docstring) and redraws each time, succeeding on the third attempt."""
    bank_path = _write_name_bank(tmp_path, ["Collide1", "Collide2", "FreshOne"])
    from twclient.credentials import Profile

    profile = Profile(
        name="crawler", host=FAKE_HOST, port=FAKE_PORT, game_letter="F",
        handle=None, ship_name="Vantage", planet_name="Anchorage", allow_register=True,
    )
    saved = {}
    attempts = {"n": 0}

    def session_provider():
        attempts["n"] += 1
        if attempts["n"] <= 2:
            return FakeLoginSession(_bank_collision_steps())
        return FakeLoginSession(_new_registration_steps_for_bank_draw("Vantage", "Anchorage"))

    cls, _ = register_with_name_bank(
        session_provider, profile, get_password=lambda n: saved.get(n),
        save_password=lambda n, pw: saved.__setitem__(n, pw),
        name_bank_path=bank_path, rng=random.Random(1234),
    )
    assert cls == "main_command"
    assert attempts["n"] == 3
    assert "crawler" in saved


def test_register_with_name_bank_exhausts_attempts_then_fails_loud(tmp_path):
    """Every draw collides -- must fail loudly with a distinct,
    attempt-count-naming error rather than retrying forever."""
    bank_path = _write_name_bank(tmp_path, ["AlwaysCollides"])
    from twclient.credentials import Profile

    profile = Profile(
        name="crawler", host=FAKE_HOST, port=FAKE_PORT, game_letter="F",
        handle=None, ship_name="Vantage", planet_name="Anchorage", allow_register=True,
    )

    def session_provider():
        return FakeLoginSession(_bank_collision_steps())

    with pytest.raises(LoginError, match=r"bank_draw_exhausted_attempts:5"):
        register_with_name_bank(
            session_provider, profile, get_password=lambda n: None, save_password=lambda n, pw: None,
            name_bank_path=bank_path, rng=random.Random(7),
        )


def test_register_with_name_bank_propagates_unrelated_login_errors_unretried(tmp_path):
    """A failure that ISN'T a bank-draw collision (here: allow_register
    left False on the per-attempt profile it builds) must propagate
    immediately -- register_with_name_bank only retries the specific
    collision signature, never masks a different failure as a redraw."""
    bank_path = _write_name_bank(tmp_path, ["Whatever"])
    from twclient.credentials import Profile

    profile = Profile(
        name="crawler", host=FAKE_HOST, port=FAKE_PORT, game_letter="F",
        handle=None, ship_name="Vantage", planet_name="Anchorage", allow_register=False,
    )
    calls = {"n": 0}

    def session_provider():
        calls["n"] += 1
        steps = [
            {"screen": "Please enter your name (ENTER for none):", "expect": _is("")},
            {"screen": "<F> Bob the Builder\nSelect a game :", "expect": _is("F")},
            {"screen": "T - Play Trade Wars 2002\nI - Introduction & Help\nEnter your choice:", "expect": _is("T")},
            {"screen": "What is your name?", "expect": _any},
            {"screen": "Use ANSI graphics?", "expect": _is("Y")},
            {"screen": "Show today's log? (Y/N) [N]", "expect": _is("N")},
            {"screen": _char_create_screen(), "expect": lambda text, secret: False},
        ]
        return FakeLoginSession(steps)

    with pytest.raises(LoginError, match="registration_not_permitted"):
        register_with_name_bank(
            session_provider, profile, get_password=lambda n: None, save_password=lambda n, pw: None,
            name_bank_path=bank_path, rng=random.Random(3),
        )
    assert calls["n"] == 1  # never retried a non-collision failure


# -- game_select answered-once-per-connection safety fix --------------------
#
# A real game-select prompt is answered exactly ONCE per TCP connection
# (session.py's `game_select_answered` flag). This closes the `ensure`-
# mid-session stale-pyte-buffer misfire vector at the SOURCE, independent
# of any classify.py heuristic: a SECOND `game_select` classification on
# the SAME session/connection -- even from a LATER `run_login` call with
# its own fresh `state` dict, the exact shape a later `ensure` dispatch
# takes -- must never be answered with a second blind keystroke.

def test_game_select_answered_flag_set_after_the_real_game_select_is_sent():
    profile = FakeProfile()
    steps = [
        {"screen": "<F> Bob the Builder\nSelect a game :", "expect": _is(profile.game_letter)},
        {"screen": "Command [TL=00:00:00]:[1] (?=Help)? :", "expect": None},
    ]
    session = FakeLoginSession(steps)
    cls, _ = run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert cls == "main_command"
    assert session.sent == [(profile.game_letter, False)]
    assert session.game_select_answered is True


def test_second_game_select_same_connection_is_refused_not_resent():
    """The concrete vector: a real game-select is answered once, then a
    LATER stale `game_select` screen (a later `run_login`/`ensure` call
    against the SAME session, its own fresh `state` dict) must fail
    loud rather than send the game letter a second time."""
    profile = FakeProfile()
    steps = [
        {"screen": "<F> Bob the Builder\nSelect a game :", "expect": _is(profile.game_letter)},
        {"screen": "Command [TL=00:00:00]:[1] (?=Help)? :", "expect": None},
    ]
    session = FakeLoginSession(steps)
    cls, _ = run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert cls == "main_command"
    assert session.sent == [(profile.game_letter, False)]

    # A later ensure/run_login call, same session/connection, fresh
    # `state` dict -- a stale scrollback buffer misclassifying the
    # current screen as game_select again. Must never be answered.
    session._steps = [{"screen": "<F> Bob the Builder\nSelect a game :", "expect": lambda text, secret: False}]
    session._i = 0
    with pytest.raises(LoginError, match="automaton_stuck"):
        run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert session.sent == [(profile.game_letter, False)]  # unchanged -- zero blind sends


def test_game_select_answered_flag_resets_after_reconnect():
    """Mirrors session.py's own reconnect() contract: a genuinely fresh
    connection (guardian's D9 reconnect-replay, or a fresh cold-start
    login) must still answer a real game-select normally -- the flag is
    per-CONNECTION, not a permanent one-time-ever latch."""
    profile = FakeProfile()
    steps = [
        {"screen": "<F> Bob the Builder\nSelect a game :", "expect": _is(profile.game_letter)},
        {"screen": "Command [TL=00:00:00]:[1] (?=Help)? :", "expect": None},
    ]
    session = FakeLoginSession(steps)
    run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert session.game_select_answered is True

    # FakeLoginSession models no real socket, so there's nothing to
    # reconnect() here -- this directly exercises the reset session.py's
    # own reconnect() performs (see test_session.py for that unit test).
    session.game_select_answered = False
    session._steps = [
        {"screen": "<F> Bob the Builder\nSelect a game :", "expect": _is(profile.game_letter)},
        {"screen": "Command [TL=00:00:00]:[1] (?=Help)? :", "expect": None},
    ]
    session._i = 0

    cls, _ = run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert cls == "main_command"
    assert session.sent[-1] == (profile.game_letter, False)


# -- REVISE (mack/cipher, adversarial review): the flag must latch only on
# a CONFIRMED send, never at decide-time -- an earlier version of this fix
# set it inside `_decide` the instant it chose to send the letter, before
# `send_and_confirm` ever confirmed anything landed. An unconfirmed or
# outright-failed send would then latch the flag True with the prompt
# never actually answered; since `conn.connected` stays True in both
# cases (only the reader thread / close()/reconnect() flip it), the one
# reset path (reconnect()) would never fire either -- a permanent
# automaton_stuck wedge on this connection until an operator force-
# restarted it. These two tests prove the fix.


class _RaisingSendSession:
    """Models mack's finding: `session.send()` itself raises (a real
    socket `sendall` failure) -- propagates uncaught out of run_login
    (same as any other send-path exception; login.py has no try/except
    around `send_and_confirm`), never reaching the confirmed-send
    checkpoint that latches the flag. Enough surface to reach the
    game_select send call and no further."""

    def __init__(self, screen):
        self._screen = screen
        self.rx_count = 0
        self.last_rx = 0.0
        self.t = 0.0
        self.game_select_answered = False  # mirrors the real Session's default

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds

    def render(self):
        return self._screen.split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._screen

    def send(self, text, enter=True, secret=False):
        raise OSError("simulated sendall failure")


def test_game_select_answered_flag_stays_false_after_a_failed_send():
    """mack's OSError-mid-send finding: a hard send failure must never
    latch the flag -- it aborts run_login entirely, uncaught, before the
    confirmed-send checkpoint that sets the flag is ever reached."""
    profile = FakeProfile()
    session = _RaisingSendSession("<F> Bob the Builder\nSelect a game :")
    with pytest.raises(OSError):
        run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)
    assert session.game_select_answered is False


class _FlakyGameSelectSession:
    """Models cipher's hub-warp-animation finding for the game_select
    send specifically: `send_and_confirm`'s `confirm_prompt=None` idle
    path (game_select's `wait_hint` is always None -- see login.py's
    module docstring) fires "idle", but ONE more byte arrives during its
    own post-idle stability-recheck pause (settle.py's own documented
    hub-warp-animation case: `test_send_and_confirm_none_rejects_when_
    more_bytes_arrive_during_the_recheck`, test_settle.py) -- unconfirmed
    on the FIRST attempt, then confirms cleanly on the identical resend.

    Combines test_settle.py's `StagedSession`/`ScriptedSession` arrival-
    timeline convention (`.sleep()` applies any arrival due by the new
    clock time -- needed to place that extra byte precisely inside the
    stability-recheck window) with this file's own `FakeLoginSession`
    ordered screen-script convention (needed to drive the automaton on to
    `main_command` once the resend succeeds). The rendered screen text
    never changes across the flaky attempt -- this isolates
    send_and_confirm's confirm TIMING from classify_screen's text
    reading, rather than modeling a literal changing game-select screen."""

    def __init__(self, steps):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._steps = steps
        self._i = 0
        self.sent = []
        self._pending_arrivals = []
        self._advance_after = False

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        while self._pending_arrivals and self._pending_arrivals[0] <= self.t:
            self._pending_arrivals.pop(0)
            self.rx_count += 1
            self.last_rx = self.t
        if not self._pending_arrivals and self._advance_after and self._i < len(self._steps) - 1:
            self._advance_after = False
            self._i += 1

    def render(self):
        return self._steps[self._i]["screen"].split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._steps[self._i]["screen"]

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350):
        return wait_for_settle(self, wait_prompt=wait_prompt, timeout_s=timeout, debounce_ms=debounce_ms)

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, secret))
        step = self._steps[self._i]
        if step.get("expect") is not None:
            assert step["expect"](text, secret), f"unexpected send {text!r} secret={secret!r}"
        attempts = step.get("_attempts", 0)
        step["_attempts"] = attempts + 1
        base = self.t
        if step.get("flaky") and attempts == 0:
            # First attempt: one arrival lands almost immediately
            # (satisfies the debounce -> "idle" fires), then a SECOND
            # arrival is timed to land during send_and_confirm's own
            # post-idle stability-recheck sleep -- confirmed=False. Never
            # advances the script -- the caller retries the same screen.
            self._pending_arrivals = [base + 0.05, base + 0.45]
            self._advance_after = False
        else:
            # A clean, single-arrival confirm -- advances the script.
            self._pending_arrivals = [base + 0.05]
            self._advance_after = True


def test_game_select_answered_flag_only_latches_after_confirmed_not_on_an_unconfirmed_attempt():
    """The wedge-fix proof: an unconfirmed first attempt at game_select
    must NOT latch the flag and must NOT raise -- the automaton retries
    itself on the very next reactive-loop iteration (exactly like every
    other branch already does), succeeds on the resend, and only THEN
    latches the flag."""
    profile = FakeProfile()
    steps = [
        {"screen": "<F> Bob the Builder\nSelect a game :", "expect": _is(profile.game_letter), "flaky": True},
        {"screen": "Command [TL=00:00:00]:[1] (?=Help)? :", "expect": None},
    ]
    session = _FlakyGameSelectSession(steps)

    cls, _ = run_login(session, profile, get_password=lambda n: "x", save_password=lambda n, pw: None)

    assert cls == "main_command"
    # Sent twice -- the flaky unconfirmed attempt, then the confirmed
    # resend -- both the identical game letter, never anything else.
    assert session.sent == [(profile.game_letter, False), (profile.game_letter, False)]
    assert session.game_select_answered is True
