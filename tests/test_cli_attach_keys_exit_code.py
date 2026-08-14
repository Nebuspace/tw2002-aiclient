"""WO-AUDIT-CLI-KEYS-IGNORE-RETURN — ``tw attach --keys`` must not report
success when the keystroke send actually failed.

``cmd_attach``'s scripted ``--keys`` branch (cli.py) discarded
``AttachInputConn.send_key()``'s bool return and always ``return 0``ed -- a
scripted caller had no way to detect a failed send. This file proves the
honest exit code both ways, faking ``AttachInputConn`` (network-free, no
``fake_daemon`` socket needed).
"""

from __future__ import annotations

from argparse import Namespace

from tests.attach_helpers import FakeAttachConn as _FakeAttachConn
from tw2002_aiclient.session import attach_client, cli, env


def _make_args(run_dir, keys):
    return Namespace(run_dir=str(run_dir), keys=keys)


def test_cmd_attach_keys_failed_send_is_non_zero_and_reported(monkeypatch, tmp_path, capsys):
    env.socket_path(tmp_path).touch()
    fake = _FakeAttachConn(None, send_ok=False)
    monkeypatch.setattr(attach_client, "AttachInputConn", lambda sock_path: fake)

    rc = cli.cmd_attach(_make_args(tmp_path, "hi"))

    assert rc == 1
    out = capsys.readouterr().out
    assert "ERROR" in out
    assert fake.sent == [b"hi"]
    assert fake.closed, "conn.close() must still run (finally:) on the failure path"


def test_cmd_attach_keys_successful_send_still_returns_zero(monkeypatch, tmp_path, capsys):
    env.socket_path(tmp_path).touch()
    fake = _FakeAttachConn(None, send_ok=True)
    monkeypatch.setattr(attach_client, "AttachInputConn", lambda sock_path: fake)

    rc = cli.cmd_attach(_make_args(tmp_path, "hi"))

    assert rc == 0
    out = capsys.readouterr().out
    assert "ERROR" not in out
    assert fake.sent == [b"hi"]
    assert fake.closed


def test_cmd_attach_keys_empty_string_sends_nothing_and_returns_zero(monkeypatch, tmp_path, capsys):
    """Pre-existing behavior, preserved deliberately: ``--keys ""`` decodes
    to empty bytes, so `cmd_attach` never calls `send_key` at all and exits
    0 -- there was nothing to fail. Not in scope to change."""
    env.socket_path(tmp_path).touch()
    fake = _FakeAttachConn(None, send_ok=False)
    monkeypatch.setattr(attach_client, "AttachInputConn", lambda sock_path: fake)

    rc = cli.cmd_attach(_make_args(tmp_path, ""))

    assert rc == 0
    assert fake.sent == []
    assert fake.closed
