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
from tw2002_aiclient.session.classify import NEVER_AUTO_ACTION_CLASSES, classify_screen
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
    """Play explore must never arm dock ON by itself.

    AMENDED by WO-PLAY-EXPLORE-FLAGS (#212, Max-GO'd 2026-07-29). The
    original pin required a literal `False` (or omission), which was the
    right shape while WO-EXPLORE-DOCK-DEFAULT-OFF held dock off
    *unconditionally* -- "until dialect known". #211 shipped the dialect and
    #212 adds the operator opt-in, so the call site now forwards a variable.

    What was retired is only the *literal-constant* requirement, which was a
    proxy for "no opt-in exists yet". The safety property is kept and
    tightened: dock may be a constant `False`, or a NAME whose initial value
    in `_run_play` is `False` -- so a hardcoded `True`, a different variable,
    or an opt-in that defaults ON all still fail. The `fight_tolls` twin of
    this pin lives in `tests/test_play_explore_flags.py` (it had none here),
    and is deliberately not duplicated into this dock-scoped file.
    """
    import ast
    import inspect

    from tw2002_aiclient import app

    source = inspect.getsource(app)
    tree = ast.parse(source)
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "explore_start_for_profile"
    ]
    assert calls, "the Play explore arm no longer calls explore_start_for_profile"

    def _initialised_constant(name: str, value: bool) -> bool:
        """True iff every plain constant init of `name` equals *value*."""
        seen = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
        ]
        assert seen, f"{name} is forwarded to the adapter but never assigned"
        return all(
            isinstance(a.value, ast.Constant) and a.value.value is value
            for a in seen
            # the toggle itself (`x = not x`) is a UnaryOp, not an Assign of
            # a constant -- only plain constant initialisations are checked
            if isinstance(a.value, ast.Constant)
        )

    for call in calls:
        kw = {k.arg: k.value for k in call.keywords}
        if "dock_new_ports" not in kw:
            continue
        node = kw["dock_new_ports"]
        # WO-PLAY-EXPLORE-GATHER-DEFAULT-ON: Play forwards a bare name that
        # initialises True. Must not hardcode a Constant True/False here —
        # that would bypass the operator toggle.
        assert isinstance(node, ast.Name), (
            f"dock_new_ports must be a bare Play toggle name, got "
            f"{ast.dump(node)}"
        )
        assert _initialised_constant(node.id, True), (
            f"{node.id} is forwarded as the dock arm but does not "
            f"initialise to True -- Play gather default must stay ON"
        )


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
NEXT_SECTOR = (
    "Sector  : 158\n"
    "Ports   : None\n"
    "Warps to Sector(s) : 4309\n"
    "Command [TL=00:00:00]:[158] (?=Help)? :"
)
COMMAND_4309 = "Command [TL=00:00:00]:[4309] (?=Help)? :"


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
        elif key == "0" and "How many holds of " in self._screen:
            self._screen = "\n".join(self._screen.splitlines()[:-1] + [COMMAND_4309])
        elif key == "158":
            self._screen = NEXT_SECTOR
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
    assert report.reason == sx.HALT_DOCK_MENU_UNRECOGNIZED
    assert _letters_sent(session) == ["P"]  # never sent T blind


def test_an_unparseable_report_halts_and_writes_no_commodities(tmp_path):
    session = _DockSession(report_screen="Docking...\nCommand [TL=0]:[4309] (?=Help)? : ")
    report = _run_to_completion(session, tmp_path, dock_new_ports=True)
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == sx.HALT_DOCK_REPORT_UNREADABLE
    rec = world_model.get_sector(WORLD, 4309, state_dir=tmp_path)
    assert not rec["port"].get("commodities")


def test_the_two_dock_failures_do_not_share_a_reason():
    """WO-EXPLORE-DOCK-DIALECT. These were both `dock_screen_unrecognized`,
    and that is precisely why #205's live halt was diagnosed as "the menu
    dialect is unknown" when the menu had matched and the sector attribution
    was what failed. A reason string shared by two failure sites is a hint,
    not a diagnosis -- so the pin is that they stay DISTINCT."""
    reasons = [
        sx.HALT_DOCK_MENU_UNRECOGNIZED,
        sx.HALT_DOCK_REPORT_UNREADABLE,
        sx.HALT_DOCK_POSITION_UNKNOWN,
    ]
    assert len(set(reasons)) == 3
    assert not hasattr(sx, "HALT_DOCK_UNRECOGNIZED"), "the ambiguous reason came back"


