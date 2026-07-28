"""E2 wire: the explore loop persists port posture (WO-EXPLORE-AUTOMATION-GATE).

`world_model.write_from_state` has always been able to store a `port`; nothing
reached it. These drive the real `_ingest_settled_sector` into a real
world-model store on disk, so a regression that unwires the capture goes red
here rather than shipping as an empty model that chain detection would later
be blamed for.

The preserve/clear asymmetry is the reason the parser returns a tri-state, so
it is pinned in both directions.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient import world_model
from tw2002_aiclient.session.sector_explore import _ingest_settled_sector

WORLD = "w-e2"

WITH_PORT = (
    "Sector  : 158 in uncharted space.\n"
    "Ports   : Aegis, Class 1 (BBS)\n"
    "Warps to Sector(s) :  231 - 4309\n"
    "\n"
    "Command [TL=00:00:00]:[158] (?=Help)? :\n"
)
WARPS_ONLY = (
    "Sector  : 158 in uncharted space.\n"
    "Warps to Sector(s) :  231 - 4309\n"
    "\n"
    "Command [TL=00:00:00]:[158] (?=Help)? :\n"
)
PORTS_NONE = (
    "Sector  : 158 in uncharted space.\n"
    "Ports   : None\n"
    "Warps to Sector(s) :  231 - 4309\n"
    "\n"
    "Command [TL=00:00:00]:[158] (?=Help)? :\n"
)


def _ingest(tmp_path, text, sector=158):
    _ingest_settled_sector(WORLD, sector_id=sector, full_text=text, state_dir=tmp_path)
    return world_model.get_sector(WORLD, sector, state_dir=tmp_path)


def test_a_visited_port_sector_persists_its_buy_sell_posture(tmp_path):
    rec = _ingest(tmp_path, WITH_PORT)
    assert rec["port"]["class"] == "BBS"


def test_the_port_write_is_last_seen_stamped(tmp_path):
    """Freshness is what a later chain detector weighs before trusting a
    record, so a port written with no timestamp is a record nothing can age."""
    rec = _ingest(tmp_path, WITH_PORT)
    assert rec["port"].get("last_seen_ts")


def test_warps_are_still_persisted_alongside(tmp_path):
    """The port capture must not have displaced the existing warps write —
    the frontier planner reads exactly that graph."""
    rec = _ingest(tmp_path, WITH_PORT)
    assert sorted(rec["warps"]) == [231, 4309]


def test_a_later_warps_only_visit_does_not_erase_a_known_port(tmp_path):
    """The whole reason the parser distinguishes unobserved from absent. A
    render that never mentions ports states nothing about them."""
    _ingest(tmp_path, WITH_PORT)
    rec = _ingest(tmp_path, WARPS_ONLY)
    assert rec["port"] is not None
    assert rec["port"]["class"] == "BBS", "a warps-only re-visit wiped a learned port"


def test_a_positive_ports_none_DOES_clear_a_known_port(tmp_path):
    """The other direction: the screen positively said there is no port, so
    continuing to assert one would be the model lying about a sector."""
    _ingest(tmp_path, WITH_PORT)
    rec = _ingest(tmp_path, PORTS_NONE)
    assert rec["port"] is None


def test_a_sector_with_no_port_never_gains_one(tmp_path):
    rec = _ingest(tmp_path, WARPS_ONLY)
    assert not rec.get("port")


def test_ingest_never_raises_on_an_unparseable_screen(tmp_path):
    """The explore loop calls this on every hop; a parser surprise must not
    take a live run down mid-flight."""
    _ingest_settled_sector(
        WORLD, sector_id=42, full_text="\x00 garbage �", state_dir=tmp_path
    )
    assert world_model.get_sector(WORLD, 42, state_dir=tmp_path) is not None


def test_the_capture_is_wired_not_merely_defined(tmp_path):
    """Guards the exact defect this WO found: `world_model` could store a
    port and `_ingest_settled_sector` never sent one. If someone drops the
    `port` forwarding from the ingest, this is what goes red."""
    rec = _ingest(tmp_path, WITH_PORT)
    assert "port" in rec and rec["port"], (
        "port capture is unwired — the world model can store it, "
        "but the explore loop is not sending it"
    )
