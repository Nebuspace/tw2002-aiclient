"""WO-RULE-WRITER-DRAFTS, Accepts 4+5 -- `tw rule draft|approve|list`.

The claim under test is about the **operator-visible boundary**: everything
`tw rule draft` can do leaves a rule inert, and the only thing that changes
that is a human typing `tw rule approve <id>`. `tests/test_rules_writer.py`
proves that of the library; this proves it of the surface an operator actually
reaches, through `build_parser()` and the dispatched handler, because a
guarantee that holds in the module and not at the CLI is not a guarantee.

Exercised through the real parser rather than by calling handlers with a
hand-built namespace: a fake args object carries whatever attributes the test
assumed, and the wiring -- which flag maps to which field, which handler a verb
dispatches to -- is precisely what would be wrong.
"""

from __future__ import annotations

import json

import pytest

from tw2002_aiclient.rules import cli as rule_cli
from tw2002_aiclient.rules.store import read_rule_store
from tw2002_aiclient.session import cli

GOOD = {
    "rule_id": "dock-when-idle",
    "screen_match": "command_prompt",
    "do": "dock",
    "priority": 10,
}


def run(argv, tmp_path):
    """Parse and dispatch exactly as `main()` does. Returns the exit code."""
    args = cli.build_parser().parse_args(argv + ["--state-dir", str(tmp_path)])
    return args.func(args)


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


def test_the_rule_verb_dispatches_to_the_rules_package_handlers():
    parser = cli.build_parser()
    assert parser.parse_args(["rule", "draft", "--rule-id", "x"]).func is rule_cli.cmd_rule_draft
    assert parser.parse_args(["rule", "approve", "x"]).func is rule_cli.cmd_rule_approve
    assert parser.parse_args(["rule", "list"]).func is rule_cli.cmd_rule_list


def test_a_bare_rule_verb_prints_help_rather_than_acting():
    """Mirrors `explore`. A verb tree that did something on its own would make
    `tw rule` a command an operator could run by mistake."""
    args = cli.build_parser().parse_args(["rule"])
    assert args.func(args) == 0


def test_the_shorthand_flags_map_to_the_schema_field_names():
    """`--screen` fills `screen_match`; a rename on either side breaks here
    rather than silently producing a document the parser refuses."""
    args = cli.build_parser().parse_args(
        ["rule", "draft", "--rule-id", "r", "--screen", "s", "--do", "d", "--priority", "7"]
    )
    assert (args.rule_id, args.screen_match, args.do, args.priority) == ("r", "s", "d", 7)


def test_there_is_no_approve_flag_anywhere_on_the_draft_verb():
    """Structural. The guarantee is that an operator cannot ask for approval
    on the writing path, so pin the absence at the surface too."""
    parser = cli.build_parser()
    draft = parser.parse_args(["rule", "draft", "--rule-id", "x"])
    assert not hasattr(draft, "approved")
    with pytest.raises(SystemExit):
        parser.parse_args(["rule", "draft", "--rule-id", "x", "--approved"])
    with pytest.raises(SystemExit):
        parser.parse_args(["rule", "draft", "--rule-id", "x", "--approve"])


# ---------------------------------------------------------------------------
# Behaviour: draft is inert, approve is the crossing
# ---------------------------------------------------------------------------


def test_draft_writes_an_inert_rule_and_says_so(tmp_path, capsys):
    code = run(["rule", "draft", "--rule-id", "dock-when-idle", "--screen",
                "command_prompt", "--do", "dock", "--priority", "10"], tmp_path)
    out = capsys.readouterr().out

    assert code == 0
    assert "draft written" in out
    # The success line is where an author is most likely to assume the rule is
    # live, so the disclaimer has to be there and has to name the next step.
    assert "inert" in out and "tw rule approve" in out

    report = read_rule_store(state_dir=tmp_path, include_drafts=True)
    assert report["rules"] == []
    assert [r.rule_id for r in report["drafts"]] == ["dock-when-idle"]
    assert all(r.approved is False for r in report["drafts"])


def test_approve_is_what_moves_a_rule_into_the_blessed_library(tmp_path, capsys):
    run(["rule", "draft", "--rule-id", "dock-when-idle", "--screen",
         "command_prompt", "--do", "dock", "--priority", "10"], tmp_path)
    capsys.readouterr()

    code = run(["rule", "approve", "dock-when-idle"], tmp_path)
    assert code == 0
    assert "approved: dock-when-idle" in capsys.readouterr().out

    report = read_rule_store(state_dir=tmp_path, include_drafts=True)
    assert [r.rule_id for r in report["rules"]] == ["dock-when-idle"]
    assert report["rules"][0].approved is True
    assert report["drafts"] == []


