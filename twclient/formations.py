"""TW-16 formation detector — topology catalog over the world-model warp graph.

LOCATE / CATALOG / RECOMMEND only (doctrine/special-formations.md). Never
deploys a Genesis device or claims space — genesis_candidates are hints
for the operator. Detection does not drive exploration; it walks what
`world_model` already knows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from twclient import world_model
from twclient.explore import known_graph


DEAD_END = "dead-end"
BUBBLE = "bubble"
ONE_WAY = "one-way"
WARP_SINK = "warp-sink"

GENESIS_TYPES = frozenset({DEAD_END, BUBBLE})


@dataclass(frozen=True)
class Formation:
    kind: str
    sectors: tuple[int, ...]
    entrance: Optional[int] = None  # bubble / dead-end approach sector
    detail: str = ""


@dataclass(frozen=True)
class FormationCatalog:
    formations: tuple[Formation, ...]
    genesis_candidates: tuple[Formation, ...]
    known_sectors: int

    def by_kind(self, kind: str) -> tuple[Formation, ...]:
        return tuple(f for f in self.formations if f.kind == kind)


def _undirected(graph: Mapping[int, Sequence[int]]) -> dict[int, set[int]]:
    adj: dict[int, set[int]] = {int(s): set() for s in graph}
    for a, warps in graph.items():
        a = int(a)
        for b in warps:
            b = int(b)
            if b not in adj:
                # Warp to an unmapped id — skip undirected pocket math
                # until both ends are known; one-way pass handles directed.
                continue
            adj[a].add(b)
            adj[b].add(a)
    return adj


def _components(undirected: Mapping[int, set[int]]) -> list[set[int]]:
    seen: set[int] = set()
    comps: list[set[int]] = []
    for start in undirected:
        if start in seen:
            continue
        stack = [start]
        comp: set[int] = set()
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            for nxt in undirected.get(n, ()):
                if nxt not in comp:
                    stack.append(nxt)
        seen |= comp
        comps.append(comp)
    return comps


def _dead_ends(graph: Mapping[int, Sequence[int]]) -> list[Formation]:
    out: list[Formation] = []
    for sid, warps in graph.items():
        w = tuple(int(x) for x in warps)
        if len(w) == 1:
            out.append(
                Formation(
                    kind=DEAD_END,
                    sectors=(int(sid),),
                    entrance=w[0],
                    detail="single outbound warp",
                )
            )
    return out


def _bubbles(
    graph: Mapping[int, Sequence[int]],
    undirected: Mapping[int, set[int]],
) -> list[Formation]:
    """Pockets sealed behind a single entrance sector (size ≥ 2 interior).

    For each candidate entrance E and neighbor N, grow the component
    reachable from N without traversing E. If every edge leaving that
    component lands only on E, it is a sealed pocket. Prefer the smaller
    side of a bridge so open-map "outside" is not catalogued as a bubble.
    """
    out: list[Formation] = []
    seen_keys: set[tuple[int, ...]] = set()
    n_all = len(undirected)
    for entrance, nbrs in undirected.items():
        for n in nbrs:
            stack = [n]
            comp: set[int] = set()
            while stack:
                x = stack.pop()
                if x == entrance or x in comp:
                    continue
                comp.add(x)
                for y in undirected.get(x, ()):
                    if y != entrance and y not in comp:
                        stack.append(y)
            if len(comp) < 2:
                continue
            # Smaller side of the cut only (hideout intuition).
            if len(comp) >= n_all - 1:
                continue
            sealed = True
            for x in comp:
                for y in undirected.get(x, ()):
                    if y not in comp and y != entrance:
                        sealed = False
                        break
                if not sealed:
                    break
            if not sealed:
                continue
            # Exactly one door from entrance into the open map.
            outside = undirected.get(entrance, set()) - comp
            if len(outside) != 1:
                continue
            members = tuple(sorted(comp | {entrance}))
            if members in seen_keys:
                continue
            seen_keys.add(members)
            out.append(
                Formation(
                    kind=BUBBLE,
                    sectors=members,
                    entrance=entrance,
                    detail="single-entrance pocket",
                )
            )
    # Prefer innermost pockets — drop any bubble that properly contains another.
    keep: list[Formation] = []
    for f in out:
        if any(
            set(g.sectors) < set(f.sectors) for g in out if g is not f
        ):
            continue
        keep.append(f)
    return keep


def _one_ways(graph: Mapping[int, Sequence[int]]) -> list[Formation]:
    out: list[Formation] = []
    for a, warps in graph.items():
        a = int(a)
        for b in warps:
            b = int(b)
            if b not in graph:
                continue
            if a not in {int(x) for x in graph[b]}:
                out.append(
                    Formation(
                        kind=ONE_WAY,
                        sectors=(a, b),
                        detail=f"{a}→{b} with no reverse warp",
                    )
                )
    return out


def _reachable(graph: Mapping[int, Sequence[int]], start: int) -> set[int]:
    if start not in graph:
        return set()
    seen = {start}
    stack = [start]
    while stack:
        n = stack.pop()
        for nxt in graph.get(n, ()):
            nxt = int(nxt)
            if nxt in graph and nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def _warp_sinks(graph: Mapping[int, Sequence[int]]) -> list[Formation]:
    """Sectors that can be entered but cannot reach the rest of the map.

    A sector S is a sink member when there exists some other known sector
    T that can reach S, but from S the reachable set does not include T
    (and is a proper subset of the full known set). Singleton out-degree-0
    nodes with inbound links are the minimal case.
    """
    if len(graph) < 2:
        return []
    known = set(int(s) for s in graph)
    # Precompute who can reach whom (expensive but OK for mapped subsets
    # under a few thousand; TW maps grow via explore gradually).
    can_reach: dict[int, set[int]] = {
        s: _reachable(graph, s) for s in known
    }
    sink_sectors: set[int] = set()
    for s in known:
        outs = {int(x) for x in graph.get(s, ()) if int(x) in known}
        # Soft: cannot leave own reachable island to a sector that reaches us
        reach_from_s = can_reach[s]
        inbounders = [
            t for t in known if t != s and s in can_reach[t]
        ]
        if not inbounders:
            continue
        # Trap: some inbounder cannot be reached back from s
        trapped = any(t not in reach_from_s for t in inbounders)
        if trapped or (not outs and inbounders):
            sink_sectors.add(s)

    # Don't double-label pure dead-ends as sinks (already catalogued).
    for sid, warps in graph.items():
        if len(tuple(warps)) == 1:
            sink_sectors.discard(int(sid))

    if not sink_sectors:
        return []

    # Cluster adjacent sinks into formations
    und = _undirected({s: graph[s] for s in sink_sectors if s in graph})
    # Ensure isolates appear
    for s in sink_sectors:
        und.setdefault(s, set())
    comps = _components(und) if und else [{s} for s in sink_sectors]
    # Also cover sink sectors missing from undirected (no mutual edges)
    covered = set()
    formations: list[Formation] = []
    for comp in comps:
        members = sorted(comp & sink_sectors)
        if not members:
            continue
        covered.update(members)
        formations.append(
            Formation(
                kind=WARP_SINK,
                sectors=tuple(members),
                detail="no return path to open map",
            )
        )
    for s in sorted(sink_sectors - covered):
        formations.append(
            Formation(
                kind=WARP_SINK,
                sectors=(s,),
                detail="no return path to open map",
            )
        )
    return formations


def detect_formations(
    graph: Mapping[int, Sequence[int]],
) -> FormationCatalog:
    """Pure topology pass — no I/O."""
    g = {int(k): tuple(int(x) for x in v) for k, v in graph.items()}
    und = _undirected(g)
    formations: list[Formation] = []
    formations.extend(_dead_ends(g))
    formations.extend(_bubbles(g, und))
    formations.extend(_one_ways(g))
    formations.extend(_warp_sinks(g))
    # Stable order: kind then first sector
    formations.sort(key=lambda f: (f.kind, f.sectors[0] if f.sectors else -1, f.detail))
    genesis = tuple(f for f in formations if f.kind in GENESIS_TYPES)
    return FormationCatalog(
        formations=tuple(formations),
        genesis_candidates=genesis,
        known_sectors=len(g),
    )


def catalog_world(
    world_id: str,
    *,
    state_dir=None,
) -> FormationCatalog:
    """Run detection over `world_model` sectors for `world_id`."""
    return detect_formations(known_graph(world_id, state_dir=state_dir))


def membership_map(catalog: FormationCatalog) -> dict[int, list[str]]:
    """sector_id → formation kind tags (for world_model.formation_membership)."""
    m: dict[int, list[str]] = {}
    for f in catalog.formations:
        for sid in f.sectors:
            tags = m.setdefault(sid, [])
            if f.kind not in tags:
                tags.append(f.kind)
    return m


def write_membership(
    world_id: str,
    catalog: FormationCatalog,
    *,
    state_dir=None,
) -> int:
    """Upsert `formation_membership` lists; returns sectors updated.

    Catalog-only side effect — still no Genesis / claim actions.
    """
    mmap = membership_map(catalog)
    n = 0
    for sid, tags in mmap.items():
        world_model.upsert_sector(
            world_id,
            {"sector_id": sid, "formation_membership": list(tags)},
            state_dir=state_dir,
        )
        n += 1
    return n


def recommend_genesis(catalog: FormationCatalog) -> tuple[Formation, ...]:
    """Operator-facing shortlist — identical to catalog.genesis_candidates."""
    return catalog.genesis_candidates
