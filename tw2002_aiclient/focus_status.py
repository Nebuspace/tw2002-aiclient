"""FOCUS candidates on ``status`` — Layer-2 ranked suggestions (display only).

``cockpit/focus.py`` is a starved consumer: it only renders
``status["focus"]["candidates"]`` and never ranks. This module is the
producer. It never sends, never arms, and never invents a money-path.

Canon: `canon/engine/priority-engine.md` Layer 2 — FOCUS. Kinds mirror the
engine vocabulary (``run_chain`` / ``explore`` / ``upgrade``). Sort:
ungated by ``ev_per_turn`` descending, gated last. The composer trusts
this order.
"""

from __future__ import annotations

__all__ = ["FocusScalars", "recommend_focus_candidates", "FOCUS_KEY"]

from tw2002_aiclient.chains import is_executable_chain
from tw2002_aiclient.chain_status import ChainScalars

FOCUS_KEY = "focus"

# Canon ``EXPLORE_BASELINE_EV`` — explore stays visible so FOCUS is never
# an empty suggestion list when the map still has work (suggestion only).
EXPLORE_BASELINE_EV = 0.01


def _sector_from_status(status: object) -> object | None:
    if not isinstance(status, dict):
        return None
    try:
        hud = status.get("hud")
        cell = hud.get("sector") if isinstance(hud, dict) else None
        if isinstance(cell, dict):
            return cell.get("value")
        return cell
    except Exception:  # noqa: BLE001
        return None


def _cargo_empty_holds(status: object) -> int | None:
    """HUD cargo is empty-holds when a real int (see hud_tracking)."""
    if not isinstance(status, dict):
        return None
    try:
        hud = status.get("hud")
        cell = hud.get("cargo") if isinstance(hud, dict) else None
        value = cell.get("value") if isinstance(cell, dict) else cell
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        if value < 0:
            return None
        return value
    except Exception:  # noqa: BLE001
        return None


def _stardock_known(status: object) -> bool:
    if not isinstance(status, dict):
        return False
    if status.get("stardock_found") is True:
        return True
    sectors = status.get("stardock_sectors")
    return isinstance(sectors, (list, tuple)) and len(sectors) > 0


def _priced_chain(chain_scalars: ChainScalars | None, status: object) -> object | None:
    if chain_scalars is None:
        return None
    try:
        subject, _caption = chain_scalars.bubble_subject(
            current_sector=_sector_from_status(status)
        )
    except Exception:  # noqa: BLE001
        return None
    return subject


def _chain_ev(chain: object) -> float | None:
    try:
        ev = getattr(chain, "cr_per_turn", None)
        if isinstance(ev, bool) or not isinstance(ev, (int, float)):
            return None
        return float(ev)
    except Exception:  # noqa: BLE001
        return None


def recommend_focus_candidates(
    status: object,
    *,
    chain_scalars: ChainScalars | None = None,
) -> list[dict]:
    """Build FOCUS candidates from status + cached chain evidence. Never raises."""
    candidates: list[dict] = []
    try:
        status_d = status if isinstance(status, dict) else {}
        chain = _priced_chain(chain_scalars, status_d)
        has_executable = False
        if chain is not None:
            try:
                has_executable = bool(is_executable_chain(chain))  # type: ignore[arg-type]
            except Exception:  # noqa: BLE001
                has_executable = False
            if has_executable:
                candidates.append(
                    {
                        "kind": "run_chain",
                        "ev_per_turn": _chain_ev(chain),
                        "gated": False,
                        "gate_reason": None,
                    }
                )

        # Explore: always a suggestion when there is no executable chain yet,
        # or StarDock is still unknown (map / landmark work remains).
        need_explore = (not has_executable) or (not _stardock_known(status_d))
        if need_explore:
            candidates.append(
                {
                    "kind": "explore",
                    "ev_per_turn": EXPLORE_BASELINE_EV,
                    "gated": False,
                    "gate_reason": None,
                }
            )

        # Upgrade: omit entirely until StarDock is known (Accept #3 — omit).
        if _stardock_known(status_d):
            empty = _cargo_empty_holds(status_d)
            hold_label = status_d.get("hold_price_label")
            hold_known = isinstance(hold_label, str) and bool(hold_label.strip())
            if empty is None:
                candidates.append(
                    {
                        "kind": "upgrade",
                        "ev_per_turn": None,
                        "gated": True,
                        "gate_reason": "empty holds unknown",
                    }
                )
            elif not hold_known:
                candidates.append(
                    {
                        "kind": "upgrade",
                        "ev_per_turn": None,
                        "gated": True,
                        "gate_reason": "hold price unknown",
                    }
                )
            else:
                candidates.append(
                    {
                        "kind": "upgrade",
                        "ev_per_turn": None,
                        "gated": False,
                        "gate_reason": None,
                    }
                )
    except Exception:  # noqa: BLE001
        return []

    return _rank_candidates(candidates)


def _rank_candidates(candidates: list[dict]) -> list[dict]:
    ungated: list[dict] = []
    gated: list[dict] = []
    for c in candidates:
        if c.get("gated"):
            gated.append(c)
        else:
            ungated.append(c)

    def _ev_key(c: dict) -> tuple:
        ev = c.get("ev_per_turn")
        if isinstance(ev, bool) or not isinstance(ev, (int, float)):
            return (1, 0.0)
        return (0, -float(ev))

    ungated.sort(key=_ev_key)
    return ungated + gated


class FocusScalars:
    """Merges ``status["focus"]`` from chain + world evidence. Draw-path cheap."""

    def __init__(self, chain_scalars: ChainScalars | None = None) -> None:
        self._chain_scalars = chain_scalars

    def bind(self, chain_scalars: ChainScalars | None) -> None:
        self._chain_scalars = chain_scalars

    def merge(self, status: object) -> dict | None:
        """Attach ``focus.candidates``; never mutates input; never clobbers."""
        if not isinstance(status, dict):
            return status
        if status.get(FOCUS_KEY) is not None:
            return status
        merged = dict(status)
        merged[FOCUS_KEY] = {
            "candidates": recommend_focus_candidates(
                merged, chain_scalars=self._chain_scalars
            )
        }
        return merged

    def wrap(self, provider):
        if provider is None:
            return None

        def _merged():
            return self.merge(provider())

        return _merged
