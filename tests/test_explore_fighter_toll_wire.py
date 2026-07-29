"""WO-FIGHTER-TOLL-POLICY-WIRE: the guarded consumer for `fighter_toll_policy`.

Until this WO the policy was a producer with no consumer -- fully tested, fully
correct, and permanently starved: `#206` built the decision logic, `#207` gave
the screen a class, and no product module imported either. This file pins the
wire that finally lets it fire, and -- more importantly -- pins every way it
must refuse to.

The wire is deliberately nested INSIDE the explore loop's existing halt branch,
so it can only ever convert a screen the loop was already stopping on into a
decided action. It cannot widen what the loop drives, and with `fight_tolls`
off it does not execute at all. Both of those are pinned below, because they
are the whole safety argument.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from tw2002_aiclient import world_model
from tw2002_aiclient.loops.player import OUTCOME_HALTED
from tw2002_aiclient.session import fighter_toll_policy as ftp
from tw2002_aiclient.session import sector_explore as sx
from tw2002_aiclient.session.control_lock import ControlLock

from .conftest import FakeAttachSession

WORLD = "w-toll"

COUNTS = "Your fighters: 9 vs. theirs: 1"

ENCOUNTER = (
    "Corp fighters block your path.\n"
    f"{COUNTS}\n"
    "Option? (A,D,I,R,S,?):?"
)

QTY = (
    "Deploying fighters.\n"
    f"{COUNTS}\n"
    "How many fighters do you wish to use (0 to 250) [0]?"
)

SECTOR = (
    "Sector  : 4309 in uncharted space.\n"
    "Warps to Sector(s) :  (158)\n"
    "\n"
    "Command [TL=00753:0/0/0/850]:[4309] (?=Help)? : "
)


class _TollSession(FakeAttachSession):
    """Scripted encounter -> quantity -> resolved sector.

    `sent` is the base class's own ``(text, enter, secret)`` log rather than a
    private list, so the assertions read what the driver actually called and
    not what this double assumed it would.
    """

    def __init__(self, *, first: str = ENCOUNTER, after_attack: str = QTY):
        super().__init__(initial_screen=first)
        self.rx_count = 1
        self.last_rx = -10.0
        self._after_attack = after_attack

    def send(self, text, enter=True, secret=False, sender="app"):
        key = text.strip().upper()
        if key == "A":
            self._screen = self._after_attack
        elif key == "R" or key.isdigit():
            self._screen = SECTOR
        return super().send(text, enter=enter, secret=secret, sender=sender)


def _letters_sent(session) -> list[str]:
    return [t[0].strip() for t in session.sent]


def _run(session, tmp_path, *, fight_tolls, turn_budget=5):
    world_model.upsert_sector(
        WORLD, {"sector_id": 4309, "warps": [158], "landmarks": []}, state_dir=tmp_path
    )
    runner = sx.ExploreRunner(
        session, ControlLock(), state_dir=tmp_path, timeout_s=2.0, debounce_ms=1
    )
    runner.start(WORLD, min_sectors=1, turn_budget=turn_budget, fight_tolls=fight_tolls)
    return runner.stop(join_timeout=10.0).report


# --- Accept 1: a real product caller exists ------------------------------


def test_the_explore_loop_is_a_real_product_caller_of_the_policy():
    """The defect this WO closes was 'nobody imports it'. Pinned structurally
    via AST rather than by observing behaviour, because behaviour could be
    satisfied by a re-implementation that quietly forks the policy's rules."""
    tree = ast.parse(inspect.getsource(sx))
    imports_policy = any(
        isinstance(n, ast.ImportFrom)
        and any(a.name == "fighter_toll_policy" for a in n.names)
        for n in ast.walk(tree)
    )
    assert imports_policy, "sector_explore must import the policy module itself"

    called = {
        n.func.attr
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }
    assert "next_encounter_input" in called


# --- Accept 3 + the safety argument: disarmed is a structural no-op -------


