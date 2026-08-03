"""In-tree formations catalogue — LOCATE / CATALOG / RECOMMEND only.

WO-FORMATIONS-CATALOG-PORT (+ WO-FORMATIONS-BUBBLE-DETECT). Reads the mapped
warp graph from ``world_model`` and surfaces topology facts. It never deploys
Genesis, never claims space, and never sends a keystroke.

Detector scope today: **dead-ends** (out-degree 1) and **bubbles**
(single-entrance pockets with ≥2 interior sectors). One-way / warp-sink
shapes stay for a later WO. Under this scope every catalogued item is a
genesis-kind siting candidate, so ``formations_count`` equals
``genesis_count``. See ``canon/strategy/special-formations.md``.

``formations_from_sectors`` is the single pure detector.
``catalog_world`` (explore provider seam) and ``world_stats.WorldStats``
both call it so panel / GOALS / coach cannot drift from
``plan_find_formations`` (WO-FORMATIONS-WORLD-STATS-VIA-CATALOG).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

__all__ = [
    "Formation",
    "FormationsCatalog",
    "catalog_world",
    "formations_from_sectors",
    "panel_items_from_catalog",
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
                # Warp to an unmapped id — skip undirected pocket math
                # until both ends are known.
                continue
            adj[a].add(b)
            adj[b].add(a)
    return adj


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
    """Pockets sealed behind a single entrance (interior size ≥ 2).

    Ported from archive ``twclient.formations._bubbles`` (TW-16). For each
    candidate entrance E and neighbor N, grow the component reachable from N
    without traversing E. If every edge leaving that component lands only on
    E, it is a sealed pocket. Prefer the smaller side of a bridge so the
    open map is never catalogued as a bubble; keep innermost pockets only.
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
                    kind="bubble",
                    sectors=members,
                    entrance=int(entrance),
                    detail="single-entrance pocket",
                )
            )
    # Prefer innermost pockets — drop any bubble that properly contains another.
    keep: list[Formation] = []
    for f in out:
        if any(set(g.sectors) < set(f.sectors) for g in out if g is not f):
            continue
        keep.append(f)
    return keep


def formations_from_sectors(sectors: object) -> Optional[FormationsCatalog]:
    """Pure dead-end + bubble detector over an ``all_sectors``-shaped list.

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
        else:
            sid = formation.sectors[0]
            name = f"{formation.kind} #{sid}"
            blurb = formation.detail or ""
            items.append(
                {"name": name, "blurb": blurb} if blurb else {"name": name}
            )
    return items


def catalog_world(
    world_id: str,
    *,
    state_dir: Any = None,
) -> FormationsCatalog:
    """Scan the world-model for dead-end + bubble formations. Never raises
    to callers of the provider seam — hostile stores yield an empty catalogue.

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
    return catalog if catalog is not None else FormationsCatalog([])
