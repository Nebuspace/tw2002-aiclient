"""TW-14 auto-explore planners — Map-fill BFS frontier over the world-model.

Pure client-side planning: reads `world_model` sector graphs and returns
the next warp targets to visit. Does NOT emit keystrokes (trainer panel /
daemon nav wire later). Respects a turn budget and an ε-greedy explore
knob (§11) as knobs on *which* frontier edge to pick, not as live sends.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from tw2002_aiclient import world_model


@dataclass(frozen=True)
class FrontierEdge:
    """A known sector with a warp to a not-yet-mapped neighbor."""

    frm: int
    to: int
    depth: int  # BFS distance from the seed sector


@dataclass(frozen=True)
class MapFillPlan:
    """Result of one Map-fill planning tick."""

    next_hop: Optional[FrontierEdge]
    frontier: tuple[FrontierEdge, ...]
    known_sectors: int
    unmapped_targets: int
    turns_budget_remaining: int
    mode: str  # "explore" | "exploit" | "exhausted"


def _sector_id(rec: Mapping) -> int:
    return int(rec["sector_id"])


def _warps(rec: Mapping) -> tuple[int, ...]:
    raw = rec.get("warps") or ()
    return tuple(int(w) for w in raw)


def known_graph(
    world_id: str,
    *,
    state_dir=None,
) -> dict[int, tuple[int, ...]]:
    """sector_id → warps for every sector currently on disk."""
    out: dict[int, tuple[int, ...]] = {}
    for rec in world_model.all_sectors(world_id, state_dir=state_dir):
        sid = _sector_id(rec)
        out[sid] = _warps(rec)
    return out


def frontier_edges(
    graph: Mapping[int, Sequence[int]],
    *,
    start: int,
) -> list[FrontierEdge]:
    """BFS from `start` over KNOWN warps; collect edges to UNKNOWN ids.

    An unknown target is any warp destination not present as a key in
    `graph` (never recorded). Depth is hop-count from start along the
    known subgraph.
    """
    if start not in graph:
        return []
    known = set(graph.keys())
    frontier: list[FrontierEdge] = []
    seen_edge: set[tuple[int, int]] = set()
    q: deque[tuple[int, int]] = deque([(start, 0)])
    visited = {start}
    while q:
        node, depth = q.popleft()
        for nxt in graph.get(node, ()):
            if nxt not in known:
                key = (node, nxt)
                if key not in seen_edge:
                    seen_edge.add(key)
                    frontier.append(FrontierEdge(frm=node, to=nxt, depth=depth + 1))
                continue
            if nxt in visited:
                continue
            visited.add(nxt)
            q.append((nxt, depth + 1))
    frontier.sort(key=lambda e: (e.depth, e.frm, e.to))
    return frontier


def known_port_sectors(
    world_id: str,
    *,
    state_dir=None,
) -> set[int]:
    """Sector ids whose world-model `port` field is non-None (flyby or docked)."""
    out: set[int] = set()
    for rec in world_model.all_sectors(world_id, state_dir=state_dir):
        if rec.get("port") is not None:
            out.add(_sector_id(rec))
    return out


def pick_frontier_edge(
    frontier: Sequence[FrontierEdge],
    *,
    epsilon: float = 0.1,
    rng: Optional[random.Random] = None,
    port_seed_frms: Optional[set[int]] = None,
) -> tuple[Optional[FrontierEdge], str]:
    """ε-greedy: usually nearest (exploit map-fill), occasionally random.

    WO-PORT-CHAIN-SEED: when `port_seed_frms` is set, exploit prefers
    frontier edges whose `frm` is a known-port sector (expand that port's
    unmapped neighborhood for pair-hunt) over a nearer unrelated edge.
    ε-explore still samples the full frontier so map-fill remains reachable.
    Map-fill is the fallback when no seeded edge exists.

    Returns (edge, mode) where mode is explore|exploit|exhausted.
    """
    if not frontier:
        return None, "exhausted"
    r = rng or random.Random()
    eps = max(0.0, min(1.0, float(epsilon)))
    if eps > 0 and r.random() < eps:
        return r.choice(list(frontier)), "explore"
    seeds = port_seed_frms or set()
    if seeds:
        seeded = [e for e in frontier if e.frm in seeds]
        if seeded:
            return seeded[0], "exploit"  # nearest seeded (frontier pre-sorted)
    return frontier[0], "exploit"  # nearest by depth (sorted)


def plan_map_fill(
    world_id: str,
    *,
    current_sector: int,
    turn_budget: int,
    epsilon: float = 0.1,
    state_dir=None,
    rng: Optional[random.Random] = None,
) -> MapFillPlan:
    """One Map-fill tick: propose the next unmapped hop under budget."""
    budget = max(0, int(turn_budget))
    graph = known_graph(world_id, state_dir=state_dir)
    frontier = frontier_edges(graph, start=current_sector)
    unmapped = len({e.to for e in frontier})
    if budget <= 0:
        return MapFillPlan(
            next_hop=None,
            frontier=tuple(frontier),
            known_sectors=len(graph),
            unmapped_targets=unmapped,
            turns_budget_remaining=0,
            mode="exhausted",
        )
    port_seeds = known_port_sectors(world_id, state_dir=state_dir)
    edge, mode = pick_frontier_edge(
        frontier, epsilon=epsilon, rng=rng, port_seed_frms=port_seeds,
    )
    return MapFillPlan(
        next_hop=edge,
        frontier=tuple(frontier),
        known_sectors=len(graph),
        unmapped_targets=unmapped,
        turns_budget_remaining=budget,
        mode=mode if edge is not None else "exhausted",
    )


@dataclass(frozen=True)
class StarDockPlan:
    """One Find-StarDock tick — route if known, else map-fill to hunt."""

    found: bool
    stardock_sectors: tuple[int, ...]
    route: Optional[tuple[int, ...]]  # path on known graph when found
    next_sector: Optional[int]  # immediate next hop toward dock or frontier
    hunt: Optional[MapFillPlan]  # set when dock not yet landmark-cached
    mode: str  # "route" | "hunt" | "arrived" | "exhausted" | "recovery:stardock" | "recovery:densest"


@dataclass(frozen=True)
class RecoveryPlan:
    """WO-EXPLORE-NO-CANDIDATES: what to do when the frontier is empty.

    Policy order (never guessed prices; never invents warps):
      1. ``stardock`` — hop toward a known StarDock landmark on the graph
      2. ``densest`` — hop toward the highest out-degree reachable sector
      3. ``halt`` — gated stop; no silent empty candidate list
    """

    next_sector: Optional[int]
    target_sector: Optional[int]
    policy: str  # "stardock" | "densest" | "halt"
    reason: str


def reachable_sectors(
    graph: Mapping[int, Sequence[int]],
    start: int,
) -> set[int]:
    """Known-subgraph BFS from ``start`` (only keys present in ``graph``)."""
    if start not in graph:
        return set()
    seen = {start}
    q: deque[int] = deque([start])
    while q:
        node = q.popleft()
        for nxt in graph.get(node, ()):
            if nxt in graph and nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return seen


def densest_reachable_sector(
    graph: Mapping[int, Sequence[int]],
    start: int,
) -> Optional[int]:
    """Highest out-degree sector reachable from ``start`` on the known graph.

    Tie-break: lowest sector id (stable, never random). Returns ``None``
    when ``start`` is absent from the graph.
    """
    reachable = reachable_sectors(graph, start)
    if not reachable:
        return None
    return max(reachable, key=lambda sid: (len(tuple(graph.get(sid, ()))), -sid))


def plan_exhausted_recovery(
    world_id: str,
    *,
    current_sector: int,
    turn_budget: int = 1,
    landmark: str = "StarDock",
    state_dir=None,
) -> RecoveryPlan:
    """Recovery when Map-fill frontier / StarDock hunt has nothing left.

    Never invents StarDock prices or unknown warps — only adjacent hops
    along the known subgraph (same discipline as ``_adjacent_hop_toward``).
    """
    budget = max(0, int(turn_budget))
    cur = int(current_sector)
    graph = known_graph(world_id, state_dir=state_dir)
    if budget <= 0:
        return RecoveryPlan(
            next_sector=None,
            target_sector=None,
            policy="halt",
            reason="explore_exhausted:turn_budget",
        )
    if cur not in graph:
        return RecoveryPlan(
            next_sector=None,
            target_sector=None,
            policy="halt",
            reason="explore_exhausted:current_unknown",
        )

    docks = tuple(find_landmark_sectors(world_id, landmark, state_dir=state_dir))
    best_dock_path: Optional[tuple[int, ...]] = None
    best_dock: Optional[int] = None
    for dock in docks:
        path = path_to_sector(graph, cur, dock)
        if path is None:
            continue
        if best_dock_path is None or len(path) < len(best_dock_path):
            best_dock_path = path
            best_dock = dock
    if best_dock_path is not None and len(best_dock_path) > 1:
        return RecoveryPlan(
            next_sector=best_dock_path[1],
            target_sector=best_dock,
            policy="stardock",
            reason="recovery:stardock",
        )

    densest = densest_reachable_sector(graph, cur)
    if densest is not None and densest != cur:
        path = path_to_sector(graph, cur, densest)
        if path is not None and len(path) > 1:
            return RecoveryPlan(
                next_sector=path[1],
                target_sector=densest,
                policy="densest",
                reason="recovery:densest",
            )

    if best_dock is not None and best_dock == cur:
        halt_reason = "explore_exhausted:at_stardock"
    elif densest is not None and densest == cur:
        halt_reason = "explore_exhausted:at_densest"
    else:
        halt_reason = "explore_exhausted:no_recovery_target"
    return RecoveryPlan(
        next_sector=None,
        target_sector=densest if densest is not None else best_dock,
        policy="halt",
        reason=halt_reason,
    )


def _apply_recovery_to_stardock_plan(
    plan: "StarDockPlan",
    *,
    world_id: str,
    current_sector: int,
    turn_budget: int,
    landmark: str,
    state_dir,
) -> "StarDockPlan":
    """When frontier/route yields no hop, attach densest/StarDock recovery.

    Leaves ``arrived`` untouched (already at dock). ``mode="exhausted"``
    after this means halt-with-attention for autopilot — never a silent
    empty candidate list.
    """
    if plan.next_sector is not None or plan.mode == "arrived":
        return plan
    recovery = plan_exhausted_recovery(
        world_id,
        current_sector=current_sector,
        turn_budget=turn_budget,
        landmark=landmark,
        state_dir=state_dir,
    )
    if recovery.next_sector is None:
        return StarDockPlan(
            found=plan.found,
            stardock_sectors=plan.stardock_sectors,
            route=plan.route,
            next_sector=None,
            hunt=plan.hunt,
            mode="exhausted",
        )
    return StarDockPlan(
        found=plan.found or recovery.policy == "stardock",
        stardock_sectors=plan.stardock_sectors,
        route=plan.route,
        next_sector=recovery.next_sector,
        hunt=plan.hunt,
        mode=f"recovery:{recovery.policy}",
    )


def plan_find_stardock(
    world_id: str,
    *,
    current_sector: int,
    turn_budget: int,
    epsilon: float = 0.1,
    landmark: str = "StarDock",
    state_dir=None,
    rng: Optional[random.Random] = None,
) -> StarDockPlan:
    """Find-StarDock tick: pathfind if landmark known, else Map-fill hunt.

    Does not write the world-model or emit keystrokes — callers that
    visit sectors (density scan / move) are what populate landmarks.

    WO-EXPLORE-NO-CANDIDATES: when the frontier is exhausted (and we are
    not already mid-route to a dock), attach densest / StarDock recovery
    or leave ``mode="exhausted"`` for an explicit autopilot halt.
    """
    budget = max(0, int(turn_budget))
    docks = tuple(find_landmark_sectors(world_id, landmark, state_dir=state_dir))
    graph = known_graph(world_id, state_dir=state_dir)
    cur = int(current_sector)

    if docks:
        # Prefer nearest known StarDock on the known subgraph.
        best: Optional[tuple[int, ...]] = None
        for dock in docks:
            path = path_to_sector(graph, cur, dock)
            if path is None:
                continue
            if best is None or len(path) < len(best):
                best = path
        if best is None:
            plan = StarDockPlan(
                found=True,
                stardock_sectors=docks,
                route=None,
                next_sector=None,
                hunt=None,
                mode="exhausted",
            )
            return _apply_recovery_to_stardock_plan(
                plan,
                world_id=world_id,
                current_sector=cur,
                turn_budget=budget,
                landmark=landmark,
                state_dir=state_dir,
            )
        if len(best) == 1:
            return StarDockPlan(
                found=True,
                stardock_sectors=docks,
                route=best,
                next_sector=None,
                hunt=None,
                mode="arrived",
            )
        if budget <= 0:
            return StarDockPlan(
                found=True,
                stardock_sectors=docks,
                route=best,
                next_sector=None,
                hunt=None,
                mode="exhausted",
            )
        return StarDockPlan(
            found=True,
            stardock_sectors=docks,
            route=best,
            next_sector=best[1],
            hunt=None,
            mode="route",
        )

    hunt = plan_map_fill(
        world_id,
        current_sector=cur,
        turn_budget=budget,
        epsilon=epsilon,
        state_dir=state_dir,
        rng=rng,
    )
    # HIGH fix (see `_adjacent_hop_toward`'s own docstring): never hand
    # back the frontier's own (possibly non-adjacent) `to` sector as
    # `next_sector` -- resolve it to a valid single hop from `cur` first.
    nxt = _adjacent_hop_toward(graph, cur, hunt.next_hop)
    plan = StarDockPlan(
        found=False,
        stardock_sectors=(),
        route=None,
        next_sector=nxt,
        hunt=hunt,
        mode="hunt" if nxt is not None else "exhausted",
    )
    if nxt is not None:
        return plan
    return _apply_recovery_to_stardock_plan(
        plan,
        world_id=world_id,
        current_sector=cur,
        turn_budget=budget,
        landmark=landmark,
        state_dir=state_dir,
    )


@dataclass(frozen=True)
class FormationsPlan:
    """One Find-Formations tick — route to a catalogued candidate, else hunt."""

    found: bool
    targets: tuple[int, ...]  # genesis / formation sectors of interest
    kind: Optional[str]
    route: Optional[tuple[int, ...]]
    next_sector: Optional[int]
    hunt: Optional[MapFillPlan]
    mode: str  # "route" | "hunt" | "arrived" | "exhausted" | "catalog"


def plan_find_formations(
    world_id: str,
    *,
    current_sector: int,
    turn_budget: int,
    epsilon: float = 0.1,
    state_dir=None,
    rng: Optional[random.Random] = None,
) -> FormationsPlan:
    """Find-Formations tick: route toward nearest genesis candidate.

    Runs TW-16 `catalog_world` (read-only). If candidates exist, pathfind
    to the nearest (entrance if set, else first sector). Otherwise Map-fill
    to grow the graph. Never deploys Genesis — locate/recommend only.
    """
    from twclient.formations import catalog_world

    budget = max(0, int(turn_budget))
    cur = int(current_sector)
    graph = known_graph(world_id, state_dir=state_dir)
    cat = catalog_world(world_id, state_dir=state_dir)
    candidates = cat.genesis_candidates
    if not candidates:
        hunt = plan_map_fill(
            world_id,
            current_sector=cur,
            turn_budget=budget,
            epsilon=epsilon,
            state_dir=state_dir,
            rng=rng,
        )
        # HIGH fix -- same non-adjacent-target defect as
        # `plan_find_stardock`'s own hunt branch, see `_adjacent_hop_toward`.
        nxt = _adjacent_hop_toward(graph, cur, hunt.next_hop)
        return FormationsPlan(
            found=False,
            targets=(),
            kind=None,
            route=None,
            next_sector=nxt,
            hunt=hunt,
            mode="hunt" if nxt is not None else "exhausted",
        )

    # Nearest candidate by path length to entrance or first member.
    best_route: Optional[tuple[int, ...]] = None
    best_kind: Optional[str] = None
    best_targets: tuple[int, ...] = ()
    for f in candidates:
        goal = f.entrance if f.entrance is not None else (f.sectors[0] if f.sectors else None)
        if goal is None:
            continue
        path = path_to_sector(graph, cur, goal)
        if path is None:
            continue
        if best_route is None or len(path) < len(best_route):
            best_route = path
            best_kind = f.kind
            best_targets = f.sectors

    if best_route is None:
        return FormationsPlan(
            found=True,
            targets=tuple(sorted({s for f in candidates for s in f.sectors})),
            kind=candidates[0].kind,
            route=None,
            next_sector=None,
            hunt=None,
            mode="catalog",
        )
    if len(best_route) == 1:
        return FormationsPlan(
            found=True,
            targets=best_targets,
            kind=best_kind,
            route=best_route,
            next_sector=None,
            hunt=None,
            mode="arrived",
        )
    if budget <= 0:
        return FormationsPlan(
            found=True,
            targets=best_targets,
            kind=best_kind,
            route=best_route,
            next_sector=None,
            hunt=None,
            mode="exhausted",
        )
    return FormationsPlan(
        found=True,
        targets=best_targets,
        kind=best_kind,
        route=best_route,
        next_sector=best_route[1],
        hunt=None,
        mode="route",
    )


EXPLORE_MODES = ("off", "mapfill", "stardock", "formations")


def cycle_explore_mode(current: str) -> str:
    """Trainer-panel tick cycle: off → mapfill → stardock → formations → off."""
    cur = current if current in EXPLORE_MODES else "off"
    i = EXPLORE_MODES.index(cur)
    return EXPLORE_MODES[(i + 1) % len(EXPLORE_MODES)]


def format_explore_decision_lines(mode: str, plan) -> list[str]:
    """Short DECISIONS-pane lines for the active explore tick (no keystrokes)."""
    if mode == "off" or plan is None:
        return ["E) explore off", "cycles map/sd/form"]
    if mode == "mapfill":
        label = "MAP-FILL"
        nxt = getattr(plan, "next_hop", None)
        nxt_s = getattr(nxt, "to", None) if nxt is not None else None
        m = getattr(plan, "mode", "?")
        if nxt_s is not None:
            return [label, f"next →{nxt_s}", f"({m})"]
        return [label, "no frontier", f"({m})"]
    if mode == "stardock":
        label = "FIND-SD"
        nxt = getattr(plan, "next_sector", None)
        m = getattr(plan, "mode", "?")
        if m == "arrived":
            return [label, "at StarDock", "(arrived)"]
        if nxt is not None:
            return [label, f"next →{nxt}", f"({m})"]
        return [label, "no route yet", f"({m})"]
    if mode == "formations":
        label = "FORMATIONS"
        nxt = getattr(plan, "next_sector", None)
        kind = getattr(plan, "kind", None) or "—"
        m = getattr(plan, "mode", "?")
        if m == "arrived":
            return [label, f"at {kind}", "(arrived)"]
        if nxt is not None:
            return [label, f"next →{nxt}", f"{kind} ({m})"]
        return [label, f"{kind}", f"({m})"]
    return [f"E) {mode}"]


def find_landmark_sectors(
    world_id: str,
    landmark_name: str,
    *,
    state_dir=None,
) -> list[int]:
    """Sectors whose landmarks list mentions `landmark_name` (casefold)."""
    needle = landmark_name.casefold()
    hits: list[int] = []
    for rec in world_model.all_sectors(world_id, state_dir=state_dir):
        marks = rec.get("landmarks") or []
        for m in marks:
            if str(m).casefold() == needle:
                hits.append(_sector_id(rec))
                break
    return sorted(hits)


def path_to_sector(
    graph: Mapping[int, Sequence[int]],
    start: int,
    goal: int,
) -> Optional[tuple[int, ...]]:
    """Shortest path (sector ids) on the known warp graph, or None."""
    if start == goal:
        return (start,)
    if start not in graph or goal not in graph:
        return None
    q: deque[int] = deque([start])
    prev: dict[int, Optional[int]] = {start: None}
    while q:
        node = q.popleft()
        for nxt in graph.get(node, ()):
            if nxt in prev or nxt not in graph:
                continue
            prev[nxt] = node
            if nxt == goal:
                path = [goal]
                cur: Optional[int] = goal
                while cur is not None and cur != start:
                    cur = prev[cur]
                    if cur is not None:
                        path.append(cur)
                path.reverse()
                return tuple(path)
            q.append(nxt)
    return None


def _adjacent_hop_toward(
    graph: Mapping[int, Sequence[int]],
    current: int,
    edge: Optional[FrontierEdge],
) -> Optional[int]:
    """HIGH fix (mack/cipher adversarial re-verify, 2026-07-21): resolve a
    frontier edge into a single VALID, ADJACENT next-hop from `current` --
    never the frontier's own `to` sector directly.

    `frontier_edges()` BFS-walks the KNOWN subgraph from the seed sector,
    so a returned edge's `frm` is whichever known sector the unmapped
    warp was actually found from -- not necessarily `current` itself
    (the nearest frontier edge overall can be several known hops away).
    `plan_find_stardock()`/`plan_find_formations()` used to hand back
    `edge.to` as `next_sector` unconditionally, so a caller several hops
    from the frontier would fire a bare warp straight at a sector it
    can't actually reach in one hop -- an invalid send the game would
    reject, spinning the loop toward `max_ticks` with no progress.

    When `current == edge.frm`, `edge.to` genuinely IS one of `current`'s
    own listed warps (safe, adjacent -- this is literally how a player
    discovers a new sector for the first time). Otherwise, warp toward
    `edge.frm` first: the FIRST hop of the shortest known path from
    `current` to `edge.frm` is guaranteed adjacent to `current` (a real
    entry in `graph[current]`) -- SELECT is stateless and re-plans fresh
    every tick (see autopilot.py's own module docstring), so taking one
    valid hop at a time toward the frontier, re-evaluated each tick, is
    both correct and sufficient; it never needs to compute the WHOLE
    remaining path up front.

    Returns `None` (never guessed) when `edge` is `None`, or -- defensive
    only, should be unreachable since `frontier_edges()` only ever
    records a `frm` it actually reached via BFS from `current` -- when
    `edge.frm` turns out unreachable from `current` on this graph."""
    if edge is None:
        return None
    if current == edge.frm:
        return edge.to
    path = path_to_sector(graph, current, edge.frm)
    if path is None or len(path) < 2:
        return None
    return path[1]


INTENT_MAP_FILL = "map_fill"
INTENT_FIND_STARDOCK = "find_stardock"
#: The intents a caller may arm. Deliberately a closed set: an unknown intent
#: is REFUSED by the daemon rather than silently falling back to map-fill,
#: because a run that quietly does something other than what the confirm line
#: promised is exactly what the arm gate exists to prevent.
INTENTS = frozenset({INTENT_MAP_FILL, INTENT_FIND_STARDOCK})

#: Cycle order for the Play `E` offer. ORDERED (a frozenset is not) and
#: map-fill FIRST so the first `E` press raises exactly the prompt it raised
#: before this WO -- an operator's muscle memory must not arm a different run
#: than it armed yesterday.
#:
#: `cycle_explore_mode`'s "off → mapfill → stardock → formations" is the
#: fuller trainer-panel cycle and stays UNWIRED: `formations` has no armable
#: path (`plan_find_formations` has no callers either) and this WO's scope
#: excludes it. Two vocabularies therefore exist -- these daemon intents and
#: that panel's mode names -- and unifying them is deliberately left to the
#: WO that wires the panel, rather than half-done here.
ARMABLE_INTENTS: tuple[str, ...] = (INTENT_MAP_FILL, INTENT_FIND_STARDOCK)


def next_armable_intent(current: object) -> str:
    """The next intent in the Play offer cycle. Never raises; anything
    unrecognised restarts at map-fill."""
    try:
        i = ARMABLE_INTENTS.index(current)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return ARMABLE_INTENTS[0]
    return ARMABLE_INTENTS[(i + 1) % len(ARMABLE_INTENTS)]


@dataclass(frozen=True)
class IntentTick:
    """One intent-driven decision: hop here, stop here, or we are done.

    Three states, and the third is why this is not a ``(target, reason)``
    tuple like :func:`map_fill_warp_target` returns. Find-StarDock can
    ``arrive`` — a *success* — and a tuple whose only non-``None`` answer is
    "next hop" would have to encode that as a halt reason, making a completed
    goal indistinguishable from an exhausted frontier in the run report.
    """

    next_sector: Optional[int]
    goal_reached: bool = False
    reason: str = ""


def warp_target_for_intent(
    intent: str,
    world_id: str,
    *,
    current_sector: int,
    turn_budget: int,
    epsilon: float = 0.1,
    state_dir=None,
    rng: Optional[random.Random] = None,
) -> IntentTick:
    """One tick for *intent* — the single seam the explore runner drives.

    ``map_fill`` delegates to :func:`map_fill_warp_target` unchanged, so the
    existing behaviour (and its tests) keep one owner. ``find_stardock``
    routes to :func:`plan_find_stardock`, which was fully built and had **no
    callers anywhere** before this WO.

    An unrecognised intent returns a halt rather than defaulting to map-fill:
    the daemon refuses unknown intents up front, so reaching here with one
    means an internal disagreement, and quietly exploring in some other
    direction is worse than stopping.
    """
    if intent == INTENT_MAP_FILL:
        target, reason = map_fill_warp_target(
            world_id,
            current_sector=current_sector,
            turn_budget=turn_budget,
            epsilon=epsilon,
            state_dir=state_dir,
            rng=rng,
        )
        return IntentTick(next_sector=target, reason=reason)
    if intent != INTENT_FIND_STARDOCK:
        return IntentTick(next_sector=None, reason=f"explore_exhausted:unknown_intent:{intent}")

    plan = plan_find_stardock(
        world_id,
        current_sector=current_sector,
        turn_budget=turn_budget,
        epsilon=epsilon,
        state_dir=state_dir,
        rng=rng,
    )
    if plan.mode == "arrived":
        return IntentTick(next_sector=None, goal_reached=True)
    if plan.next_sector is None:
        reason = plan.mode or "no_hop"
        if not reason.startswith("explore_exhausted"):
            reason = f"explore_exhausted:{reason}"
        return IntentTick(next_sector=None, reason=reason)
    # `StarDockPlan.next_sector` is already the IMMEDIATE next hop ("next hop
    # toward dock or frontier"), not a distant waypoint, so it is returned as
    # given -- resolving it again through `_adjacent_hop_toward` would be
    # wrong twice over (that helper takes a `FrontierEdge`, not a sector id).
    # The runner re-checks adjacency against the known graph before sending,
    # which is where a planner that ever returned a non-adjacent hop is
    # caught -- one owner for that refusal, and it is the layer that sends.
    return IntentTick(next_sector=int(plan.next_sector))


def map_fill_warp_target(
    world_id: str,
    *,
    current_sector: int,
    turn_budget: int,
    epsilon: float = 0.1,
    state_dir=None,
    rng: Optional[random.Random] = None,
) -> tuple[Optional[int], str]:
    """Map-fill tick → one adjacent warp target, or ``(None, halt_reason)``.

    Uses ``plan_map_fill`` then ``plan_exhausted_recovery`` when the frontier
    is empty — same AP-08 discipline as archive ``autopilot`` explore ticks.
    """
    plan = plan_map_fill(
        world_id,
        current_sector=current_sector,
        turn_budget=turn_budget,
        epsilon=epsilon,
        state_dir=state_dir,
        rng=rng,
    )
    graph = known_graph(world_id, state_dir=state_dir)
    if plan.next_hop is not None and plan.mode != "exhausted":
        nxt = _adjacent_hop_toward(graph, current_sector, plan.next_hop)
        if nxt is not None:
            return nxt, ""
    recovery = plan_exhausted_recovery(
        world_id,
        current_sector=current_sector,
        turn_budget=turn_budget,
        state_dir=state_dir,
    )
    if recovery.next_sector is not None:
        return recovery.next_sector, recovery.reason
    reason = recovery.reason or "explore_exhausted:no_recovery_target"
    if not reason.startswith("explore_exhausted"):
        reason = f"explore_exhausted:{reason}"
    return None, reason