def test_a_disarmed_run_never_consults_the_policy_at_all(tmp_path, monkeypatch):
    """Not merely 'sends nothing' -- the policy must not even be ASKED.

    A wire that computes a decision and then declines to send it is one edit
    away from sending it. Pinning the call itself keeps the disarmed path a
    structural no-op rather than a suppressed action.
    """
    calls = []
    monkeypatch.setattr(
        ftp, "next_encounter_input",
        lambda *a, **k: calls.append(a) or ftp.EncounterDecision(False, None, "spy"),
    )
    session = _TollSession()
    report = _run(session, tmp_path, fight_tolls=False)
    assert calls == []
    assert _letters_sent(session) == []
    assert report.outcome == OUTCOME_HALTED


def test_an_armed_run_fights_the_winnable_encounter_through_the_quantity_step(tmp_path):
    """The happy path, end to end: Attack, then the bounded quantity commit.

    `9 vs 1` is force_share 0.90 -- exactly Max's ratified gate -- and the
    quantity step commits `min(max(theirs,1), max_avail)` = 1, never `max`.
    """
    session = _TollSession()
    _run(session, tmp_path, fight_tolls=True)
    assert _letters_sent(session)[:2] == ["A", "1"]


# --- Accept 2: no key is never permission to send ------------------------


def test_not_encounter_leaves_the_ordinary_halt_verdict_untouched(tmp_path):
    """`detected=False` is the policy saying "not my screen". The loop must
    keep its own verdict rather than treating a non-answer as a green light."""
    session = _TollSession(first="Some screen we do not know.\nWhat now? ")
    report = _run(session, tmp_path, fight_tolls=True)
    assert _letters_sent(session) == []
    assert report.outcome == OUTCOME_HALTED
    assert report.reason != sx.HALT_FIGHT_POLICY_STOP


@pytest.mark.parametrize(
    "decision,expected",
    [
        (ftp.EncounterDecision(True, None, "pvp_hard_stop", halt=True),
         sx.HALT_FIGHT_POLICY_STOP),
        # THE Accept-2 case: detected, no key, and halt left at its dataclass
        # default of False. Nothing here says "stop", and nothing says "send"
        # either -- absence of a key must be read as refusal on its own.
        (ftp.EncounterDecision(True, None, "not_encounter_but_detected"),
         sx.HALT_FIGHT_NO_KEY),
        # A key the policy should never produce. Pinned anyway: this module's
        # allowlist is a second layer, not a restatement of the policy's logic.
        (ftp.EncounterDecision(True, "P", "would_pay"),
         sx.HALT_FIGHT_FORBIDDEN_KEY),
        (ftp.EncounterDecision(True, "D", "would_duck"),
         sx.HALT_FIGHT_FORBIDDEN_KEY),
        # Digits without a quantity-commit reason: the shape an unrelated
        # numeric prompt would present.
        (ftp.EncounterDecision(True, "250", "some_other_reason"),
         sx.HALT_FIGHT_FORBIDDEN_KEY),
    ],
)
def test_every_undecided_or_disallowed_key_halts_and_sends_nothing(
    tmp_path, monkeypatch, decision, expected
):
    monkeypatch.setattr(ftp, "next_encounter_input", lambda *a, **k: decision)
    session = _TollSession()
    report = _run(session, tmp_path, fight_tolls=True)
    assert _letters_sent(session) == [], "a refused decision must reach no socket"
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == expected


def test_halt_false_is_not_permission_at_the_predicate_level():
    """The same claim as above, one layer down, so it survives a refactor of
    the loop: `halt=False` is the dataclass DEFAULT, so a future policy branch
    that forgets to set it must still not be able to send."""
    d = ftp.EncounterDecision(True, None, "forgot_to_set_halt")
    assert d.halt is False
    assert d.key is None
    assert not sx._fight_key_permitted(d.key, d.reason)


# --- Accept 6: Pay is never sent -----------------------------------------


def test_pay_is_forbidden_by_name_not_merely_absent_from_the_allowlist():
    """`P` is enumerated in `FIGHT_FORBIDDEN_KEYS` so that widening the
    allowlist later cannot silently admit it. Both facts pinned: it is refused,
    AND the refusal survives someone adding it to the allowed set."""
    assert not sx._fight_key_permitted("P", "qty_commit:1:max=9")
    assert not sx._fight_key_permitted("p", "attack_npc:share=0.99")
    assert "P" in sx.FIGHT_FORBIDDEN_KEYS
    assert sx.FIGHT_LETTER_ALLOWLIST == frozenset({"A", "R"})
    assert not (sx.FIGHT_LETTER_ALLOWLIST & sx.FIGHT_FORBIDDEN_KEYS)


