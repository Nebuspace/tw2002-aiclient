"""Ship-upgrade DECISION engine (PWO-107 Option A / TW-30) — pure logic, no I/O.

Encodes the five §24 live-play learnings so the trainer never recommends
capacity that cannot amortize in the remaining turn budget. Inputs are
mockable stand-ins for introspected game_data (PWO-092 residual).

Recommend-only: this module never sends a purchase keystroke. Purchase
adapter + armconfirm (Option B) stay HELD pending a fresh GO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence


@dataclass(frozen=True)
class ShipSpec:
    """One shipyard offering (mockable stand-in for TW-27 introspected data)."""

    name: str
    cost: int
    holds: int
    turns_per_warp: int
    fighters: int
    shields: int
    alignment_req: int = 0
    # True when the player's current alignment/rank meets alignment_req.
    commissioned: bool = True


@dataclass(frozen=True)
class LoopEconomics:
    """Per-cycle profit model for the trader's current (or planned) loop."""

    margin_per_hold: int  # credits of profit per hold filled once per cycle
    turns_per_cycle: int  # wall-turns to run one full cycle (warp+trade)
    stock_capacity: int  # max holds the loop's stock can sustain without chains
    needs_chains_above: Optional[int] = None  # if set, alias for stock_capacity


@dataclass(frozen=True)
class PlayerState:
    turns_left: int
    current_holds: int
    turn_reserve: int = 0  # keep this many turns unspent (safety / login buffer)
    hostile_or_pvp: bool = False
    current_fighters: int = 0
    current_shields: int = 0


@dataclass(frozen=True)
class UpgradeDecision:
    recommend: bool
    ship: Optional[ShipSpec]
    rationale: str
    projected_payback: Optional[float]  # turns to amortize; None if HOLD / N/A
    flags: tuple[str, ...] = field(default_factory=tuple)


def remaining_productive_turns(state: PlayerState) -> int:
    return max(0, state.turns_left - state.turn_reserve)


def holds_per_turn(ship: ShipSpec, loop: LoopEconomics) -> float:
    """Hold-throughput score: (holds × margin) / (cycle_turns × turns_per_warp).

    Shared loop cycle length; ships that burn more turns per warp rank lower
    at equal holds (Barge 6/warp vs Galleon 3/warp).
    """
    if loop.turns_per_cycle <= 0 or ship.turns_per_warp <= 0:
        return 0.0
    return (ship.holds * loop.margin_per_hold) / (
        loop.turns_per_cycle * ship.turns_per_warp
    )


def hold_fill_cost(extra_holds: int, cost_per_hold: int) -> int:
    return max(0, extra_holds) * max(0, cost_per_hold)


def payback_turns(
    ship: ShipSpec,
    state: PlayerState,
    loop: LoopEconomics,
    *,
    cost_per_hold: int = 0,
) -> Optional[float]:
    """Turns to amortize upgrade cost from the extra credits/turn."""
    extra_holds = ship.holds - state.current_holds
    if extra_holds <= 0:
        return None
    hpt_new = holds_per_turn(ship, loop)
    # Approximate current throughput with same warp as candidate for delta.
    current_as_ship = ShipSpec(
        name="current",
        cost=0,
        holds=state.current_holds,
        turns_per_warp=ship.turns_per_warp,
        fighters=state.current_fighters,
        shields=state.current_shields,
        commissioned=True,
    )
    hpt_cur = holds_per_turn(current_as_ship, loop)
    extra_cr_per_turn = hpt_new - hpt_cur
    if extra_cr_per_turn <= 0:
        return None
    total_cost = ship.cost + hold_fill_cost(extra_holds, cost_per_hold)
    return total_cost / extra_cr_per_turn


def _stock_cap(loop: LoopEconomics) -> int:
    if loop.needs_chains_above is not None:
        return loop.needs_chains_above
    return loop.stock_capacity


