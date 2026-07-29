"""WO-REFLEX-CLIENT-REACH -- adapter + `tw reflex` CLI, both read-only.

Two properties carry this slice:

1. **Transport honesty.** `ok` is about whether the daemon answered, never
   about what it said. A proposal that resolves to a STOP is a *successful*
   call. Collapsing those would make "the daemon refused to answer" and "the
   library answered, and the answer is do nothing" the same value -- the
   distinction `rules/reflex.py` split `autopilot_rules_unreadable` out of
   `autopilot_no_candidates` to preserve, thrown away one layer up.

2. **A proposal is not an act.** The operator-visible wording is load-bearing
   here in a way it usually is not: this is the first surface that names a
   macro without running it, and a verb that reads as "doing" would train
   exactly the wrong reflex in the human. Pinned by asserting the forbidden
   vocabulary is absent, with a control proving the check can see it.
"""

from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stdout

import pytest

from tw2002_aiclient import adapters
from tw2002_aiclient.session import cli as cli_mod

OK_PROPOSAL = {
    "ok": True,
    "classification": "main_command",
    "reflex": {"macro": "dock", "rule_id": "dock-when-idle", "stop_reason": None},
}
OK_STOP = {
    "ok": True,
    "classification": "main_command",
    "reflex": {"macro": None, "rule_id": None,
               "stop_reason": "autopilot_no_candidates:main_command"},
}


def _fake_send(resp, seen=None):
    def send(verb, args, run_dir=None):
        if seen is not None:
            seen.append((verb, args))
        if isinstance(resp, Exception):
            raise resp
        return resp
    return send


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


def test_a_proposal_round_trips_with_its_rule_and_screen(monkeypatch):
    monkeypatch.setattr(adapters._cli, "send_request", _fake_send(OK_PROPOSAL))
    r = adapters.reflex_propose(run_dir="/nowhere")

    assert (r.ok, r.macro, r.rule_id, r.classification) == (
        True, "dock", "dock-when-idle", "main_command")
    assert r.stop_reason is None


def test_a_stop_is_a_SUCCESSFUL_call_not_a_failure(monkeypatch):
    """The property this whole adapter exists to keep straight."""
    monkeypatch.setattr(adapters._cli, "send_request", _fake_send(OK_STOP))
    r = adapters.reflex_propose(run_dir="/nowhere")

    assert r.ok is True, "a STOP means the library answered, not that the call failed"
    assert r.macro is None
    assert r.stop_reason == "autopilot_no_candidates:main_command"


def test_a_transport_failure_is_the_only_thing_that_sets_ok_false(monkeypatch):
    """Non-vacuity control for the test above: something DOES set ok=False."""
    monkeypatch.setattr(adapters._cli, "send_request",
                        _fake_send(ConnectionRefusedError("no daemon")))
    r = adapters.reflex_propose(run_dir="/nowhere")

    assert r.ok is False
    assert r.reason == "unknown"
    assert "ConnectionRefusedError" in (r.detail or "")
    assert r.macro is None


def test_the_adapter_never_raises_whatever_the_transport_does(monkeypatch):
    for exc in (OSError("boom"), ValueError("bad"), RuntimeError("x"), TimeoutError()):
        monkeypatch.setattr(adapters._cli, "send_request", _fake_send(exc))
        r = adapters.reflex_propose(run_dir="/nowhere")
        assert r.ok is False, f"{type(exc).__name__} escaped as a raise"


def test_a_daemon_error_reply_carries_its_reason(monkeypatch):
    monkeypatch.setattr(adapters._cli, "send_request",
                        _fake_send({"ok": False, "error": "unknown_verb:reflex"}))
    r = adapters.reflex_propose(run_dir="/nowhere")

    assert (r.ok, r.reason) == (False, "unknown_verb:reflex")


def test_an_older_daemon_answering_without_the_block_yields_an_empty_proposal(monkeypatch):
    """Version skew must not become a traceback.

    A daemon predating this verb can answer `ok` with no `reflex` key. Reading
    it defensively turns that into "nothing proposed", which is true, instead
    of an AttributeError in the operator's terminal.
    """
    for payload in ({"ok": True}, {"ok": True, "reflex": None}, {"ok": True, "reflex": []}):
        monkeypatch.setattr(adapters._cli, "send_request", _fake_send(payload))
        r = adapters.reflex_propose(run_dir="/nowhere")
        assert (r.ok, r.macro, r.stop_reason) == (True, None, None)


def test_a_non_dict_reply_is_a_broken_transport_not_an_empty_proposal(monkeypatch):
    """`ok=True, macro=None` would say the library answered 'do nothing'.

    It did not answer at all. These are the two states the whole type exists
    to keep apart, so a garbage reply must land on the failure side.
    """
    monkeypatch.setattr(adapters._cli, "send_request", _fake_send(["not", "a", "dict"]))
    r = adapters.reflex_propose(run_dir="/nowhere")

    assert r.ok is False
    assert r.reason == "malformed_response"


