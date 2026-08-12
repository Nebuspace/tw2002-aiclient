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
from typing import Any, Callable, Mapping, Optional, Sequence

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


def _formation_membership_index(
    world_id: str,
    *,
    state_dir=None,
) -> dict[int, tuple[str, ...]]:
    """sector_id → formation_membership tags (empty when unset)."""
    out: dict[int, tuple[str, ...]] = {}
    for rec in world_model.all_sectors(world_id, state_dir=state_dir):
        tags = rec.get("formation_membership") or ()
        if tags:
            out[_sector_id(rec)] = tuple(str(t) for t in tags)
    return out


def _threats_by_sector_index(
    world_id: str,
    *,
    state_dir=None,
) -> dict[int, dict]:
    """sector_id → threats mapping for route-hazard STOP checks."""
    out: dict[int, dict] = {}
    for rec in world_model.all_sectors(world_id, state_dir=state_dir):
        threats = rec.get("threats")
        if isinstance(threats, dict):
            out[_sector_id(rec)] = threats
    return out


def _guard_route_hazard_hop(
    graph: Mapping[int, Sequence[int]],
    current_sector: int,
    next_sector: int,
    *,
    world_id: str,
    state_dir=None,
) -> Optional[str]:
    """STOP reason if ``current→next`` is a known route hazard; else None.

    Never searches an alternate hop — callers must halt on a non-None return
    (canon: hazards → guards that STOP, not autonomous reroute).
    """
    from tw2002_aiclient.formations import route_hazard_for_hop

    return route_hazard_for_hop(
        graph,
        current_sector,
        next_sector,
        membership=_formation_membership_index(world_id, state_dir=state_dir),
        threats_by_sector=_threats_by_sector_index(world_id, state_dir=state_dir),
    )


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
    deny: frozenset[int] = frozenset(),
) -> list[FrontierEdge]:
    """BFS from `start` over KNOWN warps; collect edges to UNKNOWN ids.

    An unknown target is any warp destination not present as a key in
    `graph` (never recorded). Depth is hop-count from start along the
    known subgraph.

    `deny` (WO-WARP-CONFIRM-Y REVISE): frontier `to` ids to exclude from
    this tick's candidates -- the runner's own record of sectors just
    declined off an avoid-list DANGER prompt, so the very next tick does
    not immediately re-pick the same hop. Never persisted (world-model
    stays untouched); the caller owns the set's lifetime.
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
                if nxt in deny:
                    continue
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
    deny: frozenset[int] = frozenset(),
) -> MapFillPlan:
    """One Map-fill tick: propose the next unmapped hop under budget.

    `deny` -- see `frontier_edges`'s own docstring (WO-WARP-CONFIRM-Y).
    """
    budget = max(0, int(turn_budget))
    graph = known_graph(world_id, state_dir=state_dir)
    frontier = frontier_edges(graph, start=current_sector, deny=deny)
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
    *,
    world_id: str | None = None,
    state_dir=None,
) -> Optional[int]:
    """Highest-density reachable sector; falls back to out-degree.

    WO-WIRE-DENSITY-SCAN-CONSUMER: when ``world_id`` is set and a sector has a
    persisted ``density_scan.value``, that value ranks first. Sectors without a
    reading still compete by known-graph out-degree (prior heuristic). Tie-break:
    lowest sector id. Returns ``None`` when ``start`` is absent from the graph.
    Never invents density readings or warps.
    """
    reachable = reachable_sectors(graph, start)
    if not reachable:
        return None

    def _score(sid: int) -> tuple:
        dens: Optional[int] = None
        if isinstance(world_id, str) and world_id:
            from tw2002_aiclient.world_model import get_sector

            rec = get_sector(world_id, sid, state_dir=state_dir)
            ds = rec.get("density_scan") if isinstance(rec, dict) else None
            if isinstance(ds, dict):
                raw = ds.get("value")
                if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
                    dens = raw
        degree = len(tuple(graph.get(sid, ())))
        has_scan = 1 if dens is not None else 0
        dens_val = dens if dens is not None else -1
        return (has_scan, dens_val, degree, -sid)

    return max(reachable, key=_score)


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

    densest = densest_reachable_sector(
        graph, cur, world_id=world_id, state_dir=state_dir
    )
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
    deny: frozenset[int] = frozenset(),
) -> StarDockPlan:
    """Find-StarDock tick: pathfind if landmark known, else Map-fill hunt.

    Does not write the world-model or emit keystrokes — callers that
    visit sectors (density scan / move) are what populate landmarks.

    WO-EXPLORE-NO-CANDIDATES: when the frontier is exhausted (and we are
    not already mid-route to a dock), attach densest / StarDock recovery
    or leave ``mode="exhausted"`` for an explicit autopilot halt.

    `deny` (WO-WARP-CONFIRM-Y) only applies to the Map-fill HUNT branch
    below (fresh frontier picks) -- the known-route path to an already
    landmarked StarDock is untouched, same reasoning as
    `map_fill_warp_target`'s own docstring.
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
        deny=deny,
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
    # "unavailable" is NOT interchangeable with "hunt"/"exhausted" -- see
    # `plan_find_formations`. It means "no catalogue was reachable", never
    # "a catalogue was read and held nothing".
    mode: str  # "route" | "hunt" | "arrived" | "exhausted" | "catalog" | "unavailable"


