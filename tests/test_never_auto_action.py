"""The never-auto-action pin, proven at every place the app acts on a class.

Canon: `DECISIONS.md` §A.2 (Accepted 2026-07-26, aligning
`canon/research/tw2002-screen-patterns.md` P-QTY) rules that a
`money_prompt` -- a quantity / money / bank-transfer question the server is
blocked on -- is **escalate-only** for generic consumers. ADR-003 adds one
narrow exception: the explicitly confirmed guarded trade driver may answer
only its freshly matched commodity-quantity/standing-offer cascade under
cash, turn, cargo, arm, and abort rails. No taught rule, generic macro, crawl
keystroke, keepalive nudge, or unrelated money prompt may fire.

WHY THIS FILE EXISTS SEPARATELY. The pin is a property of the SYSTEM, not
of `classify.py`. Classification alone cannot enforce it: canon
(`engine/screen-understanding.md`, "The Unknown Is First-Class") makes
`unknown` the escalate trigger, which means every named class is, by
default, a screen a consumer is allowed to act on. Adding a label is
therefore normally a widening -- and this WO's whole safety claim is that
`money_prompt` is a NARROWING. That claim is only true if every consumer
that branches on a class refuses this one, so the proof has to live where
the consumers are, not where the label is.

Written inventory (WO-NEVER-AUTO-ACTION-CONSUMER-AUDIT / C-06) — every
sender that uses classification to choose keystrokes, enumerated by
reading the tree rather than assumed. Durable twin:
`audit/never-auto-action-consumer-audit-20260726.md`.

  1. `menu/crawler.py` · `screen_state`
       -- (a) `_NON_MENU_GATE_CLASSES` unions `NEVER_AUTO_ACTION_CLASSES`
  2. `loops/player.py` · `_gate` (taught-macro / arm fire via autoloop)
       -- (a) `klass in NEVER_AUTO_ACTION_CLASSES` → halt
  3. `session/guardian.py` · `_maybe_keepalive`
       -- (b) `main_command`-only whitelist
  4. `session/daemon.py` · `_attempt_graceful_quit`
       -- (b) `main_command`-only whitelist
  5. `session/login.py` · `_decide`
       -- (b) positive table; absent class → None (no keystroke)
  6. `session/protocol.py` · `_dispatch_ensure`
       -- (b) `cls == target` with default `target="main_command"`
  7. `session/sector_explore.py` · `_gate_screen` (ExploreRunner map-fill)
       -- (a) `klass in NEVER_AUTO_ACTION_CLASSES` → halt
  8. `session/hud_seed.py` · `seed_hud_after_join`
       -- (b) `main_command`-only whitelist
  9. `trade_driver.py` · `_trade_target` (ADR-003 guarded trade only)
       -- (c) exact `_QTY_PROMPT_RE` commodity + offer-total cascade; every
              send remains behind arm/abort/fresh-render/floor/PALADIN rails

Cockpit `arm.py` is presentation-only (no classify, no send). Taught-run
fire is consumer #2 only. Operator `do`/`send` report class; they do not
choose keystrokes from it.

The shape they share is the load-bearing part: every one is a POSITIVE
match on a named class, or a denylist. Not one of them is of the form
"act unless the class is unknown". That is what makes a new label unable
to enable an action anywhere. The inventory frozenset + marker pin below
is the tripwire on a seventh consumer arriving that omits the refuse.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient.loops import player as player_mod
from tw2002_aiclient.menu import crawler as menu_crawler
from tw2002_aiclient.session import daemon as daemon_mod
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
# Quantity-shaped password chrome — classifies as `unknown` (not money_prompt).
PASSWORD_LENGTH_PROMPT = "How many characters in your password?"

# Relative to `tw2002_aiclient/`. Marker must appear in source: dropping the
# refuse (or rewriting past the marker without updating this map) fails the
# inventory pin before a behavioral gap can hide.
_INVENTORIED_CONSUMERS: dict[str, str] = {
    "menu/crawler.py": "NEVER_AUTO_ACTION_CLASSES",
    "loops/player.py": "NEVER_AUTO_ACTION_CLASSES",
    "session/guardian.py": '!= "main_command"',
    "session/daemon.py": '!= "main_command"',
    "session/login.py": "def _decide",
    "session/protocol.py": 'target = args.get("target", "main_command")',
    "session/sector_explore.py": "NEVER_AUTO_ACTION_CLASSES",
    "session/hud_seed.py": '!= "main_command"',
    "trade_driver.py": "_QTY_PROMPT_RE",
}

# Modules that may mention classify + send symbols without being a
# classification→send *decision* site (wrappers, reporters, capture).
_CLASSIFY_SEND_ALLOWLIST = frozenset(
    {
        "session/classify.py",  # defines the labels; does not send
        "session/session.py",  # Session.classify / Session.send primitives
        "session/settle.py",  # settle helpers used by send_and_confirm
        "session/protocol.py",  # inventoried (ensure); also reports class
        "session/login.py",  # inventoried
        "session/guardian.py",  # inventoried
        "session/daemon.py",  # inventoried
        "session/autoloop.py",  # port only; player owns refusal
        "session/cli.py",  # CLI surface; does not choose from class
        "loops/player.py",  # inventoried
        "loops/recorder.py",  # records expected_post_class; no class→send
        "menu/crawler.py",  # inventoried
    }
)

_PKG_ROOT = Path(__file__).resolve().parents[1] / "tw2002_aiclient"
_CLASSIFY_HINTS = ("classify_screen", ".classify(", "session.classify")
_SEND_HINTS = (
    ".send(",
    "send_and_confirm",
    "send_raw",
    "session.send",
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

    def send(self, text, enter=True, redact=False, sender="app"):
        self.sent.append((text, redact, sender))


class _QuitSession:
    """Minimal surface `_attempt_graceful_quit` reads."""

    def __init__(self, classification: str):
        self._classification = classification
        self.sent = []

    def classify(self):
        return self._classification

    def send(self, text, enter=True, redact=False, sender="app"):
        self.sent.append(text)

    def wait_settle(self, timeout=2.0):
        return ("idle", 0.0)


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


def test_the_taught_loop_player_refuses_a_money_prompt():
    """Consumer 2. Taught-macro / cockpit arm fire: `_gate` is the choke
    before every send. A money screen at a boundary must halt with
    `HALT_NEVER_AUTO_ACTION` — including a macro whose own
    `expected_post_class` named the money prompt (see
    tests/test_loop_player.py for the mid-loop / recorded-answer proofs)."""
    observation = player_mod._Observation(klass="money_prompt")
    assert player_mod._gate(observation) == "never_auto_action:money_prompt"
    # Anti-drift: the player refuses via the shared frozenset, not a
    # restated "money_prompt" literal that could diverge from classify.
    assert player_mod.NEVER_AUTO_ACTION_CLASSES is NEVER_AUTO_ACTION_CLASSES


def test_the_guardian_never_nudges_a_money_prompt():
    """Consumer 3. The idle keepalive sends a bare Enter, which on a
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


