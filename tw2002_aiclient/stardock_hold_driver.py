"""One-pass cargo-hold purchase driver (StarDock quote → qty send).

Never pays fighter tolls. Refuses unknown P-QTY ranges. Display/session
sends only — no explore/trade_chain calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .stardock_hold_plan import (
    StardockHoldPlan,
    parse_hold_qty_range,
    parse_hold_unit_price,
)


@dataclass(frozen=True)
class HoldRunResult:
    ok: bool
    outcome: str  # completed | halted | refused
    reason: Optional[str]
    sends_issued: int
    qty_sent: Optional[int] = None


def _screen_text(session: object) -> str:
    for name in ("rendered_text", "screen_text", "last_text"):
        fn = getattr(session, name, None)
        if callable(fn):
            try:
                text = fn()
            except Exception:  # noqa: BLE001
                continue
            if isinstance(text, str):
                return text
    text = getattr(session, "text", None)
    return text if isinstance(text, str) else ""


def _send(session: object, payload: str) -> None:
    send = getattr(session, "send", None)
    if not callable(send):
        raise RuntimeError("session_send_unavailable")
    send(payload)


def run_hold_purchase(
    session: object,
    plan: StardockHoldPlan,
    *,
    should_abort: Callable[[], bool],
    is_armed: Callable[[], bool],
) -> HoldRunResult:
    """Confirm-armed one-pass buy. Expects quote (+ qty prompt) already on screen."""
    sends = 0
    if should_abort() or not is_armed():
        return HoldRunResult(False, "halted", "aborted", sends)
    text = _screen_text(session)
    rng = parse_hold_qty_range(text)
    if rng is None:
        return HoldRunResult(False, "refused", "unknown_qty_range", sends)
    lo, hi = rng
    if plan.qty < lo or plan.qty > hi:
        return HoldRunResult(False, "refused", "qty_out_of_range", sends)
    unit = parse_hold_unit_price(text)
    if unit is not None and unit != plan.hold_price:
        return HoldRunResult(False, "refused", "hold_price_mismatch", sends)
    if should_abort() or not is_armed():
        return HoldRunResult(False, "halted", "aborted", sends)
    try:
        _send(session, str(plan.qty))
        sends += 1
    except Exception as exc:  # noqa: BLE001
        return HoldRunResult(
            False, "halted", f"send_failed:{type(exc).__name__}", sends
        )
    return HoldRunResult(True, "completed", None, sends, qty_sent=plan.qty)
