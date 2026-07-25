"""MT-09 / SESSION-F1-MICRO-SETTLE-NUDGE — post-spawn ``read`` discard is benign.

``ensure_raw`` nudges a freshly spawned daemon with ``send_request("read")``
and discards the response before the real ``ensure`` round-trip. A nudge
failure must not poison the ensure result or invent a false spawn failure.
"""

from __future__ import annotations

from tw2002_aiclient.session import cli


def test_ensure_raw_settle_nudge_failure_does_not_flip_ensure_result(
    tmp_path, monkeypatch
):
    """Pin: discarded post-spawn ``read`` failure leaves ensure decisive."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    sock = run_dir / "twd.sock"
    # Present before spawn wait so the loop exits without sleeping on a
    # real daemon — we only care about the discarded nudge + ensure path.
    sock.write_text("")
    (tmp_path / "logs").mkdir()

    calls = []

    def fake_send_request(verb, args_payload, *, timeout=15.0, run_dir=None):
        calls.append(verb)
        if verb == "read":
            return {"ok": False, "error": "connect_failed:nudge"}
        if verb == "ensure":
            return {"ok": True, "classification": "main_command"}
        return {"ok": False, "error": f"unexpected:{verb}"}

    monkeypatch.setattr(cli, "_resolve_profile_connection", lambda name: ("127.0.0.1", 23))
    monkeypatch.setattr(cli, "daemon_alive", lambda run_dir=None: False)
    monkeypatch.setattr(cli, "send_request", fake_send_request)
    monkeypatch.setattr(cli.env, "socket_path", lambda run_dir=None: sock)
    monkeypatch.setattr(cli.env, "resolve_run_dir", lambda: run_dir)
    monkeypatch.setattr(cli.env, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(cli.env, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli.env, "RUN_DIR_VAR", "TW_RUN_DIR")

    class _FakePopen:
        def __init__(self, *a, **k):
            pass

    monkeypatch.setattr(cli.subprocess, "Popen", _FakePopen)

    resp = cli.ensure_raw("demo", timeout=5.0, run_dir=run_dir)
    assert resp == {"ok": True, "classification": "main_command"}
    assert calls == ["read", "ensure"]
