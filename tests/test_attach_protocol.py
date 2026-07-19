"""End-to-end (real unix socket, fake session) proof of the interactive
`tw attach` control-lock handoff: daemon.py's CommandHandler._handle_attach
+ protocol.py's do/send guard + the "set_mode" verb, driven through the
actual wire protocol via twclient.interactive_app.AttachInputConn
(production code, unmodified) -- no curses, no pty (that's
test_interactive_app.py's job), no network, never the live game.
"""

import time

from twclient.control_lock import MODE_HUMAN
from twclient.interactive_app import AttachInputConn

from .conftest import send_request


def test_do_succeeds_when_nobody_is_attached(fake_daemon):
    resp = send_request(fake_daemon.sock_path, "do", {"input": "d"})
    assert resp["ok"] is True


def test_status_reports_mode_ai_pilot_by_default(fake_daemon):
    resp = send_request(fake_daemon.sock_path, "status")
    assert resp["ok"] is True
    assert resp["mode"] == "ai_pilot"


def test_attach_takes_the_lock_and_rejects_ai_do_and_send(fake_daemon):
    conn = AttachInputConn(fake_daemon.sock_path)
    assert conn.connect() is True

    do_resp = send_request(fake_daemon.sock_path, "do", {"input": "d"})
    assert do_resp["ok"] is False
    assert do_resp["error"] == "controller_locked_by_human"

    send_resp = send_request(fake_daemon.sock_path, "send", {"input": "d"})
    assert send_resp["ok"] is False
    assert send_resp["error"] == "controller_locked_by_human"

    status = send_request(fake_daemon.sock_path, "status")
    assert status["mode"] == "human"

    conn.close()


def test_attach_forwards_raw_keystrokes_to_the_session(fake_daemon):
    conn = AttachInputConn(fake_daemon.sock_path)
    assert conn.connect() is True

    assert conn.send_key(b"d") is True
    assert conn.send_key(b"\r\n") is True

    assert fake_daemon.session.raw_sent == [b"d", b"\r\n"]
    conn.close()


def test_detach_releases_the_lock_so_ai_can_send_again(fake_daemon):
    conn = AttachInputConn(fake_daemon.sock_path)
    assert conn.connect() is True
    conn.close()

    # The daemon's handler thread notices the closed socket asynchronously
    # -- give its `finally: lock.release_human()` a beat to run.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and fake_daemon.control_lock.mode == MODE_HUMAN:
        time.sleep(0.02)

    resp = send_request(fake_daemon.sock_path, "do", {"input": "d"})
    assert resp["ok"] is True


def test_second_attach_is_rejected_while_one_is_active(fake_daemon):
    first = AttachInputConn(fake_daemon.sock_path)
    assert first.connect() is True

    second = AttachInputConn(fake_daemon.sock_path)
    assert second.connect() is False
    assert second.error == "already_attached"

    first.close()


def test_attach_succeeds_again_after_first_session_detaches(fake_daemon):
    first = AttachInputConn(fake_daemon.sock_path)
    assert first.connect() is True
    first.close()

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and fake_daemon.control_lock.mode == MODE_HUMAN:
        time.sleep(0.02)

    second = AttachInputConn(fake_daemon.sock_path)
    assert second.connect() is True
    second.close()


# -- set_mode verb -- the future control panel's seam --------------------

def test_set_mode_verb_switches_mode_and_pauses_ai_sends(fake_daemon):
    resp = send_request(fake_daemon.sock_path, "set_mode", {"mode": "spectate"})
    assert resp == {"ok": True, "mode": "spectate"}

    do_resp = send_request(fake_daemon.sock_path, "do", {"input": "d"})
    assert do_resp["ok"] is False
    # Same guard as the human-attach case, but a distinct error string --
    # a caller shouldn't be told "human" when the real blocker is the
    # panel's own spectate/pause mode.
    assert do_resp["error"] == "controller_locked:spectate"

    status = send_request(fake_daemon.sock_path, "status")
    assert status["mode"] == "spectate"

    back = send_request(fake_daemon.sock_path, "set_mode", {"mode": "ai_pilot"})
    assert back == {"ok": True, "mode": "ai_pilot"}
    assert send_request(fake_daemon.sock_path, "do", {"input": "d"})["ok"] is True


def test_set_mode_verb_rejects_unknown_and_human_and_auto_loop(fake_daemon):
    for bad_mode in ("warp_speed", "human", "auto_loop"):
        resp = send_request(fake_daemon.sock_path, "set_mode", {"mode": bad_mode})
        assert resp["ok"] is False
        assert resp["error"].startswith("invalid_mode:")


def test_set_mode_verb_cannot_clobber_an_active_attach(fake_daemon):
    conn = AttachInputConn(fake_daemon.sock_path)
    assert conn.connect() is True

    resp = send_request(fake_daemon.sock_path, "set_mode", {"mode": "spectate"})
    assert resp["ok"] is False
    assert resp["error"] == "locked_by_human_attach"
    assert send_request(fake_daemon.sock_path, "status")["mode"] == "human"

    conn.close()
