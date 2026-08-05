"""``tw servers list`` / ``tw probe`` — WO-BUILD-SERVERS-PROBE-CLI-VERBS."""

from __future__ import annotations

import json
from pathlib import Path

from tw2002_aiclient import catalog_cli
from tw2002_aiclient.session import cli


def test_parser_registers_servers_and_probe():
    parser = cli.build_parser()
    listed = parser.parse_args(["servers", "list"])
    probed = parser.parse_args(["probe", "--limit", "1"])
    assert listed.func is catalog_cli.cmd_servers_list
    assert probed.func is catalog_cli.cmd_probe
    assert probed.limit == 1
    sub = next(a for a in parser._actions if getattr(a, "choices", None) is not None)
    assert "servers" in sub.choices
    assert "probe" in sub.choices


def test_servers_list_json(tmp_path, capsys):
    inv = {
        "scraped_at_utc": "2026-08-05T00:00:00Z",
        "servers": [
            {
                "name": "demo",
                "host": "example.test",
                "port": 2002,
                "status": "listed",
            }
        ],
    }
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(inv), encoding="utf-8")
    live = tmp_path / "live.json"
    live.write_text(json.dumps({"hosts": {}}), encoding="utf-8")
    args = cli.build_parser().parse_args(
        ["servers", "list", "--inventory", str(path), "--liveness", str(live), "--json"]
    )
    assert args.func(args) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["planning_endpoint_count"] == 1
    assert out["provenance"]["listed"] == 1


def test_probe_writes_sidecar(tmp_path, monkeypatch, capsys):
    inv = {
        "scraped_at_utc": "2026-08-05T00:00:00Z",
        "servers": [
            {
                "name": "demo",
                "host": "127.0.0.1",
                "port": 9,
                "status": "listed",
            }
        ],
    }
    inv_path = tmp_path / "inv.json"
    inv_path.write_text(json.dumps(inv), encoding="utf-8")
    out_path = tmp_path / "live.json"

    monkeypatch.setattr(
        catalog_cli,
        "tcp_probe",
        lambda host, port, *, timeout_s: {"tcp_open": True, "error": None},
    )
    args = cli.build_parser().parse_args(
        [
            "probe",
            "--inventory",
            str(inv_path),
            "--out",
            str(out_path),
            "--json",
        ]
    )
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["open_count"] == 1
    assert payload["target_count"] == 1
    disk = json.loads(out_path.read_text(encoding="utf-8"))
    assert disk["hosts"]["127.0.0.1:9"]["tcp_open"] is True


def test_format_servers_report_mentions_planning():
    summary = catalog_cli.format_servers_report(
        {
            "scraped_at_utc": "t",
            "row_count": 1,
            "planning_endpoint_count": 1,
            "provenance": {"listed": 1},
            "liveness": {"unprobed": 1},
            "connectable_note": "absent — do not derive",
            "planning_endpoints": [
                {
                    "name": "demo",
                    "endpoint": "h:1",
                    "provenance": "listed",
                    "liveness": "unprobed",
                }
            ],
        }
    )
    text = "\n".join(summary)
    assert "planning=1" in text
    assert "demo" in text
    assert "live-prove planning: available" in text
