"""WO-CATALOG-SOURCE-LIVENESS-SPLIT — provenance vs TCP liveness pins."""

from __future__ import annotations

import json
from pathlib import Path

from tw2002_aiclient import server_inventory as inv


def test_tracked_inventory_status_is_provenance_vocabulary():
    raw = inv.load_inventory()
    for row in raw["servers"]:
        assert row["status"] in inv.PROVENANCE_STATUSES


def test_summary_splits_provenance_from_liveness_and_omits_connectable():
    summary = inv.summarize_inventory()
    assert "connectable" not in summary
    assert "connectable_note" in summary
    assert summary["planning_endpoint_count"] > 0
    assert "listed" in summary["provenance"] or "listed_bbsguide" in summary["provenance"]
    assert inv.LIVENESS_UNPROBED in summary["liveness"]
    assert inv.live_prove_planning_available(summary) is True


def test_listed_plus_unprobed_is_not_no_hosts(tmp_path: Path):
    inventory = {
        "scraped_at_utc": "2026-07-28T00:00:00Z",
        "servers": [
            {
                "name": "Example TWGS",
                "host": "example.invalid",
                "port": 2002,
                "status": "listed",
                "sources": ["test"],
            }
        ],
    }
    inv_path = tmp_path / "servers.inventory.json"
    inv_path.write_text(json.dumps(inventory), encoding="utf-8")
    live_path = tmp_path / "servers.liveness.json"
    # No sidecar → unprobed; must still plan as available hosts.
    summary = inv.summarize_inventory(
        inventory_path=inv_path, liveness_path=live_path
    )
    assert summary["provenance"] == {"listed": 1}
    assert summary["liveness"] == {inv.LIVENESS_UNPROBED: 1}
    assert summary["planning_endpoint_count"] == 1
    assert inv.live_prove_planning_available(summary) is True
    assert "connectable" not in summary


def test_listed_plus_unreachable_still_counts_for_planning(tmp_path: Path):
    inventory = {
        "servers": [
            {
                "name": "Down but listed",
                "host": "down.example",
                "port": 2002,
                "status": "listed",
                "liveness": inv.LIVENESS_UNREACHABLE,
                "last_probed_utc": "2026-07-28T04:00:00Z",
            }
        ]
    }
    summary = inv.summarize_inventory(inventory)
    assert summary["liveness"][inv.LIVENESS_UNREACHABLE] == 1
    assert summary["planning_endpoint_count"] == 1
    assert inv.live_prove_planning_available(summary) is True


def test_sidecar_tcp_open_merges_into_liveness(tmp_path: Path):
    inventory = {
        "servers": [
            {
                "name": "Open host",
                "host": "open.example",
                "port": 2002,
                "status": "listed_bbsguide",
            }
        ]
    }
    inv_path = tmp_path / "inv.json"
    live_path = tmp_path / "live.json"
    inv_path.write_text(json.dumps(inventory), encoding="utf-8")
    live_path.write_text(
        json.dumps(
            {
                "probed_at_utc": "2026-07-28T04:00:00Z",
                "hosts": {
                    "open.example:2002": {
                        "tcp_open": True,
                        "probed_at_utc": "2026-07-28T04:00:00Z",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    summary = inv.summarize_inventory(
        inventory_path=inv_path, liveness_path=live_path
    )
    assert summary["liveness"] == {inv.LIVENESS_TCP_OPEN: 1}
    assert summary["planning_endpoints"][0]["liveness"] == inv.LIVENESS_TCP_OPEN


def test_dead_provenance_excluded_from_planning_endpoints(tmp_path: Path):
    inventory = {
        "servers": [
            {
                "name": "Graveyard",
                "host": "dead.example",
                "port": 23,
                "status": "dead",
            },
            {
                "name": "Listed",
                "host": "live.example",
                "port": 2002,
                "status": "listed",
            },
        ]
    }
    summary = inv.summarize_inventory(inventory)
    assert summary["provenance"]["dead"] == 1
    assert summary["planning_endpoint_count"] == 1
    assert summary["planning_endpoints"][0]["host"] == "live.example"
