"""End-to-end proof that the TW-06/TW-25 world-model foundation is
actually wired, not just unit-tested in isolation -- drives the real
`protocol.dispatch()`/`build_response()` path with a scripted fake
session (same bare-dispatch-harness idiom as test_protocol_haggle.py's/
test_actor_attribution.py's FakeSession/FakeServer), through
`_current_world_id()`'s real profile resolution (a monkeypatched
`credentials.PROFILES_PATH`, not a stubbed resolver), into a
tmp-path-isolated `world_model` store. protocol.py's write-hook calls
`world_model.write_from_state()`/`bulk_upsert()` with no `state_dir` of
its own to thread through (there's no such session/server surface to
carry one) -- monkeypatching `world_model.WORLD_DIR`, the store's own
default-path constant, is the sanctioned way to isolate this per its
`state_dir=` convention (see world_model.py's module docstring / TW-06
dispatch note)."""

import os

import pytest

from twclient import credentials, protocol, state_parser, world_model
from twclient.terminal import TerminalScreen

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name):
    with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as f:
        return f.read()


class FakeSession:
    """Minimal bare-dispatch-harness session (same surface as
    test_protocol_haggle.py's/test_actor_attribution.py's FakeSession)
    plus `.host`/`.auto_login_profile` -- the two fields
    `_current_world_id()` actually reads."""

    def __init__(self, host, initial_text, auto_login_profile=None):
        self.host = host
        self.auto_login_profile = auto_login_profile
        self._text = initial_text
        self.sent = []
        self.rx_count = 1
        self.last_rx = 0.0
        self.t = 0.0

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds

    def render(self):
        return self._text.splitlines()

    def render_with_color(self):
        return self.render(), None

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._text

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))
        self.rx_count += 1
        self.last_rx = self.t

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350):
        return "idle", 0.0

    def record_history(self, *a, **kw):
        pass


class FakeServer:
    """Deliberately bare -- no `.control_lock`/`.ledger`/
    `.skill_recorder`, matching protocol.py's own documented "bare
    dispatch harness" convention (every one of those is getattr-guarded
    to a no-op)."""


def _write_profiles(path, profiles):
    lines = []
    for name, p in profiles.items():
        lines.append(f"[{name}]")
        lines.append(f'host = "{p["host"]}"')
        lines.append(f'port = {p["port"]}')
        lines.append(f'game_letter = "{p["game_letter"]}"')
        lines.append(f'handle = "{p["handle"]}"')
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture(autouse=True)
def isolated_world_store(tmp_path, monkeypatch):
    """Every test in this file gets its own tmp world_model directory
    AND its own tmp profiles.toml -- never the real project's state/ or
    config/ (this is the integration-proof suite; it must never read or
    write the live daemon's on-disk state). Returns the tmp
    profiles.toml path for tests to populate via `_write_profiles`."""
    monkeypatch.setattr(world_model, "WORLD_DIR", tmp_path / "world")
    profiles_path = tmp_path / "profiles.toml"
    monkeypatch.setattr(credentials, "PROFILES_PATH", profiles_path)
    return profiles_path


# A genuine sector-status shape (mack round-3: the world-model write-hook
# now gates on `is_genuine_sector_status` -- a bare "Sector : N" with no
# sibling status marker beneath it no longer qualifies, exactly the same
# "Ports :" sibling convention this file's own combined-screen tests
# below already use).
ALICE_SCREEN = "Sector : 123\nPorts   : None\nCommand [TL=00753:0/0/0/850] (?=Help)? : "
BOB_SCREEN = "Sector : 999\nPorts   : None\nCommand [TL=00753:0/0/0/850] (?=Help)? : "


# -- (a) a `do` producing a screen with a sector persists it, queryable -----


def test_do_with_a_sector_screen_persists_the_sector_queryable(isolated_world_store):
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    session = FakeSession("bat.example.com", ALICE_SCREEN, auto_login_profile="alice")

    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())

    assert resp["ok"] is True
    world_id = protocol._current_world_id(session)
    assert world_id is not None
    sector = world_model.get_sector(world_id, 123)
    assert sector is not None
    assert sector["sector_id"] == 123


