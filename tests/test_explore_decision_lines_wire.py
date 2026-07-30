"""WO-WIRE-EXPLORE-DECISION-LINES — DECISIONS next-hop overlay + wire field."""

from __future__ import annotations

from types import SimpleNamespace

from tw2002_aiclient import explore
from tw2002_aiclient.cockpit.decisions import compose_decisions_lines
from tw2002_aiclient.session import sector_explore as sx


def test_wire_exposes_next_sector_and_dock_new_ports():
    report = sx.ExploreReport(
        world_id="w",
        started_at="t",
        min_sectors=1,
        intent=explore.INTENT_MAP_FILL,
        dock_new_ports=True,
        next_sector=42,
    )
    wire = sx.explore_run_wire(sx.ExploreSnapshot(running=True, report=report))
    assert wire["run"]["next_sector"] == 42
    assert wire["run"]["dock_new_ports"] is True


def test_wire_next_sector_null_when_unknown():
    report = sx.ExploreReport(world_id="w", started_at="t", min_sectors=1)
    wire = sx.explore_run_wire(sx.ExploreSnapshot(running=True, report=report))
    assert "next_sector" in wire["run"]
    assert wire["run"]["next_sector"] is None
    assert wire["run"]["dock_new_ports"] is False


def test_composer_from_run_map_fill_with_hop():
    lines = explore.explore_decision_lines_from_run(
        {
            "intent": explore.INTENT_MAP_FILL,
            "next_sector": 9,
        }
    )
    assert lines is not None
    assert lines[0] == "MAP-FILL"
    assert "→9" in lines[1]


def test_composer_from_run_map_fill_no_frontier():
    lines = explore.explore_decision_lines_from_run(
        {"intent": explore.INTENT_MAP_FILL, "next_sector": None}
    )
    assert lines is not None
    assert lines[0] == "MAP-FILL"
    assert lines[1] == "no frontier"


def test_composer_from_run_stardock():
    lines = explore.explore_decision_lines_from_run(
        {
            "intent": explore.INTENT_FIND_STARDOCK,
            "next_sector": 7,
        }
    )
    assert lines is not None
    assert lines[0] == "FIND-SD"
    assert "→7" in lines[1]


def test_composer_from_run_rejects_unknown_intent():
    assert explore.explore_decision_lines_from_run({"intent": "nope"}) is None
    assert explore.explore_decision_lines_from_run(None) is None


def test_compose_decisions_prefers_explore_overlay():
    status = {
        explore.EXPLORE_DECISION_LINES_KEY: ["MAP-FILL", "next →3", "(live)"],
        "autopilot_trace": {
            "chosen": "trade",
            "candidates": [
                {
                    "kind": "trade",
                    "gated": False,
                    "ev_cr_per_turn": 1.0,
                    "rationale": "should not win",
                }
            ],
        },
    }
    lines = compose_decisions_lines(status, width=60)
    assert lines[0] == "MAP-FILL"
    assert "→3" in lines[1]


def test_merge_explore_decision_lines_is_vocabulary_producer():
    """Guard-facing shape: merged[KEY]=…; return merged."""
    out = explore.merge_explore_decision_lines({}, ["MAP-FILL", "next →1"])
    assert out[explore.EXPLORE_DECISION_LINES_KEY][0] == "MAP-FILL"
    assert explore.merge_explore_decision_lines({"a": 1}, None) == {"a": 1}


def test_poll_sets_and_clears_decision_overlay(monkeypatch):
    from tw2002_aiclient import app as app_mod
    from tw2002_aiclient import adapters

    play = object.__new__(app_mod.PlayShellScreen)
    play.status_line = ""
    play.explore_band = None
    play.explore_decision_lines = ["stale"]
    play.world_stats = SimpleNamespace(refresh=lambda *_a, **_k: None)
    play.profile = SimpleNamespace()

    live = adapters.ExploreResult(
        ok=True,
        reason=None,
        raw={
            "ok": True,
            "running": True,
            "run": {
                "intent": explore.INTENT_MAP_FILL,
                "next_sector": 11,
                "distinct_sectors": 1,
                "min_sectors": 5,
                "outcome": None,
            },
        },
    )
    monkeypatch.setattr(adapters, "explore_status", lambda **_k: live)
    assert app_mod._poll_explore_status(play, run_dir=None) is True
    assert play.explore_decision_lines is not None
    assert play.explore_decision_lines[0] == "MAP-FILL"
    assert "→11" in play.explore_decision_lines[1]

    done = adapters.ExploreResult(
        ok=True,
        reason=None,
        raw={
            "ok": True,
            "running": False,
            "run": {
                "intent": explore.INTENT_MAP_FILL,
                "next_sector": 11,
                "distinct_sectors": 5,
                "min_sectors": 5,
                "outcome": "completed",
            },
        },
    )
    monkeypatch.setattr(adapters, "explore_status", lambda **_k: done)
    assert app_mod._poll_explore_status(play, run_dir=None) is False
    assert play.explore_decision_lines is None
    assert play.explore_band is None
