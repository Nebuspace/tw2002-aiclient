"""WO-WIRE-COCKPIT-ANALYZE-TO-AI-TEACHER — cockpit Analyze → ai_teacher.

Pins:

1. Default / no backend → scaffold stub (create_analyze_draft shape).
2. Injected valid backend → inert draft on disk via write_draft.
3. PvP-initiating draft → declined; drafts dir empty.
4. app.py analyze_close routes through complete_cockpit_analyze.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from tw2002_aiclient import ai_teacher, app
from tw2002_aiclient.rules.store import drafts_dir


VALID_DRAFT = {
    "rule_id": "cockpit-warp-yes",
    "when": "warp_confirm",
    "do": "send-y",
    "priority": 10,
}

PVP_DRAFT = {
    "rule_id": "cockpit-attack",
    "when": "player_attack",
    "do": "attack-player",
    "priority": 10,
}


def _fake_backend(draft: dict):
    def backend(context: dict) -> dict:
        assert "frame" in context
        return dict(draft)

    return backend


def test_complete_cockpit_analyze_scaffold_when_no_backend():
    result = ai_teacher.complete_cockpit_analyze("main_command")
    assert result["path"] == "scaffold"
    draft = result["draft"]
    assert draft["source"] == "analyze"
    assert draft["approved"] is False
    assert draft["playback_eligible"] is False
    assert draft["when"]["screen"] == "main_command"


def test_complete_cockpit_analyze_teacher_writes_inert_draft(tmp_path: Path):
    result = ai_teacher.complete_cockpit_analyze(
        "warp_confirm",
        backend=_fake_backend(VALID_DRAFT),
        state_dir=tmp_path,
    )
    assert result["path"] == "teacher"
    assert result["declined"] is False
    path = Path(result["draft"])
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert '"approved": false' in text


def test_complete_cockpit_analyze_teacher_decline_writes_nothing(tmp_path: Path):
    result = ai_teacher.complete_cockpit_analyze(
        "player_attack",
        backend=_fake_backend(PVP_DRAFT),
        state_dir=tmp_path,
    )
    assert result["path"] == "teacher"
    assert result["declined"] is True
    assert result.get("reason")
    assert list(drafts_dir(tmp_path).glob("*.md")) == []


def test_app_analyze_close_calls_complete_cockpit_analyze():
    src = inspect.getsource(app)
    assert "complete_cockpit_analyze" in src, (
        "app.py analyze_close must route through ai_teacher.complete_cockpit_analyze"
    )
    # Must not be scaffold-only anymore (the old one-liner path).
    close_idx = src.find('action == "analyze_close"')
    assert close_idx >= 0
    chunk = src[close_idx : close_idx + 1200]
    assert "complete_cockpit_analyze" in chunk
    assert "create_analyze_draft" not in chunk or "scaffold" in chunk