def test_a_human_dock_already_on_screen_is_ingested_for_free(tmp_path):
    """The report classifies as `main_command`, so it reaches the loop whoever
    docked. Before this WO every one of those tables was discarded."""
    session = _DockSession()
    session._screen = REPORT_SCREEN
    _run_to_completion(session, tmp_path, dock_new_ports=False)
    assert _letters_sent(session) == []
    rec = world_model.get_sector(WORLD, 4309, state_dir=tmp_path)
    assert len(rec["port"]["commodities"]) == 3


# --- WO-EXPLORE-DOCK-DIALECT: the real wire ------------------------------
#
# The WO was written believing `--dock-new-ports` failed because the dock UI
# spoke an uncaptured dialect. It did not. Fixtures below are extracted from
# `logs/session-20260725T202110Z.log`, not retyped, because the defect lived
# exactly in the gap between what I assumed the screen looked like and what
# the game actually sends.

REAL_MENU = (FIXTURES / "port_menu_post_p.txt").read_text().rstrip("\n")
REAL_TRADEABLE = (FIXTURES / "port_commerce_report_tradeable.txt").read_text().rstrip("\n")


def test_the_real_captured_port_menu_was_always_recognized():
    """The premise the WO rested on, falsified against captured wire."""
    assert sx._PORT_MENU_MARKER in REAL_MENU.lower()
    assert "<A> Attack this Port" in REAL_MENU  # still the first option


def test_the_real_post_T_screen_parses_perfectly_and_carries_no_sector():
    """THE defect. Both halves matter: the table reads fine, so nothing looked
    broken about the parse, while the trailing prompt is a trade dialogue with
    no sector in it -- so a design taking the sector from THIS screen could
    never work at any port that has goods to trade."""
    parsed = sp.read_port_commodities_from_report(REAL_TRADEABLE)
    assert parsed.observed is True
    assert [c["name"] for c in parsed.commodities] == list(sp.COMMERCE_COMMODITIES)

    last = REAL_TRADEABLE.splitlines()[-1].strip()
    assert last == "How many holds of Equipment do you want to buy [40]?"
    assert sp.read_current_sector(last).sector is None


def test_the_pre_P_command_prompt_is_where_the_sector_actually_lives():
    """The control for the test above -- the sector is readable, just from the
    screen BEFORE `P`, which is why it is now passed in rather than re-derived."""
    assert sp.read_current_sector("Command [TL=06:45:36]:[23372] (?=Help)? : ").sector == 23372


def test_the_old_fixtures_were_all_the_no_trade_case():
    """Why a green suite sat on top of a path that could not work. Both
    captured reports are real -- and both are the case where the port has
    nothing to trade with you, so TW2002 skips the dialogue and returns to the
    Command prompt. The sample selected exactly the case that hides the bug."""
    for name in ("port_commerce_report_gorram_primus.txt", "port_trade_screen.txt"):
        text = (FIXTURES / name).read_text()
        assert "don't have anything they want" in text
        assert sp.read_current_sector(text.splitlines()[-1].strip()).sector is not None


def test_a_tradeable_port_now_stores_its_commodities(tmp_path):
    """The WO's Accept, against the screen that used to fail."""
    session = _DockSession(menu_screen=REAL_MENU, report_screen=REAL_TRADEABLE)
    _run_to_completion(session, tmp_path, dock_new_ports=True)
    rec = world_model.get_sector(WORLD, 4309, state_dir=tmp_path)
    assert [(c["name"], c["status"], c["amount"], c["pct"]) for c in rec["port"]["commodities"]] == [
        ("Fuel Ore", "buying", 2030, 100),
        ("Organics", "buying", 2970, 100),
        ("Equipment", "selling", 2800, 100),
    ]