def plan_find_formations(
    world_id: str,
    *,
    current_sector: int,
    turn_budget: int,
    epsilon: float = 0.1,
    state_dir=None,
    rng: Optional[random.Random] = None,
    catalog_provider: Optional[Callable[..., Any]] = None,
) -> FormationsPlan:
    """Find-Formations tick: route toward nearest genesis candidate.

    If candidates exist, pathfind to the nearest (entrance if set, else
    first sector). Otherwise Map-fill to grow the graph. Never deploys
    Genesis — locate/recommend only.

    ``catalog_provider`` is the TW-16 formation catalogue seam: a callable
    ``(world_id, *, state_dir) -> object`` exposing ``.genesis_candidates``
    (read via :func:`tw2002_aiclient.formations.recommend_genesis`).
    It mirrors ``screens.py``'s ``status_provider`` contract — **defaults to
    ``None``, and with no provider set this returns an honest
    ``mode="unavailable"`` rather than inventing content.**

    WO-EXPLORE-TWCLIENT-FORMATIONS-LANDMINE: this function previously did
    ``from twclient.formations import catalog_world`` in its body. ADR-001
    deleted the whole ``twclient`` package, so that line raised
    ``ModuleNotFoundError`` on the first call — armed, and invisible because
    it is a *function-level* import (module import stayed clean) whose only
    tests are ``--ignore``d (``pytest.ini`` → ``tests/test_formations.py``).

    Why a distinct ``"unavailable"`` and not the existing ``"hunt"``: with no
    catalogue, "no candidates" and "could not look for candidates" are the
    same empty value. Degrading to the Map-fill hunt branch would report
    *exploring, none found* — a confident statement about the world derived
    from a missing dependency. The refusal is typed so a caller can tell the
    two apart. No resurrect: the catalogue is not reimplemented here, and
    wiring a real one later is one argument at the call site.
    """
    budget = max(0, int(turn_budget))
    cur = int(current_sector)
    graph = known_graph(world_id, state_dir=state_dir)

    if catalog_provider is None:
        return FormationsPlan(
            found=False,
            targets=(),
            kind=None,
            route=None,
            next_sector=None,
            hunt=None,
            mode="unavailable",
        )

    from tw2002_aiclient.formations import recommend_genesis

    cat = catalog_provider(world_id, state_dir=state_dir)
    candidates = recommend_genesis(cat)
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