# -- (b) a second world (different profile handle) stays isolated ----------


def test_two_worlds_stay_isolated_by_profile_handle(isolated_world_store):
    _write_profiles(
        isolated_world_store,
        {
            "alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"},
            "bob": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Bob"},
        },
    )
    alice_session = FakeSession("bat.example.com", ALICE_SCREEN, auto_login_profile="alice")
    bob_session = FakeSession("bat.example.com", BOB_SCREEN, auto_login_profile="bob")

    protocol.dispatch(alice_session, "do", {"input": ""}, FakeServer())
    protocol.dispatch(bob_session, "do", {"input": ""}, FakeServer())

    alice_world = protocol._current_world_id(alice_session)
    bob_world = protocol._current_world_id(bob_session)
    assert alice_world != bob_world  # same host+game_letter, different handle -- anti-galaxy-bleed

    alice_sectors = {s["sector_id"] for s in world_model.all_sectors(alice_world)}
    bob_sectors = {s["sector_id"] for s in world_model.all_sectors(bob_world)}
    assert alice_sectors == {123}
    assert bob_sectors == {999}
    assert 999 not in alice_sectors
    assert 123 not in bob_sectors


# -- (c) a CIM-report-shaped screen bulk-upserts multiple sectors -----------


def test_cim_report_screen_bulk_upserts_every_sector(isolated_world_store):
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    session = FakeSession(
        "bat.example.com", _load_fixture("cim_port_report.txt"), auto_login_profile="alice"
    )

    resp = protocol.dispatch(session, "do", {"input": "v"}, FakeServer())

    assert resp["ok"] is True
    world_id = protocol._current_world_id(session)
    sectors = {s["sector_id"] for s in world_model.all_sectors(world_id)}
    assert {1234, 5001, 5678} <= sectors


# -- (c2) mack Finding 2: a screen merely QUOTING the report shape is ------
# -- NOT ingested, even though parse_port_report() itself still finds ------
# -- well-formed rows in it (the gate is classification, not parsing) ------


def test_help_screen_quoting_a_cim_report_is_not_ingested(isolated_world_store):
    """Adapted from mack's probe_poison.py Scenario A: a help/tutorial
    screen quoting the CIM report format as a worked example must not
    get bulk-ingested as real sector data, even though its text
    reproduces the header/footer/row punctuation byte-for-byte."""
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    help_screen = (
        "Command [TL=00:00:00]:[1000] (?=Help) ? cim\n"
        "\n"
        "The Continuous Information Manifest (CIM) report looks like this:\n"
        "\n"
        "-=-=- Port Report (CIM) -=-=-\n"
        "Sector 999  Class: BBS F:10% O:20% E:30%  Warps: 1-2-3\n"
        "-=-=- End of Report -=-=-\n"
        "\n"
        "Use it to scan multiple sectors at once.\n"
        "Command [TL=00:00:01]:[1000] (?=Help) ?"
    )
    session = FakeSession("bat.example.com", help_screen, auto_login_profile="alice")

    resp = protocol.dispatch(session, "do", {"input": "cim"}, FakeServer())

    assert resp["ok"] is True
    world_id = protocol._current_world_id(session)
    sector = world_model.get_sector(world_id, 999)
    # The single-sector write_from_state() path is explicitly OUT OF
    # SCOPE for this finding (mack: "fine to keep unconditional") --
    # parse_state()'s bare `sector\s*:?\s*\d+` anchor has no CIM-specific
    # awareness at all and may still pick up "Sector 999" from this
    # quoted text as a bare sector_id-only entry. What must NOT happen is
    # the BULK path deriving port/warps data from the report's own row
    # grammar -- that's the actual vulnerability this finding fixes.
    assert sector is None or (sector["port"] is None and sector["warps"] == []), (
        "the bulk parse_port_report() path ingested port/warps data from a quoted example: "
        f"{sector}"
    )