def evaluate_candidate(
    ship: ShipSpec,
    state: PlayerState,
    loop: LoopEconomics,
    *,
    cost_per_hold: int = 0,
    defense_floor_fighters: int = 1,
) -> UpgradeDecision:
    """Evaluate a single commissioned ship against the five TW-30 gates."""
    flags: list[str] = []

    if not ship.commissioned:
        return UpgradeDecision(
            recommend=False,
            ship=ship,
            rationale=f"{ship.name}: not commissioned (alignment/rank gate).",
            projected_payback=None,
            flags=("alignment_rank",),
        )

    stock = _stock_cap(loop)
    if ship.holds > stock:
        flags.append("needs_chains")
        return UpgradeDecision(
            recommend=False,
            ship=ship,
            rationale=(
                f"{ship.name}: {ship.holds} holds exceed loop stock capacity "
                f"({stock}) — needs chains (TW-21) first."
            ),
            projected_payback=None,
            flags=tuple(flags),
        )

    if state.hostile_or_pvp and ship.fighters < defense_floor_fighters:
        flags.append("defense_floor")
        return UpgradeDecision(
            recommend=False,
            ship=ship,
            rationale=(
                f"{ship.name}: fighters={ship.fighters} below defense floor "
                f"({defense_floor_fighters}) on hostile/PvP — refuse 0-fighter mug risk."
            ),
            projected_payback=None,
            flags=tuple(flags),
        )

    productive = remaining_productive_turns(state)
    pb = payback_turns(ship, state, loop, cost_per_hold=cost_per_hold)
    if pb is None:
        return UpgradeDecision(
            recommend=False,
            ship=ship,
            rationale=f"{ship.name}: no positive credit delta vs current holds.",
            projected_payback=None,
            flags=tuple(flags),
        )
    if pb > productive:
        flags.append("roi_vs_budget")
        return UpgradeDecision(
            recommend=False,
            ship=ship,
            rationale=(
                f"{ship.name}: payback {pb:.1f} turns > remaining productive "
                f"{productive} — HOLD (ROI-vs-turn-budget)."
            ),
            projected_payback=pb,
            flags=tuple(flags),
        )

    return UpgradeDecision(
        recommend=True,
        ship=ship,
        rationale=(
            f"{ship.name}: payback {pb:.1f} turns within productive {productive}; "
            f"holds/turn≈{holds_per_turn(ship, loop):.1f}."
        ),
        projected_payback=pb,
        flags=tuple(flags),
    )


def choose_upgrade(
    catalog: Sequence[ShipSpec],
    state: PlayerState,
    loop: LoopEconomics,
    *,
    cost_per_hold: int = 0,
    defense_floor_fighters: int = 1,
) -> UpgradeDecision:
    """Pick the best hold-throughput ship that passes all five gates, or HOLD."""
    eligible: list[tuple[float, UpgradeDecision]] = []
    refusals: list[UpgradeDecision] = []

    for ship in catalog:
        decision = evaluate_candidate(
            ship,
            state,
            loop,
            cost_per_hold=cost_per_hold,
            defense_floor_fighters=defense_floor_fighters,
        )
        if decision.recommend and decision.ship is not None:
            eligible.append((holds_per_turn(decision.ship, loop), decision))
        else:
            refusals.append(decision)

    if not eligible:
        # Prefer the most informative refusal (ROI gate first if present).
        for key in ("roi_vs_budget", "needs_chains", "defense_floor", "alignment_rank"):
            for r in refusals:
                if key in r.flags:
                    return UpgradeDecision(
                        recommend=False,
                        ship=None,
                        rationale=f"HOLD — {r.rationale}",
                        projected_payback=r.projected_payback,
                        flags=r.flags,
                    )
        return UpgradeDecision(
            recommend=False,
            ship=None,
            rationale="HOLD — no eligible commissioned upgrade in catalog.",
            projected_payback=None,
            flags=(),
        )

    eligible.sort(key=lambda pair: pair[0], reverse=True)
    best = eligible[0][1]
    return best


def _catalog_row_matches_ship_type(row_name: str, ship_type: str) -> bool:
    """True when a shipyard catalog name plausibly matches an I-info type line.

    Match is case-insensitive exact, or catalog name as a whole-word/substring
    of the type string (e.g. catalog ``Dragon Quest`` vs type
    ``4 Dragons Ltd Dragon Quest``). Never fuzzy-guesses across unrelated names.
    """
    a = (row_name or "").strip().lower()
    b = (ship_type or "").strip().lower()
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b:
        # Require a token boundary so short names don't false-match.
        idx = b.find(a)
        before_ok = idx == 0 or not b[idx - 1].isalnum()
        after = idx + len(a)
        after_ok = after >= len(b) or not b[after].isalnum()
        return before_ok and after_ok
    return False