def explore_decision_lines_from_run(run: object) -> list[str] | None:
    """Product seam for ``explore_status.run`` → DECISIONS lines.

    Maps daemon intents onto the panel mode names ``format_explore_decision_lines``
    already knows (``map_fill``→``mapfill``, ``find_stardock``→``stardock``,
    ``find_formations``→``formations``) and builds the minimal plan-shaped
    object that composer reads. Returns ``None`` when the run is unusable so
    the caller clears the overlay rather than inventing chrome. Does not fork
    a second string table.

    WO-EXPLORE-DECISION-FLAGS: when ``dock_new_ports`` / ``fight_tolls`` are
    present on the run dict, append one flags line using
    ``cockpit.explore_flags`` markers (``+dock`` / ``no-dock…`` /
    ``+fight-tolls``). Absent keys → no invented flags line.

    WO-EXPLORE-DECISION-TURNS: when ``turns_remaining`` is a non-bool int
    ≥ 0, append ``turns N``. Omit when absent or wrong type — never invent.
    """
    from types import SimpleNamespace

    if not isinstance(run, dict):
        return None
    intent = run.get("intent")
    nxt = run.get("next_sector")
    if isinstance(nxt, bool) or (nxt is not None and not isinstance(nxt, int)):
        nxt = None
    if intent == INTENT_MAP_FILL:
        hop = SimpleNamespace(to=nxt) if nxt is not None else None
        plan = SimpleNamespace(next_hop=hop, mode="live")
        lines = format_explore_decision_lines("mapfill", plan)
    elif intent == INTENT_FIND_STARDOCK:
        plan = SimpleNamespace(next_sector=nxt, mode="live")
        lines = format_explore_decision_lines("stardock", plan)
    elif intent == INTENT_FIND_FORMATIONS:
        plan = SimpleNamespace(next_sector=nxt, mode="live")
        lines = format_explore_decision_lines("formations", plan)
    else:
        return None
    extra: list[str] = []
    flags = _explore_decision_flags_line(run)
    if flags is not None:
        extra.append(flags)
    turns = _explore_decision_turns_line(run)
    if turns is not None:
        extra.append(turns)
    if extra:
        lines = list(lines) + extra
    return lines


def _explore_decision_turns_line(run: dict) -> str | None:
    """``turns N`` when wire carries a usable remaining budget; else omit."""
    raw = run.get("turns_remaining")
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return None
    return f"turns {raw}"


def _explore_decision_flags_line(run: dict) -> str | None:
    """Short dock/tolls disclosure for DECISIONS, or ``None`` if unknown.

    Reuses ``explore_flags`` markers only — never invents ``+dock`` when the
    wire omits the key. Tolls stay ON-only (same asymmetry as the confirm
    line). Non-bool values are skipped rather than coerced.
    """
    # Lazy: keep explore.py free of cockpit import at module load.
    from tw2002_aiclient.cockpit import explore_flags as _flags

    if "dock_new_ports" not in run and "fight_tolls" not in run:
        return None
    parts: list[str] = []
    if "dock_new_ports" in run:
        dock = run["dock_new_ports"]
        if isinstance(dock, bool):
            parts.append(_flags.DOCK_MARKER if dock else _flags.DOCK_OFF_MARKER)
    if "fight_tolls" in run:
        tolls = run["fight_tolls"]
        if tolls is True:
            parts.append(_flags.TOLLS_MARKER)
    if not parts:
        return None
    return " ".join(parts)


#: Status-dict key for the Play → DECISIONS explore overlay
#: (WO-WIRE-EXPLORE-DECISION-LINES). Named constant so the vocabulary guard
#: sees the producer write (``merged[KEY] = …; return merged``).
EXPLORE_DECISION_LINES_KEY = "explore_decision_lines"


