"""Pin: do not re-claim that no ship-upgrade decision engine exists.

WO-CANON-FIX-MODE-LINE-SHIP-UPGRADE-ENGINE-FALSE-CLAIM / #653 lesson:
Mode-line + auto-fire comments once asserted absence while
``ship_upgrade_decision.py`` was already tip-live. Keep "gates nothing" for
missing EXECUTE / offer-kind wiring — not for a missing engine.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Exact absence phrasing from the pre-#654 / stale cycle-49 claim.
_FORBIDDEN = (
    "No ship-upgrade engine or offer kind exists",
    "no ship-upgrade engine or offer kind exists",
    "no ship-upgrade engine exists",
    "adapter verb for a ship-upgrade engine exists yet",
)

_SURFACES = (
    ROOT / "canon" / "surfaces" / "mode-line-and-teach-controls.md",
    ROOT / "tw2002_aiclient" / "app.py",
    ROOT / "tw2002_aiclient" / "cockpit" / "teachband.py",
    ROOT / "tw2002_aiclient" / "screens.py",
)


def test_ship_upgrade_decision_module_exists() -> None:
    assert (ROOT / "tw2002_aiclient" / "ship_upgrade_decision.py").is_file()


def test_surfaces_do_not_claim_engine_absent() -> None:
    for path in _SURFACES:
        text = path.read_text(encoding="utf-8")
        for phrase in _FORBIDDEN:
            assert phrase not in text, f"{path.relative_to(ROOT)} still has {phrase!r}"


def test_mode_line_names_recommend_only_engine() -> None:
    text = (ROOT / "canon" / "surfaces" / "mode-line-and-teach-controls.md").read_text(
        encoding="utf-8"
    )
    assert "ship_upgrade_decision.py" in text
    assert "gates nothing yet" in text
    assert "recommend-only" in text.lower() or "Recommend-only" in text
