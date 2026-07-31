"""Pure identity and preview for a human-approved StarDock hold purchase."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class StardockHoldPlan:
    world_id: str
    fingerprint: str
    stardock_sector: int
    empty_holds: int
    hold_price: int
    credits: int
    qty: int

    def wire_identity(self) -> dict:
        return {
            "world_id": self.world_id,
            "fingerprint": self.fingerprint,
        }


def _pos_int(value: object) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def plan_from_evidence(
    world_id: object,
    *,
    stardock_sector: object,
    empty_holds: object,
    hold_price: object,
    credits: object,
    qty: object = 1,
) -> Optional[StardockHoldPlan]:
    """Exact scaffold or ``None`` when any required field is incomplete/hostile."""
    if not isinstance(world_id, str) or not world_id.strip():
        return None
    dock = _pos_int(stardock_sector)
    empty = _pos_int(empty_holds)
    price = _pos_int(hold_price)
    cash = _pos_int(credits)
    buy = _pos_int(qty)
    if dock is None or dock <= 0:
        return None
    if empty is None:
        return None
    if price is None or price <= 0:
        return None
    if cash is None:
        return None
    if buy is None or buy <= 0:
        return None
    if buy > empty:
        return None
    if price * buy > cash:
        return None
    payload = {
        "world_id": world_id.strip(),
        "stardock_sector": dock,
        "empty_holds": empty,
        "hold_price": price,
        "credits": cash,
        "qty": buy,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    fingerprint = hashlib.sha256(encoded).hexdigest()
    return StardockHoldPlan(
        world_id=payload["world_id"],
        fingerprint=fingerprint,
        stardock_sector=dock,
        empty_holds=empty,
        hold_price=price,
        credits=cash,
        qty=buy,
    )


def plan_from_status(world_id: object, status: object) -> Optional[StardockHoldPlan]:
    """Build a plan from GOALS/HUD status evidence. Never raises."""
    try:
        if not isinstance(status, dict):
            return None
        sectors = status.get("stardock_sectors")
        dock = None
        if isinstance(sectors, (list, tuple)) and sectors:
            dock = sectors[0]
        elif status.get("stardock_found") is True:
            dock = status.get("stardock_sector")
        hud = status.get("hud") if isinstance(status.get("hud"), dict) else {}
        cargo_cell = hud.get("cargo") if isinstance(hud, dict) else None
        empty = (
            cargo_cell.get("value")
            if isinstance(cargo_cell, dict)
            else cargo_cell
        )
        credits_cell = hud.get("credits") if isinstance(hud, dict) else None
        credits = (
            credits_cell.get("value")
            if isinstance(credits_cell, dict)
            else credits_cell
        )
        price = status.get("hold_price")
        if price is None:
            label = status.get("hold_price_label")
            if isinstance(label, str):
                digits = "".join(ch for ch in label if ch.isdigit())
                price = int(digits) if digits else None
        return plan_from_evidence(
            world_id,
            stardock_sector=dock,
            empty_holds=empty,
            hold_price=price,
            credits=credits,
            qty=1,
        )
    except Exception:  # noqa: BLE001
        return None


def compose_confirm_action(
    plan: object, *, cash_floor: object
) -> Optional[str]:
    """Default-deny arm text naming the exact one-pass hold purchase."""
    if (
        not isinstance(plan, StardockHoldPlan)
        or isinstance(cash_floor, bool)
        or not isinstance(cash_floor, int)
        or cash_floor < 0
    ):
        return None
    if plan.credits < cash_floor:
        return None
    return (
        f"Buy {plan.qty} cargo hold(s) @ StarDock {plan.stardock_sector} — "
        f"{plan.hold_price}cr each, floor {cash_floor}cr"
    )


def parse_hold_qty_range(text: object) -> Optional[tuple[int, int]]:
    """Parse ``How many holds would you like to buy [lo-hi] ?``. Refuse unknown."""
    if not isinstance(text, str) or not text:
        return None
    match = re.search(
        r"How many holds would you like to buy\s*\[(\d+)\s*-\s*(\d+)\]\s*\?",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    try:
        lo = int(match.group(1))
        hi = int(match.group(2))
    except ValueError:
        return None
    if lo < 0 or hi < lo:
        return None
    return lo, hi


def parse_hold_unit_price(text: object) -> Optional[int]:
    """Parse ``Holds cost N credits each`` from the quote block."""
    if not isinstance(text, str) or not text:
        return None
    match = re.search(
        r"Holds cost\s+([\d,]+)\s+credits each",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None
