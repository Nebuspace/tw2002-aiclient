"""Sector explore driver — planner unit + FakeSession integration (WO M4)."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from tw2002_aiclient import explore, world_model
from tw2002_aiclient.loops.player import (
    HALT_UNRECOGNIZED_SCREEN,
    OUTCOME_COMPLETED,
    OUTCOME_HALTED,
)
from tw2002_aiclient.session import protocol, sector_explore
from tw2002_aiclient.session.control_lock import ControlLock

from .conftest import FakeAttachSession

WORLD = "explore-fake+G+CAP"


def _seed_line(tmp_path: Path, sectors: list[int], *, extra_frontier: tuple[int, int] | None = None):
    records = []
    for i, sid in enumerate(sectors):
        warps = []
        if i > 0:
            warps.append(sectors[i - 1])
        if i + 1 < len(sectors):
            warps.append(sectors[i + 1])
        if extra_frontier and sid == extra_frontier[0]:
            warps.append(extra_frontier[1])
        records.append({"sector_id": sid, "warps": warps, "landmarks": []})
    world_model.bulk_upsert(WORLD, records, state_dir=tmp_path)


def _command_screen(sector: int, warps: list[int] | None = None) -> str:
    warp_text = ", ".join(str(w) for w in (warps or [])) or " "
    return (
        f"Sector : {sector}\n"
        f"Warps to Sector(s) :  ({warp_text})\n"
        f"Command [TL=00753:0/0/0/850]:[{sector}] (?=Help)? : "
    )


class ExploreMapSession(FakeAttachSession):
    """Scripted main_command screens; warps on numeric send when adjacent."""

    def __init__(self, *, sector: int, graph: dict[int, list[int]], state_dir: Path):
        self._sector = sector
        self._graph = {int(k): [int(w) for w in v] for k, v in graph.items()}
        self._state_dir = state_dir
        super().__init__(
            initial_screen=_command_screen(sector, self._graph.get(sector, [])),
        )
        self.rx_count = 1
        self.last_rx = -10.0
        self._sync_sector()

    def _sync_sector(self) -> None:
        warps = self._graph.get(self._sector, [])
        world_model.upsert_sector(
            WORLD,
            {"sector_id": self._sector, "warps": warps, "landmarks": []},
            state_dir=self._state_dir,
        )

    def send(self, text, enter=True, secret=False):
        dest = text.strip()
        if dest.isdigit():
            target = int(dest)
            allowed = self._graph.get(self._sector, [])
            if target in allowed:
                self._graph.setdefault(self._sector, [])
                if target not in self._graph[self._sector]:
                    self._graph[self._sector].append(target)
                self._graph.setdefault(target, [])
                if self._sector not in self._graph[target]:
                    self._graph[target].append(self._sector)
                self._sector = target
                self._sync_sector()
                self._screen = _command_screen(self._sector, self._graph.get(self._sector, []))
        return super().send(text, enter=enter, secret=secret)


def test_map_fill_warp_target_adjacent_hop(tmp_path: Path):
    _seed_line(tmp_path, [1, 2, 3], extra_frontier=(3, 99))
    nxt, reason = explore.map_fill_warp_target(
        WORLD, current_sector=1, turn_budget=5, state_dir=tmp_path,
    )
    assert reason == ""
    assert nxt == 2


def test_map_fill_warp_target_exhausted_halts(tmp_path: Path):
    _seed_line(tmp_path, [1, 2])
    nxt, reason = explore.map_fill_warp_target(
        WORLD, current_sector=1, turn_budget=5, state_dir=tmp_path,
    )
    assert nxt is None
    assert reason.startswith("explore_exhausted")


def test_explore_runner_visits_five_distinct_sectors(tmp_path: Path):
    _seed_line(tmp_path, [1, 2, 3, 4, 5, 6], extra_frontier=(6, 99))
    graph = {i: [i - 1, i + 1] if 1 < i < 6 else ([2] if i == 1 else [5, 99]) for i in range(1, 7)}
    session = ExploreMapSession(sector=1, graph=graph, state_dir=tmp_path)
    lock = ControlLock()
    runner = sector_explore.ExploreRunner(session, lock, state_dir=tmp_path)
    snap = runner.start(WORLD, min_sectors=5, turn_budget=20)
    assert snap.running is True
    runner._thread.join(timeout=30)
    snap = runner.snapshot()
    assert snap.report is not None, snap
    assert snap.report.outcome == OUTCOME_COMPLETED, (
        f"reason={snap.report.reason!r} distinct={snap.report.distinct_sectors} sends={snap.report.sends_issued}"
    )
    assert snap.report.distinct_sectors >= 5
    assert snap.report.sends_issued >= 4


def test_explore_halts_on_unknown_screen(tmp_path: Path):
    _seed_line(tmp_path, [1, 2], extra_frontier=(2, 99))
    session = ExploreMapSession(sector=1, graph={1: [2], 2: [1, 99]}, state_dir=tmp_path)
    session._screen = "Enter your password: "
    session.rx_count = 1
    session.last_rx = -10.0
    lock = ControlLock()
    runner = sector_explore.ExploreRunner(session, lock, state_dir=tmp_path)
    runner.start(WORLD, min_sectors=5, turn_budget=10)
    runner._thread.join(timeout=15)
    report = runner.snapshot().report
    assert report is not None
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == HALT_UNRECOGNIZED_SCREEN


def test_protocol_explore_start_and_status(tmp_path: Path):
    _seed_line(tmp_path, [1, 2, 3, 4, 5, 6], extra_frontier=(6, 99))
    graph = {i: [i - 1, i + 1] if 1 < i < 6 else ([2] if i == 1 else [5, 99]) for i in range(1, 7)}
    session = ExploreMapSession(sector=1, graph=graph, state_dir=tmp_path)
    lock = ControlLock()
    runner = sector_explore.ExploreRunner(session, lock, state_dir=tmp_path)

    class Server:
        control_lock = lock
        sector_explore = runner

    started = protocol.dispatch(
        session,
        "explore_start",
        {"world_id": WORLD, "min_sectors": 5, "turn_budget": 15},
        Server(),
    )
    assert started["ok"] is True
    runner._thread.join(timeout=30)
    status = protocol.dispatch(session, "explore_status", {}, Server())
    assert status["ok"] is True
    assert status["run"]["outcome"] == OUTCOME_COMPLETED
    assert status["run"]["distinct_sectors"] >= 5
