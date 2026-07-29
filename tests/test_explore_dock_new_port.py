"""WO-EXPLORE-DOCK-NEW-PORT: dock a first-sight port and ingest its commodities.

`world_model.write_port_only` shipped fully tested and **never called by any
product code**. Its docstring names `protocol._write_world_model` as its caller
and `state_parser.is_genuine_port_report` as its gate; neither symbol has ever
existed anywhere in the tree, and neither did the commodity extraction canon's
Ingestion section says this path "reuses". So the writer was a correct consumer
of a shape nothing produced, and every commodity table the client rendered was
dropped on the floor.

These pin the producer, the trigger, and the wire. Three are falsification pins
against specific forbidden behaviour rather than tests of intended behaviour:

* :func:`test_a_clipped_table_is_refused_because_a_partial_write_deletes` —
  canon's upsert replaces the commodities list outright, so ingesting 2 of 3
  rows would silently DELETE the third from a complete record.
* :func:`test_ports_none_never_docks` — spending a turn docking with a port the
  screen positively said is absent.
* :func:`test_the_attack_letter_can_never_be_sent` — the menu `P` opens leads
  with `<A> Attack this Port`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient import world_model
from tw2002_aiclient.loops.player import OUTCOME_HALTED
from tw2002_aiclient.session import sector_explore as sx
from tw2002_aiclient.session import state_parser as sp
from tw2002_aiclient.session.control_lock import ControlLock
from tw2002_aiclient.session.state_parser import PortRead

from .conftest import FakeAttachSession

WORLD = "w-dock"

FIXTURES = Path(__file__).parent / "fixtures"

REPORT = (
    "Commerce report for Gorram Primus: 07:08:00 AM Tue Jul 21, 2054\n"
    "\n"
    " Items     Status  Trading % of max OnBoard\n"
    " -----     ------  ------- -------- -------\n"
    "Fuel Ore   Buying    2850    100%       0\n"
    "Organics   Selling    930     75%       0\n"
    "Equipment  Buying    2720    100%       0\n"
    "\n"
    "Command [TL=00:00:00]:[4309] (?=Help)? :\n"
)


# --- the producer that did not exist -------------------------------------


@pytest.mark.parametrize(
    "name", ["port_commerce_report_gorram_primus.txt", "port_trade_screen.txt"]
)
def test_both_captured_reports_parse_to_canon_shape(name):
    """Real captures, not hand-built text: a double shaped like my assumption
    would agree with a parser built from the same assumption."""
    read = sp.read_port_commodities_from_report((FIXTURES / name).read_text())
    assert read.observed is True
    assert [c["name"] for c in read.commodities] == list(sp.COMMERCE_COMMODITIES)
    for c in read.commodities:
        assert set(c) == {"name", "status", "amount", "pct"}  # canon's Schema row
        assert c["status"] in {"buying", "selling"}
        assert isinstance(c["amount"], int) and isinstance(c["pct"], int)


def test_status_and_numbers_are_read_not_assumed():
    read = sp.read_port_commodities_from_report(REPORT)
    assert [(c["name"], c["status"], c["amount"], c["pct"]) for c in read.commodities] == [
        ("Fuel Ore", "buying", 2850, 100),
        ("Organics", "selling", 930, 75),
        ("Equipment", "buying", 2720, 100),
    ]


def test_a_clipped_table_is_refused_because_a_partial_write_deletes():
    """FALSIFICATION: two-of-three rows must NOT ingest.

    Canon: "an old and new `port` commodities list are never unioned; the new
    one wins outright." So a partial read does not add less information, it
    REMOVES the row it could not see from a previously complete record.
    """
    clipped = REPORT.replace("Equipment  Buying    2720    100%       0\n", "")
    assert sp.read_port_commodities_from_report(clipped).observed is False


@pytest.mark.parametrize(
    "text",
    [
        "The trader says: Fuel Ore Buying 2850 100% here, friend.\n",
        "Sector  : 42\nPorts   : Aegis, Class 1 (BBS)\nWarps to Sector(s) : 1\n",
        "Commerce report for X: 10:00:00 AM Sat Jul 18, 2054\n\nCommand [TL=0]:[1] (?=Help)? :\n",
        None,
        12345,
    ],
)
def test_never_ingests_a_screen_it_cannot_vouch_for(text):
    assert sp.read_port_commodities_from_report(text).observed is False


def test_the_newest_report_wins_on_a_scrolled_screen():
    older = REPORT.replace("2850", "1111").replace("Gorram Primus", "Old Port")
    read = sp.read_port_commodities_from_report(older + REPORT)
    assert read.commodities[0]["amount"] == 2850


# --- the trigger: when is a turn worth spending? --------------------------


def test_ports_none_never_docks():
    """FALSIFICATION (WO Accept 4): `Ports : None` is a positive statement that
    there is nothing here. Docking on it spends a turn on nothing."""
    assert sx.port_needs_dock(PortRead(observed=True, port=None), None) is False


def test_an_unobserved_flyby_never_docks():
    assert sx.port_needs_dock(PortRead(observed=False), None) is False
    assert sx.port_needs_dock(None, None) is False


def test_a_first_sight_port_with_no_stored_commodities_docks():
    assert sx.port_needs_dock(PortRead(observed=True, port={"class": "BBS"}), None) is True
    assert sx.port_needs_dock(
        PortRead(observed=True, port={"class": "BBS"}), {"class": "BBS"}
    ) is True


def test_a_port_whose_commodities_we_hold_is_not_re_docked():
    stored = {"class": "BBS", "commodities": [{"name": "Fuel Ore"}]}
    assert sx.port_needs_dock(PortRead(observed=True, port={"class": "BBS"}), stored) is False


def test_an_unreadable_world_model_refuses_to_spend(tmp_path, monkeypatch):
    """A read failure must not read as "no commodities stored", which is the
    one answer that licences spending a turn."""
    def boom(*a, **k):
        raise RuntimeError("disk gone")

    monkeypatch.setattr(world_model, "get_sector", boom)
    stored = sx._stored_port(WORLD, 158, state_dir=tmp_path)
    assert sx.port_needs_dock(PortRead(observed=True, port={"class": "BBS"}), stored) is False


# --- the wire: write_port_only's first product caller ---------------------


def test_the_report_is_written_to_the_sector_from_its_own_prompt(tmp_path):
    wrote = sx._ingest_docked_report(
        WORLD, full_text=REPORT, prompt_line="Command [TL=00:00:00]:[4309] (?=Help)? :",
        state_dir=tmp_path,
    )
    assert wrote == 4309
    rec = world_model.get_sector(WORLD, 4309, state_dir=tmp_path)
    assert [c["name"] for c in rec["port"]["commodities"]] == list(sp.COMMERCE_COMMODITIES)
    assert rec["port"]["last_seen_ts"]


def test_an_unreadable_prompt_writes_nothing_rather_than_guessing(tmp_path):
    """A port written into the wrong sector cannot be removed by any product
    path, so a missing sector is a refusal, never a fallback."""
    assert sx._ingest_docked_report(
        WORLD, full_text=REPORT, prompt_line="garbage", state_dir=tmp_path
    ) is None
    assert world_model.get_sector(WORLD, 4309, state_dir=tmp_path) is None


def test_a_docked_write_never_clobbers_a_class_learned_elsewhere(tmp_path):
    world_model.upsert_sector(
        WORLD, {"sector_id": 4309, "port": {"class": "SSB"}}, state_dir=tmp_path
    )
    sx._ingest_docked_report(
        WORLD, full_text=REPORT, prompt_line="Command [TL=00:00:00]:[4309] (?=Help)? :",
        state_dir=tmp_path,
    )
    rec = world_model.get_sector(WORLD, 4309, state_dir=tmp_path)
    assert rec["port"]["class"] == "SSB"
    assert len(rec["port"]["commodities"]) == 3


# --- the safety boundary --------------------------------------------------


def test_the_attack_letter_can_never_be_sent():
    """FALSIFICATION: the menu `P` opens leads with `<A> Attack this Port`.

    A one-character slip here is not a wrong menu item, it is an unattended
    attack -- the thing alignment-and-conduct forbids outright and that
    `fighter_toll_policy` keeps behind a Max-ratified gate.
    """
    assert "A" not in sx.DOCK_LETTER_ALLOWLIST
    assert sx.DOCK_LETTER_ALLOWLIST == frozenset({"P", "T"})

    runner = sx.ExploreRunner(session=object(), control_lock=object())
    for forbidden in ("A", "a", "PT", "", "1"):
        with pytest.raises(ValueError) as exc:
            runner._send_dock_letter(forbidden)
        assert sx.HALT_DOCK_FORBIDDEN_KEY in str(exc.value)


# --- the arm reaches the runner through every layer ----------------------
#
# Hub ruling 2026-07-28: library default False, and the explore ARM surfaces
# set True -- the turn-spend belongs to the operator's arm, not to a silent
# library default. A flag no surface ever sets is a gate whose verdict nothing
# reads, which is the same shape as the unwired writer this WO exists to fix.


class _CapturingRunner:
    def __init__(self):
        self.kwargs = None

    def start(self, world_id, **kwargs):
        self.kwargs = kwargs
        return sx.ExploreSnapshot(running=True, report=None)


def _dispatch(monkeypatch, args):
    from tw2002_aiclient.session import protocol

    runner = _CapturingRunner()
    monkeypatch.setattr(protocol, "_explore_runner", lambda server: runner)
    protocol._dispatch_explore_start(args, object())
    return runner.kwargs


def test_dispatch_without_the_flag_stays_false_for_compat(monkeypatch):
    assert _dispatch(monkeypatch, {"world_id": "w"})["dock_new_ports"] is False


@pytest.mark.parametrize("sent", [True, False])
def test_dispatch_forwards_the_flag_it_was_given(monkeypatch, sent):
    kwargs = _dispatch(monkeypatch, {"world_id": "w", "dock_new_ports": sent})
    assert kwargs["dock_new_ports"] is sent


def test_a_non_bool_flag_is_refused_not_coerced():
    """`"no"` is truthy in Python. Coercing it would arm a turn-spending
    cascade from a string the caller meant as a refusal."""
    runner = sx.ExploreRunner(object(), object())
    with pytest.raises(sx.ExploreRefused) as exc:
        runner.start("w", dock_new_ports="no")
    assert "invalid_dock_new_ports" in str(exc.value)


def test_the_arg_is_accepted_by_the_protocol_allowlist():
    assert "dock_new_ports" in sx.ARGS_EXPLORE_START


def test_the_adapter_omits_the_key_when_unspecified(monkeypatch):
    from tw2002_aiclient import adapters
    from tw2002_aiclient.session import cli as _cli

    seen = {}
    monkeypatch.setattr(
        _cli, "send_request", lambda verb, payload, run_dir=None: seen.update(payload) or {"ok": True}
    )
    adapters.explore_start("w", run_dir=Path("/nonexistent"))
    assert "dock_new_ports" not in seen
    seen.clear()
    adapters.explore_start("w", dock_new_ports=True, run_dir=Path("/nonexistent"))
    assert seen["dock_new_ports"] is True


def test_the_cli_explore_arm_defaults_off(monkeypatch):
    """`tw explore start` defaults dock OFF until dialect known (WO-…-DEFAULT-OFF)."""
    from tw2002_aiclient.session import cli as _cli

    parser = _cli.build_parser()
    args = parser.parse_args(["explore", "start", "--world-id", "w"])
    assert args.dock_new_ports is False
    assert parser.parse_args(
        ["explore", "start", "--world-id", "w", "--dock-new-ports"]
    ).dock_new_ports is True

    seen = {}
    monkeypatch.setattr(
        _cli, "send_request", lambda verb, payload, run_dir=None: seen.update(payload) or {"ok": True}
    )
    monkeypatch.setattr(_cli, "print_response", lambda *a, **k: None)
    _cli.cmd_explore_start(args)
    assert seen["dock_new_ports"] is False


def test_the_play_explore_arm_does_not_force_dock_on():
    """Play explore must not pass dock_new_ports=True (omit or False)."""
    import ast
    import inspect

    from tw2002_aiclient import app

    tree = ast.parse(inspect.getsource(app))
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "explore_start_for_profile"
    ]
    assert calls, "the Play explore arm no longer calls explore_start_for_profile"
    for call in calls:
        kw = {k.arg: k.value for k in call.keywords}
        if "dock_new_ports" in kw:
            assert isinstance(kw["dock_new_ports"], ast.Constant)
            assert kw["dock_new_ports"].value is False


# --- wired, not merely defined -------------------------------------------
#
# The whole reason this WO exists is a writer that was correct, fully tested,
# and never called. A test file that only exercises the new functions directly
# would reproduce exactly that failure one layer up, so these drive the REAL
# `ExploreRunner` and assert against the on-disk store.

SECTOR_WITH_PORT = (
    "Sector  : 4309 in uncharted space.\n"
    "Ports   : Gorram Primus, Class 1 (BBS)\n"
    "Warps to Sector(s) :  (158)\n"
    "\n"
    "Command [TL=00753:0/0/0/850]:[4309] (?=Help)? : "
)
PORT_MENU = (
    "<A> Attack this Port\n"
    "<T> Trade with this Port\n"
    "<Q> Quit\n"
    "Enter your choice [T] ? "
)


#: A rendered screen's last row IS the live prompt, so these carry no trailing
#: newline -- one would make `rows[-1]` empty and every screen unrecognized.
REPORT_SCREEN = REPORT.rstrip("\n")


class _DockSession(FakeAttachSession):
    """Scripted P -> menu -> T -> commerce report.

    `sent` is the base class's own list of ``(text, enter, secret)`` tuples --
    deliberately not a private list of my own. A hand-kept log records what I
    assumed the driver sends; the base's records what it actually called.
    """

    def __init__(self, *, menu_screen: str = PORT_MENU, report_screen: str = REPORT_SCREEN):
        super().__init__(initial_screen=SECTOR_WITH_PORT)
        self.rx_count = 1
        self.last_rx = -10.0
        self._menu = menu_screen
        self._report = report_screen

    def send(self, text, enter=True, secret=False, sender="app"):
        key = text.strip().upper()
        if key == "P":
            self._screen = self._menu
        elif key == "T":
            self._screen = self._report
        return super().send(text, enter=enter, secret=secret, sender=sender)


def _letters_sent(session) -> list[str]:
    return [t[0].strip() for t in session.sent]


def _run_to_completion(session, tmp_path, *, dock_new_ports):
    world_model.upsert_sector(
        WORLD, {"sector_id": 4309, "warps": [158], "landmarks": []}, state_dir=tmp_path
    )
    runner = sx.ExploreRunner(
        session, ControlLock(), state_dir=tmp_path, timeout_s=2.0, debounce_ms=1
    )
    runner.start(WORLD, min_sectors=1, turn_budget=5, dock_new_ports=dock_new_ports)
    snap = runner.stop(join_timeout=10.0)
    return snap.report


def test_an_armed_run_docks_a_first_sight_port_and_stores_its_commodities(tmp_path):
    session = _DockSession()
    _run_to_completion(session, tmp_path, dock_new_ports=True)
    assert _letters_sent(session) == ["P", "T"]
    rec = world_model.get_sector(WORLD, 4309, state_dir=tmp_path)
    assert [c["name"] for c in rec["port"]["commodities"]] == list(sp.COMMERCE_COMMODITIES)


def test_an_unarmed_run_reads_the_free_flyby_and_spends_nothing(tmp_path):
    """Off by default is the safety posture, but it must not cost the free
    read: an unarmed run still learns the port CLASS from the flyby."""
    session = _DockSession()
    _run_to_completion(session, tmp_path, dock_new_ports=False)
    assert _letters_sent(session) == []
    rec = world_model.get_sector(WORLD, 4309, state_dir=tmp_path)
    assert rec["port"]["class"] == "BBS"
    assert not rec["port"].get("commodities")


def test_an_unrecognized_dock_screen_halts_rather_than_wandering(tmp_path):
    """WO Accept 3: no silent wander. Mid-cascade we are inside a menu whose
    first option attacks the port -- guessing an exit is the unsafe move."""
    session = _DockSession(menu_screen="Some screen we have never seen.\n:")
    report = _run_to_completion(session, tmp_path, dock_new_ports=True)
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == sx.HALT_DOCK_UNRECOGNIZED
    assert _letters_sent(session) == ["P"]  # never sent T blind


def test_an_unparseable_report_halts_and_writes_no_commodities(tmp_path):
    session = _DockSession(report_screen="Docking...\nCommand [TL=0]:[4309] (?=Help)? : ")
    report = _run_to_completion(session, tmp_path, dock_new_ports=True)
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == sx.HALT_DOCK_UNRECOGNIZED
    rec = world_model.get_sector(WORLD, 4309, state_dir=tmp_path)
    assert not rec["port"].get("commodities")


def test_a_human_dock_already_on_screen_is_ingested_for_free(tmp_path):
    """The report classifies as `main_command`, so it reaches the loop whoever
    docked. Before this WO every one of those tables was discarded."""
    session = _DockSession()
    session._screen = REPORT_SCREEN
    _run_to_completion(session, tmp_path, dock_new_ports=False)
    assert _letters_sent(session) == []
    rec = world_model.get_sector(WORLD, 4309, state_dir=tmp_path)
    assert len(rec["port"]["commodities"]) == 3
