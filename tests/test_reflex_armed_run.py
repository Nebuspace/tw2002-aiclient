"""WO-REFLEX-ARMED-RUN -- an approved proposal becomes a run only via a human `y`.

The claim has two halves and they fail in opposite directions, so they are
proven separately throughout:

* **Nothing arms without the key.** Every input except a literal `y`/`Y`
  performs zero launch calls. Most of this file is that half.
* **The key actually arms.** A flow that can never launch satisfies the first
  half perfectly. `test_a_typed_y_reaches_the_real_autoloop_start` and the
  keycode-adapter tests are the controls that stop this file from passing on
  a surface that does nothing at all -- which is exactly what the obvious
  wiring (`resolve_arm_confirm_key(typed_string)`) silently builds.

Drift is pinned **one identity field per test**. A single combined test that
mutated all three at once would pass if any one of them were compared, and the
whole point is that all three are.
"""

from __future__ import annotations

import ast
import inspect
import io
from pathlib import Path

import pytest

from tw2002_aiclient.cockpit.armconfirm import CANCEL, CONFIRM
from tw2002_aiclient.rule_engine import Decision
from tw2002_aiclient.rules import arm as arm_mod
from tw2002_aiclient.rules.arm import (
    IDENTITY_INCOMPLETE,
    NON_INTERACTIVE,
    resolve_typed_confirm,
    run_arm_flow,
)
from tw2002_aiclient.rules.reflex import (
    ARGS_REFLEX_ARM,
    PROPOSAL_IDENTITY,
    STOP_PROPOSAL_DRIFT,
    proposal_drift,
)
from tw2002_aiclient.session import cli

MAIN_COMMAND_SCREEN = b"Command [TL=00:00:00]:[1] (?=Help)? :"


class _StubSocket:
    def sendall(self, _data):
        return None

    def close(self):
        return None


class _BareServer:
    """No `autoloop` -- `_autoloop_runner` reads it via `getattr`."""


class _Snapshot:
    report = None
    running = True


class _SpyRunner:
    """Records what `_dispatch_autoloop_start` asked it to play.

    `snapshot()` is required, not optional: `_status_response` -- which this
    verb calls to take its fresh reading -- routes through
    `autoloop.observe(runner, lock)`, so a runner double without it fails
    before the code under test is reached.
    """

    def __init__(self, refuse=None):
        self.started = []
        self._refuse = refuse

    def snapshot(self):
        from tw2002_aiclient.session.autoloop import AutoLoopSnapshot

        return AutoLoopSnapshot(running=False)

    def start(self, name, floor=None, turn_budget=None, cycles=None):
        self.started.append((name, floor, turn_budget, cycles))
        if self._refuse is not None:
            from tw2002_aiclient.session import autoloop

            raise autoloop.AutoLoopRefused(self._refuse)
        return self.snapshot()


class _Server:
    def __init__(self, runner):
        self.autoloop = runner


class Tty(io.StringIO):
    """A stdin double that claims to be a terminal."""

    def isatty(self):
        return True


class Pipe(io.StringIO):
    """A stdin double that is honest about not being one."""

    def isatty(self):
        return False


class _Launch:
    """Launch spy. `calls` is the evidence for every zero-launch claim."""

    def __init__(self, reply=None):
        self.calls = []
        self.reply = reply if reply is not None else {"ok": True, "started": True}

    def __call__(self, payload):
        self.calls.append(payload)
        return self.reply


def _flow(block, classification="port_menu", typed="y\n", stream_in=None, reply=None):
    launch = _Launch(reply)
    out = io.StringIO()
    code = run_arm_flow(
        block,
        classification,
        launch=launch,
        stream_in=stream_in if stream_in is not None else Tty(typed),
        stream_out=out,
    )
    return code, out.getvalue(), launch.calls


# ---------------------------------------------------------------------------
# The keycode adapter -- Accept 3 and its indispensable control
# ---------------------------------------------------------------------------


def test_a_typed_y_confirms_even_though_the_policy_speaks_keycodes():
    """The control that catches the camouflaged failure.

    `resolve_arm_confirm_key("y")` is CANCEL -- it takes an int keycode. A CLI
    that forwards the typed string straight to the policy therefore builds a
    flow that can never arm, while satisfying every zero-launch requirement in
    this file. Without this assertion the whole suite passes on a dead surface.
    """
    assert resolve_typed_confirm("y") == CONFIRM
    assert resolve_typed_confirm("Y") == CONFIRM
    assert resolve_typed_confirm("y\n") == CONFIRM, "readline always brings the newline"
    assert resolve_typed_confirm(" y \n") == CONFIRM, "surrounding whitespace is a typo"


