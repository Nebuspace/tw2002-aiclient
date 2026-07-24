"""Actor attribution at the send choke point (WO-P2-025).

Ledger persistence is out of scope while ledger.py is missing — prove via
Session.last_sender + VALID_SENDERS. Reborn live senders are {app, human}
only (never ai / trainer).
"""

import pytest

from tw2002_aiclient.session.connection import TelnetConnection
from tw2002_aiclient.session.control_lock import MODE_APP, MODE_HUMAN, ControlLock
from tw2002_aiclient.session.session import VALID_SENDERS, Session

from .conftest import FAKE_HOST, FAKE_PORT


def _noop_send_text(self, text, enter=True, secret=False):
    pass


def _noop_send_bytes(self, data, secret=False):
    pass


def test_valid_senders_are_app_and_human_only():
    assert VALID_SENDERS == ("app", "human")
    assert "ai" not in VALID_SENDERS
    assert "trainer" not in VALID_SENDERS


def test_send_defaults_to_app_and_records_last_sender(tmp_path, monkeypatch):
    monkeypatch.setattr(TelnetConnection, "send_text", _noop_send_text)
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))

    session.send("d")

    assert session.last_sender == "app"
    assert session.last_sent == "d"


def test_send_raw_defaults_to_human_and_records_last_sender(tmp_path, monkeypatch):
    monkeypatch.setattr(TelnetConnection, "send_bytes", _noop_send_bytes)
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))

    session.send_raw(b"H")

    assert session.last_sender == "human"


def test_send_rejects_legacy_ai_sender(tmp_path, monkeypatch):
    monkeypatch.setattr(TelnetConnection, "send_text", _noop_send_text)
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    with pytest.raises(ValueError, match="sender must be one of"):
        session.send("d", sender="ai")


def test_send_rejects_legacy_trainer_sender(tmp_path, monkeypatch):
    monkeypatch.setattr(TelnetConnection, "send_text", _noop_send_text)
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    with pytest.raises(ValueError, match="sender must be one of"):
        session.send("d", sender="trainer")


def test_send_raw_rejects_legacy_ai_sender(tmp_path, monkeypatch):
    monkeypatch.setattr(TelnetConnection, "send_bytes", _noop_send_bytes)
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    with pytest.raises(ValueError, match="sender must be one of"):
        session.send_raw(b"H", sender="ai")


def test_explicit_human_sender_on_send_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(TelnetConnection, "send_text", _noop_send_text)
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))

    session.send("M", sender="human")

    assert session.last_sender == "human"


def test_control_lock_default_mode_is_app_not_ai_pilot():
    lock = ControlLock()
    assert lock.mode == MODE_APP
    assert lock.mode != "ai_pilot"


def test_take_human_flips_mode_to_human_for_attribution_consumers():
    """Until ledger/_current_actor land, mode + last_sender are the dual
    attribution surfaces protocol/daemon will read."""
    lock = ControlLock()
    lock.take_human()
    assert lock.mode == MODE_HUMAN
