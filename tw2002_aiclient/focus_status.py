"""FOCUS candidates on ``status`` — Layer-2 ranked suggestions (display only).

``cockpit/focus.py`` is a starved consumer: it only renders
``status["focus"]["candidates"]`` and never ranks. This module is the
producer. It never sends, never arms, and never invents a money-path.

Canon: `canon/engine/priority-engine.md` Layer 2 — FOCUS + boolean-weight
overlay. Kinds mirror the engine vocabulary (``run_chain`` / ``explore`` /
``upgrade``). Sort: unmet prerequisite weight ``(0, weight)`` above action EV
``(1, ev)``; gated last. The composer trusts this order.

RT / stay-vs-leave (``priority_engine.upgrade_gate_while_chaining``) demotes
an upgrade behind a running executable chain when pre-flight fails or
``stay_vs_leave_upgrade`` says stay — never invents hop counts.
"""

from __future__ import annotations

__all__ = ["FocusScalars", "recommend_focus_candidates", "FOCUS_KEY"]

from tw2002_aiclient.chains import is_executable_chain
from tw2002_aiclient.chain_status import ChainScalars
from tw2002_aiclient.game_data_stats import HOLD_PRICE_LABEL_KEY, SHIP_PRICES_COUNT_KEY
from tw2002_aiclient.priority_engine import hops_of_path, upgrade_gate_while_chaining

FOCUS_KEY = "focus"

# Canon ``EXPLORE_BASELINE_EV`` — explore stays visible so FOCUS is never
# an empty suggestion list when the map still has work (suggestion only).
EXPLORE_BASELINE_EV = 0.01

# Canon weight ladder (priority-engine.md objective table) — catalog booleans.
WEIGHT_SHIP_PRICES = 80
WEIGHT_HOLD_PRICE = 75


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
    """HUD cargo empty-holds: int wire or ``N empty`` / ``N empty / T`` display."""
    if not isinstance(status, dict):
        return None
    try:
        hud = status.get("hud")
        cell = hud.get("cargo") if isinstance(hud, dict) else None
        value = cell.get("value") if isinstance(cell, dict) else cell
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value >= 0 else None
        if isinstance(value, str):
            # Protocol paints ``format_cargo_hud_value`` text for the gutter.
            head = value.strip().split(" ", 1)[0].replace(",", "")
            if head.isdigit():
                return int(head)
            return None
        return None
    except Exception:  # noqa: BLE001
        return None


def _stardock_known(status: object) -> bool:
    if not isinstance(status, dict):
        return False
    if status.get("stardock_found") is True:
        return True
    sectors = status.get("stardock_sectors")
    return isinstance(sectors, (list, tuple)) and len(sectors) > 0


def _ship_prices_met(status: object) -> bool:
    if not isinstance(status, dict):
        return False
    count = status.get(SHIP_PRICES_COUNT_KEY)
    if isinstance(count, bool) or not isinstance(count, int):
        return False
    return count > 0


def _hold_price_met(status: object) -> bool:
    if not isinstance(status, dict):
        return False
    label = status.get(HOLD_PRICE_LABEL_KEY)
    return isinstance(label, str) and bool(label.strip())


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _hops_to_stardock(status: dict) -> int | None:
    raw = status.get("hops_to_stardock")
    hops = _optional_int(raw)
    if hops is not None:
        return hops if hops >= 0 else None
    route = status.get("stardock_route")
    if isinstance(route, (list, tuple)):
        try:
            return hops_of_path(tuple(int(s) for s in route))
        except (TypeError, ValueError):
            return None
    return None


def _hops_return_to_work(status: dict) -> int | None:
    raw = status.get("hops_return_to_work")
    hops = _optional_int(raw)
    if hops is not None:
        return hops if hops >= 0 else None
    path = status.get("return_path_to_work")
    if isinstance(path, (list, tuple)):
        try:
            return hops_of_path(tuple(int(s) for s in path))
        except (TypeError, ValueError):
            return None
    return None


def _productive_turns(status: dict) -> int | None:
    turns_left = _optional_int(status.get("turns_left"))
    if turns_left is None:
        return None
    reserve = _optional_int(status.get("turn_reserve")) or 0
    if reserve < 0:
        reserve = 0
    return turns_left - reserve