def test_the_policy_really_would_have_rejected_the_raw_string():
    """Pins *why* the adapter exists, so deleting it fails loudly here too."""
    from tw2002_aiclient.cockpit.armconfirm import resolve_arm_confirm_key

    assert resolve_arm_confirm_key("y") == CANCEL
    assert resolve_arm_confirm_key(ord("y")) == CONFIRM


def test_only_y_and_Y_confirm_across_every_printable_key():
    """Exhaustive over the printable range rather than a hand-picked list --
    a curated set only proves the author thought of those."""
    confirming = [chr(i) for i in range(32, 127) if resolve_typed_confirm(chr(i)) == CONFIRM]
    assert confirming == ["Y", "y"]


@pytest.mark.parametrize(
    "typed",
    ["", "\n", "n", "N", "no", "yes", "YES", "yy", "y y", " ", "\t", "q", "1", "ok"],
)
def test_no_other_typed_answer_confirms(typed):
    assert resolve_typed_confirm(typed) == CANCEL


def test_yes_is_cancelled_deliberately():
    """`yes` is not `y`. A money-path prompt that starts inferring intent from
    near-misses has stopped being a confirmation."""
    assert resolve_typed_confirm("yes") == CANCEL


@pytest.mark.parametrize("value", [None, 121, True, b"y", ["y"], object()])
def test_a_non_string_answer_cannot_confirm(value):
    """Including `121` -- `ord("y")`. Nothing but a typed line reaches here, so
    a caller passing the keycode directly is a caller bypassing the prompt."""
    assert resolve_typed_confirm(value) == CANCEL


