"""E1 + E3 at the runner: intents, exhaustive map-fill, typed halts.

Reuses `test_sector_explore.py`'s `ExploreMapSession` harness rather than
building a second fake — one fake session, one set of behaviours to keep
honest.

The sharpest pin here is
`test_find_stardock_does_not_report_completed_just_for_visiting_sectors`.
The distinct-sector cap is map-fill's stopping rule; before this WO it sat
above the intent tick and would have reported `completed` for a StarDock hunt
that never found a dock — a run claiming success for a goal it did not reach.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient import explore, world_model
from tw2002_aiclient.loops.player import OUTCOME_COMPLETED, OUTCOME_HALTED
from tw2002_aiclient.session import sector_explore
from tw2002_aiclient.session.control_lock import ControlLock

from .test_sector_explore import WORLD, ExploreMapSession, _seed_line


def _line_graph(n: int, *, frontier_from: int | None = None, frontier_to: int = 99):
    graph: dict[int, list[int]] = {}
    for i in range(1, n + 1):
        w = []
        if i > 1:
            w.append(i - 1)
        if i < n:
            w.append(i + 1)
        graph[i] = w
    if frontier_from is not None:
        graph[frontier_from] = graph.get(frontier_from, []) + [frontier_to]
    return graph


def _run(tmp_path, *, sector=1, graph=None, timeout=30, sync_world_model=True, **start_kw):
    """`sync_world_model=False` matters for the landmark tests: the harness's
    `_sync_sector()` upserts `landmarks: []` on construction and after every
    hop, which would wipe a seeded StarDock before the planner ever looks for
    it. Turning the sync off leaves the seeded world intact; warps still
    reach the model through the product's own screen ingest."""
    session = ExploreMapSession(
        sector=sector, graph=graph, state_dir=tmp_path,
        sync_world_model=sync_world_model,
    )
    runner = sector_explore.ExploreRunner(session, ControlLock(), state_dir=tmp_path)
    runner.start(WORLD, **start_kw)
    runner._thread.join(timeout=timeout)
    return runner.snapshot().report


# ------------------------------------------------------------------ E3 intents

def test_an_unknown_intent_is_refused_not_defaulted(tmp_path: Path):
    """A run that quietly map-fills when the operator confirmed something
    else would have done other than what the arm gate promised."""
    _seed_line(tmp_path, [1, 2])
    session = ExploreMapSession(sector=1, graph={1: [2], 2: [1]}, state_dir=tmp_path)
    runner = sector_explore.ExploreRunner(session, ControlLock(), state_dir=tmp_path)
    with pytest.raises(sector_explore.ExploreRefused) as exc:
        runner.start(WORLD, intent="nonsense")
    assert "invalid_intent" in str(exc.value)


def test_the_default_intent_is_map_fill_so_existing_callers_are_unchanged(tmp_path: Path):
    _seed_line(tmp_path, [1, 2, 3], extra_frontier=(3, 99))
    report = _run(tmp_path, graph=_line_graph(3, frontier_from=3), min_sectors=2, turn_budget=5)
    assert report.intent == explore.INTENT_MAP_FILL


def test_the_intent_is_reported_so_an_outcome_can_be_interpreted(tmp_path: Path):
    """"exhausted" means a filled frontier for map-fill and an unreachable
    landmark for find-StarDock; the report has to say which run it was."""
    _seed_line(tmp_path, [1, 2])
    report = _run(
        tmp_path, graph={1: [2], 2: [1]},
        min_sectors=5, turn_budget=5, intent=explore.INTENT_FIND_STARDOCK,
    )
    assert report.intent == explore.INTENT_FIND_STARDOCK


def test_find_stardock_does_not_report_completed_just_for_visiting_sectors(tmp_path: Path):
    """THE pin. The distinct-sector cap is map-fill's rule. A StarDock hunt
    that hit it would report `completed` having never found a dock."""
    _seed_line(tmp_path, [1, 2, 3, 4, 5, 6], extra_frontier=(6, 99))
    report = _run(
        tmp_path, graph=_line_graph(6, frontier_from=6),
        min_sectors=2, turn_budget=20, intent=explore.INTENT_FIND_STARDOCK,
    )
    assert report.outcome != OUTCOME_COMPLETED, (
        "find-StarDock claimed success for a dock it never found"
    )


def test_find_stardock_completes_on_arrival(tmp_path: Path):
    """Arrival IS the goal, so it is `completed` — not an exhausted halt."""
    world_model.bulk_upsert(
        WORLD,
        [
            {"sector_id": 1, "warps": [2], "landmarks": []},
            {"sector_id": 2, "warps": [1], "landmarks": ["StarDock"]},
        ],
        state_dir=tmp_path,
    )
    report = _run(
        tmp_path, sector=2, graph={1: [2], 2: [1]}, sync_world_model=False,
        min_sectors=0, turn_budget=10, intent=explore.INTENT_FIND_STARDOCK,
    )
    assert report.outcome == OUTCOME_COMPLETED
    assert report.reason is None