def ship_spec_from_current_info(
    info: object,
    catalog: Sequence[object] | None = None,
    *,
    player_alignment: Optional[int] = None,
) -> Optional[ShipSpec]:
    """Build a :class:`ShipSpec` from an I-info observation (+ optional catalog).

    Live screen supplies holds / fighters / turns_per_warp when present.
    Cost, shields, and alignment come **only** from a matching Layer-B catalog
    row (via ``game_data.ship_row_to_spec``) — never invented. No catalog match
    → ``None`` (type may still be known on status for priority row 2).
    """
    if not isinstance(info, dict):
        return None
    ship_type = info.get("ship_type")
    if not isinstance(ship_type, str) or not ship_type.strip():
        return None
    if not catalog:
        return None

    from .game_data import ShipRow, ship_row_to_spec

    match = None
    for item in catalog:
        if isinstance(item, ShipRow):
            name = item.ship_name
            row = item
        elif isinstance(item, dict):
            name = item.get("ship_name")
            row = item
        elif isinstance(item, ShipSpec):
            name = item.name
            row = item
        else:
            continue
        if not isinstance(name, str):
            continue
        if _catalog_row_matches_ship_type(name, ship_type):
            match = row
            break
    if match is None:
        return None

    if isinstance(match, ShipSpec):
        base = match
    else:
        commissioned = True
        if player_alignment is not None and isinstance(match, (ShipRow, dict)):
            req = (
                match.alignment_requirement
                if isinstance(match, ShipRow)
                else match.get("alignment_requirement")
            )
            if req is not None:
                try:
                    commissioned = int(player_alignment) >= int(req)
                except (TypeError, ValueError):
                    commissioned = True
        base = ship_row_to_spec(match, commissioned=commissioned)

    holds = info.get("total_holds")
    fighters = info.get("fighters")
    warp = info.get("turns_per_warp")
    return ShipSpec(
        name=base.name,
        cost=base.cost,
        holds=int(holds) if isinstance(holds, int) else base.holds,
        turns_per_warp=int(warp) if isinstance(warp, int) and warp >= 1 else base.turns_per_warp,
        fighters=int(fighters) if isinstance(fighters, int) else base.fighters,
        shields=base.shields,
        alignment_req=base.alignment_req,
        commissioned=base.commissioned,
    )


def ship_spec_as_dict(spec: ShipSpec) -> dict:
    """Wire-shaped ShipSpec mapping for ``status["upgrade_catalog"]`` rows."""
    return {
        "name": spec.name,
        "cost": spec.cost,
        "holds": spec.holds,
        "turns_per_warp": spec.turns_per_warp,
        "fighters": spec.fighters,
        "shields": spec.shields,
        "alignment_req": spec.alignment_req,
        "commissioned": spec.commissioned is True,
    }


def upgrade_catalog_from_ships(ships: Sequence[object] | None) -> list[dict]:
    """Layer-B ``GameData.ships`` → ``upgrade_catalog`` rows (priced only).

    Cost/shields come from catalog rows via ``ship_row_to_spec`` — never invented.
    Zero-cost / hostile rows are skipped. Never raises.
    """
    if not ships:
        return []
    from .game_data import ShipRow, ship_row_to_spec

    out: list[dict] = []
    for item in ships:
        try:
            if isinstance(item, ShipSpec):
                if item.cost <= 0:
                    continue
                out.append(ship_spec_as_dict(item))
                continue
            if isinstance(item, ShipRow):
                cost = item.base_cost_credits
            elif isinstance(item, dict):
                cost = item.get("base_cost_credits", item.get("cost"))
            else:
                continue
            if isinstance(cost, bool) or not isinstance(cost, int) or cost <= 0:
                continue
            spec = ship_row_to_spec(item)
            out.append(ship_spec_as_dict(spec))
        except Exception:  # noqa: BLE001 -- skip hostile row
            continue
    return out


def upgrade_player_from_status(
    status: dict,
    *,
    ships: Sequence[object] | None = None,
) -> Optional[dict]:
    """Build ``upgrade_player`` from live status + optional GameData ships.

    Requires genuine ``turns_left`` and ``current_ship.total_holds``. When
    ``ships`` is provided, calls :func:`ship_spec_from_current_info` so shields
    (catalog-only) enrich the player snapshot. Fail-closed → ``None``.
    """
    if not isinstance(status, dict):
        return None
    turns = status.get("turns_left")
    if isinstance(turns, bool) or not isinstance(turns, int) or turns < 0:
        return None
    current = status.get("current_ship")
    if not isinstance(current, dict):
        return None
    holds = current.get("total_holds")
    fighters = current.get("fighters")
    current_holds = holds if isinstance(holds, int) and not isinstance(holds, bool) else None
    current_fighters = (
        fighters if isinstance(fighters, int) and not isinstance(fighters, bool) else None
    )
    current_shields = 0
    if ships:
        enriched = ship_spec_from_current_info(current, catalog=ships)
        if enriched is not None:
            if current_holds is None:
                current_holds = enriched.holds
            if current_fighters is None:
                current_fighters = enriched.fighters
            current_shields = enriched.shields
    if current_holds is None:
        return None
    reserve = status.get("turn_reserve")
    if isinstance(reserve, bool) or not isinstance(reserve, int) or reserve < 0:
        reserve = 0
    return {
        "turns_left": turns,
        "current_holds": current_holds,
        "turn_reserve": reserve,
        "hostile_or_pvp": status.get("hostile_or_pvp") is True,
        "current_fighters": current_fighters if current_fighters is not None else 0,
        "current_shields": current_shields,
    }