def test_the_port_is_attributed_to_where_we_stood_not_to_the_report(tmp_path):
    """The report names port `Raven` and the sector screen says 4309; the
    fixtures deliberately disagree so that a sector sourced from the report
    would land somewhere else and be caught. A port written into the wrong
    sector cannot be removed by any product path."""
    assert "Raven" in REAL_TRADEABLE and "4309" not in REAL_TRADEABLE
    session = _DockSession(menu_screen=REAL_MENU, report_screen=REAL_TRADEABLE)
    _run_to_completion(session, tmp_path, dock_new_ports=True)
    assert world_model.get_sector(WORLD, 4309, state_dir=tmp_path)["port"].get("commodities")


def test_gather_declines_the_trade_prompt_and_continues(tmp_path):
    """Gather is not Trade: exact quantity prompts receive numeric zero.

    `How many holds ... [40]?` takes its DEFAULT on input it cannot parse --
    captured wire shows a human typing `quit` there and buying equipment.
    The archived guarded driver identifies `0` as the explicit decline; no
    blank Enter is sent at the quantity or offer.
    """
    session = _DockSession(menu_screen=REAL_MENU, report_screen=REAL_TRADEABLE)
    report = _run_to_completion(session, tmp_path, dock_new_ports=True)
    assert _letters_sent(session) == ["P", "T", "0"]
    assert report.outcome == sx.OUTCOME_COMPLETED
    assert report.reason is None


def test_the_next_warp_is_sent_only_after_zero_returns_to_command(tmp_path):
    """REGRESSION, and the reason the gate lives inside the dock cascade.

    A successful dock returns into the MIDDLE of a loop iteration, past the
    gate at its top and immediately before the next warp is sent. Without a
    gate at the end of the cascade this run sent `P`, `T`, `158` -- the third
    being a sector number typed into `How many holds ... [40]?`, a prompt that
    takes its default on input it cannot parse.

    `min_sectors=2` so the run genuinely wants to keep going; a run that had
    already met its goal would stop for an unrelated reason and this pin would
    pass without exercising anything.
    """
    world_model.upsert_sector(
        WORLD, {"sector_id": 4309, "warps": [158], "landmarks": []}, state_dir=tmp_path
    )
    session = _DockSession(menu_screen=REAL_MENU, report_screen=REAL_TRADEABLE)
    runner = sx.ExploreRunner(
        session, ControlLock(), state_dir=tmp_path, timeout_s=2.0, debounce_ms=1
    )
    runner.start(WORLD, min_sectors=2, turn_budget=5, dock_new_ports=True)
    runner._thread.join(10.0)
    report = runner.snapshot().report
    assert report.outcome == sx.OUTCOME_COMPLETED
    assert _letters_sent(session) == ["P", "T", "0", "158"]


def test_the_trade_prompt_really_is_classified_never_auto():
    """Non-vacuity for the pin above: it asserts a halt reason that only
    arrives because the classifier names this screen `money_prompt`. If that
    ever stops being true the test above would still pass for some other
    halt, so the classification is pinned on its own."""
    last = REAL_TRADEABLE.splitlines()[-1].strip()
    klass = classify_screen(REAL_TRADEABLE, last)
    assert klass == "money_prompt"
    assert klass in NEVER_AUTO_ACTION_CLASSES


def _trade_frame(prompt: str) -> str:
    return "\n".join(REAL_TRADEABLE.splitlines()[:-1] + [prompt])


class _CascadeDockSession(_DockSession):
    def __init__(self, screens: list[str]):
        super().__init__(menu_screen=REAL_MENU, report_screen=screens[0])
        self._after_zero = iter(screens[1:])

    def send(self, text, enter=True, secret=False, sender="app"):
        if text.strip() == "0":
            self._screen = next(self._after_zero, _trade_frame(COMMAND_4309))
            return FakeAttachSession.send(
                self, text, enter=enter, secret=secret, sender=sender
            )
        return super().send(text, enter=enter, secret=secret, sender=sender)


@pytest.mark.parametrize("count", [2, 3])
def test_gather_declines_each_known_commodity_then_returns_to_command(tmp_path, count):
    prompts = [
        "How many holds of Fuel Ore do you want to buy [40]?",
        "How many holds of Organics do you want to sell [12]?",
        "How many holds of Equipment do you want to buy [7]?",
    ][:count]
    screens = [_trade_frame(p) for p in prompts] + [_trade_frame(COMMAND_4309)]
    session = _CascadeDockSession(screens)
    report = _run_to_completion(session, tmp_path, dock_new_ports=True)
    assert _letters_sent(session) == ["P", "T"] + ["0"] * count
    assert report.outcome == sx.OUTCOME_COMPLETED


