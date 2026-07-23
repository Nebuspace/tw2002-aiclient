"""Play-screen panel wiring from mocked ``tw status`` (WO-AICLIENT-PLAY-PANELS)."""

from __future__ import annotations

from tw2002_aiclient import adapters


def _healthy_status(**extra):
    base = {
        "ok": True,
        "mode": "auto_loop",
        "credits": 12_500,
        "turns_left": 400,
        "fighters_aboard": 5,
        "prompt": "Command [TL=04:00:00]:[2642]",
        "autopilot": {
            "running": True,
            "ticks_done": 3,
            "last_error": None,
            "last_reason": "highest EV: explore",
        },
        "autopilot_trace": None,
        "intervention": {
            "needs_attention": False,
            "reasons": [],
            "autopilot": {
                "running": True,
                "ticks_done": 3,
                "last_error": None,
                "last_reason": "highest EV: explore",
            },
            "mode": "auto_loop",
        },
    }
    base.update(extra)
    return base


def test_compose_play_panels_metrics_and_goals_focus():
    panels = adapters.compose_play_panels(_healthy_status(), width=36)
    assert "2642" in panels["metrics"]
    assert "12500" in panels["metrics"] or "12,500" in panels["metrics"]
    assert "400" in panels["metrics"]
    assert any("GOALS" in ln for ln in panels["goals"])
    assert any("FOCUS" in ln for ln in panels["focus"])
    assert any("GOALS" in ln for ln in panels["priorities"])
    assert any("FOCUS" in ln for ln in panels["priorities"])
    assert panels["needs_attention"] is False
    assert panels["mode"] == "auto_loop"


def test_compose_play_panels_focus_from_trace():
    trace = {
        "chosen": "explore",
        "candidates": [
            {"kind": "explore", "ev_cr_per_turn": 10.0, "gated": False},
            {"kind": "run_chain", "ev_cr_per_turn": 5.0, "gated": True},
        ],
    }
    panels = adapters.compose_play_panels(_healthy_status(autopilot_trace=trace), width=40)
    focus_body = "\n".join(panels["focus"])
    assert "Explore" in focus_body or "explore" in focus_body.lower()
    decisions_body = "\n".join(panels["decisions"])
    assert "DECISIONS" in decisions_body
    assert decisions_body.count("—") < len(decisions_body.splitlines())  # not empty placeholder only


def test_compose_play_panels_attention_and_log():
    status = _healthy_status(
        mode="human",
        intervention={
            "needs_attention": True,
            "reasons": [
                {"code": "autopilot_halted", "detail": "credit floor"},
                {"code": "fighters_unknown"},
                {"code": "credits_stale", "detail": {"age_ms": 20000}},
                {"code": "totally_new_code"},
            ],
            "autopilot": {
                "running": False,
                "ticks_done": 9,
                "last_error": "credit floor",
                "last_reason": None,
            },
            "mode": "human",
        },
        autopilot={
            "running": False,
            "ticks_done": 9,
            "last_error": "credit floor",
            "last_reason": None,
        },
    )
    panels = adapters.compose_play_panels(status, width=72)
    assert panels["needs_attention"] is True
    assert panels["attention_banner"] == (
        "! autopilot halted; fighters unknown; credits stale; totally_new_code"
    )
    assert panels["reason_labels"] == [
        "autopilot halted",
        "fighters unknown",
        "credits stale",
        "totally_new_code",
    ]
    log = "\n".join(panels["log"])
    assert "autopilot halted" in log
    assert "fighters unknown" in log
    assert "credits stale" in log
    assert "totally_new_code" in log
    assert "credits_stale" not in log  # labeled, not raw snake_case
    assert "fighters_unknown" not in log
    assert "credit floor" in log


def test_intervention_reason_label_known_and_passthrough():
    assert adapters.intervention_reason_label("fighters_unknown") == "fighters unknown"
    assert adapters.intervention_reason_label("autopilot_halted") == "autopilot halted"
    assert adapters.intervention_reason_label("autopilot_no_candidates") == (
        "autopilot no candidates"
    )
    assert adapters.intervention_reason_label("autopilot_max_ticks_exhausted") == (
        "autopilot max ticks exhausted"
    )
    assert adapters.intervention_reason_label("autopilot_game_select") == (
        "autopilot game select"
    )
    assert adapters.intervention_reason_label("explore_exhausted") == "explore exhausted"
    assert adapters.intervention_reason_label("custom_future") == "custom_future"
    assert adapters.intervention_reason_label(None) == "?"
    assert adapters.intervention_reason_label("") == "?"


def test_compose_play_panels_labels_new_halt_codes():
    """Post INTERVENTION-AP-HALT-ATTENTION codes must label on compose."""
    status = _healthy_status(
        intervention={
            "needs_attention": True,
            "reasons": [
                {"code": "autopilot_no_candidates", "detail": "no_candidates"},
                {
                    "code": "autopilot_max_ticks_exhausted",
                    "detail": "max_ticks_exhausted",
                },
                {"code": "autopilot_game_select", "detail": "game_select"},
                {"code": "explore_exhausted", "detail": "explore_exhausted"},
            ],
            "autopilot": {
                "running": False,
                "ticks_done": 12,
                "last_error": None,
                "last_reason": "no_candidates",
                "stop_reason": "game_select",
            },
            "mode": "auto_loop",
        },
        autopilot={
            "running": False,
            "ticks_done": 12,
            "last_error": None,
            "last_reason": "no_candidates",
            "stop_reason": "game_select",
        },
    )
    panels = adapters.compose_play_panels(status, width=96)
    assert panels["needs_attention"] is True
    assert panels["reason_labels"] == [
        "autopilot no candidates",
        "autopilot max ticks exhausted",
        "autopilot game select",
        "explore exhausted",
    ]
    assert panels["attention_banner"] == (
        "! autopilot no candidates; autopilot max ticks exhausted; "
        "autopilot game select; explore exhausted"
    )
    log = "\n".join(panels["log"])
    assert "autopilot_no_candidates" not in log
    assert "autopilot no candidates" in log
    assert "explore exhausted" in log


def test_goals_snapshot_from_status_unknowns():
    snap = adapters.goals_snapshot_from_status({"ok": True})
    assert snap.credits_known is False
    assert snap.turns_known is False
    assert snap.fighters_known is False


def test_sector_from_status_prompt():
    assert adapters.sector_from_status(
        {"prompt": "Command [TL=04:00:00]:[8816]"}
    ) == 8816
    assert adapters.sector_from_status({"prompt": "Password?"}) is None