# ------------------------------------------------------- E1 exhaustive + halts

def test_min_sectors_zero_means_no_cap_and_runs_until_exhausted(tmp_path: Path):
    """E1: "runs until turn budget or frontier exhausted". With a cap of 5
    the run would stop at 5; with 0 it keeps going and halts with a typed
    frontier reason."""
    _seed_line(tmp_path, [1, 2])
    report = _run(tmp_path, graph={1: [2], 2: [1]}, min_sectors=0, turn_budget=20)
    assert report.outcome == OUTCOME_HALTED
    assert report.reason.startswith("explore_exhausted")


def test_a_capped_run_still_completes_at_its_cap(tmp_path: Path):
    """The cap is not broken by making 0 mean uncapped."""
    _seed_line(tmp_path, [1, 2, 3, 4, 5, 6], extra_frontier=(6, 99))
    report = _run(
        tmp_path, graph=_line_graph(6, frontier_from=6), min_sectors=2, turn_budget=20
    )
    assert report.outcome == OUTCOME_COMPLETED


def test_a_negative_cap_is_still_refused(tmp_path: Path):
    """0 became meaningful; a cap you cannot reach did not."""
    _seed_line(tmp_path, [1, 2])
    session = ExploreMapSession(sector=1, graph={1: [2], 2: [1]}, state_dir=tmp_path)
    runner = sector_explore.ExploreRunner(session, ControlLock(), state_dir=tmp_path)
    with pytest.raises(sector_explore.ExploreRefused) as exc:
        runner.start(WORLD, min_sectors=-1)
    assert "invalid_min_sectors" in str(exc.value)


def test_the_turn_budget_halt_is_typed(tmp_path: Path):
    """E1 asks for a typed halt reason, not a bare stop."""
    _seed_line(tmp_path, [1, 2, 3, 4, 5, 6], extra_frontier=(6, 99))
    report = _run(
        tmp_path, graph=_line_graph(6, frontier_from=6), min_sectors=0, turn_budget=1
    )
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == "explore_exhausted:turn_budget"


def test_explore_halts_on_a_never_auto_action_screen(tmp_path: Path):
    """E4's sharper half. `test_sector_explore.py` pins the *unrecognized*
    screen; this pins the *recognized-and-forbidden* one — a money/action
    prompt appearing mid-explore. The explorer must stop rather than send
    into it, and the two halts must stay DISTINGUISHABLE: "I did not
    understand" and "I understood and refused" are different facts for the
    human who has to take the keyboard back.

    The autoloop player has this pin (`test_autoloop.py`); the explorer did
    not.
    """
    from tw2002_aiclient.loops.player import HALT_NEVER_AUTO_ACTION

    _seed_line(tmp_path, [1, 2], extra_frontier=(2, 99))
    session = ExploreMapSession(
        sector=1, graph={1: [2], 2: [1, 99]}, state_dir=tmp_path,
    )
    session._screen = (
        "How many holds of Fuel Ore do you want to buy [50]? "
    )
    session.rx_count = 1
    session.last_rx = -10.0
    runner = sector_explore.ExploreRunner(session, ControlLock(), state_dir=tmp_path)
    runner.start(WORLD, min_sectors=0, turn_budget=10)
    runner._thread.join(timeout=15)
    report = runner.snapshot().report
    assert report.outcome == OUTCOME_HALTED
    assert report.reason in (HALT_NEVER_AUTO_ACTION,), (
        f"explore did not refuse an action prompt; halted as {report.reason!r}"
    )
    assert report.sends_issued == 0, "explore sent into an action prompt"


def test_the_intent_reaches_the_wire_report(tmp_path: Path):
    """`explore_run_wire` is what a cockpit reads; an intent the surface
    cannot see is an intent the operator cannot be shown."""
    _seed_line(tmp_path, [1, 2])
    session = ExploreMapSession(sector=1, graph={1: [2], 2: [1]}, state_dir=tmp_path)
    runner = sector_explore.ExploreRunner(session, ControlLock(), state_dir=tmp_path)
    runner.start(WORLD, min_sectors=0, turn_budget=2, intent=explore.INTENT_FIND_STARDOCK)
    runner._thread.join(timeout=15)
    wire = sector_explore.explore_run_wire(runner.snapshot())
    assert wire["run"]["intent"] == explore.INTENT_FIND_STARDOCK
