"""WO-ENSURE-STALE-SOCK-RECOVER — orphan ``twd.sock`` must not fool ensure.

When the socket file exists but no daemon is alive, the old spawn path treated
file presence as readiness: the wait loop exited immediately and settle
``read`` probed a corpse → ``spawn_failed: daemon socket present but never
answered``. Fix: unlink the orphan before spawn when ``daemon_alive`` is
False.
"""

from __future__ import annotations

import socket
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tw2002_aiclient.session import cli, env


def _plant_orphan_afunix(sock_path: Path) -> None:
    """Leave an AF_UNIX node on disk with no listener (hub repro shape)."""
    sock_path.parent.mkdir(parents=True, exist_ok=True)
    if sock_path.exists():
        sock_path.unlink()
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.bind(str(sock_path))
    finally:
        s.close()
    assert sock_path.exists()


@pytest.fixture
def short_run_dir():
    """macOS AF_UNIX path limit — keep under ~104 bytes (incl. twd.sock)."""
    with tempfile.TemporaryDirectory(prefix="tw-ss-", dir="/tmp") as d:
        run_dir = Path(d) / "run"
        run_dir.mkdir()
        yield run_dir


def test_ensure_raw_unlinks_orphan_sock_before_spawn_and_reaches_ensure(
    monkeypatch, short_run_dir
):
    """PIN: orphan sock + no pid → unlink before Popen; settle/ensure succeed.

    Never surfaces ``socket present but never answered`` solely from the
    orphan. Crux: sock gone at Popen time + top-level ok.
    """
    run_dir = short_run_dir
    sock_path = env.socket_path(run_dir)
    _plant_orphan_afunix(sock_path)

    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: False)
    monkeypatch.setattr(cli, "_resolve_profile_connection", lambda _p: ("127.0.0.1", 23))

    at_popen = {"sock_exists": None}

    def fake_popen(cmd, **kwargs):
        at_popen["sock_exists"] = sock_path.exists()
        # Fresh daemon bind: recreate the node so the wait-for-exists gate
        # can pass after a real unlink cleared the orphan.
        _plant_orphan_afunix(sock_path)
        return SimpleNamespace(pid=999999)

    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        if verb == "read":
            return {"ok": True, "class": "settled"}
        if verb == "ensure":
            return {"ok": True, "class": "main_command"}
        raise AssertionError(f"unexpected verb {verb!r}")

    monkeypatch.setattr(cli, "send_request", fake_send)

    resp = cli.ensure_raw("scratch", timeout=5.0, run_dir=run_dir)

    assert at_popen["sock_exists"] is False, (
        "orphan sock still present at Popen — ensure did not unlink before spawn"
    )
    assert resp == {"ok": True, "class": "main_command"}
    assert "never answered" not in str(resp.get("detail", ""))


def test_mutation_noop_unlink_orphan_yields_never_answered(monkeypatch, short_run_dir):
    """MUTATION: skip unlink → orphan wait-exit + settle corpse → never answered.

    No-op ``Path.unlink`` for ``twd.sock`` reproduces the Max/hub failure
    mode. Flip red if the product somehow succeeds without clearing the
    orphan.
    """
    run_dir = short_run_dir
    sock_path = env.socket_path(run_dir)
    _plant_orphan_afunix(sock_path)

    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: False)
    monkeypatch.setattr(cli, "_resolve_profile_connection", lambda _p: ("127.0.0.1", 23))

    real_unlink = Path.unlink

    def selective_unlink(self, *args, **kwargs):
        if self.name == env.SOCK_NAME:
            return None  # skip — mutation
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", selective_unlink)

    def fake_popen(cmd, **kwargs):
        # Orphan still present; do not create a live listener.
        return SimpleNamespace(pid=999999)

    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        return {"ok": False, "error": "empty_response"}

    monkeypatch.setattr(cli, "send_request", fake_send)

    resp = cli.ensure_raw("scratch", timeout=1.0, run_dir=run_dir)

    assert resp["ok"] is False
    assert resp["error"] == "spawn_failed"
    assert "never answered" in resp.get("detail", ""), (
        f"expected orphan never-answered detail, got {resp!r}"
    )