def test_approve_names_one_rule_and_offers_no_bulk_form():
    """Deliberate friction. `--all` on the one verb that grants live authority
    to AI-authored rules is the feature this design exists to not have."""
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["rule", "approve", "--all"])
    with pytest.raises(SystemExit):
        parser.parse_args(["rule", "approve"])  # rule_id is positional and required
    assert parser.parse_args(["rule", "approve", "a"]).rule_id == "a"


def test_the_json_document_form_can_express_guards_in_authored_order(tmp_path):
    """The reason `--from-file` exists: guard order is authored content that a
    repeatable flag would turn into an accident of assembly."""
    doc = {
        **GOOD,
        "guards": [
            {"fact": "connected", "op": "is_true", "posture": "stop",
             "stop_reason": "autopilot_not_connected"},
            {"fact": "idle_ms", "op": "ge", "value": 500, "posture": "ineligible"},
        ],
    }
    src = tmp_path / "rule.json"
    src.write_text(json.dumps(doc))

    assert run(["rule", "draft", "--from-file", str(src)], tmp_path) == 0
    written = read_rule_store(state_dir=tmp_path, include_drafts=True)["drafts"][0]
    assert [g.fact for g in written.guards] == ["connected", "idle_ms"]
    assert written.guards[0].posture == "stop"
    assert written.approved is False


def test_a_document_from_stdin_is_read_and_validated(tmp_path, monkeypatch, capsys):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(GOOD)))
    assert run(["rule", "draft", "--from-file", "-"], tmp_path) == 0
    assert read_rule_store(state_dir=tmp_path, include_drafts=True)["drafts"][0].rule_id == (
        "dock-when-idle"
    )


# ---------------------------------------------------------------------------
# Refusals are errors here, unlike a reflex STOP
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv, expect",
    [
        (["rule", "draft", "--rule-id", "x"], "missing"),
        (["rule", "draft"], "--from-file"),
        (["rule", "approve", "never-written"], "no draft named"),
    ],
)
def test_a_refusal_exits_1_and_says_why(argv, expect, tmp_path, capsys):
    """`tw reflex` exits 0 on a STOP because a STOP is an answer. Here the
    operator asked for something to be persisted and it was not, so 1."""
    assert run(argv, tmp_path) == 1
    assert expect in capsys.readouterr().err


def test_an_invalid_document_leaves_the_store_untouched(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({**GOOD, "priority": "high"}))

    assert run(["rule", "draft", "--from-file", str(bad)], tmp_path) == 1
    assert "ERROR" in capsys.readouterr().err
    report = read_rule_store(state_dir=tmp_path, include_drafts=True)
    assert report["rules"] == [] and report["drafts"] == []


def test_a_document_that_claims_approval_is_refused_at_the_cli(tmp_path, capsys):
    """The end-to-end version of the writer's refusal: a hand-authored file
    asking to be born approved does not get there through the operator surface
    either."""
    src = tmp_path / "sneaky.json"
    src.write_text(json.dumps({**GOOD, "approved": True}))

    assert run(["rule", "draft", "--from-file", str(src)], tmp_path) == 1
    assert "approved: true" in capsys.readouterr().err
    assert read_rule_store(state_dir=tmp_path, include_drafts=True)["drafts"] == []


def test_unreadable_json_is_named_not_crashed(tmp_path, capsys):
    src = tmp_path / "broken.json"
    src.write_text("{not json")
    assert run(["rule", "draft", "--from-file", str(src)], tmp_path) == 1
    assert "not valid JSON" in capsys.readouterr().err

    assert run(["rule", "draft", "--from-file", str(tmp_path / "absent.json")], tmp_path) == 1
    assert "could not read" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# list keeps the two populations apart
# ---------------------------------------------------------------------------


def test_list_shows_approved_and_draft_rules_as_distinct_populations(tmp_path, capsys):
    run(["rule", "draft", "--rule-id", "blessed", "--screen", "s", "--do", "d",
         "--priority", "1"], tmp_path)
    run(["rule", "approve", "blessed"], tmp_path)
    run(["rule", "draft", "--rule-id", "pending", "--screen", "s", "--do", "d",
         "--priority", "2"], tmp_path)
    capsys.readouterr()

    assert run(["rule", "list"], tmp_path) == 0
    out = capsys.readouterr().out
    assert "approved  blessed" in out
    assert "draft     pending" in out
    assert "cannot fire until approved" in out


def test_list_reports_status_so_empty_is_not_confused_with_unreadable(tmp_path, capsys):
    assert run(["rule", "list", "--json"], tmp_path) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "absent"
    assert payload["rules"] == [] and payload["drafts"] == []