def merge_explore_decision_lines(status: object, lines: object) -> object:
    """Overlay explore DECISIONS lines onto a status snapshot.

    Returns ``status`` unchanged when there is nothing to overlay. Never
    mutates the input dict. Shape matches ``chain_status.ChainScalars.merge``
    so the status-vocabulary scanner credits the write.
    """
    if not isinstance(lines, list) or not lines:
        return status
    if isinstance(status, dict):
        merged = dict(status)
    else:
        merged = {}
    merged[EXPLORE_DECISION_LINES_KEY] = list(lines)
    return merged


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
INTENT_FIND_FORMATIONS = "find_formations"
INTENT_CHAIN_HUNT = "chain_hunt"
#: The intents a caller may arm. Deliberately a closed set: an unknown intent
#: is REFUSED by the daemon rather than silently falling back to map-fill,
#: because a run that quietly does something other than what the confirm line
#: promised is exactly what the arm gate exists to prevent.
#:
#: ``find_formations`` / ``chain_hunt`` are CLI/daemon-armable but deliberately
#: NOT in ``ARMABLE_INTENTS`` — Play's E-cycle stays 2-wide (#247).
INTENTS = frozenset(
    {
        INTENT_MAP_FILL,
        INTENT_FIND_STARDOCK,
        INTENT_FIND_FORMATIONS,
        INTENT_CHAIN_HUNT,
    }
)

#: Cycle order for the Play `E` offer. ORDERED (a frozenset is not) and
#: map-fill FIRST so the first `E` press raises exactly the prompt it raised
#: before this WO -- an operator's muscle memory must not arm a different run
#: than it armed yesterday.
#:
#: A fuller trainer-panel cycle (off → mapfill → stardock → formations) was
#: never product-wired and was retired (WO-RETIRE-CYCLE-EXPLORE-MODE / #247).
#: Formations is a separate CLI intent (`tw explore start --intent
#: find_formations`); Play stays on these two daemon intents only.
#: The old Play E-cycle helper ``next_armable_intent`` was retired with
#: ``cycle_explore_mode`` (#247 / WO-RETIRE-CYCLE-EXPLORE-MODE) — tip Play
#: arms via find-stardock toggle, not a rotating offer cycle.
#:
#: Runtime-enforced at the Play confirm-arm site (``app.py``): an intent not
#: in this tuple is refused closed rather than silently started. CLI/daemon
#: may still arm the wider ``INTENTS`` set (e.g. ``find_formations``).
ARMABLE_INTENTS: tuple[str, ...] = (INTENT_MAP_FILL, INTENT_FIND_STARDOCK)


@dataclass(frozen=True)
class IntentTick:
    """One intent-driven decision: hop here, stop here, or we are done.

    Three states, and the third is why this is not a ``(target, reason)``
    tuple like :func:`map_fill_warp_target` returns. Find-StarDock can
    ``arrive`` — a *success* — and a tuple whose only non-``None`` answer is
    "next hop" would have to encode that as a halt reason, making a completed
    goal indistinguishable from an exhausted frontier in the run report.

    ``chain_state`` carries Chain-hunt working memory across ticks (None for
    other intents).
    """

    next_sector: Optional[int]
    goal_reached: bool = False
    reason: str = ""
    chain_state: Optional["ChainHuntState"] = None


@dataclass(frozen=True)
class ChainHuntState:
    """Cross-tick Chain-hunt memory (immutable snapshots; runner stores latest).

    Canon steps 1–5: ``anchor`` is the confirmed-port closed-set owner;
    ``ancestors`` is the backtrack stack of prior anchors; ``visiting`` is the
    unmapped sibling hop in flight; ``return_to`` is set when the next hop
    must be the trip back to the anchor after a no-port (or depth-capped)
    classify.
    """

    ancestors: tuple[int, ...] = ()
    anchor: Optional[int] = None
    visiting: Optional[int] = None
    return_to: Optional[int] = None