class _CursorOwnedCascadeSession(_DockSession):
    """Real-grid shape: active prompt above a stale painted Command row."""

    def __init__(self, active_frames: list[str]):
        self._active_frames = iter(active_frames[1:])
        self._active_prompt = active_frames[0].splitlines()[-1].strip()
        super().__init__(
            menu_screen=REAL_MENU,
            report_screen=active_frames[0] + "\n" + COMMAND_4309,
        )

    def current_cursor_line(self):
        return self._active_prompt

    def send(self, text, enter=True, secret=False, sender="app"):
        key = text.strip().upper()
        if key == "P":
            result = super().send(text, enter=enter, secret=secret, sender=sender)
            self._active_prompt = "Enter your choice [T] ?"
            return result
        if key == "T":
            result = super().send(text, enter=enter, secret=secret, sender=sender)
            self._active_prompt = self._report.splitlines()[-2].strip()
            return result
        if key == "0":
            frame = next(self._active_frames)
            self._active_prompt = frame.splitlines()[-1].strip()
            self._screen = (
                frame
                if self._active_prompt.startswith("Command [")
                else frame + "\n" + COMMAND_4309
            )
            return FakeAttachSession.send(
                self, text, enter=enter, secret=secret, sender=sender
            )
        return super().send(text, enter=enter, secret=secret, sender=sender)


def test_gather_declines_all_three_cursor_owned_prompts_above_stale_command(
    tmp_path,
):
    """Regression: stale tail Command must not hide prompt two or three."""
    prompts = [
        "How many holds of Fuel Ore do you want to buy [50]?",
        "How many holds of Organics do you want to buy [50]?",
        "How many holds of Equipment do you want to sell [0]?",
    ]
    frames = [_trade_frame(prompt) for prompt in prompts]
    frames.append(_trade_frame(COMMAND_4309))
    session = _CursorOwnedCascadeSession(frames)

    report = _run_to_completion(session, tmp_path, dock_new_ports=True)

    assert _letters_sent(session) == ["P", "T", "0", "0", "0"]
    assert report.outcome == sx.OUTCOME_COMPLETED
    assert report.reason is None


def test_gather_refuses_a_fourth_quantity_without_sending_it(tmp_path):
    prompts = [
        "How many holds of Fuel Ore do you want to buy [40]?",
        "How many holds of Organics do you want to sell [12]?",
        "How many holds of Equipment do you want to buy [7]?",
        "How many holds of Fuel Ore do you want to sell [1]?",
    ]
    session = _CascadeDockSession([_trade_frame(p) for p in prompts])
    report = _run_to_completion(session, tmp_path, dock_new_ports=True)
    assert _letters_sent(session) == ["P", "T", "0", "0", "0"]
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == "never_auto_action:money_prompt"


def test_gather_never_answers_a_non_commodity_money_prompt(tmp_path):
    session = _DockSession(
        menu_screen=REAL_MENU,
        report_screen=_trade_frame("Transfer how many credits to the vault:"),
    )
    report = _run_to_completion(session, tmp_path, dock_new_ports=True)
    assert _letters_sent(session) == ["P", "T"]
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == "never_auto_action:money_prompt"


def test_gather_halts_if_zero_lands_on_an_offer(tmp_path):
    session = _CascadeDockSession(
        [
            REAL_TRADEABLE,
            _trade_frame("Your offer [924] ?"),
        ]
    )
    report = _run_to_completion(session, tmp_path, dock_new_ports=True)
    assert _letters_sent(session) == ["P", "T", "0"]
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == sx.HALT_CONFIRM_FAILED


def test_docking_blind_is_refused_before_any_letter_goes_out(tmp_path):
    """Defence in depth, and deliberately UNREACHABLE from the loop today --
    the run halts on `unrecognized_screen` at an unreadable sector long before
    the dock branch. So this calls the method directly rather than pretending
    the loop can produce the input; a test that drove the loop here would pass
    for the loop guard's reason while claiming to pin this one.

    It exists for the future where another caller reaches this method: docking
    blind spends a turn to learn a table it cannot safely attribute.
    """
    session = _DockSession()
    runner = sx.ExploreRunner(
        session, ControlLock(), state_dir=tmp_path, timeout_s=2.0, debounce_ms=1
    )
    rep = sx.ExploreReport(world_id=WORLD, started_at="t", min_sectors=1)
    assert runner._dock_and_ingest(rep, None) == (sx.HALT_DOCK_POSITION_UNKNOWN, 0, 0)
    assert _letters_sent(session) == []