def test_the_policy_itself_never_returns_pay_on_a_pay_offering_screen():
    """Belt and braces across the seam: the wire refuses `P`, and the policy
    does not produce it even when the screen offers it."""
    screen = f"Fighters: 1 (Somecorp) [Toll]\n{COUNTS}\nOption? (A,D,I,R,P,S,?):?"
    decision = ftp.next_encounter_input(screen, "Option? (A,D,I,R,P,S,?):?")
    assert decision.key != "P"


@pytest.mark.parametrize(
    "key,reason,allowed",
    [
        ("A", "attack_npc:share=0.95", True),
        ("R", "retreat_band_exceeded", True),
        ("1", "qty_commit:1:max=250", True),
        ("250", "qty_commit:250:max=250", True),
        ("1", "attack_npc:share=0.95", False),   # digits need a qty reason
        ("P", "qty_commit:1:max=9", False),
        ("", "qty_commit:1:max=9", False),
        (None, "qty_commit:1:max=9", False),
        (3, "qty_commit:3:max=9", False),        # not a str
    ],
)
def test_the_allowlist_admits_exactly_what_it_claims(key, reason, allowed):
    assert sx._fight_key_permitted(key, reason) is allowed


# --- a send that cannot be confirmed is not a completed action ------------


def test_an_unconfirmed_send_halts_rather_than_guessing_the_next_key(
    tmp_path, monkeypatch
):
    """`confirmed=False` means the screen did not become what we expected.
    Guessing the next keystroke into a live combat screen is exactly the
    failure this module exists to prevent -- and the send still counts."""
    monkeypatch.setattr(
        sx._settle, "send_and_confirm", lambda *a, **k: ("desync", 0.1, False)
    )
    session = _TollSession()
    report = _run(session, tmp_path, fight_tolls=True)
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == sx.HALT_FIGHT_CONFIRM_FAILED
    assert report.sends_issued >= 1


# --- the arm is refused, not coerced -------------------------------------


@pytest.mark.parametrize("bad", ["no", "false", 0, 1, None, ""])
def test_a_non_bool_arm_is_refused_rather_than_coerced(tmp_path, bad):
    """`fight_tolls="no"` is truthy in Python. Coercing it would arm combat
    from a string the caller meant as a refusal."""
    runner = sx.ExploreRunner(
        _TollSession(), ControlLock(), state_dir=tmp_path, timeout_s=2.0, debounce_ms=1
    )
    with pytest.raises(sx.ExploreRefused) as exc:
        runner.start(WORLD, min_sectors=1, turn_budget=5, fight_tolls=bad)
    assert str(exc.value) == "invalid_fight_tolls"


def test_the_arm_defaults_off_at_every_layer():
    """Three independent defaults, pinned together: the report field, the
    runner signature, and the CLI flag. #208 merged hours before this WO
    precisely because an arm defaulted ON in one layer."""
    assert sx.ExploreReport(world_id="w", started_at="t", min_sectors=1).fight_tolls is False
    assert inspect.signature(sx.ExploreRunner.start).parameters["fight_tolls"].default is False

    from tw2002_aiclient.session import cli

    args = cli.build_parser().parse_args(["explore", "start", "--world-id", "w"])
    assert args.fight_tolls is False


def test_the_daemon_forwards_the_arm_and_defaults_it_off():
    """`ARGS_EXPLORE_START` accepting the key is not the same as the daemon
    forwarding it -- a key the protocol accepts and drops would leave the CLI
    flag inert while looking wired."""
    assert "fight_tolls" in sx.ARGS_EXPLORE_START

    from tw2002_aiclient.session import protocol

    tree = ast.parse(inspect.getsource(protocol))
    starts = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "start"
    ]
    assert any(
        any(k.arg == "fight_tolls" for k in call.keywords) for call in starts
    ), "protocol must forward fight_tolls to runner.start"