@dataclass(frozen=True)
class ChainHuntPlan:
    """One Chain-hunt tick — next adjacent hop + updated working memory."""

    next_sector: Optional[int]
    state: ChainHuntState
    mode: str
    reason: str = ""


def unmapped_warp_neighbors(
    graph: Mapping[int, Sequence[int]],
    sector: int,
) -> list[int]:
    """Sorted warp destinations from ``sector`` that are not yet graph keys."""
    known = set(graph.keys())
    return sorted(w for w in graph.get(int(sector), ()) if w not in known)


def _hop_toward_sector(
    graph: Mapping[int, Sequence[int]],
    current: int,
    goal: int,
) -> Optional[int]:
    """Immediate adjacent hop on the known graph toward ``goal``, or None."""
    cur = int(current)
    g = int(goal)
    if cur == g:
        return None
    if g not in graph and cur in graph and g in graph.get(cur, ()):
        # First visit to an unmapped neighbor — adjacent warp from current.
        return g
    path = path_to_sector(graph, cur, g)
    if path is None or len(path) < 2:
        return None
    return path[1]


def _nearest_port_with_unmapped_siblings(
    graph: Mapping[int, Sequence[int]],
    ports: set[int],
    start: int,
) -> Optional[int]:
    """Nearest known port (by known-graph hops) that still has unmapped warps."""
    if start not in graph:
        return None
    best: Optional[int] = None
    best_len: Optional[int] = None
    for port in ports:
        if port not in graph:
            continue
        if not unmapped_warp_neighbors(graph, port):
            continue
        path = path_to_sector(graph, start, port)
        if path is None:
            continue
        plen = len(path)
        if best_len is None or plen < best_len or (plen == best_len and port < (best or port)):
            best = port
            best_len = plen
    return best


