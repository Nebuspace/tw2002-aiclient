"""Pure identity and preview for a human-approved discovered trade chain."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Optional

from .chains import ProfitChain

_COMMODITIES = frozenset({"Fuel Ore", "Organics", "Equipment"})


@dataclass(frozen=True)
class TradeChainPlan:
    world_id: str
    fingerprint: str
    sectors: tuple[int, ...]
    commodities: tuple[str, ...]
    turns: int
    cr_per_turn: float

    @property
    def start_anchor(self) -> int:
        return self.sectors[0]

    @property
    def hops(self) -> int:
        return len(self.commodities)

    @property
    def route(self) -> str:
        return ">".join(str(sector) for sector in self.sectors)

    @property
    def commodity_route(self) -> str:
        return ">".join(self.commodities)

    def wire_identity(self) -> dict:
        return {
            "world_id": self.world_id,
            "fingerprint": self.fingerprint,
        }


def _canonical_payload(world_id: str, chain: ProfitChain) -> Optional[dict]:
    if not isinstance(world_id, str) or not world_id.strip():
        return None
    sectors = chain.sectors
    hops = chain.hops
    if (
        not isinstance(sectors, tuple)
        or len(sectors) < 3
        or sectors[0] != sectors[-1]
        or not isinstance(hops, tuple)
        or len(hops) < 2
        or len(sectors) != len(hops) + 1
    ):
        return None
    clean_sectors: list[int] = []
    clean_hops: list[dict] = []
    for sector in sectors:
        if isinstance(sector, bool) or not isinstance(sector, int) or sector <= 0:
            return None
        clean_sectors.append(sector)
    for index, hop in enumerate(hops):
        if (
            isinstance(hop.frm, bool)
            or not isinstance(hop.frm, int)
            or isinstance(hop.to, bool)
            or not isinstance(hop.to, int)
            or hop.frm != clean_sectors[index]
            or hop.to != clean_sectors[index + 1]
            or hop.commodity not in _COMMODITIES
            or isinstance(hop.turns, bool)
            or not isinstance(hop.turns, int)
            or hop.turns <= 0
            or isinstance(hop.margin, bool)
            or not isinstance(hop.margin, (int, float))
            or not math.isfinite(float(hop.margin))
            or float(hop.margin) <= 0
        ):
            return None
        clean_hops.append(
            {
                "frm": hop.frm,
                "to": hop.to,
                "commodity": hop.commodity,
                "margin": repr(float(hop.margin)),
                "turns": hop.turns,
            }
        )
    if (
        isinstance(chain.turns, bool)
        or not isinstance(chain.turns, int)
        or chain.turns <= 0
        or isinstance(chain.cr_per_turn, bool)
        or not isinstance(chain.cr_per_turn, (int, float))
        or not math.isfinite(float(chain.cr_per_turn))
        or float(chain.cr_per_turn) <= 0
    ):
        return None
    return {
        "world_id": world_id.strip(),
        "sectors": clean_sectors,
        "hops": clean_hops,
        "turns": chain.turns,
        "cr_per_turn": repr(float(chain.cr_per_turn)),
    }


def plan_from_chain(world_id: str, chain: object) -> Optional[TradeChainPlan]:
    """Return an exact, stable approval plan or refuse an incomplete chain."""
    if not isinstance(chain, ProfitChain):
        return None
    payload = _canonical_payload(world_id, chain)
    if payload is None:
        return None
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    fingerprint = hashlib.sha256(encoded).hexdigest()
    return TradeChainPlan(
        world_id=payload["world_id"],
        fingerprint=fingerprint,
        sectors=tuple(payload["sectors"]),
        commodities=tuple(hop["commodity"] for hop in payload["hops"]),
        turns=payload["turns"],
        cr_per_turn=float(payload["cr_per_turn"]),
    )


def resolve_exact_chain(
    world_id: str, fingerprint: str, chains: object
) -> Optional[ProfitChain]:
    """Resolve exactly one current chain by identity; never choose a fallback."""
    if (
        not isinstance(fingerprint, str)
        or len(fingerprint) != 64
        or not isinstance(chains, (tuple, list))
    ):
        return None
    matched: list[ProfitChain] = []
    for chain in chains:
        plan = plan_from_chain(world_id, chain)
        if plan is not None and plan.fingerprint == fingerprint:
            matched.append(chain)
    return matched[0] if len(matched) == 1 else None


def compose_confirm_action(
    plan: object, *, cash_floor: object, turn_reserve: object
) -> Optional[str]:
    """Default-deny arm text naming the exact one-pass semantic scaffold."""
    if (
        not isinstance(plan, TradeChainPlan)
        or isinstance(cash_floor, bool)
        or not isinstance(cash_floor, int)
        or cash_floor < 0
        or isinstance(turn_reserve, bool)
        or not isinstance(turn_reserve, int)
        or turn_reserve < 0
    ):
        return None
    return (
        f"Trade {plan.route} — {plan.commodity_route}; one pass, "
        f"{plan.hops} hops, floor {cash_floor}cr, reserve {turn_reserve}t"
    )
