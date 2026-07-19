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