def test_the_loop_cannot_reach_the_dock_branch_without_a_sector(tmp_path):
    """The other half of the statement above -- pinned, not assumed."""
    session = _DockSession()
    session._screen = "Ports   : Gorram Primus, Class 1 (BBS)\nSome prompt with no sector : "
    report = _run_to_completion(session, tmp_path, dock_new_ports=True)
    assert report.outcome == OUTCOME_HALTED
    assert report.reason == sx.HALT_UNRECOGNIZED_SCREEN
    assert _letters_sent(session) == []


def test_the_free_flyby_ingest_still_reads_its_own_prompt(tmp_path):
    """`sector_id` is optional, and the free-flyby caller deliberately does not
    pass it: on that path the prompt IS the ship Command prompt. Pinning that
    the fallback survived the change, since losing it would silently stop
    ingesting reports the human docked for."""
    assert _ingest_docked_report_sector(tmp_path) == 4309


def _ingest_docked_report_sector(tmp_path):
    return sx._ingest_docked_report(
        WORLD, full_text=REPORT, prompt_line="Command [TL=0]:[4309] (?=Help)? :",
        state_dir=tmp_path,
    )


# --- #211 live REVISE: the trailing Enter, and the scrollback marker -----
#
# Live prove on `32e7825` filled commodities and then produced this on two
# hosts (`.samantha/audit/dock-kernel-live-20260729T0354Z/`):
#
#     How many holds of Fuel Ore do you want to buy [50]?
#     Agreed, 50 units.
#     We'll sell them for 924 credits.
#     Your offer [924] ?
#
# with `sends_issued=2`. The app accepted a trade quantity it was never asked
# to accept, one Enter short of spending 924 credits.
#
# `_DockSession` could never have caught it: it ignores `enter=` and swaps
# screens per letter. The double below models the game as a KEYSTROKE consumer
# instead, which is the only way a trailing Enter can be seen at all.

_HOLDS = (
    "Commerce report for Harrison Minor: 10:56:29 PM Tue Jul 28, 2054\n"
    "\n"
    " Items     Status  Trading % of max OnBoard\n"
    " -----     ------  ------- -------- -------\n"
    "Fuel Ore   Selling    780    100%       0\n"
    "Organics   Buying    2520    100%       0\n"
    "Equipment  Buying    1910    100%       0\n"
    "\n"
    "We are selling up to 780.  You have 0 in your holds.\n"
    "How many holds of Fuel Ore do you want to buy [50]? "
)
_OFFER = _HOLDS + "\nAgreed, 50 units.\n\nWe'll sell them for 924 credits.\nYour offer [924] ? "


class _KeystrokeSession(FakeAttachSession):
    """The port cascade as a keystroke consumer -- hot-key menus, where a
    trailing Enter is an extra keystroke the NEXT prompt consumes.

    `keys` is every character the game actually received, which is the thing
    under test; asserting on screens alone cannot distinguish "sent T" from
    "sent T and an Enter that bought something".
    """

    SCREENS = {
        "command": SECTOR_WITH_PORT,
        "menu": REAL_MENU,
        "holds": _HOLDS,
        "offer": _OFFER,
        "declined": _HOLDS + "\n" + COMMAND_4309,
        "bought": _OFFER + "\nYou are a shrewd trader, they're all yours.\n",
        "attacked": "You attack the port!\n",
    }

    def __init__(self):
        super().__init__(initial_screen=SECTOR_WITH_PORT)
        self.rx_count = 1
        self.last_rx = -10.0
        self.keys: list[str] = []
        self._state = "command"
        self._quantity = ""

    def _feed(self, ch: str) -> None:
        self.keys.append(ch)
        s = self._state
        if s == "command":
            if ch.upper() == "P":
                self._state = "menu"
        elif s == "menu":
            # `T` selects trade; a bare Enter accepts the `[T]` default. Both
            # dock -- which is why the trailing Enter is not harmless.
            if ch.upper() == "T" or ch == "\r":
                self._state = "holds"
            elif ch.upper() == "Q":
                self._state = "command"
            elif ch.upper() == "A":
                self._state = "attacked"
        elif s == "holds":
            # Captured wire: unparsable input is ignored and Enter commits the
            # DEFAULT. A human typing `quit` here bought 40 units.
            if ch.isdigit():
                self._quantity += ch
            elif ch == "\r":
                self._state = "declined" if self._quantity == "0" else "offer"
        elif s == "offer":
            if ch == "\r":
                self._state = "bought"
        self._screen = self.SCREENS[self._state]

    def send(self, text, enter=True, secret=False, sender="app"):
        for ch in text.strip():
            self._feed(ch)
        if enter:
            self._feed("\r")
        return super().send(text, enter=enter, secret=secret, sender=sender)


