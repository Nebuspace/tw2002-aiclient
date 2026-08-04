"""Pins for WO-AUDIT-CLEANUP-TRADE-AUTOFIRE-HALF-WIRED.

Abandoned Port Trade auto-fire cooldown / prefer-explore scaffolding must stay
gone — arm-without-check was half-wired, and silent run_chain auto-fire is
intentionally refused.
"""

from __future__ import annotations

from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "tw2002_aiclient" / "app.py"

_GONE = (
    "_arm_trade_auto_fire_cooldown",
    "_trade_auto_fire_cooldown_active",
    "_trade_auto_fire_reason_is_backoff",
    "_prefer_explore_while_trade_blocked",
    "auto_fire_kicked_explore",
    "_TRADE_AUTO_FIRE_COOLDOWN_S",
    "_TRADE_AUTO_FIRE_BACKOFF_REASONS",
)


def test_abandoned_trade_autofire_scaffolding_absent() -> None:
    src = _APP.read_text(encoding="utf-8")
    for name in _GONE:
        assert name not in src, f"{name} must stay removed from app.py"


def test_trade_auto_fire_map_marker_still_present() -> None:
    src = _APP.read_text(encoding="utf-8")
    assert "def _trade_auto_fire_map_marker(" in src
    # Call site for bubble subject (not only the def).
    assert src.count("_trade_auto_fire_map_marker") >= 2
