"""Pins for CIM port-report → bulk_upsert ingest (WO-WIRE-BULK-UPSERT-CIM-INGEST)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tw2002_aiclient import cim_report_capture as crc
from tw2002_aiclient import world_model as wm
from tw2002_aiclient.session.state_parser import parse_port_report

WORLD_ID = "cim-demo_example__A__Pilot"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cim_port_report.txt"


@dataclass
class _Snap:
    latest_event: dict | None


class _Play:
    def __init__(self, event: dict | None) -> None:
        self._event = event
        self.viewport_provider = lambda: _Snap(self._event)


class _Profile:
    host, game_letter, handle = "cim-demo.example", "A", "Pilot"


def test_parse_port_report_clean_multi_sector_fixture() -> None:
    text = FIXTURE.read_text()
    records = parse_port_report(text)
    by_sector = {r["sector_id"]: r for r in records}
    assert set(by_sector) == {1234, 5001, 5678}
    full = by_sector[1234]
    assert full["warps"] == [2235, 2100, 1999]
    assert full["port"]["class"] == "BBS"
    commodities = {c["name"]: c for c in full["port"]["commodities"]}
    assert commodities["Fuel Ore"] == {"name": "Fuel Ore", "status": "buying", "pct": 100}
    assert commodities["Organics"] == {"name": "Organics", "status": "buying", "pct": 40}
    assert commodities["Equipment"] == {"name": "Equipment", "status": "selling", "pct": 60}
    assert by_sector[5001]["warps"] == [5002, 5003]
    assert "port" not in by_sector[5001]
    assert by_sector[5678]["port"]["class"] == "SSB"
    assert "warps" not in by_sector[5678]


def test_write_from_cim_report_calls_bulk_upsert(tmp_path: Path, monkeypatch) -> None:
    """Product call site: write_from_cim_report → bulk_upsert."""
    calls: list[list] = []
    real = wm.bulk_upsert

    def _spy(world_id, records, state_dir=None, now=None):
        calls.append(list(records))
        return real(world_id, records, state_dir=state_dir, now=now)

    monkeypatch.setattr(wm, "bulk_upsert", _spy)
    text = FIXTURE.read_text()
    written = wm.write_from_cim_report(WORLD_ID, text, state_dir=tmp_path)
    assert len(calls) == 1
    assert {r["sector_id"] for r in calls[0]} == {1234, 5001, 5678}
    assert len(written) == 3
    rec = wm.get_sector(WORLD_ID, 1234, state_dir=tmp_path)
    assert rec is not None
    assert rec["port"]["class"] == "BBS"
    assert rec["warps"] == [2235, 2100, 1999]


def test_capture_refuses_non_cim_screen(tmp_path: Path) -> None:
    play = _Play(
        {
            "screen": ["Command [TL=00:00:00]:[1] (?=Help)? :"],
            "prompt": "Command [TL=00:00:00]:[1] (?=Help)? :",
            "classification": "main_command",
        }
    )
    result = crc.CimReportCapture().tick(play, _Profile(), state_dir=tmp_path)
    assert result.attempted is False
    assert result.reason in {"not_cim_report", "no_cim_rows"}
    assert wm.get_sector(WORLD_ID, 1234, state_dir=tmp_path) is None


def test_capture_writes_when_classified_cim(tmp_path: Path) -> None:
    text = FIXTURE.read_text()
    play = _Play(
        {
            "screen": text.splitlines(),
            "prompt": "Command [TL=00752:0/0/0/850] (?=Help)? :",
            "classification": "cim_report",
        }
    )
    cap = crc.CimReportCapture()
    first = cap.tick(play, _Profile(), state_dir=tmp_path)
    second = cap.tick(play, _Profile(), state_dir=tmp_path)
    assert first.attempted is True
    assert first.sectors_written == 3
    assert wm.get_sector(WORLD_ID, 1234, state_dir=tmp_path)["port"]["class"] == "BBS"
    assert second.attempted is False
    assert second.reason == "unchanged"


def test_app_idle_tick_wires_cim_capture() -> None:
    """Product call site in app.py: CimReportCapture constructed + ticked."""
    import ast
    from pathlib import Path as P

    src = P("tw2002_aiclient/app.py").read_text()
    assert "cim_report_capture" in src
    assert "CimReportCapture" in src
    assert "cim_capture.tick" in src
    assert ast.parse(src) is not None
