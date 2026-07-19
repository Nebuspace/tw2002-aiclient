"""Login Automaton tests (DESIGN-v2 B1/B3/B4) — no network.

FakeLoginSession drives an ORDERED script of (screen, expected-response)
steps, so tests assert the exact real-flow sequence captured live
against twgs.test.example (see login.py's module docstring) without
depending on literal password text (which is CSPRNG-random for a fresh
NEW-registration and must not be predictable/hardcoded in a test)."""

import pytest

from twclient.login import LoginError, run_login
from twclient.settle import wait_for_settle

from .conftest import FAKE_HOST, FAKE_PORT


class FakeLoginSession:
    """Walks an ordered list of steps: `{"screen": text, "expect": fn}`.
    On send(), validates `expect(text, secret)` (if given) against what
    the automaton sent, records it, and advances to the next step's
    screen. Once the script is exhausted, stays on the final screen
    (models a settled target screen that doesn't change further)."""

    def __init__(self, steps):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._steps = steps
        self._i = 0
        self.sent = []  # [(text, secret), ...]

    # -- settle-detection protocol surface (matches Session) -------------
    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds

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
        if self._i < len(self._steps) - 1:
            self._i += 1
        self.rx_count += 1
        self.last_rx = self.t


class FakeProfile:
    def __init__(self, name="default", host=FAKE_HOST, port=FAKE_PORT, game_letter="F", handle="AEGIS",
                 ship_name="Vantage", planet_name="Anchorage"):
        self.name = name
        self.host = host
        self.port = port
        self.game_letter = game_letter
        self.handle = handle
        self.ship_name = ship_name
        self.planet_name = planet_name


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
