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
    """UPDATED by WO-AUDIT-CLI-MENUMAP-LOOKUP (F4): this test used to assert
    ``here off-map`` with the daemon DOWN, and to build its expected output
    with ``current_sig=None`` and no reason.

    That was asserting the defect. With no daemon there is no live screen,
    ``localize()`` is never called, and nothing about the player's position
    was ever established -- so ``off-map``, which canon reserves for
    localize's own None ("STOP, escalate, never navigate blind",
    canon/engine/menu-map-and-introspection.md:298-302), was a claim the verb
    had not earned. The daemon-down case now renders ``here ? no daemon
    (store only)``.

    Everything this test was actually FOR -- that the printed report matches
    the store summary exactly, with real coverage/dead-end/orphan lines -- is
    unchanged and still asserted; only the you-are-here expectation moved,
    and the expected-output builder now passes the same reason the CLI does.
    """
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
            menu_map_summary_from_store(
                path, current_sig=None, here_unknown="no daemon (store only)"
            ),
        )
    )
    assert out.strip() == expected
    assert "orphans: sig-z" in out
    assert "dead-ends: sig-b" in out
    assert "here ? no daemon (store only)" in out
    assert "off-map" not in out, "with no daemon, nothing looked -- so nothing may claim off-map"
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


def test_menumap_accepts_to_sig():
    parser = cli.build_parser()
    args = parser.parse_args(["menumap", "--path", "/tmp/gk.json", "--to", "sig-b"])
    assert args.to_sig == "sig-b"


def test_cmd_menumap_to_plans_without_send(tmp_path, capsys, monkeypatch):
    path = tmp_path / "game_knowledge.json"
    sig_a = menu_signature(SCREEN_A)
    screen_b = "=== Ship ===\n(Q) Quit\n"
    sig_b = menu_signature(screen_b)
    menu_knowledge.upsert_menu_node(path, sig_a, label="Computer")
    menu_knowledge.upsert_menu_node(path, sig_b, label="Ship")
    menu_knowledge.upsert_menu_edge(path, sig_a, "2", sig_b, kind="nav")

    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: True)

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        assert verb == "screen"
        return {"ok": True, "screen": SCREEN_A.splitlines()}

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = cli.build_parser().parse_args(
        ["menumap", "--path", str(path), "--to", sig_b, "--json"]
    )
    assert cli.cmd_menumap(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["plan"]["ok"] is True
    assert payload["plan"]["steps"][0]["key"] == "2"
    assert payload["plan"]["steps"][0]["to_node"] == sig_b


def test_cmd_menumap_to_refuses_without_daemon(tmp_path, capsys, monkeypatch):
    path = tmp_path / "game_knowledge.json"
    menu_knowledge.upsert_menu_node(path, "sig-a", label="Computer")
    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: False)
    args = cli.build_parser().parse_args(
        ["menumap", "--path", str(path), "--to", "sig-b"]
    )
    assert cli.cmd_menumap(args) == 1
    err = capsys.readouterr().out
    assert "cannot plan_nav" in err
    assert "no daemon" in err


def test_menumap_exec_requires_arm_flag():
    parser = cli.build_parser()
    args = parser.parse_args(
        ["menumap", "--path", "/tmp/gk.json", "--to", "sig-b", "--exec"]
    )
    assert args.exec_nav is True
    assert args.arm_nav is False


