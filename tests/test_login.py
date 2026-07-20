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
                 ship_name="Vantage", planet_name="Anchorage", server=None):
        self.name = name
        self.host = host
        self.port = port
        self.game_letter = game_letter
        self.handle = handle
        self.ship_name = ship_name
        self.planet_name = planet_name
        self.server = server  # optional catalog key (WO-MS-1/WO-MS-2); None = today's bare host/port shape


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