def test_forged_chat_broadcast_quoting_a_cim_report_is_not_ingested(isolated_world_store):
    """Adapted from mack's probe_poison.py Scenario B: a forged/griefing
    chat broadcast reproducing the identical report punctuation must not
    get ingested either."""
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    chat_screen = (
        "Incoming transmission from Rival Trader:\n"
        "-=-=- Port Report (CIM) -=-=-\n"
        "Sector 42  Class: SSB F:1% O:1% E:1%  Warps: 66-77-88\n"
        "-=-=- End of Report -=-=-\n"
        "\n"
        "Command [TL=00:00:05]:[1000] (?=Help) ?"
    )
    session = FakeSession("bat.example.com", chat_screen, auto_login_profile="alice")

    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())

    assert resp["ok"] is True
    world_id = protocol._current_world_id(session)
    sector = world_model.get_sector(world_id, 42)
    # See the comment in test_help_screen_quoting_a_cim_report_is_not_ingested
    # above -- the single-sector path is out of scope; the bulk path
    # deriving port/warps from the report's row grammar is the bug.
    assert sector is None or (sector["port"] is None and sector["warps"] == []), (
        f"the bulk parse_port_report() path ingested port/warps data from a forged broadcast: {sector}"
    )


# -- (c3) mack's fresh-eyes follow-up: the single-sector write_from_state() -
# -- path's F2 carve-out was ITSELF exploitable -- closed via a line-anchored
# -- _SECTOR_RE (state_parser.py), not a protocol.py/classify.py change -----


def test_real_sector_wins_over_a_same_screen_phantom_chat_mention_end_to_end(isolated_world_store):
    """Adapted from mack's probe_f2_combined.py, driven through the real
    dispatch path: the bot is REALLY in sector 100 at a real port; a
    same-screen chat line mentions "Sector: 8675" mid-sentence AFTER the
    real status line. The real port data must persist under the bot's
    ACTUAL sector (100), never the phantom (8675). (WO-FA2b REVISE: the
    commodity rows now sit under a real "Commerce report for..." header
    -- the block-scoping fix's own anchor requirement -- rather than
    bare, matching every genuine live capture in this repo.)"""
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    combined_screen = (
        "Sector : 100\n"
        "Ports   : Terran (Class 0)\n"
        "\n"
        "Commerce report for Terran:\n"
        "Fuel Ore   Buying     1200    75%\n"
        "Organics   Selling     800    40%\n"
        "Equipment  Buying      300    90%\n"
        "\n"
        "Incoming transmission from Rival Trader:\n"
        '"Great deals waiting in Sector: 8675, come check it out!"\n'
        "\n"
        "Command [TL=00:12:34]:[1000] (?=Help) ?"
    )
    session = FakeSession("bat.example.com", combined_screen, auto_login_profile="alice")

    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())

    assert resp["ok"] is True
    assert resp["state"]["sector"] == 100
    world_id = protocol._current_world_id(session)
    real_sector = world_model.get_sector(world_id, 100)
    phantom_sector = world_model.get_sector(world_id, 8675)
    assert real_sector is not None
    assert real_sector["port"]["commodities"][0]["name"] == "Fuel Ore"
    assert phantom_sector is None, "a same-screen chat mention must never create a phantom sector entry"


# -- (c4) mack round-3's fresh-eyes follow-up: a line-isolated forgery ------
# -- REPRODUCING the "own line" shape the round-2 fix requires, but --------
# -- embedded in an otherwise-narrative block, was itself still ------------
# -- exploitable -- closed via `is_genuine_sector_status`'s sibling --------
# -- co-occurrence gate on the world-model WRITE path only ------------------


