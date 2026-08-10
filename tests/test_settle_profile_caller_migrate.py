"""WO-CLEANUP-SETTLE-PROFILES-CALLER-MIGRATE — product callers use profiles."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PKG = _ROOT / "tw2002_aiclient"

_MIGRATE_FILES = (
    _PKG / "session" / "hud_seed.py",
    _PKG / "session" / "haggle.py",
    _PKG / "session" / "login.py",
    _PKG / "session" / "sector_explore.py",
    _PKG / "trade_driver.py",
)


def _bare_settle_helper_calls(src: str) -> list[str]:
    """Lines that call settle.send_and_confirm( but not send_and_confirm_for(."""
    out: list[str] = []
    for line in src.splitlines():
        if "send_and_confirm(" not in line:
            continue
        if "send_and_confirm_for(" in line:
            continue
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        if stripped.startswith("def send_and_confirm("):
            # ReplaySession / local method name — not the settle helper.
            continue
        if "`send_and_confirm`" in line or "``send_and_confirm``" in line:
            continue
        out.append(stripped)
    return out


def test_migrated_modules_call_send_and_confirm_for() -> None:
    for path in _MIGRATE_FILES:
        src = path.read_text(encoding="utf-8")
        assert "send_and_confirm_for" in src, f"{path.name} missing send_and_confirm_for"
        bare = _bare_settle_helper_calls(src)
        assert bare == [], f"{path.name} still has bare settle helper calls: {bare}"


def test_autoloop_replay_send_routes_through_profile_helper() -> None:
    src = (_PKG / "session" / "autoloop.py").read_text(encoding="utf-8")
    assert "send_and_confirm_for(" in src
    # Method may still be named send_and_confirm (ReplaySession contract).
    assert "def send_and_confirm(self, keystrokes" in src
    assert 'profile="positive_shape" if wait_prompt else "stable_idle"' in src


def test_trade_driver_maps_retry_to_warp_unstable() -> None:
    src = (_PKG / "trade_driver.py").read_text(encoding="utf-8")
    assert 'profile = "warp_unstable"' in src
    assert 'profile = "positive_shape"' in src
    assert 'profile = "stable_idle"' in src