def test_the_adapter_sends_the_reflex_verb_and_no_arguments(monkeypatch):
    """Read-only, proven by what went on the wire rather than by the docstring."""
    seen = []
    monkeypatch.setattr(adapters._cli, "send_request", _fake_send(OK_STOP, seen))
    adapters.reflex_propose(run_dir="/nowhere")

    assert seen == [("reflex", {})], f"expected exactly one bare reflex call, got {seen}"


def test_the_result_type_is_not_shared_with_the_autoloop_family():
    """A shared type invites handing a proposal to a consumer expecting a run."""
    assert adapters.ReflexResult is not adapters.AutoLoopResult
    assert adapters.ReflexResult is not adapters.ExploreResult


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _run_cli(monkeypatch, resp, argv):
    monkeypatch.setattr(cli_mod, "send_request", _fake_send(resp))
    args = cli_mod.build_parser().parse_args(argv)
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = args.func(args)
    return code, buf.getvalue()


def test_the_cli_renders_a_proposal_and_says_it_is_not_armed(monkeypatch):
    code, out = _run_cli(monkeypatch, OK_PROPOSAL, ["reflex"])

    assert code == 0
    assert "dock" in out and "dock-when-idle" in out
    assert "not armed" in out, (
        "naming a macro without saying it is unarmed is the misreading this "
        "surface most invites"
    )


def test_a_stop_renders_as_an_answer_and_exits_zero(monkeypatch):
    """Today, with no rule writer shipped, this is the NORMAL result.

    Exiting non-zero here would make the everyday case look broken and train
    the operator to ignore the channel that reports real refusals.
    """
    code, out = _run_cli(monkeypatch, OK_STOP, ["reflex"])

    assert code == 0
    assert "nothing" in out
    assert "autopilot_no_candidates:main_command" in out
    assert "ERROR" not in out


def test_only_a_transport_failure_exits_nonzero(monkeypatch):
    code, out = _run_cli(monkeypatch, {"ok": False, "error": "daemon_unreachable"}, ["reflex"])

    assert code == 1
    assert "ERROR" in out and "daemon_unreachable" in out


def test_json_mode_emits_the_wire_dict_verbatim(monkeypatch):
    code, out = _run_cli(monkeypatch, OK_PROPOSAL, ["reflex", "--json"])

    assert code == 0
    assert json.loads(out) == OK_PROPOSAL


def test_the_cli_reports_the_screen_class_it_answered_about(monkeypatch):
    """A proposal without the screen it was made for cannot be sanity-checked."""
    _, out = _run_cli(monkeypatch, OK_PROPOSAL, ["reflex"])
    assert "main_command" in out


def test_a_malformed_reflex_block_does_not_crash_the_cli(monkeypatch):
    code, out = _run_cli(monkeypatch, {"ok": True, "reflex": "garbage"}, ["reflex"])
    assert code == 0
    assert "nothing" in out


# ---------------------------------------------------------------------------
# The wording is the safety surface
# ---------------------------------------------------------------------------

_ACTION_WORDS = ("running", "armed and", "executing", "firing", "will run", "started")


def test_the_operator_facing_output_never_claims_the_macro_is_running(monkeypatch):
    _, out = _run_cli(monkeypatch, OK_PROPOSAL, ["reflex"])
    lowered = out.lower()
    offenders = [w for w in _ACTION_WORDS if w in lowered]
    assert offenders == [], (
        f"output implies action: {offenders}. This surface names a macro "
        f"without running it; the wording is what stops that being misread."
    )


def test_that_wording_check_can_actually_see_an_action_word():
    """Control. A substring scan that matched nothing would pass on anything."""
    lowered = "proposes: dock — now running the macro".lower()
    assert [w for w in _ACTION_WORDS if w in lowered] == ["running"]


def test_the_subcommand_help_says_propose_not_run():
    """The `help` string is what an operator reads BEFORE deciding it is safe."""
    parser = cli_mod.build_parser()
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            parser.parse_args(["--help"])
        except SystemExit:
            pass
    help_text = buf.getvalue().lower()
    assert "reflex" in help_text
    # The listing line for `reflex` must not promise execution.
    line = next((ln for ln in help_text.splitlines() if ln.strip().startswith("reflex")), "")
    assert line, "reflex is missing from the top-level help listing"
    assert "run" not in line.replace("run-dir", ""), f"help line implies running: {line!r}"


def test_the_cli_sends_only_the_reflex_verb(monkeypatch):
    """Read-only at the CLI layer too, proven on the wire."""
    seen = []
    monkeypatch.setattr(cli_mod, "send_request", _fake_send(OK_STOP, seen))
    parser = cli_mod.build_parser()
    args = parser.parse_args(["reflex"])
    with redirect_stdout(io.StringIO()):
        args.func(args)

    assert seen == [("reflex", {})]
