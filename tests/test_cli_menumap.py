"""`tw menumap` wiring + fixture printout (WO-P2-OPS-VERB-G1)."""

from __future__ import annotations

import json

from tw2002_aiclient.menu import knowledge as menu_knowledge
from tw2002_aiclient.menu.map_view import (
    format_menu_map_report,
    menu_map_summary_from_store,
)
from tw2002_aiclient.menu.sig import menu_signature
from tw2002_aiclient.session import cli

SCREEN_A = "=== Computer ===\n(1) Status\n(2) Ship\n"


def test_menumap_verb_is_wired():
    parser = cli.build_parser()
    help_text = parser.format_help()
    assert "menumap" in help_text
    args = parser.parse_args(["menumap", "--path", "/tmp/gk.json"])
    assert args.func is cli.cmd_menumap
    assert args.path == "/tmp/gk.json"
    assert args.world_id is None
    assert not hasattr(args, "profile")


def test_menumap_verb_accepts_world_id_and_json():
    parser = cli.build_parser()
    args = parser.parse_args(["menumap", "--world-id", "host__a__h", "--json"])
    assert args.world_id == "host__a__h"
    assert args.json is True
    assert args.path is None


def test_knowledge_path_for_world_joins_under_state(tmp_path):
    path = menu_knowledge.knowledge_path_for_world("slug_a", state_dir=tmp_path)
    assert path == tmp_path / "world" / "slug_a" / "game_knowledge.json"


def test_cmd_menumap_prints_coverage_orphans_matching_fixture(tmp_path, capsys, monkeypatch):
    path = tmp_path / "game_knowledge.json"
    menu_knowledge.upsert_menu_node(path, "sig-a", label="Computer")
    menu_knowledge.upsert_menu_node(path, "sig-b", label="Ship")
    menu_knowledge.upsert_menu_node(path, "sig-z", label="Orphan")
    menu_knowledge.upsert_menu_edge(path, "sig-a", "2", "sig-b", kind="nav")

    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: False)
    args = cli.build_parser().parse_args(["menumap", "--path", str(path)])
    assert cli.cmd_menumap(args) == 0
    out = capsys.readouterr().out
    expected = "\n".join(
        format_menu_map_report(
            menu_map_summary_from_store(path, current_sig=None),
        )
    )
    assert out.strip() == expected
    assert "orphans: sig-z" in out
    assert "dead-ends: sig-b" in out
    assert "here off-map" in out
    assert "3n" in out


def test_cmd_menumap_json_output(tmp_path, capsys, monkeypatch):
    path = tmp_path / "game_knowledge.json"
    menu_knowledge.upsert_menu_node(path, "sig-a", label="Computer")

    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: False)
    args = cli.build_parser().parse_args(["menumap", "--path", str(path), "--json"])
    assert cli.cmd_menumap(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["path"] == str(path)
    assert payload["node_count"] == 1
    assert payload["current"] is None


def test_cmd_menumap_live_localize_sets_here_star(tmp_path, capsys, monkeypatch):
    path = tmp_path / "game_knowledge.json"
    sig = menu_signature(SCREEN_A)
    menu_knowledge.upsert_menu_node(path, sig, label="Computer")

    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: True)

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        assert verb == "screen"
        assert args_payload == {}
        return {"ok": True, "screen": SCREEN_A.splitlines()}

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = cli.build_parser().parse_args(["menumap", "--path", str(path)])
    assert cli.cmd_menumap(args) == 0
    out = capsys.readouterr().out
    assert "here ★ Computer" in out


def test_cmd_menumap_world_id_resolves_path(tmp_path, capsys, monkeypatch):
    path = menu_knowledge.knowledge_path_for_world("demo_world", state_dir=tmp_path)
    menu_knowledge.upsert_menu_node(path, "sig-a", label="Root")

    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: False)
    monkeypatch.setattr(
        menu_knowledge,
        "knowledge_path_for_world",
        lambda slug, state_dir=None: path,
    )
    args = cli.build_parser().parse_args(
        ["menumap", "--world-id", "demo_world", "--json"]
    )
    assert cli.cmd_menumap(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["path"] == str(path)
    assert payload["node_count"] == 1
