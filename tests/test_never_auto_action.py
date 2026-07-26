"""The never-auto-action pin, proven at every place the app acts on a class.

Canon: `DECISIONS.md` §A.2 (Accepted 2026-07-26, aligning
`canon/research/tw2002-screen-patterns.md` P-QTY) rules that a
`money_prompt` -- a quantity / money / bank-transfer question the server is
blocked on -- is **escalate-only**. The App must hand the keyboard to the
human; no taught rule, macro, crawl keystroke or keepalive nudge may fire.

WHY THIS FILE EXISTS SEPARATELY. The pin is a property of the SYSTEM, not
of `classify.py`. Classification alone cannot enforce it: canon
(`engine/screen-understanding.md`, "The Unknown Is First-Class") makes
`unknown` the escalate trigger, which means every named class is, by
default, a screen a consumer is allowed to act on. Adding a label is
therefore normally a widening -- and this WO's whole safety claim is that
`money_prompt` is a NARROWING. That claim is only true if every consumer
that branches on a class refuses this one, so the proof has to live where
the consumers are, not where the label is.

The four sites that branch on `classify_screen`'s answer, enumerated by
reading them rather than assumed:

  - `menu.crawler.screen_state`      -- refusal list (proven in
                                        tests/test_menu_crawler.py)
  - `session.guardian._maybe_keepalive` -- acts on `main_command` only
  - `session.login._decide`          -- a positive table; anything absent
                                        returns None (= no keystroke)
  - `session.protocol` ensure        -- `cls == target` equality only

The shape they share is the load-bearing part: every one is a POSITIVE
match on a named class, or a denylist. Not one of them is of the form
"act unless the class is unknown". That is what makes a new label unable
to enable an action anywhere, and `test_no_consumer_acts_on_merely_being_
recognized` below is the tripwire on a fifth consumer arriving that breaks
the pattern.
"""

import pytest

from tw2002_aiclient.menu import crawler as menu_crawler
from tw2002_aiclient.session import login as login_module
from tw2002_aiclient.session.classify import NEVER_AUTO_ACTION_CLASSES, classify_screen
from tw2002_aiclient.session.guardian import SessionGuardian

MONEY_PROMPT = "How many holds would you like to buy [0-20] ?"
MONEY_SCREEN = (
    "-=-=-        StarDock Shipyard - Cargo Hold Upgrade        -=-=-\n"
    "Holds cost 1,468 credits each, for a total of 29,360 credits to fill them all.\n"
    "-=-=-        End of Cargo Hold Upgrade Quote        -=-=-\n"
    "\n" + MONEY_PROMPT
)


class _FakeConn:
    connected = True


class _KeepaliveSession:
    """Minimal surface `guardian._maybe_keepalive` reads. Mirrors
    tests/test_guardian.py's own double rather than importing it, so this
    file stays readable as a single statement of the invariant."""

    def __init__(self, text):
        self._text = text
        self.last_rx = -1000.0
        self.sent = []
        self.conn = _FakeConn()

    def render(self):
        return self._text.split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._text

    def send(self, text, enter=True, secret=False, sender="app"):
        self.sent.append((text, secret, sender))


class _FakeProfile:
    name = "default"
    handle = "AEGIS"
    game_letter = "F"
    ship_name = "Vantage"
    planet_name = "Anchorage"
    allow_register = False
    clear_avoids_on_login = False


def test_the_captured_purchase_screen_carries_a_never_auto_action_class():
    """Precondition for everything below. If this ever stops holding, the
    consumer proofs become assertions about a screen that no longer
    reaches them -- green, and meaningless."""
    assert classify_screen(MONEY_SCREEN, MONEY_PROMPT) in NEVER_AUTO_ACTION_CLASSES


def test_the_crawler_refuses_to_enumerate_a_money_prompt():
    """Consumer 1. `screen_state` is the crawler's per-screen gate; an
    "unsafe" screen is never enumerated and never pressed from, so no
    keystroke can originate here. The leg-isolated version of this proof
    -- with the crawler's other two safety legs switched off, so it pins
    the CLASS check specifically -- lives in tests/test_menu_crawler.py."""
    assert menu_crawler.screen_state(MONEY_SCREEN, MONEY_PROMPT) == "unsafe"


def test_the_guardian_never_nudges_a_money_prompt():
    """Consumer 2. The idle keepalive sends a bare Enter, which on a
    quantity prompt is not a no-op at all: canon's P-QTY is precisely
    about `[12]`-style brackets that Enter ACCEPTS. `_maybe_keepalive`
    acts on `main_command` and nothing else, so the nudge cannot land
    here -- proven by driving a fully idle guardian rather than by
    reading the branch."""
    session = _KeepaliveSession(MONEY_SCREEN)
    guardian = SessionGuardian(
        session,
        get_password=lambda n: "unused",
        save_password=lambda n, pw: None,
        load_profile=lambda n: _FakeProfile(),
        reconnect_backoff_s=0,
        idle_keepalive_ms=1,
    )
    guardian._tick()
    assert session.sent == []


def test_the_login_automaton_has_no_keystroke_for_a_money_prompt():
    """Consumer 3. `login._decide` is a positive table: a class it does
    not name returns None, which routes through the caller's stagnation
    budget to a fail-loud `automaton_stuck` rather than to a guess. A
    money prompt has no entry, so the automaton escalates."""
    state = {"registering": None, "password": None, "password_attempts": 0}
    action = login_module._decide(
        "money_prompt",
        MONEY_SCREEN,
        MONEY_PROMPT,
        _FakeProfile(),
        state,
        lambda name: None,
        lambda name, pw: None,
        session=None,
    )
    assert action is None


@pytest.mark.parametrize("forbidden", sorted(NEVER_AUTO_ACTION_CLASSES))
def test_no_consumer_acts_on_merely_being_recognized(forbidden):
    """The generalization, and the reason the pin survives the next class
    added to the set. `login._decide` is the only consumer that dispatches
    over MANY classes, so it is the one that could plausibly grow an
    "anything recognized is fair game" branch. Every escalate-only class
    must return None from it -- not just the one that happens to exist
    today."""
    state = {"registering": None, "password": None, "password_attempts": 0}
    assert (
        login_module._decide(
            forbidden,
            MONEY_SCREEN,
            MONEY_PROMPT,
            _FakeProfile(),
            state,
            lambda name: None,
            lambda name, pw: None,
            session=None,
        )
        is None
    )


def test_ensure_never_treats_a_money_prompt_as_a_reached_target():
    """Consumer 4. `protocol`'s ensure verb decides "already there" by
    `cls == target`, and its target is `main_command`. An equality against
    a named class cannot be satisfied by a different named class -- pinned
    here because the *shape* is what protects the pin, and a future
    rewrite to "cls is not unknown" would silently pass a money screen off
    as a ready session."""
    assert classify_screen(MONEY_SCREEN, MONEY_PROMPT) != "main_command"