def test_residual_line_isolated_forgery_in_a_narrative_block_is_not_ingested_end_to_end(
    isolated_world_store,
):
    """Adapted from mack's probe_residual_line_anchor.py, driven through
    the real dispatch path: the bot is REALLY in sector 100 at a real
    port; a planet-comment/bulletin block later on the SAME screen
    contains a line-isolated "Sector : 8675" with no sibling status
    marker of its own. The phantom sector must never get a world-model
    entry -- see `is_genuine_sector_status`'s docstring for why the
    real, earlier "Ports :"-adjacent block does not vouch for it."""
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    residual_screen = (
        "Sector : 100\n"
        "Ports   : Terran (Class 0)\n"
        "\n"
        "-- Planet comment --\n"
        "Great deals waiting here!\n"
        "Sector : 8675\n"
        "Come check it out!\n"
        "\n"
        "Command [TL=00:12:34]:[1000] (?=Help) ?"
    )
    session = FakeSession("bat.example.com", residual_screen, auto_login_profile="alice")

    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())

    assert resp["ok"] is True
    # parse_state()'s own extraction is unaffected by this fix -- other
    # consumers (skills.py/ledger.py/protocol.py's replay start-anchor)
    # still need the last-match value exactly as before.
    assert resp["state"]["sector"] == 8675
    world_id = protocol._current_world_id(session)
    assert world_model.get_sector(world_id, 8675) is None, (
        "a line-isolated forged 'Sector : N' in a narrative block must never create a phantom "
        "sector entry, even though it reproduces the round-2 fix's own-line requirement"
    )


def test_genuine_sector_screen_with_warps_sibling_persists_correctly(isolated_world_store):
    """A plain, non-adversarial genuine sector-status screen using the
    OTHER accepted sibling shape (`Warps to Sector(s) :`, not `Ports :`)
    must still persist normally -- the new gate narrows the false-
    positive surface, it doesn't disable ordinary genuine writes."""
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    genuine_screen = (
        "Sector : 4242\n"
        "Warps to Sector(s) :  12 - 45 - 99\n"
        "Command [TL=00:12:34]:[1000] (?=Help) ?"
    )
    session = FakeSession("bat.example.com", genuine_screen, auto_login_profile="alice")

    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())

    assert resp["ok"] is True
    world_id = protocol._current_world_id(session)
    sector = world_model.get_sector(world_id, 4242)
    assert sector is not None
    assert sector["warps"] == [12, 45, 99]


def test_genuine_sector_screen_with_full_paren_wrapped_warps_persists_all_six(isolated_world_store):
    """WO-FA1 end-to-end propagation proof: the REAL live-server warps
    shape (each destination paren-wrapped -- state_parser's old capture
    group couldn't even start matching it, see that module's `_WARPS_RE`
    comment) must make it, complete, all the way through `parse_state()`
    -> the `_write_world_model()` write-hook -> the persisted sector --
    never truncated to the first sector, never dropped entirely."""
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    real_shape_screen = (
        "Sector  : 2335\n"
        "Ports   : None\n"
        "Warps to Sector(s) :  (379) - (597) - (1302) - (3424) - (4069) - (4182)\n"
        "Command [TL=00:12:34]:[1000] (?=Help) ?"
    )
    session = FakeSession("bat.example.com", real_shape_screen, auto_login_profile="alice")

    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())

    assert resp["ok"] is True
    world_id = protocol._current_world_id(session)
    sector = world_model.get_sector(world_id, 2335)
    assert sector is not None
    assert sector["warps"] == [379, 597, 1302, 3424, 4069, 4182]


def test_chat_only_screen_with_no_genuine_status_line_persists_nothing(isolated_world_store):
    """Adapted from mack's probe_f2_carveout.py: a screen whose ONLY
    "sector" mention is embedded in narrative/chat text (no genuine
    status line at all) must not create ANY sector entry."""
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    forged_narrative_screen = (
        "Incoming transmission from Rival Trader:\n"
        '"Meet me in Sector: 8675 with 50000 credits, I have a great deal!"\n'
        "\n"
        "You have 50,000 credits.\n"
        "Command [TL=00:12:34]:[1000] (?=Help) ?"
    )
    session = FakeSession("bat.example.com", forged_narrative_screen, auto_login_profile="alice")

    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())

    assert resp["ok"] is True
    assert resp["state"].get("sector") is None
    world_id = protocol._current_world_id(session)
    assert world_model.get_sector(world_id, 8675) is None


# -- (d) auto_login_profile=None no-ops the write-hook cleanly -------------