def test_the_module_names_no_confirm_key_of_its_own():
    """Single authority. If this module grew its own `y`/`Y` set it could drift
    out of step with `armconfirm`'s, and the two would disagree silently."""
    source = Path(arm_mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    literals = [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]
    assert "y" not in literals and "Y" not in literals


# ---------------------------------------------------------------------------
# Accept 2 -- nothing to arm performs zero launch
# ---------------------------------------------------------------------------


def test_no_candidate_never_prompts_and_never_launches():
    code, out, calls = _flow({"macro": None, "stop_reason": "autopilot_no_candidates"})
    assert calls == []
    assert code == 0, "a STOP is an answer, matching cmd_reflex's documented doctrine"
    assert "autopilot_no_candidates" in out
    assert "LIVE?" not in out, "a prompt was raised for a proposal that does not exist"


def test_a_typed_stop_reports_its_own_reason():
    code, out, calls = _flow({"macro": None, "stop_reason": "autopilot_rules_unreadable:partial"})
    assert calls == []
    assert "autopilot_rules_unreadable:partial" in out


def test_a_proposal_block_that_is_not_even_a_mapping_launches_nothing():
    for block in (None, [], "nope", 7):
        code, out, calls = _flow(block)
        assert calls == []
        assert "LIVE?" not in out


# ---------------------------------------------------------------------------
# Accept 3 -- every non-`y` input performs zero launch, through the real flow
# ---------------------------------------------------------------------------


GOOD_BLOCK = {"macro": "dock", "rule_id": "dock-when-idle"}


@pytest.mark.parametrize("typed", ["\n", "n\n", "N\n", "no\n", "yes\n", "q\n", " \n", "yy\n"])
def test_the_flow_launches_nothing_for_any_answer_but_y(typed):
    code, out, calls = _flow(GOOD_BLOCK, typed=typed)
    assert calls == [], f"{typed!r} armed a live run"
    assert code == 0
    assert "cancelled" in out


def test_bare_enter_cancels():
    """Canon: "Enter alone must never fire". It cancels for being not-`y`,
    which is why there is no Enter branch anywhere to get wrong."""
    _, out, calls = _flow(GOOD_BLOCK, typed="\n")
    assert calls == []
    assert "cancelled" in out


def test_end_of_input_cancels():
    """Ctrl-D at the prompt. `readline` returns "" and nothing arms."""
    code, out, calls = _flow(GOOD_BLOCK, typed="")
    assert calls == []
    assert code == 0
    assert "end of input" in out


def test_a_pipe_is_refused_rather_than_read():
    """`echo y | tw reflex --arm` is a `--yes` flag in different syntax.

    The WO forbids the flag; arriving through stdin instead of argv does not
    make it a different thing. Note the piped text IS `y` -- if this ever
    starts reading pipes, this test goes red rather than quietly arming.
    """
    code, out, calls = _flow(GOOD_BLOCK, stream_in=Pipe("y\n"))
    assert calls == [], "a piped 'y' armed a live run"
    assert code == 1
    assert NON_INTERACTIVE in out


def test_a_stream_that_cannot_say_whether_it_is_a_tty_is_refused():
    """Fail-closed: "could not establish a human is present" and "no human" have
    to arrive at the same place."""

    class Mute(io.StringIO):
        def isatty(self):
            raise OSError("no fd")

    code, out, calls = _flow(GOOD_BLOCK, stream_in=Mute("y\n"))
    assert calls == []
    assert code == 1


def test_an_incomplete_identity_is_never_offered_for_confirmation():
    """A confirmation has to be *of* something. Asking "arm this?" about a
    proposal we cannot name would collect a real `y` for an unnamed act."""
    for block in ({"macro": "dock"}, {"macro": "dock", "rule_id": ""}):
        code, out, calls = _flow(block)
        assert calls == []
        assert code == 1
        assert IDENTITY_INCOMPLETE in out


def test_an_absent_classification_is_never_offered_for_confirmation():
    code, out, calls = _flow(GOOD_BLOCK, classification=None)
    assert calls == []
    assert IDENTITY_INCOMPLETE in out


# ---------------------------------------------------------------------------
# Accept 4 -- `y` launches, exactly once, carrying the identity that was shown
# ---------------------------------------------------------------------------


def test_a_typed_y_launches_exactly_once_with_the_identity_on_the_glass():
    code, out, calls = _flow(GOOD_BLOCK, typed="y\n")
    assert calls == [
        {"rule_id": "dock-when-idle", "macro": "dock", "classification": "port_menu"}
    ]
    assert code == 0
    # The full success line. `"armed" in out` would pass on `"not armed"` --
    # i.e. on the cancellation this test exists to distinguish from a launch.
    assert "armed — running dock (rule dock-when-idle)" in out


def test_the_prompt_shows_what_runs_and_why_it_was_chosen():
    _, out, _ = _flow(GOOD_BLOCK, typed="n\n")
    assert "Arm dock LIVE?  y/N" in out, "canon's confirm-line wording"
    assert "dock-when-idle" in out and "port_menu" in out


def test_a_daemon_refusal_after_confirmation_is_reported_not_swallowed():
    code, out, calls = _flow(
        GOOD_BLOCK, typed="y\n", reply={"ok": False, "error": "already_running"}
    )
    assert len(calls) == 1
    assert "already_running" in out
    # The success wording in full. `"armed —"` alone is a SUBSTRING of
    # `"not armed — already_running"`, so the obvious assertion passes on the
    # refusal it was written to catch and fails on the code that is correct.
    assert "armed — running" not in out, "a refusal was rendered as a successful arm"
    assert "not armed" in out


# ---------------------------------------------------------------------------
# Accept 5 -- drift, one identity field at a time
# ---------------------------------------------------------------------------


FRESH = Decision(macro="dock", rule_id="dock-when-idle")
CLAIM = {"rule_id": "dock-when-idle", "macro": "dock", "classification": "main_command"}


def test_an_unchanged_proposal_does_not_drift():
    """The control. Without it every drift test below passes on a function
    that returns a reason unconditionally."""
    assert proposal_drift(CLAIM, decision=FRESH, classification="main_command") is None


@pytest.mark.parametrize("field", PROPOSAL_IDENTITY)
def test_each_identity_field_is_compared_on_its_own(field):
    """One test per field. A combined mutation would pass if ANY single field
    were checked, which is precisely the bug worth catching."""
    claimed = dict(CLAIM)
    claimed[field] = "something-else"
    drift = proposal_drift(claimed, decision=FRESH, classification="main_command")
    assert drift == f"{STOP_PROPOSAL_DRIFT}:{field}"


@pytest.mark.parametrize("field", PROPOSAL_IDENTITY)
def test_an_absent_field_drifts_rather_than_matching_a_null(field):
    """The vacuous-match guard.

    `rule_id` is None on document-level outcomes and `classification` is None
    for an unnamed screen, so an omitted field compared `None == None` would
    *pass* and arm a run whose identity was never established.

    **Every other field is made to match exactly, and the drift is asserted by
    name.** The first draft of this test asserted only `drift is not None` with
    a fixture where two fields differed -- so deleting the guard still produced
    a drift, just on a different field, and the mutant survived a test written
    to kill it. An assertion that any refusal happened cannot prove a specific
    refusal happened.
    """
    fresh = {"rule_id": "dock-when-idle", "macro": "dock", "classification": "main_command"}
    fresh[field] = None  # the null an omitted claim could silently match
    claimed = {k: v for k, v in fresh.items() if k != field}
    decision = Decision(macro=fresh["macro"], rule_id=fresh["rule_id"])

    drift = proposal_drift(claimed, decision=decision, classification=fresh["classification"])
    assert drift == f"{STOP_PROPOSAL_DRIFT}:{field}", (
        f"omitting {field} was compared None == None and passed as a match"
    )


def test_a_claim_that_is_not_a_mapping_drifts():
    for claimed in (None, [], "dock", 3):
        assert proposal_drift(claimed, decision=FRESH, classification="main_command")


# ---------------------------------------------------------------------------
# Accept 5 + 4 through the REAL daemon path -- no fake in the load-bearing spot
# ---------------------------------------------------------------------------


def _live_session(tmp_path, monkeypatch, approve=True):
    """A real store holding one (approved) rule + a session parked on the
    screen that rule matches. Only the socket is a stub."""
    from tw2002_aiclient.rules import store as store_mod
    from tw2002_aiclient.session.session import Session

    state = tmp_path / "state"
    monkeypatch.setattr(store_mod, "STATE_DIR", state)

    def run(argv):
        args = cli.build_parser().parse_args(argv + ["--state-dir", str(state)])
        return args.func(args)

    run(["rule", "draft", "--rule-id", "dock-when-idle", "--screen", "main_command",
         "--do", "dock", "--priority", "10"])
    if approve:
        run(["rule", "approve", "dock-when-idle"])

    session = Session("twgs.test.example", 23, None, str(tmp_path))
    session.conn._sock = _StubSocket()
    session.terminal.feed(MAIN_COMMAND_SCREEN)
    return session


def test_a_typed_y_reaches_the_real_autoloop_start(tmp_path, monkeypatch, capsys):
    """Accept 4 end to end: real store, real selection, real dispatch, real
    `_dispatch_autoloop_start`. Only the runner is a spy, and only so the
    assertion can name what it was asked to play."""
    from tw2002_aiclient.session import protocol

    session = _live_session(tmp_path, monkeypatch)
    capsys.readouterr()
    runner = _SpyRunner()

    preview = protocol.dispatch(session, "reflex", {}, _BareServer())
    assert preview["reflex"]["macro"] == "dock"

    resp = protocol.dispatch(
        session,
        "reflex_arm",
        {"rule_id": "dock-when-idle", "macro": "dock", "classification": "main_command"},
        _Server(runner),
    )
    assert resp["ok"] is True
    assert runner.started == [
        ("dock", None, None, None)
    ], "the existing player was not the launcher"


def test_the_launched_name_is_read_from_the_fresh_decision_not_the_caller():
    """Structural, because behaviourally this is **unfalsifiable**.

    The drift check has already proven `args["macro"] == decision.macro` by the
    time the delegation happens, so swapping one for the other changes no
    observable output -- a behavioural test asserting `name == "dock"` passes
    either way and pins nothing. (Written that way first; the mutation pass is
    what exposed it.)

    The property is still worth holding: the value that reaches the player
    should come from this snapshot, so that weakening the comparison could
    never widen into "the caller names the macro". A property that only exists
    in the source has to be asserted about the source.
    """
    from tw2002_aiclient.session import protocol

    tree = ast.parse(Path(protocol.__file__).read_text(encoding="utf-8"))
    func = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_dispatch_reflex_arm"
    )
    delegations = [
        n for n in ast.walk(func)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "_dispatch_autoloop_start"
    ]
    assert len(delegations) == 1, "the WO allows exactly one delegation"

    # Payload is built then passed (may carry cycles for repeating scope);
    # the name that launches must still come from decision.macro.
    arg0 = delegations[0].args[0]
    assert isinstance(arg0, ast.Name) and arg0.id == "payload"
    decision_macros = [
        n
        for n in ast.walk(func)
        if isinstance(n, ast.Attribute)
        and n.attr == "macro"
        and isinstance(n.value, ast.Name)
        and n.value.id == "decision"
    ]
    assert decision_macros, (
        "the launched name is not read from an attribute of the fresh decision"
    )


