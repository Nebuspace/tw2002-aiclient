"""`tw menumap` wiring + fixture printout (WO-FA8 / FA13)."""

from twclient import cli
from twclient import game_knowledge
from twclient.menu_map_view import format_menu_map_report, menu_map_summary_from_store


def test_menumap_verb_is_wired():
    parser = cli.build_parser()
    args = parser.parse_args(["menumap", "--path", "/tmp/gk.json"])
    assert args.func is cli.cmd_menumap
    assert args.path == "/tmp/gk.json"
    assert args.profile is None
    assert args.world_id is None


def test_menumap_verb_accepts_world_id_and_profile():
    parser = cli.build_parser()
    args = parser.parse_args(["menumap", "--world-id", "host__a__h", "--json"])
    assert args.world_id == "host__a__h"
    assert args.json is True
    args2 = parser.parse_args(["menumap", "--profile", "demo"])
    assert args2.profile == "demo"


def test_cmd_menumap_prints_coverage_orphans_matching_fixture(tmp_path, capsys, monkeypatch):
    path = tmp_path / "game_knowledge.json"
    game_knowledge.upsert_menu_node(path, "sig-a", label="Computer")
    game_knowledge.upsert_menu_node(path, "sig-b", label="Ship")
    game_knowledge.upsert_menu_node(path, "sig-z", label="Orphan")
    game_knowledge.upsert_menu_edge(path, "sig-a", "2", "sig-b", kind="nav")

    monkeypatch.setattr(cli, "daemon_alive", lambda: False)
    args = cli.build_parser().parse_args(["menumap", "--path", str(path)])
    cli.cmd_menumap(args)
    out = capsys.readouterr().out
    expected = "\n".join(format_menu_map_report(
        menu_map_summary_from_store(path, current_sig=None),
    ))
    assert out.strip() == expected
    assert "orphans: sig-z" in out
    assert "dead-ends: sig-b" in out
    assert "here off-map" in out
    assert "3n" in out
