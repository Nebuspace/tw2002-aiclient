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
from twclient.control_lock import MODE_AI_PILOT, MODE_AUTO_LOOP

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
    skills.save_skill("running-loop", [_STEP, _STEP, _STEP], source="recorded")
    skill = skills.load_skill("running-loop")
    fake_daemon.session.wait_settle = lambda **kw: (time.sleep(0.05), ("idle", 0.05))[1]
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
    skills.save_skill("start-loop", [_STEP, _STEP], source="recorded")
    fake_daemon.session.wait_settle = lambda **kw: (time.sleep(0.05), ("idle", 0.05))[1]

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
    skills.save_skill("stop-loop", [_STEP], source="recorded")
    fake_daemon.session.wait_settle = lambda **kw: (time.sleep(0.05), ("idle", 0.05))[1]
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
    skills.save_skill("pause-loop", [_STEP], source="recorded")
    fake_daemon.session.wait_settle = lambda **kw: (time.sleep(0.05), ("idle", 0.05))[1]
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
    skills.save_skill("lock-check-loop", [_STEP], source="recorded")
    fake_daemon.session.wait_settle = lambda **kw: (time.sleep(0.05), ("idle", 0.05))[1]
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