def test_the_double_reproduces_the_live_overshoot_when_enter_is_sent():
    """Control: this double must be able to FAIL the way the live host did,
    or the pin below passes for the double's blindness rather than the fix."""
    s = _KeystrokeSession()
    s.send("P", enter=True)
    s.send("T", enter=True)
    assert "Agreed, 50 units." in s.render_text(s.render())
    assert s._state == "offer"


def test_the_dock_letters_go_out_as_hot_keys_with_no_trailing_enter(tmp_path):
    """REGRESSION (#211 live). The exact keystrokes, not the outcome: an
    assertion on screens or halt reason would pass even if an Enter had gone
    out and bought something first."""
    session = _KeystrokeSession()
    report = _run_to_completion(session, tmp_path, dock_new_ports=True)
    assert session.keys == ["P", "T", "0", "\r"], (
        f"unexpected keystrokes reached the game: {session.keys}"
    )

    screen = session.render_text(session.render())
    assert "Agreed," not in screen, "the run accepted a trade quantity"
    assert "Your offer" not in screen
    assert report.outcome == sx.OUTCOME_COMPLETED
    assert report.reason is None


def test_the_commodities_still_land_through_the_hot_key_path(tmp_path):
    """The fix must not buy safety by breaking the Accept."""
    session = _KeystrokeSession()
    _run_to_completion(session, tmp_path, dock_new_ports=True)
    rec = world_model.get_sector(WORLD, 4309, state_dir=tmp_path)
    assert [(c["name"], c["status"], c["amount"]) for c in rec["port"]["commodities"]] == [
        ("Fuel Ore", "selling", 780),
        ("Organics", "buying", 2520),
        ("Equipment", "buying", 1910),
    ]


class _ScrollbackMenuSession(FakeAttachSession):
    """`P` lands on a screen that still SHOWS the port menu while its live
    prompt is already the money prompt -- what the host actually rendered when
    `P\\r` docked us inside a single send."""

    def __init__(self):
        super().__init__(initial_screen=SECTOR_WITH_PORT)
        self.rx_count = 1
        self.last_rx = -10.0

    def send(self, text, enter=True, secret=False, sender="app"):
        self._screen = REAL_MENU + "\n<Port>\nDocking...\n" + _HOLDS
        return super().send(text, enter=enter, secret=secret, sender=sender)


def test_a_menu_left_in_scrollback_cannot_satisfy_the_menu_check(tmp_path):
    """The fail-closed half, and on its own it would have stopped the trade.

    The menu text is still on screen after docking, so a whole-screen check
    confirms "we are at the port menu" while the live prompt underneath is
    `How many holds ... [50]?`. Those two differ by one turn and one trade.
    Matching the PROMPT LINE is what tells them apart.
    """
    session = _ScrollbackMenuSession()
    report = _run_to_completion(session, tmp_path, dock_new_ports=True)
    assert report.reason == sx.HALT_DOCK_MENU_UNRECOGNIZED
    assert _letters_sent(session) == ["P"]  # never sent T into the money prompt


def test_that_screen_really_does_contain_the_marker():
    """Non-vacuity: the pin above is only meaningful because a whole-screen
    check WOULD have passed on this exact text."""
    screen = REAL_MENU + "\n<Port>\nDocking...\n" + _HOLDS
    assert sx._PORT_MENU_MARKER in screen.lower()          # the old check: passes
    assert sx._PORT_MENU_MARKER not in screen.splitlines()[-1].lower()  # the new one: refuses