def plan_chain_hunt(
    world_id: str,
    *,
    current_sector: int,
    turn_budget: int,
    exhaust_depth: int,
    state: Optional[ChainHuntState] = None,
    state_dir=None,
    epsilon: float = 0.1,
    rng: Optional[random.Random] = None,
    deny: frozenset[int] = frozenset(),
) -> ChainHuntPlan:
    """Chain-hunt tick: sibling-exhaust + ancestor-port backtrack (canon).

    ``exhaust_depth`` and ``turn_budget`` are **required caller-supplied** —
    this function does not invent defaults. Depth is the max number of nested
    port anchors (1 = current anchor only; finding a deeper port maps it but
    does not re-anchor). While any ancestor still has open unmapped siblings,
    this never falls through to Map-fill densest/stardock recovery.
    """
    if isinstance(exhaust_depth, bool) or not isinstance(exhaust_depth, int) or exhaust_depth < 1:
        return ChainHuntPlan(
            None,
            state or ChainHuntState(),
            "halt",
            "explore_exhausted:invalid_exhaust_depth",
        )
    budget = int(turn_budget)
    if isinstance(turn_budget, bool) or not isinstance(turn_budget, int) or budget < 0:
        return ChainHuntPlan(
            None,
            state or ChainHuntState(),
            "halt",
            "explore_exhausted:invalid_turn_budget",
        )
    if budget <= 0:
        return ChainHuntPlan(
            None,
            state or ChainHuntState(),
            "exhausted",
            "explore_exhausted:turn_budget",
        )

    cur = int(current_sector)
    graph = known_graph(world_id, state_dir=state_dir)
    ports = known_port_sectors(world_id, state_dir=state_dir)
    st = state or ChainHuntState()

    def _last_resort_mapfill(st_now: ChainHuntState) -> ChainHuntPlan:
        """Map-fill recovery ONLY when the ancestor stack is empty."""
        if st_now.ancestors:
            # Canon: never densest-reachable while an ancestor remains.
            return ChainHuntPlan(
                None,
                st_now,
                "halt",
                "explore_exhausted:ancestor_open_but_unreachable",
            )
        target, reason = map_fill_warp_target(
            world_id,
            current_sector=cur,
            turn_budget=budget,
            epsilon=epsilon,
            state_dir=state_dir,
            rng=rng,
            deny=deny,
        )
        if target is None:
            return ChainHuntPlan(
                None,
                st_now,
                "exhausted",
                reason or "explore_exhausted:no_hop",
            )
        return ChainHuntPlan(int(target), st_now, "last_resort_mapfill", reason)

    # --- return trip after classify ---
    if st.return_to is not None:
        goal = int(st.return_to)
        if cur == goal:
            st = ChainHuntState(
                ancestors=st.ancestors,
                anchor=st.anchor,
                visiting=None,
                return_to=None,
            )
        else:
            hop = _hop_toward_sector(graph, cur, goal)
            if hop is None:
                return ChainHuntPlan(
                    None,
                    st,
                    "halt",
                    "explore_exhausted:return_unreachable",
                )
            return ChainHuntPlan(hop, st, "return_anchor")

    # --- arrive at visiting sibling: classify (canon step 4) ---
    if (
        st.anchor is not None
        and st.visiting is not None
        and cur == int(st.visiting)
        and cur != int(st.anchor)
    ):
        anchor = int(st.anchor)
        depth_now = len(st.ancestors) + 1  # depth of current anchor
        if cur in ports and depth_now < exhaust_depth:
            # Port found — re-anchor; push previous onto ancestor stack.
            st = ChainHuntState(
                ancestors=st.ancestors + (anchor,),
                anchor=cur,
                visiting=None,
                return_to=None,
            )
            # Fall through to exhaust the new anchor this tick.
        else:
            # No port, or depth-capped: close branch, return to anchor.
            hop = _hop_toward_sector(graph, cur, anchor)
            st = ChainHuntState(
                ancestors=st.ancestors,
                anchor=anchor,
                visiting=None,
                return_to=anchor,
            )
            if hop is None:
                return ChainHuntPlan(
                    None,
                    st,
                    "halt",
                    "explore_exhausted:return_unreachable",
                )
            return ChainHuntPlan(hop, st, "return_anchor")

    # --- choose / reach an anchor (canon step 1) ---
    if st.anchor is None:
        if cur in ports:
            st = ChainHuntState(ancestors=(), anchor=cur)
        else:
            candidate = _nearest_port_with_unmapped_siblings(graph, ports, cur)
            if candidate is None:
                return _last_resort_mapfill(st)
            if candidate == cur:
                st = ChainHuntState(ancestors=(), anchor=cur)
            else:
                hop = _hop_toward_sector(graph, cur, candidate)
                if hop is None:
                    return _last_resort_mapfill(st)
                # Navigate toward the seed port; anchor latches on arrival.
                return ChainHuntPlan(
                    hop,
                    ChainHuntState(ancestors=(), anchor=candidate),
                    "seek_anchor",
                )

    anchor = int(st.anchor)
    if cur != anchor:
        hop = _hop_toward_sector(graph, cur, anchor)
        if hop is None:
            # Cannot reach declared anchor — try backtrack / last resort.
            if st.ancestors:
                parent = int(st.ancestors[-1])
                st2 = ChainHuntState(
                    ancestors=st.ancestors[:-1],
                    anchor=parent,
                    visiting=None,
                    return_to=None,
                )
                hop2 = _hop_toward_sector(graph, cur, parent)
                if hop2 is not None:
                    return ChainHuntPlan(hop2, st2, "backtrack")
            return _last_resort_mapfill(st)
        return ChainHuntPlan(hop, st, "seek_anchor")

    # --- at anchor: exhaust closed sibling set (canon steps 2–5) ---
    siblings = [
        s for s in unmapped_warp_neighbors(graph, anchor) if s not in deny
    ]
    if siblings:
        nxt = siblings[0]  # deterministic: lowest id
        st2 = ChainHuntState(
            ancestors=st.ancestors,
            anchor=anchor,
            visiting=nxt,
            return_to=None,
        )
        return ChainHuntPlan(nxt, st2, "visit_sibling")

    # Closed set empty — backtrack to nearest ancestor with open siblings.
    for i in range(len(st.ancestors) - 1, -1, -1):
        parent = int(st.ancestors[i])
        open_sibs = [
            s for s in unmapped_warp_neighbors(graph, parent) if s not in deny
        ]
        if not open_sibs:
            continue
        st2 = ChainHuntState(
            ancestors=st.ancestors[:i],
            anchor=parent,
            visiting=None,
            return_to=None,
        )
        hop = _hop_toward_sector(graph, cur, parent)
        if hop is None:
            return ChainHuntPlan(
                None,
                st2,
                "halt",
                "explore_exhausted:backtrack_unreachable",
            )
        return ChainHuntPlan(hop, st2, "backtrack")

    # Ancestor stack empty (or all ancestors exhausted) — last-resort Map-fill.
    return _last_resort_mapfill(
        ChainHuntState(ancestors=(), anchor=None, visiting=None, return_to=None)
    )


