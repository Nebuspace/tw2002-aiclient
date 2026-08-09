"""In-tree formations catalogue — LOCATE / CATALOG / RECOMMEND only.

WO-FORMATIONS-CATALOG-PORT · BUBBLE-DETECT · HAZARD-DETECT. Reads the mapped
warp graph from ``world_model`` and surfaces topology facts. It never deploys
Genesis, never claims space, and never sends a keystroke.

Detector scope today:

* **dead-ends** / **bubbles** — genesis (siting) candidates
* **one_way** / **warp_sink** — route hazards (not genesis)

So ``formations_count`` (panel items) may exceed ``genesis_count``. See
``canon/strategy/special-formations.md``.

``formations_from_sectors`` is the single pure detector.
``catalog_world`` (explore provider seam) and ``world_stats.WorldStats``
both call it so panel / GOALS / coach cannot drift from
``plan_find_formations`` (WO-FORMATIONS-WORLD-STATS-VIA-CATALOG).

``route_hazard_for_hop`` is the guard predicate for one-way / warp-sink
hops (WO-ROUTE-HAZARD-GUARD) and known sector threats (mines / fighters —
WO-AUDIT-BUILD-SECTOR-THREAT-FIGHTERS-GUARD-INPUT). Callers STOP; they
must not silently reroute.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

__all__ = [
    "Formation",
    "FormationsCatalog",
    "catalog_world",
    "formations_from_sectors",
    "membership_map",
    "panel_items_from_catalog",
    "recommend_genesis",
    "route_hazard_for_hop",
    "threat_hazard_for_sector",
    "write_membership",
]


@dataclass(frozen=True)
class Formation:
    """One topology record. Duck-typed by ``plan_find_formations``."""

    kind: str
    sectors: tuple[int, ...]
    entrance: Optional[int] = None
    detail: str = ""


class FormationsCatalog:
    """Catalogue object exposing ``.genesis_candidates`` for the planner seam."""

    __slots__ = ("_formations",)

    def __init__(self, formations: list[Formation]) -> None:
        self._formations = list(formations)

    @property
    def genesis_candidates(self) -> list[Formation]:
        # Dead-ends and bubbles are siting / genesis candidates.
        # One-ways / warp-sinks are route hazards — not genesis.
        return [
            f
            for f in self._formations
            if f.kind in ("dead_end", "bubble")
        ]

    @property
    def formations(self) -> list[Formation]:
        return list(self._formations)


def _graph_from_sectors(
    sectors: list,
) -> Optional[dict[int, tuple[int, ...]]]:
    """Build sid→outbound warps. ``None`` = hostile mid-list abort."""
    graph: dict[int, tuple[int, ...]] = {}
    for record in sectors:
        if not isinstance(record, dict):
            return None
        sid = record.get("sector_id")
        if isinstance(sid, bool) or not isinstance(sid, int):
            continue
        warps = record.get("warps")
        if not isinstance(warps, list):
            continue
        outs: list[int] = []
        for w in warps:
            if isinstance(w, bool) or not isinstance(w, int):
                continue
            outs.append(w)
        graph[sid] = tuple(outs)
    return graph


def _undirected(graph: Mapping[int, Sequence[int]]) -> dict[int, set[int]]:
    """Mutual adjacency over *known* endpoints only (archive port)."""
    adj: dict[int, set[int]] = {int(s): set() for s in graph}
    for a, warps in graph.items():
        a = int(a)
        for b in warps:
            b = int(b)
            if b not in adj:
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
        if len(warps) != 1:
            continue
        neighbor = warps[0]
        out.append(
            Formation(
                kind="dead_end",
                sectors=(int(sid),),
                entrance=int(neighbor),
                detail=f"one warp → {neighbor}",
            )
        )
    return out


def _bubbles(
    graph: Mapping[int, Sequence[int]],
    undirected: Mapping[int, set[int]],
) -> list[Formation]:
    """Pockets sealed behind a single entrance (interior size ≥ 2)."""
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
            outside = undirected.get(entrance, set()) - comp
            if len(outside) != 1:
                continue
            members = tuple(sorted(comp | {entrance}))
            if members in seen_keys:
                continue
            seen_keys.add(members)
            out.append(
                Formation(
                    kind="bubble",
                    sectors=members,
                    entrance=int(entrance),
                    detail="single-entrance pocket",
                )
            )
    keep: list[Formation] = []
    for f in out:
        if any(set(g.sectors) < set(f.sectors) for g in out if g is not f):
            continue
        keep.append(f)
    return keep


def _one_ways(graph: Mapping[int, Sequence[int]]) -> list[Formation]:
    """Directed A→B with no reverse B→A among known sectors (archive port)."""
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
                        kind="one_way",
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
    """Sectors enterable but without a return path (archive port).

    Pure dead-ends are not double-labeled as sinks.
    """
    if len(graph) < 2:
        return []
    known = set(int(s) for s in graph)
    can_reach: dict[int, set[int]] = {
        s: _reachable(graph, s) for s in known
    }
    sink_sectors: set[int] = set()
    for s in known:
        outs = {int(x) for x in graph.get(s, ()) if int(x) in known}
        reach_from_s = can_reach[s]
        inbounders = [t for t in known if t != s and s in can_reach[t]]
        if not inbounders:
            continue
        trapped = any(t not in reach_from_s for t in inbounders)
        if trapped or (not outs and inbounders):
            sink_sectors.add(s)

    for sid, warps in graph.items():
        if len(tuple(warps)) == 1:
            sink_sectors.discard(int(sid))

    if not sink_sectors:
        return []

    und = _undirected({s: graph[s] for s in sink_sectors if s in graph})
    for s in sink_sectors:
        und.setdefault(s, set())
    comps = _components(und) if und else [{s} for s in sink_sectors]
    covered: set[int] = set()
    formations: list[Formation] = []
    for comp in comps:
        members = sorted(comp & sink_sectors)
        if not members:
            continue
        covered.update(members)
        formations.append(
            Formation(
                kind="warp_sink",
                sectors=tuple(members),
                detail="no return path to open map",
            )
        )
    for s in sorted(sink_sectors - covered):
        formations.append(
            Formation(
                kind="warp_sink",
                sectors=(s,),
                detail="no return path to open map",
            )
        )
    return formations


def formations_from_sectors(sectors: object) -> Optional[FormationsCatalog]:
    """Pure topology detector over an ``all_sectors``-shaped list.

    Returns ``None`` when the input is hostile (not a list, or a non-dict
    record mid-scan) so callers that preserve a prior observation
    (``WorldStats``) can abort without inventing a zero. A valid empty list
    yields an empty catalogue.

    The explore provider seam (``catalog_world``) maps ``None`` → empty
    catalogue so it never raises and never reports a partial scan.
    """
    if not isinstance(sectors, list):
        return None
    graph = _graph_from_sectors(sectors)
    if graph is None:
        return None
    found: list[Formation] = []
    found.extend(_dead_ends(graph))
    found.extend(_bubbles(graph, _undirected(graph)))
    found.extend(_one_ways(graph))
    found.extend(_warp_sinks(graph))
    found.sort(
        key=lambda f: (
            f.kind,
            f.sectors[0] if f.sectors else 0,
            f.detail,
        )
    )
    return FormationsCatalog(found)


def panel_items_from_catalog(catalog: FormationsCatalog) -> list[dict]:
    """Map catalogue records to FORMATIONS-panel ``{name, blurb}`` items."""
    items: list[dict] = []
    for formation in catalog.formations:
        if not formation.sectors:
            continue
        if formation.kind == "dead_end":
            sid = formation.sectors[0]
            items.append(
                {
                    "name": f"Dead-end #{sid}",
                    "blurb": "one warp — defensible siting candidate",
                }
            )
        elif formation.kind == "bubble":
            tag = (
                formation.entrance
                if formation.entrance is not None
                else formation.sectors[0]
            )
            items.append(
                {
                    "name": f"Bubble #{tag}",
                    "blurb": "single-entrance pocket — genesis candidate",
                }
            )
        elif formation.kind == "one_way":
            a, b = formation.sectors[0], formation.sectors[1] if len(formation.sectors) > 1 else "?"
            items.append(
                {
                    "name": f"One-way {a}→{b}",
                    "blurb": "route hazard — no reverse warp",
                }
            )
        elif formation.kind == "warp_sink":
            sid = formation.sectors[0]
            items.append(
                {
                    "name": f"Warp-sink #{sid}",
                    "blurb": "route hazard — no return path",
                }
            )
        else:
            sid = formation.sectors[0]
            name = f"{formation.kind} #{sid}"
            blurb = formation.detail or ""
            items.append(
                {"name": name, "blurb": blurb} if blurb else {"name": name}
            )
    return items



# Canon world-model membership tags use hyphens (world-model.md example).
_KIND_TO_MEMBERSHIP = {
    "dead_end": "dead-end",
    "bubble": "bubble",
    "one_way": "one-way",
    "warp_sink": "warp-sink",
}


def threat_hazard_for_sector(
    sector_id: int, threats: Mapping[str, Any] | None
) -> Optional[str]:
    """Typed STOP reason if ``threats`` names a known mine/fighter hazard.

    * ``mines is True`` → ``route_hazard:mines:<id>``
    * ``fighters`` count ``> 0`` (int or ``{count: int, …}``) →
      ``route_hazard:fighters:<id>``
    * ``fighters is None`` / missing / zero → not a hazard (never observed
      must not invent danger; zero is an explicit clear observation)

    Canon (``toll-and-defense.md``): known mines/fighters on a planned
    crossing are route-hazard STOP inputs — not silent drive-through.
    """
    if not isinstance(threats, Mapping):
        return None
    sid = int(sector_id)
    if threats.get("mines") is True:
        return f"route_hazard:mines:{sid}"
    fighters = threats.get("fighters")
    count: int | None = None
    if isinstance(fighters, bool):
        # Broken fact shape — refuse as hazard rather than treat True as 1.
        if fighters:
            return f"route_hazard:fighters:{sid}"
    elif isinstance(fighters, int):
        count = fighters
    elif isinstance(fighters, Mapping):
        raw = fighters.get("count")
        if isinstance(raw, int):
            count = raw
    if count is not None and count > 0:
        return f"route_hazard:fighters:{sid}"
    return None


def route_hazard_for_hop(
    graph: Mapping[int, Sequence[int]],
    frm: int,
    to: int,
    *,
    membership: Mapping[int, Sequence[str]] | None = None,
    threats_by_sector: Mapping[int, Mapping[str, Any]] | None = None,
) -> Optional[str]:
    """Typed STOP reason if this hop crosses a known route hazard, else None.

    Canon (``special-formations.md`` Dual consumer split): one-ways and
    warp-sinks feed **guards that STOP**, never an autonomous reroute.
    Sector threats (mines / fighters) follow the same STOP rail
    (``toll-and-defense.md``). This predicate only names the hazard —
    callers must halt, not search for an alternate path.

    * One-way: directed ``frm→to`` among known sectors with no reverse.
    * Warp-sink: ``to`` carries ``warp-sink`` in ``formation_membership``.
    * Threats: ``to`` has known mines or fighter presence in world-model.
    """
    a = int(frm)
    b = int(to)
    if a in graph and b in graph:
        outs_a = {int(x) for x in graph.get(a, ())}
        outs_b = {int(x) for x in graph.get(b, ())}
        if b in outs_a and a not in outs_b:
            return f"route_hazard:one_way:{a}->{b}"
    if membership is not None:
        tags = {str(t) for t in (membership.get(b) or ())}
        if "warp-sink" in tags:
            return f"route_hazard:warp_sink:{b}"
    if threats_by_sector is not None:
        threat = threat_hazard_for_sector(b, threats_by_sector.get(b))
        if threat is not None:
            return threat
    return None


def membership_map(catalog: FormationsCatalog) -> dict[int, list[str]]:
    """sector_id → formation kind tags for ``world_model.formation_membership``.

    Tags are canon hyphen forms (``dead-end``, ``one-way``, …). Detector
    internal kinds stay snake_case.
    """
    m: dict[int, list[str]] = {}
    for f in catalog.formations:
        tag = _KIND_TO_MEMBERSHIP.get(f.kind, f.kind)
        for sid in f.sectors:
            tags = m.setdefault(int(sid), [])
            if tag not in tags:
                tags.append(tag)
    return m


def write_membership(
    world_id: str,
    catalog: FormationsCatalog,
    *,
    state_dir: Any = None,
) -> int:
    """Upsert ``formation_membership`` lists; returns sectors updated.

    Catalog-only side effect — still no Genesis / claim actions.
    """
    from tw2002_aiclient import world_model as _world_model

    mmap = membership_map(catalog)
    n = 0
    kwargs: dict = {}
    if state_dir is not None:
        kwargs["state_dir"] = state_dir
    for sid, tags in mmap.items():
        _world_model.upsert_sector(
            world_id,
            {"sector_id": sid, "formation_membership": list(tags)},
            **kwargs,
        )
        n += 1
    return n


def recommend_genesis(catalog: FormationsCatalog) -> list[Formation]:
    """Operator-facing shortlist — identical to ``catalog.genesis_candidates``.

    Product explore / world_stats already consume ``catalog.genesis_candidates``
    directly; this alias exists for call sites that want the free-function shape.
    Not a missing bridge.
    """
    return list(catalog.genesis_candidates)


def catalog_world(
    world_id: str,
    *,
    state_dir: Any = None,
) -> FormationsCatalog:
    """Scan the world-model for formations + hazards. Never raises to callers
    of the provider seam — hostile stores yield an empty catalogue.

    Callable shape matches ``plan_find_formations``'s ``catalog_provider``:
    ``(world_id, *, state_dir=None) -> object`` with ``.genesis_candidates``.
    """
    try:
        from tw2002_aiclient import world_model as _world_model

        kwargs: dict = {}
        if state_dir is not None:
            kwargs["state_dir"] = state_dir
        sectors = _world_model.all_sectors(world_id, **kwargs)
    except Exception:  # noqa: BLE001 — provider seam must not raise
        return FormationsCatalog([])
    catalog = formations_from_sectors(sectors)
    if catalog is None:
        return FormationsCatalog([])
    try:
        write_membership(world_id, catalog, state_dir=state_dir)
    except Exception:  # noqa: BLE001 — provider seam must not raise
        pass
    return catalog