def test_cmd_menumap_exec_without_arm_refuses(tmp_path, capsys, monkeypatch):
    path = tmp_path / "game_knowledge.json"
    sig_a = menu_signature(SCREEN_A)
    screen_b = "=== Ship ===\n(Q) Quit\n"
    sig_b = menu_signature(screen_b)
    menu_knowledge.upsert_menu_node(path, sig_a, label="Computer")
    menu_knowledge.upsert_menu_node(path, sig_b, label="Ship")
    menu_knowledge.upsert_menu_edge(path, sig_a, "2", sig_b, kind="nav")
    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: True)
    calls = []

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        calls.append(verb)
        assert verb == "screen"
        return {"ok": True, "screen": SCREEN_A.splitlines()}

    monkeypatch.setattr(cli, "send_request", fake_send)
    ran = []

    def boom(*_a, **_k):
        ran.append(1)
        raise AssertionError("run_nav must not be called unarmed")

    monkeypatch.setattr("tw2002_aiclient.menu_nav_exec.run_nav", boom)
    args = cli.build_parser().parse_args(
        ["menumap", "--path", str(path), "--to", sig_b, "--exec"]
    )
    assert cli.cmd_menumap(args) == 1
    out = capsys.readouterr().out
    assert "requires --arm" in out
    assert ran == []
    assert calls == ["screen"]  # plan only; no do


def test_cmd_menumap_exec_arm_calls_run_nav(tmp_path, capsys, monkeypatch):
    path = tmp_path / "game_knowledge.json"
    sig_a = menu_signature(SCREEN_A)
    screen_b = "=== Ship ===\n(Q) Quit\n"
    sig_b = menu_signature(screen_b)
    menu_knowledge.upsert_menu_node(path, sig_a, label="Computer")
    menu_knowledge.upsert_menu_node(path, sig_b, label="Ship")
    menu_knowledge.upsert_menu_edge(path, sig_a, "2", sig_b, kind="nav")
    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: True)

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        if verb == "screen":
            return {"ok": True, "screen": SCREEN_A.splitlines()}
        raise AssertionError(f"unexpected verb {verb}")

    monkeypatch.setattr(cli, "send_request", fake_send)
    seen = {}

    def fake_run_nav(session, plan, path_arg, *, should_abort, is_armed):
        seen["armed"] = bool(is_armed())
        seen["steps"] = len(plan.get("steps") or [])
        from tw2002_aiclient.menu_nav_exec import NavRunResult

        return NavRunResult(True, "completed", None, 1, 1)

    monkeypatch.setattr("tw2002_aiclient.menu_nav_exec.run_nav", fake_run_nav)
    # Import path used inside cmd_menumap — patch the module attribute after import.
    import tw2002_aiclient.menu_nav_exec as nav_exec

    monkeypatch.setattr(nav_exec, "run_nav", fake_run_nav)
    args = cli.build_parser().parse_args(
        [
            "menumap",
            "--path",
            str(path),
            "--to",
            sig_b,
            "--exec",
            "--arm",
            "--json",
        ]
    )
    assert cli.cmd_menumap(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["exec"]["ok"] is True
    assert payload["exec"]["sends_issued"] == 1
    assert seen["armed"] is True
    assert seen["steps"] == 1


def test_cmd_menumap_json_includes_last_crawl(tmp_path, capsys, monkeypatch):
    path = tmp_path / "game_knowledge.json"
    menu_knowledge.upsert_menu_node(path, "sig-a", label="Computer")
    menu_knowledge.record_crawl_status(
        path, status="complete", nodes_visited=1, frontier_remaining=0
    )
    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: False)
    args = cli.build_parser().parse_args(["menumap", "--path", str(path), "--json"])
    assert cli.cmd_menumap(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["last_crawl"]["status"] == "complete"
    assert payload["last_crawl"]["nodes_visited"] == 1


def test_cmd_menumap_text_shows_last_crawl(tmp_path, capsys, monkeypatch):
    path = tmp_path / "game_knowledge.json"
    menu_knowledge.upsert_menu_node(path, "sig-a", label="Computer")
    menu_knowledge.record_crawl_status(
        path, status="error", reason="structural", nodes_visited=0, frontier_remaining=0
    )
    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: False)
    args = cli.build_parser().parse_args(["menumap", "--path", str(path)])
    assert cli.cmd_menumap(args) == 0
    out = capsys.readouterr().out
    assert "last-crawl: error" in out
    assert "reason=structural" in out