def upgrade_loop_from_chain(
    chain: object,
    *,
    current_holds: int,
    catalog_max_holds: Optional[int] = None,
) -> Optional[dict]:
    """Honest ``upgrade_loop`` from a priced ProfitChain-like object.

    ``margin_per_hold`` ← ``overall_profit`` (per-unit spread sum);
    ``turns_per_cycle`` ← ``turns``. Stock capacity uses the canon
    ``MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE`` gate rather than inventing port
    stock: short chains cap at ``current_holds`` (bigger hulls need chains);
    long chains defer the stock gate to ROI by allowing up to the largest
    known catalog hull. Never raises.
    """
    try:
        overall = getattr(chain, "overall_profit", None)
        turns = getattr(chain, "turns", None)
        hops = getattr(chain, "hops", None)
        if isinstance(overall, bool) or not isinstance(overall, (int, float)):
            return None
        if isinstance(turns, bool) or not isinstance(turns, int) or turns <= 0:
            return None
        margin = int(round(float(overall)))
        if margin <= 0:
            return None
        try:
            hop_count = len(hops) if hops is not None else 0
        except TypeError:
            hop_count = 0
        from .chains import MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE

        cur = max(0, int(current_holds))
        if hop_count < MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE:
            stock = cur
        else:
            cap = catalog_max_holds if isinstance(catalog_max_holds, int) else cur
            stock = max(cur, cap, 1)
        return {
            "margin_per_hold": margin,
            "turns_per_cycle": turns,
            "stock_capacity": stock,
        }
    except Exception:  # noqa: BLE001 -- fail-closed
        return None


def merge_upgrade_status_inputs(
    status: object,
    *,
    ships: Sequence[object] | None = None,
    chain: object | None = None,
    cost_per_hold: Optional[int] = None,
) -> object:
    """Attach ``upgrade_*`` keys when evidence exists; never mutates; never clobbers.

    Call from ``GameDataStats.merge`` (catalog + player + hold cost) and from
    ``FocusScalars.merge`` (loop from priced chain). Incomplete evidence → omit.
    Never raises.
    """
    if not isinstance(status, dict):
        return status
    try:
        merged = dict(status)
        catalog = merged.get("upgrade_catalog")
        if not isinstance(catalog, list):
            catalog = None
        if catalog is None and ships:
            built = upgrade_catalog_from_ships(ships)
            if built:
                merged["upgrade_catalog"] = built
                catalog = built

        if (
            merged.get("upgrade_cost_per_hold") is None
            and isinstance(cost_per_hold, int)
            and not isinstance(cost_per_hold, bool)
            and cost_per_hold >= 0
        ):
            merged["upgrade_cost_per_hold"] = cost_per_hold

        if merged.get("upgrade_player") is None:
            player = upgrade_player_from_status(merged, ships=ships)
            if player is not None:
                merged["upgrade_player"] = player

        if merged.get("upgrade_loop") is None and chain is not None:
            player = merged.get("upgrade_player")
            holds = 0
            if isinstance(player, dict):
                h = player.get("current_holds")
                if isinstance(h, int) and not isinstance(h, bool):
                    holds = h
            max_holds: Optional[int] = None
            if isinstance(catalog, list):
                for row in catalog:
                    if not isinstance(row, dict):
                        continue
                    rh = row.get("holds")
                    if isinstance(rh, int) and not isinstance(rh, bool):
                        max_holds = rh if max_holds is None else max(max_holds, rh)
            loop = upgrade_loop_from_chain(
                chain, current_holds=holds, catalog_max_holds=max_holds
            )
            if loop is not None:
                merged["upgrade_loop"] = loop
        return merged
    except Exception:  # noqa: BLE001 -- never break the status path
        return status


def compose_upgrade_decision_lines(
    decision: UpgradeDecision,
    *,
    width: int = 40,
) -> list[str]:
    """Human-facing recommend-only callout lines for DECISIONS / coach.

    Never invents purchase commands — rationale text only. Never raises.
    """
    try:
        width = max(8, int(width))
    except (TypeError, ValueError):
        width = 40
    if not isinstance(decision, UpgradeDecision):
        return []
    if decision.recommend and decision.ship is not None:
        title = f"Upgrade: {decision.ship.name}"
    else:
        title = "Upgrade: HOLD"
    rationale = (decision.rationale or "").strip() or "no rationale"
    lines = [title[:width], f" {rationale}"[:width]]
    return lines