# ---------------------------------------------------------------------------
# Accept 5 -- a draft-only install still answers "nothing", all the way out
# ---------------------------------------------------------------------------


class _StubSocket:
    def sendall(self, _data):
        return None

    def close(self):
        return None


class _BareServer:
    """No `control_lock`/`watch_hub` -- protocol reads both via `getattr`."""


def test_a_draft_only_install_answers_no_candidates_through_the_real_daemon_path(
    tmp_path, monkeypatch, capsys
):
    """Accept 5, without a fake in the load-bearing position.

    The other CLI tests in this repo hand `cmd_reflex` a reply dict they wrote
    themselves. For *this* claim that would be circular: the question is
    whether a store containing only drafts produces `autopilot_no_candidates`,
    and a hand-built `{"stop_reason": "autopilot_no_candidates"}` asserts only
    that the test author can type the string.

    So the chain is real from end to end. `tw rule draft` writes an actual
    file; `protocol.dispatch` runs the actual `_dispatch_reflex` against the
    actual store rooted at `tmp_path`; and the dict the CLI renders is the one
    the daemon just produced, not one composed here. Only the socket is a
    stub, and only so that nothing can reach a wire.
    """
    from tw2002_aiclient.rules import store as store_mod
    from tw2002_aiclient.session import protocol
    from tw2002_aiclient.session.session import Session

    # The real store, pointed at a real temporary root. `rules_dir` reads this
    # global at call time, so the whole read path stays genuine -- patching
    # `read_rule_store` instead would remove the very code under test.
    monkeypatch.setattr(store_mod, "STATE_DIR", tmp_path / "state")

    run(["rule", "draft", "--rule-id", "dock-when-idle", "--screen",
         "main_command", "--do", "dock", "--priority", "10"], tmp_path / "state")
    capsys.readouterr()
    assert (tmp_path / "state" / "rules" / "_drafts" / "dock-when-idle.json").is_file()

    session = Session("twgs.test.example", 23, None, str(tmp_path))
    session.conn._sock = _StubSocket()
    session.terminal.feed(b"Command [TL=00:00:00]:[1] (?=Help)? :")
    resp = protocol.dispatch(session, "reflex", {}, _BareServer())

    assert resp["ok"] is True
    assert resp["classification"] == "main_command"
    assert resp["reflex"]["macro"] is None, (
        "a draft reached selection -- the reflex layer must stay on include_drafts=False"
    )
    assert resp["reflex"]["stop_reason"].startswith("autopilot_no_candidates")

    # Now render the daemon's OWN reply through the operator's verb.
    monkeypatch.setattr(cli, "send_request", lambda *a, **k: resp)
    args = cli.build_parser().parse_args(["reflex"])
    code = args.func(args)
    out = capsys.readouterr().out

    assert code == 0, "a STOP is an answer, not a transport failure"
    assert "proposes: nothing" in out
    assert "autopilot_no_candidates" in out


def test_that_chain_does_fire_once_the_draft_is_approved(tmp_path, monkeypatch, capsys):
    """Control for the test above.

    Without it, `macro is None` is equally consistent with "drafts are
    correctly excluded" and "this wiring cannot produce a macro at all" --
    a store the dispatcher never reads, a classification that never matches.
    The single difference between the two tests is the human's approve step.
    """
    from tw2002_aiclient.rules import store as store_mod
    from tw2002_aiclient.session import protocol
    from tw2002_aiclient.session.session import Session

    monkeypatch.setattr(store_mod, "STATE_DIR", tmp_path / "state")
    state = tmp_path / "state"
    run(["rule", "draft", "--rule-id", "dock-when-idle", "--screen",
         "main_command", "--do", "dock", "--priority", "10"], state)
    run(["rule", "approve", "dock-when-idle"], state)
    capsys.readouterr()

    session = Session("twgs.test.example", 23, None, str(tmp_path))
    session.conn._sock = _StubSocket()
    session.terminal.feed(b"Command [TL=00:00:00]:[1] (?=Help)? :")
    resp = protocol.dispatch(session, "reflex", {}, _BareServer())

    assert resp["reflex"]["macro"] == "dock"
    assert resp["reflex"]["rule_id"] == "dock-when-idle"
    assert resp["reflex"]["stop_reason"] is None


def test_json_output_reports_the_approval_state_it_actually_wrote(tmp_path, capsys):
    run(["rule", "draft", "--rule-id", "r", "--screen", "s", "--do", "d",
         "--priority", "1", "--json"], tmp_path)
    assert json.loads(capsys.readouterr().out)["approved"] is False

    run(["rule", "approve", "r", "--json"], tmp_path)
    assert json.loads(capsys.readouterr().out)["approved"] is True