def test_graceful_quit_never_keys_a_money_prompt():
    """Consumer 4. Daemon shutdown's best-effort `Q`/`Y` is gated on
    `main_command` only. A money prompt must produce zero sends — Enter
    on a quantity bracket, or `Q` mid-purchase, is exactly the hazard
    never-auto-action exists to forbid."""
    session = _QuitSession("money_prompt")
    daemon_mod._attempt_graceful_quit(session)
    assert session.sent == []


def test_the_login_automaton_has_no_keystroke_for_a_money_prompt():
    """Consumer 5. `login._decide` is a positive table: a class it does
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


def test_no_consumer_acts_on_unknown():
    """Canonical escalate-first property for ``unknown``, asserted not assumed.

    Canon (``engine/screen-understanding.md``, "The Unknown Is First-Class")
    makes ``unknown`` escalate-first. Inventoried classify→send consumers are
    positive-match or denylist shapes — never "act unless unknown" — so none
    may send on ``unknown``. This pin is an explicit assertion of that
    property (mirror of ``test_no_consumer_acts_on_merely_being_recognized``),
    not a membership of ``unknown`` in ``NEVER_AUTO_ACTION_CLASSES`` (that
    set is recognized-but-forbidden only).

    Password-length chrome (WO-CLASSIFY-PASSWORD-LENGTH-UNKNOWN / #40) is the
    concrete exemplar: correct class ``unknown``, not ``money_prompt``.
    """
    assert classify_screen("", PASSWORD_LENGTH_PROMPT) == "unknown"
    assert "unknown" not in NEVER_AUTO_ACTION_CLASSES

    # Consumer 1: crawler enumerates only ``menu``; unknown must not be menu.
    assert menu_crawler.screen_state("", PASSWORD_LENGTH_PROMPT) != "menu"

    # Consumer 2: taught-loop gate stops unrecognized screens; that is
    # escalate-on-unknown, not HALT_NEVER_AUTO_ACTION.
    observation = player_mod._Observation(klass="unknown")
    assert player_mod._gate(observation) == player_mod.HALT_UNRECOGNIZED_SCREEN
    # Compare the CODE, not the whole string: once reasons can be
    # qualified, `never_auto_action:x != never_auto_action` is trivially
    # true and this line would pass even for a wrongly-qualified
    # never-auto halt -- the assertion would weaken silently.
    assert (
        player_mod.halt_reason_code(player_mod._gate(observation))
        != player_mod.HALT_NEVER_AUTO_ACTION
    )

    # Consumer 3: keepalive is main_command-only.
    session = _KeepaliveSession(PASSWORD_LENGTH_PROMPT)
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

    # Consumer 4: graceful quit is main_command-only.
    quit_session = _QuitSession("unknown")
    daemon_mod._attempt_graceful_quit(quit_session)
    assert quit_session.sent == []

    # Consumer 5: login automaton is a positive table; unknown → None.
    state = {"registering": None, "password": None, "password_attempts": 0}
    assert (
        login_module._decide(
            "unknown",
            "",
            PASSWORD_LENGTH_PROMPT,
            _FakeProfile(),
            state,
            lambda name: None,
            lambda name, pw: None,
            session=None,
        )
        is None
    )

    # Consumer 6: ensure reaches target only on equality with main_command.
    assert classify_screen("", PASSWORD_LENGTH_PROMPT) != "main_command"


def test_ensure_never_treats_a_money_prompt_as_a_reached_target():
    """Consumer 6. `protocol`'s ensure verb decides "already there" by
    `cls == target`, and its target is `main_command`. An equality against
    a named class cannot be satisfied by a different named class -- pinned
    here because the *shape* is what protects the pin, and a future
    rewrite to "cls is not unknown" would silently pass a money screen off
    as a ready session."""
    assert classify_screen(MONEY_SCREEN, MONEY_PROMPT) != "main_command"


def test_inventoried_consumers_still_carry_their_refuse_marker():
    """Accept §3 / Scope tripwire: if a listed consumer drops its refuse
    (deletes the frozenset import, widens past `main_command`, etc.) this
    fails before a behavioral regression has to be rediscovered live."""
    missing = []
    for rel, marker in _INVENTORIED_CONSUMERS.items():
        path = _PKG_ROOT / rel
        text = path.read_text(encoding="utf-8")
        if marker not in text:
            missing.append(f"{rel} missing marker {marker!r}")
    assert missing == [], "; ".join(missing)


def test_inventory_frozenset_matches_audit_table():
    """The map above IS the Accept inventory — keep it exact. Adding a
    consumer requires a row here AND a refuse marker AND (usually) a
    behavioral pin in this file."""
    assert frozenset(_INVENTORIED_CONSUMERS) == frozenset(
        {
            "menu/crawler.py",
            "loops/player.py",
            "session/guardian.py",
            "session/daemon.py",
            "session/login.py",
            "session/protocol.py",
            "session/sector_explore.py",
            "session/hud_seed.py",
            "trade_driver.py",
        }
    )


def test_no_uninventoried_classify_send_module():
    """Fails when a new package module both references classify and an App
    send symbol without appearing in the inventory/allowlist — the C-06
    "fifth consumer" gap restated as a pin."""
    offenders = []
    for path in sorted(_PKG_ROOT.rglob("*.py")):
        rel = path.relative_to(_PKG_ROOT).as_posix()
        if rel in _CLASSIFY_SEND_ALLOWLIST or rel in _INVENTORIED_CONSUMERS:
            continue
        text = path.read_text(encoding="utf-8")
        if not any(h in text for h in _CLASSIFY_HINTS):
            continue
        if not any(h in text for h in _SEND_HINTS):
            continue
        offenders.append(rel)
    assert offenders == [], (
        "new classification→send module(s) not in the NEVER_AUTO_ACTION "
        f"inventory/allowlist: {offenders}. Add a refuse + inventory row "
        "(see audit/never-auto-action-consumer-audit-20260726.md)."
    )


def test_app_does_not_import_session_classify():
    """Pin: app.py routes secret-prompt detection through
    ``_record_macro.is_secret_prompt_line`` and must not import
    ``session.classify`` directly — which would place it in the
    classify→send audit perimeter (WO-P5-069)."""
    app_src = (_PKG_ROOT / "app.py").read_text(encoding="utf-8")
    assert "session.classify" not in app_src, (
        "app.py must not import session.classify directly; "
        "use _record_macro.is_secret_prompt_line() instead"
    )