def test_no_auto_login_profile_no_ops_the_write_hook_cleanly(isolated_world_store):
    session = FakeSession("bat.example.com", ALICE_SCREEN, auto_login_profile=None)

    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())

    assert resp["ok"] is True
    assert resp["state"]["sector"] == 123  # the response itself is unaffected
    assert protocol._current_world_id(session) is None
    assert not world_model.WORLD_DIR.exists()  # no world store ever created -- no crash, no file


# -- (e) a world_model write failure never fails the `tw do` response ------


def test_a_world_model_write_failure_never_fails_the_do_response(isolated_world_store, monkeypatch):
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    session = FakeSession("bat.example.com", ALICE_SCREEN, auto_login_profile="alice")

    def _boom(*a, **kw):
        raise RuntimeError("simulated world_model failure")

    monkeypatch.setattr(world_model, "write_from_state", _boom)
    monkeypatch.setattr(world_model, "bulk_upsert", _boom)

    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())

    assert resp["ok"] is True
    assert resp["state"]["sector"] == 123


# -- (e2) mack Finding 4: a swallowed failure is no longer 100% silent -----


class FakeLogger:
    """Minimal stand-in for `logging_util.TranscriptLogger` -- only the
    one method `_log_world_model_failure` actually calls."""

    def __init__(self):
        self.notes = []

    def log_note(self, note):
        self.notes.append(note)


def test_a_world_model_write_failure_is_logged_when_the_session_has_a_logger(
    isolated_world_store, monkeypatch
):
    """Adapted from mack's probe_silent_loss.py: the response must still
    never fail (unchanged guarantee), but a session WITH a transcript
    logger must now see a diagnostic note -- the failure is no longer
    100% invisible."""
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    session = FakeSession("bat.example.com", ALICE_SCREEN, auto_login_profile="alice")
    session.logger = FakeLogger()

    def _boom(*a, **kw):
        raise RuntimeError("simulated world_model failure")

    monkeypatch.setattr(world_model, "write_from_state", _boom)

    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())

    assert resp["ok"] is True
    assert resp["state"]["sector"] == 123
    assert session.logger.notes, "a world_model failure with a session logger present must be logged"
    assert any("write_from_state" in note for note in session.logger.notes)


def test_a_world_model_write_failure_with_no_session_logger_stays_a_clean_noop(
    isolated_world_store, monkeypatch
):
    """The bare fake-session test doubles that predate `.logger` (this
    whole file's own FakeSession, before we opted one in above) must
    keep working exactly as before -- getattr-guarded, no crash."""
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    session = FakeSession("bat.example.com", ALICE_SCREEN, auto_login_profile="alice")
    assert not hasattr(session, "logger")

    def _boom(*a, **kw):
        raise RuntimeError("simulated world_model failure")

    monkeypatch.setattr(world_model, "write_from_state", _boom)

    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())

    assert resp["ok"] is True
    assert resp["state"]["sector"] == 123


# -- (f) mack Finding 5: `tw state` feeds the world-model too --------------


def test_state_verb_persists_the_observed_sector(isolated_world_store):
    """`tw state` observes the current sector exactly like `do`/`read`/
    `screen` do, but never fed the world-model write-hook at all --
    inconsistent coverage for a verb explicitly meant for cheap
    polling."""
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    session = FakeSession("bat.example.com", ALICE_SCREEN, auto_login_profile="alice")

    resp = protocol.dispatch(session, "state", {}, FakeServer())

    assert resp["ok"] is True
    assert resp["state"]["sector"] == 123
    world_id = protocol._current_world_id(session)
    sector = world_model.get_sector(world_id, 123)
    assert sector is not None
    assert sector["sector_id"] == 123


def test_state_verb_also_bulk_ingests_a_genuine_cim_report(isolated_world_store):
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    session = FakeSession(
        "bat.example.com", _load_fixture("cim_port_report.txt"), auto_login_profile="alice"
    )

    resp = protocol.dispatch(session, "state", {}, FakeServer())

    assert resp["ok"] is True
    world_id = protocol._current_world_id(session)
    sectors = {s["sector_id"] for s in world_model.all_sectors(world_id)}
    assert {1234, 5001, 5678} <= sectors