def warp_target_for_intent(
    intent: str,
    world_id: str,
    *,
    current_sector: int,
    turn_budget: int,
    epsilon: float = 0.1,
    state_dir=None,
    rng: Optional[random.Random] = None,
    deny: frozenset[int] = frozenset(),
    exhaust_depth: Optional[int] = None,
    chain_state: Optional[ChainHuntState] = None,
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

    `deny` (WO-WARP-CONFIRM-Y): sector ids the runner just declined off an
    avoid-list DANGER prompt this run -- excluded from this tick's fresh-
    frontier candidates so the very next tick does not re-pick the same hop.
    """
    if intent == INTENT_CHAIN_HUNT:
        if exhaust_depth is None:
            return IntentTick(
                next_sector=None,
                reason="explore_exhausted:missing_exhaust_depth",
                chain_state=chain_state,
            )
        plan = plan_chain_hunt(
            world_id,
            current_sector=current_sector,
            turn_budget=turn_budget,
            exhaust_depth=exhaust_depth,
            state=chain_state,
            state_dir=state_dir,
            epsilon=epsilon,
            rng=rng,
            deny=deny,
        )
        if plan.next_sector is None:
            reason = plan.reason or plan.mode or "no_hop"
            if not reason.startswith("explore_exhausted") and not reason.startswith(
                "route_hazard:"
            ):
                reason = f"explore_exhausted:{reason}"
            return IntentTick(
                next_sector=None, reason=reason, chain_state=plan.state
            )
        nxt = int(plan.next_sector)
        graph = known_graph(world_id, state_dir=state_dir)
        hazard = _guard_route_hazard_hop(
            graph, current_sector, nxt, world_id=world_id, state_dir=state_dir
        )
        if hazard is not None:
            return IntentTick(
                next_sector=None, reason=hazard, chain_state=plan.state
            )
        return IntentTick(next_sector=nxt, chain_state=plan.state)
    if intent == INTENT_MAP_FILL:
        target, reason = map_fill_warp_target(
            world_id,
            current_sector=current_sector,
            turn_budget=turn_budget,
            epsilon=epsilon,
            state_dir=state_dir,
            rng=rng,
            deny=deny,
        )
        # map_fill_warp_target already applies the route-hazard guard.
        return IntentTick(next_sector=target, reason=reason)
    if intent == INTENT_FIND_FORMATIONS:
        # Product call path for WO-FORMATIONS-CATALOG-PORT: real in-tree
        # catalog_provider (dead-end-only). Never import twclient.
        from tw2002_aiclient.formations import catalog_world

        plan = plan_find_formations(
            world_id,
            current_sector=current_sector,
            turn_budget=turn_budget,
            epsilon=epsilon,
            state_dir=state_dir,
            rng=rng,
            catalog_provider=catalog_world,
        )
        if plan.mode == "arrived":
            return IntentTick(next_sector=None, goal_reached=True)
        if plan.mode == "unavailable":
            return IntentTick(
                next_sector=None,
                reason="explore_exhausted:formations_unavailable",
            )
        if plan.next_sector is None:
            reason = plan.mode or "no_hop"
            if not reason.startswith("explore_exhausted"):
                reason = f"explore_exhausted:{reason}"
            return IntentTick(next_sector=None, reason=reason)
        nxt = int(plan.next_sector)
        graph = known_graph(world_id, state_dir=state_dir)
        hazard = _guard_route_hazard_hop(
            graph, current_sector, nxt, world_id=world_id, state_dir=state_dir
        )
        if hazard is not None:
            return IntentTick(next_sector=None, reason=hazard)
        return IntentTick(next_sector=nxt)
    if intent != INTENT_FIND_STARDOCK:
        return IntentTick(next_sector=None, reason=f"explore_exhausted:unknown_intent:{intent}")

    plan = plan_find_stardock(
        world_id,
        current_sector=current_sector,
        turn_budget=turn_budget,
        epsilon=epsilon,
        state_dir=state_dir,
        rng=rng,
        deny=deny,
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
    nxt = int(plan.next_sector)
    graph = known_graph(world_id, state_dir=state_dir)
    hazard = _guard_route_hazard_hop(
        graph, current_sector, nxt, world_id=world_id, state_dir=state_dir
    )
    if hazard is not None:
        return IntentTick(next_sector=None, reason=hazard)
    return IntentTick(next_sector=nxt)


def map_fill_warp_target(
    world_id: str,
    *,
    current_sector: int,
    turn_budget: int,
    epsilon: float = 0.1,
    state_dir=None,
    rng: Optional[random.Random] = None,
    deny: frozenset[int] = frozenset(),
) -> tuple[Optional[int], str]:
    """Map-fill tick → one adjacent warp target, or ``(None, halt_reason)``.

    Uses ``plan_map_fill`` then ``plan_exhausted_recovery`` when the frontier
    is empty — same AP-08 discipline as archive ``autopilot`` explore ticks.

    `deny` -- see `frontier_edges`'s own docstring (WO-WARP-CONFIRM-Y).
    Recovery is NOT deny-filtered: recovery only ever targets already-KNOWN
    graph sectors (StarDock landmark / densest reachable), never the fresh
    frontier `to` a decline was just issued against.
    """
    plan = plan_map_fill(
        world_id,
        current_sector=current_sector,
        turn_budget=turn_budget,
        epsilon=epsilon,
        state_dir=state_dir,
        rng=rng,
        deny=deny,
    )
    graph = known_graph(world_id, state_dir=state_dir)
    if plan.next_hop is not None and plan.mode != "exhausted":
        nxt = _adjacent_hop_toward(graph, current_sector, plan.next_hop)
        if nxt is not None:
            hazard = _guard_route_hazard_hop(
                graph,
                current_sector,
                nxt,
                world_id=world_id,
                state_dir=state_dir,
            )
            if hazard is not None:
                # STOP — do not fall through to recovery (that would be a
                # silent alternate route around the hazard).
                return None, hazard
            return nxt, ""
    recovery = plan_exhausted_recovery(
        world_id,
        current_sector=current_sector,
        turn_budget=turn_budget,
        state_dir=state_dir,
    )
    if recovery.next_sector is not None:
        hazard = _guard_route_hazard_hop(
            graph,
            current_sector,
            int(recovery.next_sector),
            world_id=world_id,
            state_dir=state_dir,
        )
        if hazard is not None:
            return None, hazard
        return recovery.next_sector, recovery.reason
    reason = recovery.reason or "explore_exhausted:no_recovery_target"
    if not reason.startswith("explore_exhausted"):
        reason = f"explore_exhausted:{reason}"
    return None, reason
