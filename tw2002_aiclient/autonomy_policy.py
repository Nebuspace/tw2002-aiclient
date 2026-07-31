"""Pure, confirm-only early-game offer selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OfferKind = Literal["explore", "run_chain", "upgrade", "idle"]


@dataclass(frozen=True)
class AutonomyOffer:
    """One operator-confirmable next action; never an arm or send command."""

    kind: OfferKind
    reason: str
    gated: bool = False
    payload: dict | None = None


def _stardock_known(status: dict) -> bool:
    if status.get("stardock_found") is True:
        return True
    sectors = status.get("stardock_sectors")
    return isinstance(sectors, (list, tuple)) and bool(sectors)


def _candidates(status: dict) -> list[dict] | None:
    focus = status.get("focus")
    if not isinstance(focus, dict):
        return None
    candidates = focus.get("candidates")
    if not isinstance(candidates, list):
        return None
    clean: list[dict] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            return None
        kind = candidate.get("kind")
        gated = candidate.get("gated")
        if kind not in {"explore", "run_chain", "upgrade"} or not isinstance(gated, bool):
            return None
        clean.append(candidate)
    return clean


def _offer(candidate: dict) -> AutonomyOffer:
    kind = candidate["kind"]
    gated = candidate["gated"]
    gate_reason = candidate.get("gate_reason")
    if gated:
        reason = gate_reason if isinstance(gate_reason, str) and gate_reason else "preconditions incomplete"
    else:
        reason = "top ungated FOCUS candidate"
    return AutonomyOffer(kind=kind, reason=reason, gated=gated, payload=dict(candidate))


def choose_offer(status: dict, *, has_hold_arm: bool = True) -> AutonomyOffer:
    """Return the next FOCUS offer without calling any live-money boundary."""
    if not isinstance(status, dict):
        return AutonomyOffer("idle", "status unavailable")
    candidates = _candidates(status)
    if candidates is None:
        return AutonomyOffer("idle", "FOCUS candidates unavailable")
    if not isinstance(has_hold_arm, bool):
        return AutonomyOffer("idle", "hold-arm capability unknown")

    eligible = [
        candidate
        for candidate in candidates
        if has_hold_arm or candidate["kind"] != "upgrade"
    ]
    has_ungated_chain = any(
        candidate["kind"] == "run_chain" and not candidate["gated"]
        for candidate in eligible
    )
    if not has_ungated_chain and not _stardock_known(status):
        return AutonomyOffer(
            "explore",
            "no executable trade chain and StarDock is unknown",
            payload={"intent": "find_stardock"},
        )

    for candidate in eligible:
        if not candidate["gated"]:
            return _offer(candidate)
    if eligible:
        return _offer(eligible[0])
    return AutonomyOffer("idle", "no eligible FOCUS candidate")
