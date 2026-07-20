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

from twclient import world_model


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


def pick_frontier_edge(
    frontier: Sequence[FrontierEdge],
    *,
    epsilon: float = 0.1,
    rng: Optional[random.Random] = None,
) -> tuple[Optional[FrontierEdge], str]:
    """ε-greedy: usually nearest (exploit map-fill), occasionally random.

    Returns (edge, mode) where mode is explore|exploit|exhausted.
    """
    if not frontier:
        return None, "exhausted"
    r = rng or random.Random()
    eps = max(0.0, min(1.0, float(epsilon)))
    if eps > 0 and r.random() < eps:
        return r.choice(list(frontier)), "explore"
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
    edge, mode = pick_frontier_edge(frontier, epsilon=epsilon, rng=rng)
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
    mode: str  # "route" | "hunt" | "arrived" | "exhausted"


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
            return StarDockPlan(
                found=True,
                stardock_sectors=docks,
                route=None,
                next_sector=None,
                hunt=None,
                mode="exhausted",
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
    nxt = hunt.next_hop.to if hunt.next_hop is not None else None
    return StarDockPlan(
        found=False,
        stardock_sectors=(),
        route=None,
        next_sector=nxt,
        hunt=hunt,
        mode="hunt" if nxt is not None else "exhausted",
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
        nxt = hunt.next_hop.to if hunt.next_hop is not None else None
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