# -- (g) WO-FA2b: docked commerce-report write path -------------------------
#
# WO-FA2b REVISE (mack CRITICAL, cipher F1): the original design anchored
# this write path to a cross-screen `session.last_genuine_sector`, set the
# last time a genuine sector-status screen was parsed -- but pyte
# (`twclient.terminal.TerminalScreen`) has NO scrollback, so a long
# warp-then-dock burst can scroll the "Sector : N" line off the settled
# grid before that ever happens, leaving the anchor stale or unset. The fix
# anchors instead to THIS SAME SCREEN's own trailing Command prompt
# (`state_parser.sector_from_command_prompt`) -- no cross-screen state at
# all, so a single dispatch of a genuine commerce report is now sufficient.


def test_docked_commerce_report_writes_port_to_its_own_command_prompt_sector(isolated_world_store):
    """The full FA2b chain, single dispatch: a docked commerce-report
    screen (the live-captured corpus, no "Sector : N" line of its own, but
    its OWN trailing Command [TL=...]:[4309] prompt) writes its parsed
    commodities to sector 4309 via the new write_port_only() path -- no
    prior sector-status screen needed to seed an anchor. Exact DoD values
    from the live capture."""
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    session = FakeSession(
        "bat.example.com", _load_fixture("port_commerce_report_gorram_primus.txt"), auto_login_profile="alice"
    )

    resp = protocol.dispatch(session, "do", {"input": "t"}, FakeServer())

    assert resp["ok"] is True
    world_id = protocol._current_world_id(session)
    sector = world_model.get_sector(world_id, 4309)
    assert sector is not None
    commodities = {c["name"]: c for c in sector["port"]["commodities"]}
    assert commodities["Fuel Ore"] == {"name": "Fuel Ore", "status": "buying", "amount": 2850, "pct": 100}
    assert commodities["Organics"] == {"name": "Organics", "status": "buying", "amount": 930, "pct": 100}
    assert commodities["Equipment"] == {"name": "Equipment", "status": "buying", "amount": 2720, "pct": 100}


def test_forged_narrative_commodity_mention_does_not_write_port_data(isolated_world_store):
    """A screen merely NAMING commodities in narrative text -- no genuine
    header/column-header co-occurring with a fully-shaped commodity row
    -- must write NOTHING, even though this screen's OWN command prompt
    does carry a sector to anchor to (RED test for the shape-not-keyword
    gate)."""
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    forged_screen = (
        "Rumor: they say the port at Gorram Primus deals heavily in Fuel\n"
        "Ore and Equipment. Organics prices have been trending up lately.\n"
        "Command [TL=00:00:00]:[4309] (?=Help)? :"
    )
    session = FakeSession("bat.example.com", forged_screen, auto_login_profile="alice")

    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())

    assert resp["ok"] is True
    world_id = protocol._current_world_id(session)
    assert world_model.get_sector(world_id, 4309) is None, (
        "a narrative-only commodity mention must never write port data, even with a real anchor present"
    )


def test_docked_commerce_report_with_no_command_prompt_sector_writes_nothing(isolated_world_store):
    """A genuine commerce report with no trailing Command [TL=...]:[NNNN]
    prompt on screen at all (an unusual dock flow, or a classic-shape TWGS
    server with no bracketed sector) -- there is no sector to attribute
    the reading to. The write is silently skipped -- never a crash, and no
    phantom sector entry is created out of thin air."""
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    no_prompt_screen = (
        "Commerce report for Gorram Primus: 07:08:00 AM Tue Jul 21, 2054\n"
        "\n"
        " Items     Status  Trading % of max OnBoard\n"
        " -----     ------  ------- -------- -------\n"
        "Fuel Ore   Buying    2850    100%       0\n"
    )
    session = FakeSession("bat.example.com", no_prompt_screen, auto_login_profile="alice")
    assert state_parser.sector_from_command_prompt(no_prompt_screen) is None  # sanity: no anchor on this screen

    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())

    assert resp["ok"] is True
    world_id = protocol._current_world_id(session)
    assert world_model.all_sectors(world_id) == []


