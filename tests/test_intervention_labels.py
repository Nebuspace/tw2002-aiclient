"""Shared intervention label map — single source for play + spectate."""

from twclient.intervention_labels import (
    INTERVENTION_REASON_LABELS,
    intervention_reason_label,
)
from twclient.spectate_layout import compose_intervention_strip
from tw2002_aiclient import adapters


def test_shared_map_covers_halt_and_stale_codes():
    expected = {
        "autopilot_halted",
        "autopilot_no_candidates",
        "autopilot_max_ticks_exhausted",
        "autopilot_game_select",
        "explore_exhausted",
        "human_attach_blocks_trainer",
        "credits_unknown",
        "credits_stale",
        "fighters_unknown",
        "fighters_stale",
    }
    assert set(INTERVENTION_REASON_LABELS) == expected
    assert intervention_reason_label("explore_exhausted") == "explore exhausted"
    assert intervention_reason_label("autopilot_game_select") == "autopilot game select"
    assert intervention_reason_label("custom_future") == "custom_future"
    assert intervention_reason_label(None) == "?"


def test_adapters_reexports_shared_helper():
    assert adapters.intervention_reason_label is intervention_reason_label
    assert adapters.INTERVENTION_REASON_LABELS is INTERVENTION_REASON_LABELS


def test_play_and_spectate_compose_share_labels():
    """Both compose paths must resolve codes via the shared map (same strip)."""
    reasons = [
        {"code": "explore_exhausted"},
        {"code": "autopilot_max_ticks_exhausted"},
        {"code": "fighters_unknown"},
        {"code": "brand_new_code"},
    ]
    status = {
        "ok": True,
        "mode": "auto_loop",
        "credits": 1,
        "turns_left": 1,
        "fighters_aboard": 0,
        "prompt": "Command [TL=04:00:00]:[1]",
        "autopilot": {"running": False, "ticks_done": 0},
        "intervention": {
            "needs_attention": True,
            "reasons": reasons,
            "autopilot": {"running": False, "ticks_done": 0},
            "mode": "auto_loop",
        },
    }
    expected_strip = "! " + "; ".join(
        intervention_reason_label(r["code"]) for r in reasons
    )
    assert compose_intervention_strip(status) == expected_strip
    panels = adapters.compose_play_panels(status, width=72)
    assert panels["attention_banner"] == expected_strip
    assert panels["reason_labels"] == [
        "explore exhausted",
        "autopilot max ticks exhausted",
        "fighters unknown",
        "brand_new_code",
    ]
