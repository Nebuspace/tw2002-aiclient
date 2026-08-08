"""Auto-haggle tuning defaults registry (WO-BUILD-HAGGLE-PARAMS-REGISTRY).

Numeric knobs for ``session.haggle.run_haggle`` live here (and in
``data/haggle/params.json``) instead of silent module literals in
``haggle.py``. Callers may still override per-call kwargs; this registry
is the authored default source.

Defaults are live-proven (DECISIONS 2026-08-05) — not hypothesis-tagged
game-economy numbers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

_PACKAGE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE_DIR.parent
DEFAULT_PARAMS_PATH = _REPO_ROOT / "data" / "haggle" / "params.json"

_REQUIRED_KEYS = frozenset(
    {
        "round_cap",
        "accept_threshold_pct",
        "open_aggression_pct",
        "step_timeout_s",
        "fresh_render_debounce_ms",
        "fresh_render_timeout_s",
        "verified_vs_live",
        "source_note",
    }
)


@dataclass(frozen=True)
class HaggleParams:
    """Authoritative default knobs for one OFFER negotiation."""

    round_cap: int
    accept_threshold_pct: float
    open_aggression_pct: float
    step_timeout_s: float
    fresh_render_debounce_ms: int
    fresh_render_timeout_s: float
    verified_vs_live: bool = True
    source_note: str = ""


# Built-in fallback identical to the pre-registry literals (and to
# data/haggle/params.json). Used when the JSON path is missing in a
# weird install layout; product tree always ships the JSON.
BUILTIN_HAGGLE_PARAMS = HaggleParams(
    round_cap=4,
    accept_threshold_pct=5.0,
    open_aggression_pct=15.0,
    step_timeout_s=8.0,
    fresh_render_debounce_ms=350,
    fresh_render_timeout_s=2.0,
    verified_vs_live=True,
    source_note=(
        "Built-in fallback matching live-proven defaults "
        "(canon/DECISIONS.md 2026-08-05)"
    ),
)


def _coerce(raw: Mapping[str, Any]) -> HaggleParams:
    missing = _REQUIRED_KEYS - set(raw)
    if missing:
        raise ValueError(f"haggle params missing keys: {sorted(missing)}")
    return HaggleParams(
        round_cap=int(raw["round_cap"]),
        accept_threshold_pct=float(raw["accept_threshold_pct"]),
        open_aggression_pct=float(raw["open_aggression_pct"]),
        step_timeout_s=float(raw["step_timeout_s"]),
        fresh_render_debounce_ms=int(raw["fresh_render_debounce_ms"]),
        fresh_render_timeout_s=float(raw["fresh_render_timeout_s"]),
        verified_vs_live=bool(raw["verified_vs_live"]),
        source_note=str(raw["source_note"]),
    )


def load_haggle_params(params_path: str | Path | None = None) -> HaggleParams:
    """Load authored haggle defaults from JSON (or builtin fallback)."""
    path = Path(params_path) if params_path is not None else DEFAULT_PARAMS_PATH
    if not path.is_file():
        return BUILTIN_HAGGLE_PARAMS
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("haggle params root must be a JSON object")
    return _coerce(raw)


# Module-level default used by ``session.haggle`` — one load at import.
DEFAULT_HAGGLE_PARAMS = load_haggle_params()
