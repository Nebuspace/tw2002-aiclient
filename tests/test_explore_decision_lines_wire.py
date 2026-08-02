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


def test_composer_from_run_formations():
    lines = explore.explore_decision_lines_from_run(
        {
            "intent": explore.INTENT_FIND_FORMATIONS,
            "next_sector": 7,
        }
    )
    assert lines is not None
    assert lines[0] == "FORMATIONS"
    assert "→7" in lines[1]


def test_composer_from_run_rejects_unknown_intent():
    assert explore.explore_decision_lines_from_run({"intent": "nope"}) is None
    assert explore.explore_decision_lines_from_run(None) is None


def test_composer_appends_dock_and_tolls_markers():
    from tw2002_aiclient.cockpit import explore_flags

    both = explore.explore_decision_lines_from_run(
        {
            "intent": explore.INTENT_MAP_FILL,
            "next_sector": 3,
            "dock_new_ports": True,
            "fight_tolls": True,
        }
    )
    assert both is not None
    assert both[-1] == f"{explore_flags.DOCK_MARKER} {explore_flags.TOLLS_MARKER}"

    dock_only = explore.explore_decision_lines_from_run(
        {
            "intent": explore.INTENT_MAP_FILL,
            "next_sector": 3,
            "dock_new_ports": True,
            "fight_tolls": False,
        }
    )
    assert dock_only is not None
    assert dock_only[-1] == explore_flags.DOCK_MARKER
    assert explore_flags.TOLLS_MARKER not in dock_only[-1]


def test_composer_dock_off_is_stated_not_silent():
    from tw2002_aiclient.cockpit import explore_flags

    lines = explore.explore_decision_lines_from_run(
        {
            "intent": explore.INTENT_FIND_STARDOCK,
            "next_sector": None,
            "dock_new_ports": False,
            "fight_tolls": False,
        }
    )
    assert lines is not None
    assert lines[-1] == explore_flags.DOCK_OFF_MARKER
    assert explore_flags.DOCK_MARKER not in lines[-1]
    assert explore_flags.TOLLS_MARKER not in lines[-1]


def test_composer_omits_flags_line_when_keys_absent():
    """No invented +dock when the wire never named the arm state."""
    from tw2002_aiclient.cockpit import explore_flags

    lines = explore.explore_decision_lines_from_run(
        {"intent": explore.INTENT_MAP_FILL, "next_sector": 1}
    )
    assert lines is not None
    joined = " ".join(lines)
    assert explore_flags.DOCK_MARKER not in joined
    assert explore_flags.DOCK_OFF_MARKER not in joined
    assert explore_flags.TOLLS_MARKER not in joined


def test_composer_non_bool_flags_do_not_invent_markers():
    from tw2002_aiclient.cockpit import explore_flags

    lines = explore.explore_decision_lines_from_run(
        {
            "intent": explore.INTENT_MAP_FILL,
            "next_sector": 1,
            "dock_new_ports": "yes",
            "fight_tolls": "no",
        }
    )
    assert lines is not None
    joined = " ".join(lines)
    assert explore_flags.DOCK_MARKER not in joined
    assert explore_flags.TOLLS_MARKER not in joined


def test_composer_appends_turns_remaining():
    lines = explore.explore_decision_lines_from_run(
        {
            "intent": explore.INTENT_MAP_FILL,
            "next_sector": 2,
            "turns_remaining": 42,
        }
    )
    assert lines is not None
    assert lines[-1] == "turns 42"


def test_composer_turns_zero_is_honest():
    lines = explore.explore_decision_lines_from_run(
        {
            "intent": explore.INTENT_FIND_STARDOCK,
            "next_sector": None,
            "turns_remaining": 0,
        }
    )
    assert lines is not None
    assert lines[-1] == "turns 0"


def test_composer_omits_turns_when_absent_or_invalid():
    for bad in (None, True, -1, "42", 3.5):
        run = {"intent": explore.INTENT_MAP_FILL, "next_sector": 1}
        if bad is not None:
            run["turns_remaining"] = bad
        lines = explore.explore_decision_lines_from_run(run)
        assert lines is not None
        assert not any(isinstance(x, str) and x.startswith("turns ") for x in lines)


def test_composer_flags_then_turns_order():
    from tw2002_aiclient.cockpit import explore_flags

    lines = explore.explore_decision_lines_from_run(
        {
            "intent": explore.INTENT_MAP_FILL,
            "next_sector": 1,
            "dock_new_ports": True,
            "fight_tolls": False,
            "turns_remaining": 7,
        }
    )
    assert lines is not None
    assert lines[-2] == explore_flags.DOCK_MARKER
    assert lines[-1] == "turns 7"


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


def test_poll_sets_decision_overlay_for_formations(monkeypatch):
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
                "intent": explore.INTENT_FIND_FORMATIONS,
                "next_sector": 13,
                "distinct_sectors": 1,
                "min_sectors": 5,
                "outcome": None,
            },
        },
    )
    monkeypatch.setattr(adapters, "explore_status", lambda **_k: live)
    assert app_mod._poll_explore_status(play, run_dir=None) is True
    assert play.explore_decision_lines is not None
    assert play.explore_decision_lines[0] == "FORMATIONS"
    assert "→13" in play.explore_decision_lines[1]
