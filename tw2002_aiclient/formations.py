"""In-tree formations catalogue — LOCATE / CATALOG / RECOMMEND only.

WO-FORMATIONS-CATALOG-PORT. Reads the mapped warp graph from ``world_model``
and surfaces topology facts. It never deploys Genesis, never claims space,
and never sends a keystroke.

This WO ships a **dead-end-only** detector (sectors whose recorded ``warps``
list has length exactly 1). Bubble / one-way / warp-sink shapes stay for a
later WO; under that scope ``formations_count`` (panel item count) equals
``genesis_count`` (genesis-kind candidate count) because every catalogued
item is a dead-end siting candidate. See ``canon/strategy/special-formations.md``.

WO-FORMATIONS-WORLD-STATS-VIA-CATALOG: ``formations_from_sectors`` is the single
pure detector. ``catalog_world`` (explore provider seam) and
``world_stats.WorldStats`` both call it so panel / GOALS / coach cannot drift
from ``plan_find_formations``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

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
        # Dead-ends (and bubbles, when added) are siting / genesis candidates.
        return [
            f
            for f in self._formations
            if f.kind in ("dead_end", "bubble")
        ]

    @property
    def formations(self) -> list[Formation]:
        return list(self._formations)


def formations_from_sectors(sectors: object) -> Optional[FormationsCatalog]:
    """Pure dead-end detector over an ``all_sectors``-shaped list.

    Returns ``None`` when the input is hostile (not a list, or a non-dict
    record mid-scan) so callers that preserve a prior observation
    (``WorldStats``) can abort without inventing a zero. A valid empty list
    yields an empty catalogue.

    The explore provider seam (``catalog_world``) maps ``None`` → empty
    catalogue so it never raises and never reports a partial scan.
    """
    if not isinstance(sectors, list):
        return None

    found: list[Formation] = []
    for record in sectors:
        if not isinstance(record, dict):
            return None
        warps = record.get("warps")
        if not isinstance(warps, list) or len(warps) != 1:
            continue
        sid = record.get("sector_id")
        if isinstance(sid, bool) or not isinstance(sid, int):
            continue
        neighbor = warps[0]
        entrance: Optional[int]
        if isinstance(neighbor, bool) or not isinstance(neighbor, int):
            entrance = None
        else:
            entrance = neighbor
        found.append(
            Formation(
                kind="dead_end",
                sectors=(sid,),
                entrance=entrance,
                detail=(
                    f"one warp → {entrance}"
                    if entrance is not None
                    else "one warp"
                ),
            )
        )
    found.sort(key=lambda f: f.sectors[0] if f.sectors else 0)
    return FormationsCatalog(found)


def panel_items_from_catalog(catalog: FormationsCatalog) -> list[dict]:
    """Map catalogue records to FORMATIONS-panel ``{name, blurb}`` items.

    Display strings stay behavior-neutral with the pre-unify WorldStats
    producer (``Dead-end #{sid}`` + siting blurb). Unknown kinds fall back to
    ``kind`` + ``detail`` so a later bubble WO does not need a second mapper.
    """
    items: list[dict] = []
    for formation in catalog.formations:
        if not formation.sectors:
            continue
        sid = formation.sectors[0]
        if formation.kind == "dead_end":
            items.append(
                {
                    "name": f"Dead-end #{sid}",
                    "blurb": "one warp — defensible siting candidate",
                }
            )
        else:
            name = f"{formation.kind} #{sid}"
            blurb = formation.detail or ""
            items.append({"name": name, "blurb": blurb} if blurb else {"name": name})
    return items


def catalog_world(
    world_id: str,
    *,
    state_dir: Any = None,
) -> FormationsCatalog:
    """Scan the world-model for dead-end formations. Never raises to callers
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
    return catalog if catalog is not None else FormationsCatalog([])