def _upgrade_economics(status: dict) -> tuple[float | None, float | None]:
    """``(upgrade_extra_cr_per_turn, payback)`` — omit rather than invent."""
    extra = _optional_float(status.get("upgrade_extra_cr_per_turn"))
    payback = _optional_float(status.get("upgrade_payback"))
    if extra is not None and payback is not None:
        return extra, payback
    decision = status.get("upgrade_decision")
    if isinstance(decision, dict):
        if extra is None:
            extra = _optional_float(decision.get("upgrade_extra_cr_per_turn"))
        if payback is None:
            payback = _optional_float(decision.get("projected_payback"))
    return extra, payback


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
        dock_known = _stardock_known(status_d)
        ships_met = _ship_prices_met(status_d)
        hold_met = _hold_price_met(status_d)

        # Unmet catalog prerequisites (StarDock known) → weight-boost explore
        # and ⊘-gate upgrade until the quote exists.
        overlay_weight: int | None = None
        upgrade_gate: str | None = None
        if dock_known:
            if not ships_met:
                overlay_weight = WEIGHT_SHIP_PRICES
                upgrade_gate = "ship prices unknown"
            elif not hold_met:
                overlay_weight = WEIGHT_HOLD_PRICE
                upgrade_gate = "hold price unknown"

        chain = _priced_chain(chain_scalars, status_d)
        has_executable = False
        chain_ev: float | None = None
        if chain is not None:
            try:
                has_executable = bool(is_executable_chain(chain))  # type: ignore[arg-type]
            except Exception:  # noqa: BLE001
                has_executable = False
            if has_executable:
                chain_ev = _chain_ev(chain)
                candidates.append(
                    {
                        "kind": "run_chain",
                        "ev_per_turn": chain_ev,
                        "gated": False,
                        "gate_reason": None,
                        "priority_weight": None,
                    }
                )

        # Explore: always a suggestion when there is no executable chain yet,
        # or StarDock is still unknown, or a catalog prereq is unmet (hunt /
        # price at dock). Overlay weight raises it above EV until satisfied.
        need_explore = (
            (not has_executable)
            or (not dock_known)
            or (overlay_weight is not None)
        )
        if need_explore:
            candidates.append(
                {
                    "kind": "explore",
                    "ev_per_turn": EXPLORE_BASELINE_EV,
                    "gated": False,
                    "gate_reason": None,
                    "priority_weight": overlay_weight,
                }
            )

        # Upgrade: omit entirely until StarDock is known (Accept #3 — omit).
        if dock_known:
            empty = _cargo_empty_holds(status_d)
            upgrade_ev: float | None = None
            travel_rt: int | None = None
            if upgrade_gate is not None:
                pass
            elif empty is None:
                upgrade_gate = "empty holds unknown"
            elif has_executable:
                # Pre-flight + stay-vs-leave while a chain is executable.
                extra, payback = _upgrade_economics(status_d)
                gated, reason, upgrade_ev, travel_rt = upgrade_gate_while_chaining(
                    chain_cr_per_turn=chain_ev,
                    upgrade_extra_cr_per_turn=extra,
                    upgrade_payback=payback,
                    hops_to_stardock=_hops_to_stardock(status_d),
                    hops_return_to_work=_hops_return_to_work(status_d),
                    turns_per_warp=_optional_int(status_d.get("turns_per_warp")),
                    productive_turns=_productive_turns(status_d),
                )
                if gated:
                    upgrade_gate = reason or "upgrade: stay trading"
            candidates.append(
                {
                    "kind": "upgrade",
                    "ev_per_turn": upgrade_ev,
                    "gated": upgrade_gate is not None,
                    "gate_reason": upgrade_gate,
                    "priority_weight": None,
                    "travel_cost_rt": travel_rt,
                }
            )
    except Exception:  # noqa: BLE001
        return []

    return _rank_candidates(candidates)


def _rank_candidates(candidates: list[dict]) -> list[dict]:
    """Boolean-weight overlay sort: unmet weight → EV → gated."""

    def _sort_key(c: dict) -> tuple:
        if c.get("gated"):
            return (2, 0, 0.0)
        weight = c.get("priority_weight")
        if isinstance(weight, bool) or not isinstance(weight, int) or weight <= 0:
            pass
        else:
            return (0, -weight, 0.0)
        ev = c.get("ev_per_turn")
        if isinstance(ev, bool) or not isinstance(ev, (int, float)):
            return (1, 0, 0.0)
        return (1, 0, -float(ev))

    return sorted(candidates, key=_sort_key)


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