@pytest.mark.parametrize(
    "field,bogus",
    [("rule_id", "some-other-rule"), ("macro", "sell"), ("classification", "port_menu")],
)
def test_drift_in_any_field_starts_no_player(tmp_path, monkeypatch, capsys, field, bogus):
    """Accept 5 at the daemon boundary, one field at a time, with a spy runner
    so "no player started" is evidence rather than inference."""
    from tw2002_aiclient.session import protocol

    session = _live_session(tmp_path, monkeypatch)
    capsys.readouterr()
    runner = _SpyRunner()
    claim = {"rule_id": "dock-when-idle", "macro": "dock", "classification": "main_command"}
    claim[field] = bogus

    resp = protocol.dispatch(session, "reflex_arm", claim, _Server(runner))
    assert resp["ok"] is False
    assert resp["error"] == f"{STOP_PROPOSAL_DRIFT}:{field}"
    assert runner.started == [], f"drifted {field} still started a run"


def test_a_library_that_now_proposes_nothing_says_why_rather_than_drift(
    tmp_path, monkeypatch, capsys
):
    """Reserved vocabulary: `autopilot_no_candidates` says *why* there is no
    proposal and drift says "there is one and it is not yours". Collapsing them
    would be true but would send the operator to the wrong next move."""
    from tw2002_aiclient.session import protocol

    session = _live_session(tmp_path, monkeypatch, approve=False)
    capsys.readouterr()
    runner = _SpyRunner()

    resp = protocol.dispatch(
        session, "reflex_arm",
        {"rule_id": "dock-when-idle", "macro": "dock", "classification": "main_command"},
        _Server(runner),
    )
    assert resp["ok"] is False
    assert resp["error"].startswith("autopilot_no_candidates")
    assert STOP_PROPOSAL_DRIFT not in resp["error"]
    assert runner.started == []


