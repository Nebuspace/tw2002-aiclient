"""Pins for density-scan → world_model writeback (WO-WIRE-DENSITY-SCAN-WRITEBACK)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tw2002_aiclient import density_scan as ds
from tw2002_aiclient import density_scan_capture as dsc
from tw2002_aiclient import world_model as wm

WORLD_ID = "density-demo_example__A__Pilot"


@dataclass
class _Snap:
    latest_event: dict | None


class _Play:
    def __init__(self, event: dict | None) -> None:
        self._event = event
        self.viewport_provider = lambda: _Snap(self._event)


class _Profile:
    host, game_letter, handle = "density-demo.example", "A", "Pilot"


DENSITY_SCREEN = (
    "Sector  1234  Density:  105\n"
    "Sector: 5678 Density = 0\n"
    "Sector 999 ==> Density 40\n"
    "Command [TL=00753:0/0/0/850] (?=Help)? :\n"
)


def test_decode_atoms_and_fighter_presence_hypothesis() -> None:
    assert ds.decode_density_atoms(105) == ["port", "fighter"]
    assert ds.fighter_presence_hypothesis(105) is True
    assert ds.fighter_presence_hypothesis(0) is False
    assert ds.fighter_presence_hypothesis(100) is None  # port only — ambiguous
    assert ds.decode_density_atoms(-1) == []
    assert ds.fighter_presence_hypothesis("x") is None


def test_write_density_scan_persists_hypothesis_field(tmp_path: Path) -> None:
    readings = ds.parse_density_scan(DENSITY_SCREEN)
    written = wm.write_density_scan(WORLD_ID, readings, state_dir=tmp_path)
    assert len(written) == 3
    rec = wm.get_sector(WORLD_ID, 1234, state_dir=tmp_path)
    assert rec is not None
    dens = rec["density_scan"]
    assert dens["value"] == 105
    assert dens["atoms"] == ["port", "fighter"]
    assert dens["verification"] == "HYPOTHESIS"
    assert dens["fighter_presence"] is True
    # Must not invent threats/port from hypothesis decode.
    assert rec["threats"] == {"mines": False, "fighters": None}
    assert rec["port"] is None
    empty = wm.get_sector(WORLD_ID, 5678, state_dir=tmp_path)
    assert empty["density_scan"]["fighter_presence"] is False
    assert empty["density_scan"]["verification"] == "HYPOTHESIS"


def test_write_density_scan_fail_closed_on_junk(tmp_path: Path) -> None:
    assert wm.write_density_scan(WORLD_ID, {}, state_dir=tmp_path) == []
    assert wm.write_density_scan(WORLD_ID, None, state_dir=tmp_path) == []  # type: ignore[arg-type]
    assert (
        wm.write_density_scan(
            WORLD_ID,
            {"bad": 5, -1: 5, True: 5, 10: -3, 11: "x"},  # type: ignore[dict-item]
            state_dir=tmp_path,
        )
        == []
    )
    assert wm.get_sector(WORLD_ID, 10, state_dir=tmp_path) is None


def test_capture_screen_writeback_success(tmp_path: Path) -> None:
    result = dsc.capture_screen(
        WORLD_ID, DENSITY_SCREEN, screen_class="main_command", state_dir=tmp_path
    )
    assert result.attempted is True
    assert result.sectors_written == 3
    assert wm.get_sector(WORLD_ID, 999, state_dir=tmp_path)["density_scan"]["value"] == 40


def test_capture_screen_junk_fail_closed(tmp_path: Path) -> None:
    result = dsc.capture_screen(
        WORLD_ID,
        "Density Scanner for sale 50,000\nCommand [TL=1]? :",
        state_dir=tmp_path,
    )
    assert result.attempted is False
    assert result.reason == "no_density_rows"
    assert result.sectors_written == 0


def test_tick_persists_and_dedupes(tmp_path: Path) -> None:
    event = {
        "screen": DENSITY_SCREEN.splitlines(),
        "prompt": "Command [TL=00753:0/0/0/850] (?=Help)? :",
        "classification": "main_command",
    }
    play = _Play(event)
    cap = dsc.DensityScanCapture()
    first = cap.tick(play, _Profile(), state_dir=tmp_path)
    second = cap.tick(play, _Profile(), state_dir=tmp_path)
    assert first.attempted is True
    assert first.sectors_written == 3
    assert second.attempted is False
    assert second.reason == "unchanged"


def test_tick_skips_non_density_screen(tmp_path: Path) -> None:
    play = _Play(
        {
            "screen": ["Command [TL=00753:0/0/0/850] (?=Help)? :"],
            "prompt": "Command [TL=00753:0/0/0/850] (?=Help)? :",
            "classification": "main_command",
        }
    )
    result = dsc.DensityScanCapture().tick(play, _Profile(), state_dir=tmp_path)
    assert result.attempted is False
    assert result.reason == "no_density_rows"


def test_capture_module_has_no_send_symbol() -> None:
    banned = {"send", "do", "crawl", "run_live_crawl"}
    assert banned.isdisjoint(set(dir(dsc)))


def test_app_idle_tick_wires_density_capture() -> None:
    import inspect
    from tw2002_aiclient import app as app_mod

    src = inspect.getsource(app_mod)
    assert "density_scan_capture" in src
    assert "density_capture.tick" in src
