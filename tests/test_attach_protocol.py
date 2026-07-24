"""Attach control-lock handoff over a real unix socket + FakeAttachSession.

Uses production ``AttachInputConn`` + daemon ``_handle_attach`` — no curses.
``set_mode`` verb tests deferred (unknown_verb until a later WO).
"""

from __future__ import annotations

import time

from tw2002_aiclient.session.attach_client import AttachInputConn
from tw2002_aiclient.session.control_lock import MODE_APP, MODE_HUMAN

from .conftest import send_request


def test_do_succeeds_when_nobody_is_attached(fake_daemon):
    resp = send_request(fake_daemon.sock_path, "do", {"input": "d"})
    assert resp["ok"] is True


def test_status_reports_mode_app_by_default(fake_daemon):
    resp = send_request(fake_daemon.sock_path, "status")
    assert resp["ok"] is True
    assert resp["mode"] == MODE_APP


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
    assert status["mode"] == MODE_HUMAN

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
