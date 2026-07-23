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
            "reasons": [{"code": "credits_stale", "detail": {"age_ms": 20000}}],
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
    panels = adapters.compose_play_panels(status, width=36)
    assert panels["needs_attention"] is True
    log = "\n".join(panels["log"])
    assert "needs attention" in log
    assert "credits_stale" in log
    assert "credit floor" in log


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
