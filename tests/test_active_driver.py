"""TW-04's exclusive active-driver slot -- protocol.py's
`_driving_dispatch()` layered on top of control_lock.py's
acquire_driver()/release_driver()/is_driving(), driven through the real
wire protocol against the isolated fake-session daemon (see conftest.py)
-- no curses, no network, never the live game.

Two incidents this guards against:
1. Two `tw do`/`send`/`replay`/`play`/`haggle` dispatches racing in from
   separate one-shot CLI connections both pass the ai_pilot mode check;
   without a second, exclusive layer, both could be mid-send at once.
2. An in-TUI `play_start` silently preempting a driving pilot instead of
   refusing (mode stays ai_pilot the whole time a plain `do` runs, so
   the pre-TW-04 enter_auto_loop() mode check alone never caught this).
"""

import re
import threading
import time

import pytest

from twclient import skills
from twclient.control_lock import MODE_AI_PILOT

from .conftest import send_request


@pytest.fixture(autouse=True)
def _isolated_skills_dirs(tmp_path, monkeypatch):
    """Redirects skills.py's module-level SKILLS_DIR/DRAFTS_DIR to a temp
    directory for every test in this file -- same convention as
    test_protocol_trainer_panel.py's own fixture of the same name -- so
    `play_start`'s load_skill() never touches this project's real
    state/skills/ directory."""
    skills_dir = tmp_path / "skills"
    drafts_dir = skills_dir / "_drafts"
    monkeypatch.setattr(skills, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(skills, "DRAFTS_DIR", drafts_dir)
    return skills_dir, drafts_dir


def _block_wait_settle(release_event, timeout=2.0):
    def _wait_settle(wait_prompt=None, timeout=8.0, debounce_ms=350):
        release_event.wait(timeout=timeout)
        return "idle", 0.0

    return _wait_settle


# -- incident 1: a second concurrent driver is refused, not interleaved --


def test_second_concurrent_do_dispatch_is_refused_with_controller_busy(fake_daemon):
    release = threading.Event()
    fake_daemon.session.wait_settle = _block_wait_settle(release)

    first_result = {}

    def first_call():
        first_result["resp"] = send_request(fake_daemon.sock_path, "do", {"input": "first"})

    t = threading.Thread(target=first_call)
    t.start()
    # Give the first dispatch time to acquire the driver slot and enter
    # its (now-blocked) wait_settle() -- a generous margin, not a race
    # against acquisition itself (acquire_driver() happens synchronously
    # before send()/wait_settle() even start).
    time.sleep(0.2)

    second_resp = send_request(fake_daemon.sock_path, "do", {"input": "second"})
    release.set()
    t.join(timeout=2.0)

    assert second_resp == {"ok": False, "error": "controller_busy"}
    assert first_result["resp"]["ok"] is True
    # The slot released cleanly once the first dispatch finished -- a
    # third caller isn't left refused forever.
    assert fake_daemon.control_lock.is_driving() is False


def test_ai_is_free_to_drive_again_immediately_after_the_first_dispatch_completes(fake_daemon):
    resp1 = send_request(fake_daemon.sock_path, "do", {"input": "d"})
    resp2 = send_request(fake_daemon.sock_path, "do", {"input": "d"})
    assert resp1["ok"] is True
    assert resp2["ok"] is True


# -- incident 2: play_start must refuse, not preempt, a driving pilot ----


def test_play_start_refuses_while_an_ai_pilot_dispatch_is_mid_flight(fake_daemon):
    skills.save_skill("preempt-loop", [{"input": "d", "wait_prompt": None, "expected_post_class": "main_command"}])

    release = threading.Event()
    fake_daemon.session.wait_settle = _block_wait_settle(release)

    do_result = {}

    def do_call():
        do_result["resp"] = send_request(fake_daemon.sock_path, "do", {"input": "d"})

    t = threading.Thread(target=do_call)
    t.start()
    time.sleep(0.2)

    play_resp = send_request(fake_daemon.sock_path, "play_start", {"name": "preempt-loop"})
    release.set()
    t.join(timeout=2.0)

    assert play_resp == {"ok": False, "error": "locked_by_active_driver"}
    assert do_result["resp"]["ok"] is True
    # The driving pilot was never preempted -- mode stayed ai_pilot
    # throughout, it was never silently flipped to auto_loop.
    assert fake_daemon.control_lock.mode == MODE_AI_PILOT


def test_play_start_succeeds_once_the_driving_dispatch_has_finished(fake_daemon):
    skills.save_skill("after-loop", [{"input": "d", "wait_prompt": None, "expected_post_class": "main_command"}])
    fake_daemon.session.wait_settle = lambda **kw: ("idle", 0.0)

    do_resp = send_request(fake_daemon.sock_path, "do", {"input": "d"})
    assert do_resp["ok"] is True

    play_resp = send_request(fake_daemon.sock_path, "play_start", {"name": "after-loop"})
    assert play_resp["ok"] is True

    send_request(fake_daemon.sock_path, "play_stop")


# -- crash-safety: the slot never leaks, mirroring take_human's own -----
# release-on-every-exit-path discipline ----------------------------------


def test_driver_slot_releases_even_when_the_dispatch_body_raises_an_uncaught_exception(fake_daemon):
    orig_send = fake_daemon.session.send

    def raising_send(text, enter=True, secret=False):
        raise RuntimeError("boom")

    fake_daemon.session.send = raising_send
    resp = send_request(fake_daemon.sock_path, "do", {"input": "d"})
    assert resp["ok"] is False
    assert "internal_error" in resp["error"]
    # The finally in protocol.py's `_driving_dispatch()` ran despite the
    # exception surfacing only at daemon.py's outer catch-all -- the
    # slot must not be left permanently held.
    assert fake_daemon.control_lock.is_driving() is False

    fake_daemon.session.send = orig_send
    follow_up = send_request(fake_daemon.sock_path, "do", {"input": "d"})
    assert follow_up["ok"] is True


def test_driver_slot_releases_when_do_dispatch_returns_a_bad_wait_prompt_regex_error(fake_daemon):
    def raising_wait_settle(wait_prompt=None, timeout=8.0, debounce_ms=350):
        raise re.error("bad regex")

    fake_daemon.session.wait_settle = raising_wait_settle
    resp = send_request(fake_daemon.sock_path, "do", {"input": "d", "wait_prompt": "("})
    assert resp["ok"] is False
    assert resp["error"].startswith("bad_wait_prompt_regex:")
    assert fake_daemon.control_lock.is_driving() is False

    fake_daemon.session.wait_settle = lambda **kw: ("idle", 0.0)
    follow_up = send_request(fake_daemon.sock_path, "do", {"input": "d"})
    assert follow_up["ok"] is True