def test_a_daemon_without_a_player_refuses_through_the_existing_path(
    tmp_path, monkeypatch, capsys
):
    """Proves delegation actually reaches `_dispatch_autoloop_start` -- the
    refusal is that function's own, not one this verb re-spelled."""
    from tw2002_aiclient.session import protocol

    session = _live_session(tmp_path, monkeypatch)
    capsys.readouterr()
    resp = protocol.dispatch(
        session, "reflex_arm",
        {"rule_id": "dock-when-idle", "macro": "dock", "classification": "main_command"},
        _BareServer(),
    )
    assert resp == {"ok": False, "error": "autoloop_unavailable"}


def test_a_runner_refusal_reaches_the_caller_unre_spelled(tmp_path, monkeypatch, capsys):
    from tw2002_aiclient.session import protocol

    session = _live_session(tmp_path, monkeypatch)
    capsys.readouterr()
    resp = protocol.dispatch(
        session, "reflex_arm",
        {"rule_id": "dock-when-idle", "macro": "dock", "classification": "main_command"},
        _Server(_SpyRunner(refuse="already_running")),
    )
    assert resp == {"ok": False, "error": "already_running"}


def test_unsupported_args_are_refused_not_ignored(tmp_path, monkeypatch, capsys):
    """A silently-dropped `cycles` would be a surface agreeing to a repetition
    it does not perform."""
    from tw2002_aiclient.session import protocol

    session = _live_session(tmp_path, monkeypatch)
    capsys.readouterr()
    runner = _SpyRunner()
    resp = protocol.dispatch(
        session, "reflex_arm",
        {"rule_id": "dock-when-idle", "macro": "dock",
         "classification": "main_command", "cycles": 10},
        _Server(runner),
    )
    assert resp == {"ok": False, "error": "unsupported_arg:cycles"}
    assert runner.started == []


def test_the_verb_accepts_only_the_identity():
    assert set(ARGS_REFLEX_ARM) == set(PROPOSAL_IDENTITY)
    for forbidden in ("cycles", "force", "yes", "floor"):
        assert forbidden not in ARGS_REFLEX_ARM


# ---------------------------------------------------------------------------
# Accept 1 -- plain `tw reflex` unchanged
# ---------------------------------------------------------------------------


def test_plain_reflex_never_requests_the_arm_verb(monkeypatch, capsys):
    """Accept 1. The evidence is the recorded verb list, not the printed text:
    output could look identical while a request went out."""
    verbs = []

    def fake_send(verb, payload, **kw):
        verbs.append(verb)
        return {
            "ok": True,
            "classification": "main_command",
            "reflex": {"macro": "dock", "rule_id": "r1", "stop_reason": None},
        }

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = cli.build_parser().parse_args(["reflex"])
    code = args.func(args)
    out = capsys.readouterr().out

    assert verbs == ["reflex"], "plain `tw reflex` reached the arm verb"
    assert code == 0
    assert "proposes: dock" in out
    assert "not armed" in out
    assert "LIVE?" not in out