def test_scroll_off_burst_writes_port_to_the_current_sector_not_a_stale_one(isolated_world_store):
    """CRITICAL repro (mack, WO-FA2b REVISE): pyte is `pyte.Screen` -- NO
    scrollback -- so a single continuous warp-into-597 + auto-dock +
    commerce-report burst longer than the 25-line viewport scrolls the
    "Sector : N" line off the settled grid entirely before settle-detection
    ever gets a checkpoint on it alone. The OLD cross-screen
    `session.last_genuine_sector` anchor design went stale in exactly this
    case; the fix (anchoring to THIS SCREEN's own trailing Command prompt)
    must still resolve the correct, CURRENT sector (597) even though
    "Sector : 597" itself is long gone from the rendered buffer. Fed
    through the REAL pyte-backed TerminalScreen (25-line viewport) so the
    scroll-off is genuine emulator behavior, not a hand-truncated string."""
    _write_profiles(
        isolated_world_store,
        {"alice": {"host": "bat.example.com", "port": 23, "game_letter": "A", "handle": "Alice"}},
    )
    burst_lines = [
        "",
        "<Re-Display>",
        "",
        "Sector  : 597 in uncharted space.",
        "Ports   : New Berlin, Class 2 (BSB)",
        "Warps to Sector(s) :  4309 - (200) - (300)",
        "",
        "Command [TL=00:00:00]:[597] (?=Help)? : P",
        "",
        "<A> Attack this Port",
        "<T> Trade at this Port",
        "<Q> Quit, nevermind",
        "",
        "Enter your choice [T] ? T",
        "<Port>",
        "",
        "Docking...",
        "One turn deducted, 1180 turns left.",
        "",
        "Commerce report for New Berlin: 07:09:00 AM Tue Jul 21, 2054",
        "",
        "-=-=-        Docking Log        -=-=-",
        "No current ship docking log on file.",
        "",
        " Items     Status  Trading % of max OnBoard",
        " -----     ------  ------- -------- -------",
        "Fuel Ore   Buying    2650    100%       0",
        "Organics   Buying    2970    100%       0",
        "Equipment  Buying    1220    100%       0",
        "",
        "You have 300 credits and 20 empty cargo holds.",
        "",
        "Command [TL=00:00:00]:[597] (?=Help)? : ",
    ]
    assert len(burst_lines) > 25, "the repro requires a burst longer than pyte's 25-line viewport"
    term = TerminalScreen(columns=80, lines=25)
    term.feed(("\r\n".join(burst_lines)).encode("cp437"))
    settled_text = "\n".join(term.render_cropped())

    assert "Sector" not in settled_text, "sanity: the burst must actually scroll the Sector line off"
    assert state_parser.sector_from_command_prompt(settled_text) == 597
    assert state_parser.is_genuine_port_report(settled_text) is True

    session = FakeSession("bat.example.com", settled_text, auto_login_profile="alice")
    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())

    assert resp["ok"] is True
    world_id = protocol._current_world_id(session)
    sector_597 = world_model.get_sector(world_id, 597)
    assert sector_597 is not None
    assert sector_597["port"]["commodities"][0]["name"] == "Fuel Ore"
    # 4309 only ever appears in the scrolled-off warps line -- never a
    # write target under the new same-screen anchor.
    assert world_model.get_sector(world_id, 4309) is None


# -- game_knowledge (TW-25) coexists, no writer wired this wave -------------


def test_game_knowledge_imports_and_coexists_with_no_write_hook_this_wave():
    """TW-25's game_knowledge store has no live write-hook this wave --
    its filler (the menu-crawler/introspector) is safety-gated and not
    built yet. This just proves the module imports cleanly alongside
    the now-wired world_model without colliding with anything
    protocol.py touches."""
    from twclient import game_knowledge

    assert callable(game_knowledge.load_knowledge)
    assert callable(game_knowledge.knowledge_path)
