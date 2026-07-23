"""Trainer Control Panel protocol verbs (TUI-POLISH-PLAN.md) -- list_skills
+ play_start/stop/pause/resume + the TX-channel (sent_input/cursor) +
play-progress-in-status, driven through the real wire protocol against
the isolated fake-session daemon (see conftest.py) -- no curses, no
network, never the live game or the REAL state/skills/ directory (this
project's genuine learned loops -- redirected to a tmp dir via
monkeypatch for every test here).
"""

import time

import pytest

from twclient import ledger, skills
from twclient.autopilot import AutopilotEngine, decision_to_trace
from twclient.chains import TradeHop
from twclient.control_lock import MODE_AI_PILOT, MODE_AUTO_LOOP, MODE_HUMAN
from twclient.credentials import Profile
from twclient.ship_upgrade_decision import LoopEconomics, ShipSpec

from .conftest import send_request


@pytest.fixture(autouse=True)
def _isolated_skills_dirs(tmp_path, monkeypatch):
    """Redirects skills.py's module-level SKILLS_DIR/DRAFTS_DIR to a temp
    directory for every test in this file -- protocol.py's
    _dispatch_list_skills() (and skills.load_skill()'s own default-path
    fallback) both read these as module globals, so monkeypatching them
    here is sufficient without touching skills.py itself."""
    skills_dir = tmp_path / "skills"
    drafts_dir = skills_dir / "_drafts"
    monkeypatch.setattr(skills, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(skills, "DRAFTS_DIR", drafts_dir)
    return skills_dir, drafts_dir


@pytest.fixture
def fake_ledger_entries(monkeypatch):
    """protocol._dispatch_list_skills() does a LOCAL `from .ledger import
    read_entries` at call time (this file's established lazy-import
    convention), which re-resolves `ledger.read_entries` fresh each call
    -- so patching the attribute on the `ledger` module itself (not on
    `protocol`) is what actually takes effect. Returns the list the
    caller populates; defaults to empty (no real state/ledger.jsonl is
    ever touched)."""
    entries = []
    monkeypatch.setattr(ledger, "read_entries", lambda path=None: entries)
    return entries


_STEP = {"input": "d", "wait_prompt": None, "expected_post_class": "main_command"}

# TW-03 integration note: skills.replay_skill/LoopPlayer now refuse a
# skill with no `start_anchor` up front (skills._check_start_anchor) --
# the hand-built skills below give a REAL start_anchor and put the fake
# session on a screen carrying that same sector, so the multi-cycle
# tests exercise the actual anchor-match path (never bypassed via
# force=True) -- these tests are about progress/pause/stop/lock
# mechanics, not anchor semantics, so a genuinely-matching anchor is the
# right fix rather than waiving the check.
_ANCHOR_SECTOR = 1234
_ANCHOR_SCREEN = f"Sector  : {_ANCHOR_SECTOR}\n\nCommand [TL=00:00:00]:[{_ANCHOR_SECTOR}] (?=Help)? : "


def _wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


# -- list_skills --------------------------------------------------------

def test_list_skills_empty_when_no_skills_saved(fake_daemon, fake_ledger_entries):
    resp = send_request(fake_daemon.sock_path, "list_skills")
    assert resp == {"ok": True, "loops": []}


def test_list_skills_reports_a_recorded_skill_with_demo_profit(fake_daemon, fake_ledger_entries):
    skills.save_skill("demo-loop", [_STEP, _STEP], source="recorded")
    fake_ledger_entries.extend(
        [
            {"capture": "demo-loop", "reward": {"d_credits": 100}},
            {"capture": "demo-loop", "reward": {"d_credits": 30}},
            {"capture": "other-loop", "reward": {"d_credits": 9999}},  # must NOT bleed in
        ]
    )
    resp = send_request(fake_daemon.sock_path, "list_skills")
    assert resp["ok"] is True
    assert len(resp["loops"]) == 1
    loop = resp["loops"][0]
    assert loop["name"] == "demo-loop"
    assert loop["source"] == "recorded"
    assert loop["steps"] == 2
    assert loop["draft"] is False
    assert loop["demo_profit"] == 130


def test_list_skills_reports_a_mined_skill_with_miner_stats(fake_daemon, fake_ledger_entries):
    skills.save_skill(
        "mined-loop", [_STEP], source="mined",
        mined_stats={"pre_class": "main_command", "support": 4, "cr_per_turn": 12.5, "cr_per_action": 3.0},
    )
    resp = send_request(fake_daemon.sock_path, "list_skills")
    loop = resp["loops"][0]
    assert loop["source"] == "mined"
    assert loop["profit_per_turn"] == 12.5
    assert loop["profit_per_action"] == 3.0
    assert loop["support"] == 4
    assert "demo_profit" not in loop  # mined skills report the miner's rate, not a demo-profit sum


def test_list_skills_includes_drafts_only_when_asked(fake_daemon, fake_ledger_entries):
    skills.save_skill("blessed", [_STEP], source="recorded")
    skills.save_skill("draft-one", [_STEP], source="mined", draft=True, mined_stats={"cr_per_turn": 1})

    resp = send_request(fake_daemon.sock_path, "list_skills")
    assert [l["name"] for l in resp["loops"]] == ["blessed"]

    resp = send_request(fake_daemon.sock_path, "list_skills", {"include_drafts": True})
    names = {l["name"] for l in resp["loops"]}
    assert names == {"blessed", "draft-one"}
    draft_entry = next(l for l in resp["loops"] if l["name"] == "draft-one")
    assert draft_entry["draft"] is True


def test_list_skills_carries_live_progress_for_the_currently_armed_loop(fake_daemon, fake_ledger_entries):
    skills.save_skill("running-loop", [_STEP, _STEP, _STEP], source="recorded", start_anchor=_ANCHOR_SECTOR)
    skill = skills.load_skill("running-loop")
    fake_daemon.session._screen = _ANCHOR_SCREEN  # TW-03: matches the skill's start_anchor above
    fake_daemon.session._real_time_scale = 0.1  # TW-02: replay_skill no longer calls session.wait_settle() directly
    fake_daemon.loop_player.start(skill, "running-loop", cycles=3)
    assert _wait_until(lambda: fake_daemon.loop_player.cycles_done >= 1)

    resp = send_request(fake_daemon.sock_path, "list_skills")
    loop = next(l for l in resp["loops"] if l["name"] == "running-loop")
    assert loop["last_run"]["running"] is True
    assert loop["last_run"]["cycles_total"] == 3

    fake_daemon.loop_player.stop()
    _wait_until(lambda: not fake_daemon.loop_player.running)


# -- play_start / play_stop / play_pause / play_resume -------------------

def test_play_start_arms_the_loop_and_status_reports_progress(fake_daemon, fake_ledger_entries):
    skills.save_skill("start-loop", [_STEP, _STEP], source="recorded", start_anchor=_ANCHOR_SECTOR)
    fake_daemon.session._screen = _ANCHOR_SCREEN  # TW-03: matches the skill's start_anchor above
    fake_daemon.session._real_time_scale = 0.1  # TW-02: replay_skill no longer calls session.wait_settle() directly

    resp = send_request(fake_daemon.sock_path, "play_start", {"name": "start-loop", "cycles": 2})
    assert resp["ok"] is True
    assert resp["name"] == "start-loop"
    assert resp["cycles_total"] == 2

    status = send_request(fake_daemon.sock_path, "status")
    assert status["mode"] == MODE_AUTO_LOOP
    assert status["play"]["running"] is True
    assert status["play"]["name"] == "start-loop"

    assert _wait_until(lambda: not fake_daemon.loop_player.running)
    status = send_request(fake_daemon.sock_path, "status")
    assert status["mode"] == MODE_AI_PILOT
    assert status["play"]["last_result"] == "cycles_complete"


def test_play_start_missing_name_is_rejected(fake_daemon, fake_ledger_entries):
    resp = send_request(fake_daemon.sock_path, "play_start", {"cycles": 1})
    assert resp == {"ok": False, "error": "missing_name"}


def test_play_start_unknown_skill_is_rejected(fake_daemon, fake_ledger_entries):
    resp = send_request(fake_daemon.sock_path, "play_start", {"name": "does-not-exist"})
    assert resp["ok"] is False
    assert "skill_not_found" in resp["error"]


def test_play_start_refuses_while_human_attached(fake_daemon, fake_ledger_entries):
    from twclient.interactive_app import AttachInputConn

    skills.save_skill("blocked-loop", [_STEP], source="recorded")
    conn = AttachInputConn(fake_daemon.sock_path)
    assert conn.connect() is True

    resp = send_request(fake_daemon.sock_path, "play_start", {"name": "blocked-loop"})
    assert resp["ok"] is False
    assert resp["error"] == "locked_by_human_attach"

    conn.close()


def test_play_stop_always_allowed_even_mid_run(fake_daemon, fake_ledger_entries):
    skills.save_skill("stop-loop", [_STEP], source="recorded", start_anchor=_ANCHOR_SECTOR)
    fake_daemon.session._screen = _ANCHOR_SCREEN  # TW-03: matches the skill's start_anchor above
    fake_daemon.session._real_time_scale = 0.1  # TW-02: replay_skill no longer calls session.wait_settle() directly
    send_request(fake_daemon.sock_path, "play_start", {"name": "stop-loop", "cycles": 50})
    assert _wait_until(lambda: fake_daemon.loop_player.cycles_done >= 1)

    resp = send_request(fake_daemon.sock_path, "play_stop")
    assert resp["ok"] is True
    assert _wait_until(lambda: not fake_daemon.loop_player.running)
    assert fake_daemon.loop_player.last_result == "stopped"

    # AI is free to drive again immediately.
    do_resp = send_request(fake_daemon.sock_path, "do", {"input": "d"})
    assert do_resp["ok"] is True


def test_play_stop_with_nothing_running_is_a_harmless_no_op(fake_daemon, fake_ledger_entries):
    resp = send_request(fake_daemon.sock_path, "play_stop")
    assert resp["ok"] is True
    assert resp["running"] is False


def test_play_pause_and_resume_round_trip(fake_daemon, fake_ledger_entries):
    skills.save_skill("pause-loop", [_STEP], source="recorded", start_anchor=_ANCHOR_SECTOR)
    fake_daemon.session._screen = _ANCHOR_SCREEN  # TW-03: matches the skill's start_anchor above
    fake_daemon.session._real_time_scale = 0.1  # TW-02: replay_skill no longer calls session.wait_settle() directly
    send_request(fake_daemon.sock_path, "play_start", {"name": "pause-loop", "cycles": 50})
    assert _wait_until(lambda: fake_daemon.loop_player.cycles_done >= 1)

    resp = send_request(fake_daemon.sock_path, "play_pause")
    assert resp["ok"] is True
    assert resp["paused"] is True
    time.sleep(0.15)
    stalled_at = fake_daemon.loop_player.cycles_done
    time.sleep(0.2)
    assert fake_daemon.loop_player.cycles_done == stalled_at

    resp = send_request(fake_daemon.sock_path, "play_resume")
    assert resp["ok"] is True
    assert resp["paused"] is False
    assert _wait_until(lambda: fake_daemon.loop_player.cycles_done > stalled_at)

    send_request(fake_daemon.sock_path, "play_stop")
    _wait_until(lambda: not fake_daemon.loop_player.running)


def test_play_pause_with_nothing_running_is_rejected(fake_daemon, fake_ledger_entries):
    resp = send_request(fake_daemon.sock_path, "play_pause")
    assert resp == {"ok": False, "error": "not_running"}


# -- control-lock now also gates play/replay/haggle ----------------------

def test_replay_and_play_verbs_are_rejected_during_an_active_attach(fake_daemon, fake_ledger_entries):
    from twclient.interactive_app import AttachInputConn

    conn = AttachInputConn(fake_daemon.sock_path)
    assert conn.connect() is True

    replay_resp = send_request(fake_daemon.sock_path, "replay", {"name": "whatever"})
    assert replay_resp == {"ok": False, "error": "controller_locked_by_human"}

    play_resp = send_request(fake_daemon.sock_path, "play", {"name": "whatever"})
    assert play_resp == {"ok": False, "error": "controller_locked_by_human"}

    haggle_resp = send_request(fake_daemon.sock_path, "haggle", {})
    assert haggle_resp == {"ok": False, "error": "controller_locked_by_human"}

    conn.close()


def test_do_is_rejected_with_a_distinct_error_while_auto_loop_is_running(fake_daemon, fake_ledger_entries):
    skills.save_skill("lock-check-loop", [_STEP], source="recorded", start_anchor=_ANCHOR_SECTOR)
    fake_daemon.session._screen = _ANCHOR_SCREEN  # TW-03: matches the skill's start_anchor above
    fake_daemon.session._real_time_scale = 0.1  # TW-02: replay_skill no longer calls session.wait_settle() directly
    send_request(fake_daemon.sock_path, "play_start", {"name": "lock-check-loop", "cycles": 50})
    assert _wait_until(lambda: fake_daemon.loop_player.cycles_done >= 1)

    resp = send_request(fake_daemon.sock_path, "do", {"input": "d"})
    assert resp == {"ok": False, "error": "controller_locked_by_auto_loop"}

    send_request(fake_daemon.sock_path, "play_stop")
    _wait_until(lambda: not fake_daemon.loop_player.running)


# -- TX channel: sent_input / cursor on every build_response() -----------

def test_do_response_carries_sent_input_and_cursor(fake_daemon, fake_ledger_entries):
    resp = send_request(fake_daemon.sock_path, "do", {"input": "158"})
    assert resp["sent_input"] == "158"
    assert resp["cursor"] == {"x": 0, "y": 0}


def test_do_response_redacts_sent_input_for_a_secret_send(fake_daemon, fake_ledger_entries):
    resp = send_request(fake_daemon.sock_path, "do", {"input": "hunter2", "secret": True})
    assert resp["sent_input"] == "<redacted>"


def test_screen_response_carries_the_most_recently_sent_input(fake_daemon, fake_ledger_entries):
    send_request(fake_daemon.sock_path, "do", {"input": "158"})
    resp = send_request(fake_daemon.sock_path, "screen")
    assert resp["sent_input"] == "158"


# -- autopilot_trace in status (WO-P2d, cross-seat trace transport) ------
#
# Transport-only: no AutopilotEngine exists on a real daemon yet (P1-d
# auto-start is deliberately deferred, see autopilot.py's own docstring) --
# these tests prove the null-safe "nothing wired" path a real daemon takes
# today, AND the populated path a caller gets once something (a future
# P1-d hook, or a test like this one) attaches an engine to
# server.autopilot_engine. Neither test starts a running/ticking engine --
# dry_run_tick() only, execution stays off.

def test_status_autopilot_trace_is_none_when_no_engine_is_wired(fake_daemon, fake_ledger_entries):
    resp = send_request(fake_daemon.sock_path, "status")
    assert resp["ok"] is True
    assert resp["autopilot_trace"] is None
    assert resp["autopilot"] == {
        "running": False,
        "ticks_done": 0,
        "last_error": None,
        "last_reason": None,
    }


def test_status_autopilot_field_matches_loop_snapshot_when_armed(fake_daemon, fake_ledger_entries, profiles_toml=None):
    """WO-STATUS-AUTOLOOP-FIELD: status.autopilot mirrors AutopilotLoop.snapshot keys."""
    from twclient.autopilot import AutopilotLoop

    class _Loop:
        running = True
        ticks_done = 7
        last_error = None
        last_decision = type("D", (), {"reason": "explore"})()

        def snapshot(self):
            return {
                "running": self.running,
                "ticks_done": self.ticks_done,
                "last_reason": self.last_decision.reason,
                "last_error": self.last_error,
                "last_trace": None,
            }

    fake_daemon.server.autopilot_loop = _Loop()
    resp = send_request(fake_daemon.sock_path, "status")
    assert resp["ok"] is True
    assert resp["autopilot"]["running"] is True
    assert resp["autopilot"]["ticks_done"] == 7
    assert resp["autopilot"]["last_reason"] == "explore"
    assert resp["autopilot"]["last_error"] is None


def test_status_autopilot_trace_surfaces_the_engines_most_recent_dry_run_tick(fake_daemon, fake_ledger_entries):
    """Attach a dry-ticked engine to the daemon's own session (mirroring
    the eventual P1-d auto-start hook's shape, minus the auto-start
    itself) and confirm `status` -- the real wire verb, not a direct
    function call -- surfaces the exact `decision_to_trace()` schema."""
    fake_daemon.session._screen = (
        "You have 60,000 credits.\n5,000 turns left.\n" + _ANCHOR_SCREEN
    )
    profile = Profile(name="t", host="h", port=1, game_letter="A", handle="X", autonomous=False)
    engine = AutopilotEngine(fake_daemon.session, profile, fake_daemon.control_lock)
    decision = engine.dry_run_tick(
        current_ship=ShipSpec(name="Prison Barge", cost=0, holds=20, turns_per_warp=6, fighters=10, shields=0),
        ship_catalog=(
            ShipSpec(name="Merchant Cruiser", cost=50_000, holds=75, turns_per_warp=3, fighters=100, shields=50),
        ),
        loop=LoopEconomics(margin_per_hold=100, turns_per_cycle=10, stock_capacity=100),
        hops=(
            TradeHop(frm=100, to=200, commodity="Fuel Ore", margin=50, turns=1),
            TradeHop(frm=200, to=100, commodity="Organics", margin=50, turns=1),
        ),
        stardock_route=(100, 150, 999),
        explore_next_sector=5,
    )
    fake_daemon.server.autopilot_engine = engine

    resp = send_request(fake_daemon.sock_path, "status")
    assert resp["ok"] is True
    assert resp["autopilot_trace"] == decision_to_trace(decision)
    # Sanity on the schema itself, not just self-consistency with the
    # direct decision_to_trace() call above -- a multi-candidate tick
    # really did score/win through the real dispatch path.
    # Preference: priority_engine defers ship upgrade on a short executable
    # chain (2-link < MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE) even when raw upgrade
    # EV is higher -- chosen is run_chain, not the EV winner.
    assert resp["autopilot_trace"]["chosen"] == "run_chain"
    by_kind = {c["kind"]: c for c in resp["autopilot_trace"]["candidates"]}
    assert set(by_kind) == {"run_chain", "upgrade", "explore"}
    assert by_kind["upgrade"]["ev_cr_per_turn"] == 550.0  # still scored, just not focus


# -- intervention in status (WO-AICLIENT-WS5-INTERVENTION) ---------------

def test_status_intervention_clear_when_autopilot_running(fake_daemon, fake_ledger_entries):
    """Healthy autopilot: needs_attention false; freshness unknowns may still appear."""
    from twclient.autopilot import DEFAULT_CREDITS_STALE_MS

    class _Loop:
        running = True
        ticks_done = 3
        last_error = None
        last_decision = type("D", (), {"reason": "explore"})()

        def snapshot(self):
            return {
                "running": self.running,
                "ticks_done": self.ticks_done,
                "last_reason": self.last_decision.reason,
                "last_error": self.last_error,
                "last_trace": None,
            }

    fake_daemon.server.autopilot_loop = _Loop()
    resp = send_request(fake_daemon.sock_path, "status")
    assert resp["ok"] is True
    iv = resp["intervention"]
    assert iv["needs_attention"] is False
    assert iv["mode"] == MODE_AI_PILOT
    assert iv["autopilot"] == resp["autopilot"]
    assert not any(r["code"] == "autopilot_halted" for r in iv["reasons"])
    assert not any(r["code"] == "human_attach_blocks_trainer" for r in iv["reasons"])
    assert DEFAULT_CREDITS_STALE_MS == 15_000


def test_status_intervention_needs_attention_on_autopilot_sticky_halt(fake_daemon, fake_ledger_entries):
    """Sticky halt: last_error set while loop not running raises needs_attention."""
    halt_msg = "settle_unconfirmed: halted rather than ticking past a send/settle desync"

    class _Loop:
        running = False
        ticks_done = 12
        last_error = halt_msg
        last_decision = None

        def snapshot(self):
            return {
                "running": self.running,
                "ticks_done": self.ticks_done,
                "last_reason": None,
                "last_error": self.last_error,
                "last_trace": None,
            }

    fake_daemon.server.autopilot_loop = _Loop()
    resp = send_request(fake_daemon.sock_path, "status")
    iv = resp["intervention"]
    assert iv["needs_attention"] is True
    halted = [r for r in iv["reasons"] if r["code"] == "autopilot_halted"]
    assert len(halted) == 1
    assert halted[0]["detail"] == halt_msg
    assert iv["autopilot"]["last_error"] == halt_msg
    assert iv["autopilot"]["running"] is False


def test_status_intervention_needs_attention_when_human_attached(fake_daemon, fake_ledger_entries):
    fake_daemon.control_lock.take_human()
    resp = send_request(fake_daemon.sock_path, "status")
    iv = resp["intervention"]
    assert iv["needs_attention"] is True
    assert iv["mode"] == MODE_HUMAN
    assert any(r["code"] == "human_attach_blocks_trainer" for r in iv["reasons"])
    fake_daemon.control_lock.release_human()


def test_status_intervention_credits_stale_is_informational_not_attention(fake_daemon, fake_ledger_entries):
    """Stale credits flag reason without needs_attention when autopilot healthy."""
    import time

    from twclient.autopilot import DEFAULT_CREDITS_STALE_MS

    now = time.monotonic()
    fake_daemon.session.credits_snapshot = lambda: (
        5000,
        now - (DEFAULT_CREDITS_STALE_MS + 1000) / 1000.0,
    )
    fake_daemon.session.fighters_snapshot = lambda: (10, now)

    resp = send_request(fake_daemon.sock_path, "status")
    iv = resp["intervention"]
    assert iv["needs_attention"] is False
    stale = [r for r in iv["reasons"] if r["code"] == "credits_stale"]
    assert len(stale) == 1
    assert stale[0]["detail"]["threshold_ms"] == DEFAULT_CREDITS_STALE_MS
    assert not any(r["code"] == "fighters_stale" for r in iv["reasons"])


def test_status_seeds_fighters_aboard_from_info_screen(fake_daemon, fake_ledger_entries):
    """WO-FIGHTERS-STATUS-FRESH: Info/`I` viewport stamps fighters; omits fighters_unknown."""
    fake_daemon.session._screen = (
        "Current Sector : 2594\n"
        "Turns left     : 1622\n"
        "Credits        : 300\n"
        "Fighters       : 600\n"
        "Command [TL=00:12:34]:[2594] (?=Help)? :"
    )
    # Clear sticky pre-seeds so observe_* must re-parse from the Info screen.
    fake_daemon.session.last_credits = None
    fake_daemon.session.last_credits_ts = None
    fake_daemon.session.last_fighters = None
    fake_daemon.session.last_fighters_ts = None

    resp = send_request(fake_daemon.sock_path, "status")
    assert resp["ok"] is True
    assert resp["fighters_aboard"] == 600
    assert resp["fighters_age_ms"] is not None
    assert resp["fighters_age_ms"] >= 0
    assert resp["credits"] == 300
    iv = resp["intervention"]
    assert not any(r["code"] == "fighters_unknown" for r in iv["reasons"])
    assert not any(r["code"] == "credits_unknown" for r in iv["reasons"])
    assert iv["needs_attention"] is False
