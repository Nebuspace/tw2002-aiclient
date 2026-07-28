"""WO-RUN-DIR-AFUNIX-REFUSE — over-long TW_RUN_DIR → named refuse, not traceback.

macOS AF_UNIX addresses are capped (~104 bytes). An operator who points
``TW_RUN_DIR`` at a deep pytest-style path used to die inside
``ThreadingUnixServer.server_bind`` with a raw ``OSError`` traceback.
These pins force that case and assert the named one-line refuse.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from tw2002_aiclient.session import daemon, env
from tw2002_aiclient.session.daemon import (
    AfunixSocketPathTooLong,
    CommandHandler,
    ThreadingUnixServer,
)


def _overlong_sock_path(base: Path) -> Path:
    """Build a ``…/twd.sock`` path that cannot bind on this platform.

    Starts from a short ``mkdtemp`` base (same trick as
    ``test_daemon_socket_mode``) and lengthens until bind refuses — so the
    pin does not hardcode a platform-specific byte ceiling.
    """
    for n in range(40, 200):
        deep = base / ("d" * n)
        deep.mkdir(parents=True, exist_ok=True)
        sock = deep / env.SOCK_NAME
        try:
            daemon._preflight_afunix_socket(sock)
        except AfunixSocketPathTooLong:
            return sock
    raise AssertionError("could not provoke AF_UNIX path-too-long on this platform")


@pytest.fixture
def short_base():
    d = Path(tempfile.mkdtemp(prefix="twd-afunix-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_threading_unix_server_raises_named_refuse_on_overlong_path(short_base):
    sock = _overlong_sock_path(short_base)
    with pytest.raises(AfunixSocketPathTooLong) as caught:
        ThreadingUnixServer(str(sock), CommandHandler)
    msg = str(caught.value)
    assert "path too long" in msg.lower()
    assert str(sock) in msg
    assert env.RUN_DIR_VAR in msg
    assert "bytes" in msg


def test_main_overlong_run_dir_is_a_line_not_a_traceback(short_base, monkeypatch, capsys):
    """Drive ``daemon.main`` far enough to hit the preflight refuse.

    Host/port are set so resolution succeeds; Session/telnet is never
    reached because the AF_UNIX preflight exits first.
    """
    # Use a run-dir whose ``twd.sock`` child is known-unbindable.
    sock = _overlong_sock_path(short_base)
    run_dir = sock.parent
    monkeypatch.setenv(env.RUN_DIR_VAR, str(run_dir))
    monkeypatch.setenv(env.HOST_VAR, "127.0.0.1")
    monkeypatch.setenv(env.PORT_VAR, "1")
    monkeypatch.setattr(env, "DOTENV_PATH", short_base / "no-such.env")

    with pytest.raises(SystemExit) as caught:
        daemon.main([])
    err = capsys.readouterr().err

    assert caught.value.code == 1
    assert "Traceback" not in err
    assert err.startswith("twd: ")
    assert "path too long" in err.lower()
    assert env.RUN_DIR_VAR in err
    assert "bytes" in err
    assert str(run_dir) in err or str(sock) in err
