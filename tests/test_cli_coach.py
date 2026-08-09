"""``tw coach show`` — WO-WIRE-STRATEGY-CARD-TRADEOFFS-OKF-REFS.

``coach_kb.py`` requires ``tradeoffs``/``okf_refs`` on every ``StrategyCard``,
but the live DECISIONS-panel renderer (``compose_decisions_coach``) never
reads them. This CLI verb is the tip-honest render path — pin that it
actually surfaces both fields, for a real shipped card and for a filesystem
fixture, in both text and ``--json`` shapes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tw2002_aiclient import coach_cli
from tw2002_aiclient.session import cli

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_parser_registers_coach_show():
    parser = cli.build_parser()
    args = parser.parse_args(["coach", "show", "pair_trade_loop"])
    assert args.func is coach_cli.cmd_coach_show
    assert args.id == "pair_trade_loop"
    sub = next(a for a in parser._actions if getattr(a, "choices", None) is not None)
    assert "coach" in sub.choices


def test_show_by_id_text_includes_tradeoffs_and_okf_refs(capsys):
    parser = cli.build_parser()
    rc = coach_cli.cmd_coach_show(
        parser.parse_args(["coach", "show", "pair_trade_loop"])
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "tradeoffs:" in out
    assert "Smaller faster loops can beat fatter slow ones." in out
    assert "okf_refs:" in out
    assert "/strategies/pair-trade-loops.md" in out


def test_show_by_id_json_includes_tradeoffs_and_okf_refs(capsys):
    parser = cli.build_parser()
    rc = coach_cli.cmd_coach_show(
        parser.parse_args(["coach", "show", "pair_trade_loop", "--json"])
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    card = payload["card"]
    assert card["id"] == "pair_trade_loop"
    assert card["tradeoffs"], "tradeoffs must not be dropped from the JSON shape"
    assert "Smaller faster loops can beat fatter slow ones." in card["tradeoffs"]
    assert card["okf_refs"] == [
        "/strategies/pair-trade-loops.md",
        "/strategies/port-economics.md",
    ]


def test_unverified_card_is_marked_in_text_output(capsys):
    parser = cli.build_parser()
    rc = coach_cli.cmd_coach_show(parser.parse_args(["coach", "show", "toll_math"]))
    assert rc == 0
    out = capsys.readouterr().out
    assert "(unverified)" in out
    assert "hypothesis_flags:" in out


def test_unknown_id_fails_closed_text(capsys):
    parser = cli.build_parser()
    rc = coach_cli.cmd_coach_show(parser.parse_args(["coach", "show", "no_such_card"]))
    assert rc == 1
    out = capsys.readouterr().out
    assert "unknown" in out.lower()


def test_unknown_id_fails_closed_json(capsys):
    parser = cli.build_parser()
    rc = coach_cli.cmd_coach_show(
        parser.parse_args(["coach", "show", "no_such_card", "--json"])
    )
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"ok": False, "error": "unknown_id", "id": "no_such_card"}


def test_omitted_id_lists_every_shipped_card_briefly(capsys):
    parser = cli.build_parser()
    rc = coach_cli.cmd_coach_show(parser.parse_args(["coach", "show"]))
    assert rc == 0
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 8, "strategies.json ships eight cards"
    assert "pair_trade_loop" in out
    # The brief listing intentionally omits the wide fields (no dump into a
    # panel-shaped strip) — only show/--json carry tradeoffs/okf_refs.
    assert "tradeoffs:" not in out


def test_omitted_id_json_lists_full_cards_incl_tradeoffs(capsys):
    parser = cli.build_parser()
    rc = coach_cli.cmd_coach_show(parser.parse_args(["coach", "show", "--json"]))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    cards = payload["cards"]
    assert len(cards) == 8
    by_id = {c["id"]: c for c in cards}
    assert by_id["pair_trade_loop"]["tradeoffs"]
    assert by_id["pair_trade_loop"]["okf_refs"]


def test_strategies_override_reads_a_fixture(tmp_path, capsys):
    doc = {
        "version": 1,
        "strategies": [
            {
                "id": "fixture_card",
                "title": "Fixture",
                "what": "W",
                "when_trigger": "docked_at_port",
                "tradeoffs": ["risk one"],
                "steps": ["step one"],
                "okf_refs": ["/strategies/fixture.md"],
                "hypothesis_flags": [],
            }
        ],
    }
    path = tmp_path / "strategies.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    parser = cli.build_parser()
    rc = coach_cli.cmd_coach_show(
        parser.parse_args(
            ["coach", "show", "fixture_card", "--strategies", str(path), "--json"]
        )
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["card"]["tradeoffs"] == ["risk one"]
    assert payload["card"]["okf_refs"] == ["/strategies/fixture.md"]


def test_malformed_strategies_path_fails_closed(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    parser = cli.build_parser()
    rc = coach_cli.cmd_coach_show(
        parser.parse_args(["coach", "show", "--strategies", str(path)])
    )
    assert rc == 1


@pytest.mark.parametrize("card_id", [
    "pair_trade_loop",
    "route_longevity",
    "dead_end_planet",
    "toll_math",
    "planet_production",
    "holds_first",
    "top_profit_chain",
    "explore_density",
])
def test_every_shipped_card_shows_without_raising(card_id, capsys):
    """No card's authored content trips the renderer (e.g. empty tradeoffs)."""
    parser = cli.build_parser()
    rc = coach_cli.cmd_coach_show(parser.parse_args(["coach", "show", card_id]))
    assert rc == 0
    out = capsys.readouterr().out
    assert card_id in out
