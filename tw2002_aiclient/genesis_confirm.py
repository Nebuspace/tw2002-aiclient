"""Genesis confirm-to-send seam (PWO-106 Option A).

Reuses ``cockpit.armconfirm``'s default-deny ``y``/``Y`` policy. This module
is the **only** approved choke-point for any future App Genesis send.

Option A deliberately ships **no Genesis adapter / stub** — only the gate.
A skipped or cancelled confirm must never reach a transport ``send``.
Option B (stub adapter + end-to-end fire) stays HELD pending a fresh GO.
"""

from __future__ import annotations

from typing import Callable, Optional

from tw2002_aiclient.cockpit.armconfirm import (
    CANCEL,
    CONFIRM,
    compose_arm_confirm_line,
    resolve_arm_confirm_key,
)

__all__ = [
    "CANCEL",
    "CONFIRM",
    "REFUSED",
    "SENT",
    "compose_genesis_confirm_line",
    "genesis_send_if_confirmed",
    "resolve_genesis_confirm_key",
]

REFUSED = "refused"
SENT = "sent"


def compose_genesis_confirm_line(sector: object = None) -> str:
    """Canon confirm line for a one-shot Genesis arm.

    Re-askable: cancel clears the pending arm; another Genesis requires a
    fresh arm + confirm. Never sticky, never default-yes.
    """
    sector_txt = ""
    if isinstance(sector, int) and not isinstance(sector, bool) and sector > 0:
        sector_txt = f" @ {sector}"
    elif isinstance(sector, str) and sector.strip():
        sector_txt = f" @ {sector.strip()}"
    return compose_arm_confirm_line(f"Genesis{sector_txt}")


def resolve_genesis_confirm_key(key: object) -> str:
    """Identical default-deny policy as ``armconfirm.resolve_arm_confirm_key``."""
    return resolve_arm_confirm_key(key)


def genesis_send_if_confirmed(
    *,
    disposition: object,
    send: Optional[Callable[[str], object]] = None,
    payload: object = None,
) -> str:
    """Call ``send(payload)`` only when ``disposition`` is CONFIRM.

    Any other disposition (CANCEL, None, junk) returns ``REFUSED`` and never
    invokes ``send``. A missing/non-callable ``send`` also refuses — there is
    no silent no-op "success". Never raises.
    """
    if disposition != CONFIRM:
        return REFUSED
    if not callable(send):
        return REFUSED
    text = payload if isinstance(payload, str) else ""
    if not text:
        return REFUSED
    try:
        send(text)
    except Exception:  # noqa: BLE001 -- refuse rather than leak mid-send errors upward
        return REFUSED
    return SENT
