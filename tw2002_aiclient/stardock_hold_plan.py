"""Pure identity and preview for a human-approved StarDock hold purchase."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Optional

from tw2002_aiclient.game_data_stats import HOLD_PRICE_LABEL_KEY


@dataclass(frozen=True)
class StardockHoldPlan:
    world_id: str
    fingerprint: str
    stardock_sector: int
    empty_holds: int
    hold_price: int
    credits: int
    qty: int


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


def compute_auto_max_qty(
    *,
    empty_holds: object,
    hold_price: object,
    credits: object,
    cash_floor: object = 0,
) -> Optional[int]:
    """Qty that fills empty holds toward ship max as credits allow (TW-22).

    ``empty_holds`` is room to the ship's current max; spendable credits are
    ``credits - cash_floor``. Returns ``None`` when nothing honest can be bought.
    """
    empty = _pos_int(empty_holds)
    price = _pos_int(hold_price)
    cash = _pos_int(credits)
    floor = _pos_int(cash_floor)
    if empty is None or empty <= 0:
        return None
    if price is None or price <= 0:
        return None
    if cash is None or floor is None:
        return None
    spendable = cash - floor
    if spendable < price:
        return None
    qty = min(empty, spendable // price)
    return qty if qty >= 1 else None


def _cargo_hud_value(status: dict) -> object:
    hud = status.get("hud") if isinstance(status.get("hud"), dict) else {}
    cargo_cell = hud.get("cargo") if isinstance(hud, dict) else None
    return (
        cargo_cell.get("value")
        if isinstance(cargo_cell, dict)
        else cargo_cell
    )


def _cargo_empty_from_status(status: dict) -> object:
    value = _cargo_hud_value(status)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        head = value.strip().split(" ", 1)[0].replace(",", "")
        if head.isdigit():
            return int(head)
    return None


def _cargo_total_from_hud(status: dict) -> Optional[int]:
    """Parse ``N empty / T`` HUD text → total holds ``T`` (observed capacity)."""
    value = _cargo_hud_value(status)
    if not isinstance(value, str):
        return None
    match = re.search(
        r"(\d+)\s*empty\s*/\s*(\d+)",
        value,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    try:
        total = int(match.group(2))
    except ValueError:
        return None
    return total if total >= 0 else None


def _ship_type_from_status(status: dict) -> Optional[str]:
    current = status.get("current_ship")
    if isinstance(current, dict):
        ship_type = current.get("ship_type")
        if isinstance(ship_type, str) and ship_type.strip():
            return ship_type.strip()
    top = status.get("ship_type")
    if isinstance(top, str) and top.strip():
        return top.strip()
    return None


def _current_holds_from_status(status: dict) -> Optional[int]:
    """Live owned-hold count — never invents from catalog max alone."""
    player = status.get("upgrade_player")
    if isinstance(player, dict):
        holds = player.get("current_holds")
        if isinstance(holds, int) and not isinstance(holds, bool) and holds >= 0:
            return holds
    current = status.get("current_ship")
    if isinstance(current, dict):
        holds = current.get("total_holds")
        if isinstance(holds, int) and not isinstance(holds, bool) and holds >= 0:
            return holds
    return _cargo_total_from_hud(status)


def _catalog_max_holds_from_status(status: dict) -> Optional[int]:
    """Layer-B catalog ``max_holds`` for the current ship type, or ``None``.

    Reads ``upgrade_catalog`` rows (``holds`` / ``max_holds``). Cost/shields are
    never consulted — holds-only. Unmatched / hostile → ``None`` (fail-closed).
    """
    ship_type = _ship_type_from_status(status)
    catalog = status.get("upgrade_catalog")
    if ship_type is None or not isinstance(catalog, list):
        return None
    # Reuse the shipyard name matcher so I-info type lines stay consistent
    # with ship_upgrade_decision (e.g. ``4 Dragons Ltd Dragon Quest``).
    from tw2002_aiclient.ship_upgrade_decision import (
        _catalog_row_matches_ship_type,
    )

    for row in catalog:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if not isinstance(name, str) or not name.strip():
            name = row.get("ship_name")
        if not isinstance(name, str) or not name.strip():
            continue
        if not _catalog_row_matches_ship_type(name, ship_type):
            continue
        for key in ("max_holds", "holds"):
            raw = row.get(key)
            if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
                return raw
        return None
    return None


def _auto_max_room(
    status: dict, observed_empty: object
) -> object:
    """Ceiling for auto-max qty: catalog headroom when resolvable, else HUD empty.

    Catalog headroom = ``catalog_max_holds - current_holds``. Incomplete or
    inconsistent evidence falls back to observed empty holds — never fabricates
    a max.
    """
    catalog_max = _catalog_max_holds_from_status(status)
    current = _current_holds_from_status(status)
    if (
        catalog_max is not None
        and current is not None
        and catalog_max >= current
    ):
        return catalog_max - current
    return observed_empty


def _credits_from_status(status: dict) -> object:
    top = status.get("credits")
    if isinstance(top, bool):
        pass
    elif isinstance(top, int) and top >= 0:
        return top
    hud = status.get("hud") if isinstance(status.get("hud"), dict) else {}
    credits_cell = hud.get("credits") if isinstance(hud, dict) else None
    value = (
        credits_cell.get("value")
        if isinstance(credits_cell, dict)
        else credits_cell
    )
    return value


def plan_from_status(
    world_id: object,
    status: object,
    *,
    auto_max: bool = False,
    cash_floor: object = 0,
) -> Optional[StardockHoldPlan]:
    """Build a plan from GOALS/HUD status evidence. Never raises.

    ``auto_max=True`` (TW-22): qty expands toward ship-max room as credits
    allow (after ``cash_floor``). Room prefers Layer-B catalog ``max_holds``
    minus owned holds when resolvable; otherwise HUD empty (fail-closed).
    Default remains qty=1 for manual one-shot offers.
    """
    try:
        if not isinstance(status, dict):
            return None
        sectors = status.get("stardock_sectors")
        dock = None
        if isinstance(sectors, (list, tuple)) and sectors:
            dock = sectors[0]
        elif status.get("stardock_found") is True:
            dock = status.get("stardock_sector")
        observed_empty = _cargo_empty_from_status(status)
        empty = (
            _auto_max_room(status, observed_empty)
            if auto_max
            else observed_empty
        )
        credits = _credits_from_status(status)
        price = status.get("hold_price")
        if price is None:
            label = status.get(HOLD_PRICE_LABEL_KEY)
            if isinstance(label, str):
                digits = "".join(ch for ch in label if ch.isdigit())
                price = int(digits) if digits else None
        if auto_max:
            qty = compute_auto_max_qty(
                empty_holds=empty,
                hold_price=price,
                credits=credits,
                cash_floor=cash_floor,
            )
            if qty is None:
                return None
        else:
            qty = 1
        return plan_from_evidence(
            world_id,
            stardock_sector=dock,
            empty_holds=empty,
            hold_price=price,
            credits=credits,
            qty=qty,
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