def test_the_arm_flag_is_off_by_default():
    assert cli.build_parser().parse_args(["reflex"]).arm is False
    assert cli.build_parser().parse_args(["reflex", "--arm"]).arm is True


def test_arm_and_json_together_are_refused(monkeypatch, capsys):
    """`--json` returns before the prompt, so honouring both would print a
    preview and silently not arm -- and a machine-readable arm flow is the
    scriptable confirmation this WO exists to prevent."""
    sent = []
    monkeypatch.setattr(cli, "send_request", lambda v, p, **k: sent.append(v) or {"ok": True})
    args = cli.build_parser().parse_args(["reflex", "--arm", "--json"])
    code = args.func(args)
    assert code == 1
    assert sent == [], "a request went out for a refused flag combination"
    assert "cannot be combined" in capsys.readouterr().out


def test_the_cli_hands_over_the_raw_classification_not_the_display_fallback(
    monkeypatch, capsys
):
    """`cmd_reflex` renders `classification or "unknown"` for the screen line.

    Feeding *that* to the arm flow would claim the human confirmed a screen
    class the daemon never reported -- and, worse, would let the flow prompt
    at all, since `"unknown"` is a perfectly usable string. The two paths are
    told apart by which refusal comes back: an absent class must reach the
    flow absent, so it refuses to ask rather than asking about "unknown".
    """
    monkeypatch.setattr(
        cli, "send_request",
        lambda v, p, **k: {
            "ok": True,
            "classification": None,
            "reflex": {"macro": "dock", "rule_id": "r1", "stop_reason": None},
        },
    )
    monkeypatch.setattr("sys.stdin", Tty("n\n"))
    args = cli.build_parser().parse_args(["reflex", "--arm"])
    code = args.func(args)
    out = capsys.readouterr().out

    assert IDENTITY_INCOMPLETE in out, "the display fallback reached the arm flow"
    assert "LIVE?" not in out, "a confirmation was offered for an unnamed screen"
    assert code == 1


def test_the_arm_flag_takes_no_value():
    """`--arm=yes` must not parse. A flag that accepts a value is one rename
    away from being the `--yes` the WO forbids."""
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["reflex", "--arm=yes"])


# ---------------------------------------------------------------------------
# Accept 6 -- the launch path structurally cannot send
# ---------------------------------------------------------------------------


_TRANSPORT_NAMES = {"send_request", "sendall", "send", "connect", "socket", "recv"}


def _call_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _imported_modules(tree):
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mods.add(node.module or "")
            mods.update(a.name for a in node.names)
    return mods


def test_the_arm_module_holds_no_transport_at_all():
    """Accept 6 as a property of the file rather than a promise about it.

    AST, not text: this module's docstring *discusses* `send_request` at length
    while explaining that it holds none, and a text scan cannot tell a citation
    from the thing cited -- the failure mode that bit three guards on #222/#223.
    """
    tree = ast.parse(Path(arm_mod.__file__).read_text(encoding="utf-8"))
    assert not (_call_names(tree) & _TRANSPORT_NAMES)
    assert not (_imported_modules(tree) & {"socket", "session.cli", "tw2002_aiclient.session.cli"})


def test_that_guard_would_actually_catch_a_send():
    """Control. Without it the assertion above passes on a broken extractor."""
    tree = ast.parse("import socket\ndef f(s):\n    return s.sendall(b'x')\n")
    assert _call_names(tree) & _TRANSPORT_NAMES
    assert _imported_modules(tree) & {"socket"}


def test_the_flow_signature_carries_no_way_to_answer_the_prompt():
    """No `yes`, no `force`, no bool of any name. A caller wanting to bypass
    the human would have to add a parameter, visibly."""
    sig = inspect.signature(run_arm_flow)
    for name, param in sig.parameters.items():
        assert not isinstance(param.default, bool), f"{name} is a boolean switch"
        assert name not in {"yes", "assume_yes", "force", "auto", "confirm", "no_prompt"}


def test_the_launch_callable_is_required():
    """`launch` has no default, so a caller cannot get a flow that silently
    launches through some module-level fallback."""
    assert inspect.signature(run_arm_flow).parameters["launch"].default is inspect.Parameter.empty