def upgrade_decision_from_status(status: object) -> Optional[UpgradeDecision]:
    """Build an :class:`UpgradeDecision` from a status dict, or ``None``.

    Accepts either a precomputed ``status["upgrade_decision"]`` mapping
    (recommend / rationale / optional ship fields) **or** structured
    ``upgrade_catalog`` + ``upgrade_player`` + ``upgrade_loop`` inputs for
    :func:`choose_upgrade`. Fail-closed: incomplete/hostile input → ``None``.
    Never raises.
    """
    if not isinstance(status, dict):
        return None
    try:
        pre = status.get("upgrade_decision")
        if isinstance(pre, UpgradeDecision):
            return pre
        if isinstance(pre, dict):
            recommend = pre.get("recommend") is True
            rationale = pre.get("rationale") if isinstance(pre.get("rationale"), str) else ""
            ship = None
            ship_raw = pre.get("ship")
            if isinstance(ship_raw, ShipSpec):
                ship = ship_raw
            elif isinstance(ship_raw, dict) and isinstance(ship_raw.get("name"), str):
                ship = ShipSpec(
                    name=str(ship_raw.get("name") or ""),
                    cost=int(ship_raw.get("cost") or 0),
                    holds=int(ship_raw.get("holds") or 0),
                    turns_per_warp=int(ship_raw.get("turns_per_warp") or 1),
                    fighters=int(ship_raw.get("fighters") or 0),
                    shields=int(ship_raw.get("shields") or 0),
                    alignment_req=int(ship_raw.get("alignment_req") or 0),
                    commissioned=ship_raw.get("commissioned", True) is True,
                )
            pb = pre.get("projected_payback")
            if pb is not None and not isinstance(pb, (int, float)):
                pb = None
            flags = pre.get("flags")
            flag_t = tuple(flags) if isinstance(flags, (list, tuple)) else ()
            return UpgradeDecision(
                recommend=recommend,
                ship=ship,
                rationale=rationale or ("recommend" if recommend else "HOLD"),
                projected_payback=float(pb) if isinstance(pb, (int, float)) else None,
                flags=tuple(str(f) for f in flag_t),
            )

        catalog_raw = status.get("upgrade_catalog")
        player_raw = status.get("upgrade_player")
        loop_raw = status.get("upgrade_loop")
        if not isinstance(catalog_raw, (list, tuple)):
            return None
        if not isinstance(player_raw, dict) or not isinstance(loop_raw, dict):
            return None
        catalog: list[ShipSpec] = []
        for item in catalog_raw:
            if isinstance(item, ShipSpec):
                catalog.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                catalog.append(
                    ShipSpec(
                        name=str(item.get("name") or ""),
                        cost=int(item.get("cost") or 0),
                        holds=int(item.get("holds") or 0),
                        turns_per_warp=int(item.get("turns_per_warp") or 1),
                        fighters=int(item.get("fighters") or 0),
                        shields=int(item.get("shields") or 0),
                        alignment_req=int(item.get("alignment_req") or 0),
                        commissioned=item.get("commissioned", True) is True,
                    )
                )
        if not catalog:
            return None
        state = PlayerState(
            turns_left=int(player_raw.get("turns_left") or 0),
            current_holds=int(player_raw.get("current_holds") or 0),
            turn_reserve=int(player_raw.get("turn_reserve") or 0),
            hostile_or_pvp=player_raw.get("hostile_or_pvp") is True,
            current_fighters=int(player_raw.get("current_fighters") or 0),
            current_shields=int(player_raw.get("current_shields") or 0),
        )
        loop = LoopEconomics(
            margin_per_hold=int(loop_raw.get("margin_per_hold") or 0),
            turns_per_cycle=int(loop_raw.get("turns_per_cycle") or 1),
            stock_capacity=int(loop_raw.get("stock_capacity") or 0),
            needs_chains_above=(
                int(loop_raw["needs_chains_above"])
                if isinstance(loop_raw.get("needs_chains_above"), int)
                else None
            ),
        )
        cost_per_hold = status.get("upgrade_cost_per_hold", 0)
        if not isinstance(cost_per_hold, int) or isinstance(cost_per_hold, bool):
            cost_per_hold = 0
        return choose_upgrade(catalog, state, loop, cost_per_hold=cost_per_hold)
    except Exception:  # noqa: BLE001 -- fail-closed
        return None

