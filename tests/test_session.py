"""Session unit tests — no network.

Constructing a bare Session never touches the network (only .start()/
.reconnect() do). Most fence-wait tests use a duck-typed control_lock stub
(``send_raw`` only requires ``is_driver_fenced()``, proven generically);
WO-CONTROL-LOCK-AUTOLOOP-FENCE adds one against the REAL
``tw2002_aiclient.session.control_lock.ControlLock`` collaborator, to prove
the two modules' preemption/wind-down handshake end to end rather than
only each side's half of the duck-typed contract.
"""

import threading
import time

import pytest

from tw2002_aiclient.session import session as session_module
from tw2002_aiclient.session.connection import TelnetConnection
from tw2002_aiclient.session.control_lock import ControlLock
from tw2002_aiclient.session.session import VALID_SENDERS, Session

from .conftest import FAKE_HOST, FAKE_PORT


def _noop_connect(self, timeout=10):
    self.connected = True


class _FenceStub:
    """Minimal duck-type for Session.send_raw(control_lock=...)."""

    def __init__(self, fenced=False):
        self._fenced = fenced

    def is_driver_fenced(self):
        return self._fenced

    def clear(self):
        self._fenced = False


def test_game_select_answered_defaults_false(tmp_path):
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    assert session.game_select_answered is False
    assert session.game_select_letter_sent is False


def test_session_id_matches_logger(tmp_path):
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    assert session.session_id == session.logger.session_id


def test_current_cursor_line_ignores_stale_content_painted_below_it(tmp_path):
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    active = "How many holds of Organics do you want to buy [50]?"
    stale = "Command [TL=00:00:00]:[7132] (?=Help)? :"
    session.terminal.feed(
        (
            f"\x1b[5;1H{active}"
            f"\x1b[10;1H{stale}"
            f"\x1b[5;{len(active) + 1}H"
        ).encode("ascii")
    )

    assert session.current_prompt_line() == stale
    assert session.current_cursor_line() == active


def test_reconnect_resets_game_select_answered_even_if_it_was_set(tmp_path, monkeypatch):
    monkeypatch.setattr(TelnetConnection, "connect", _noop_connect)
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    session.game_select_answered = True
    session.game_select_letter_sent = True

    session.reconnect()

    assert session.game_select_answered is False
    assert session.game_select_letter_sent is False


def test_send_rejects_invalid_sender(tmp_path, monkeypatch):
    monkeypatch.setattr(TelnetConnection, "send_text", lambda *a, **k: None)
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    with pytest.raises(ValueError, match="sender must be one of"):
        session.send("A", sender="ai")


def test_send_records_last_sent_and_sender(tmp_path, monkeypatch):
    monkeypatch.setattr(TelnetConnection, "send_text", lambda *a, **k: None)
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    session.send("M", sender="app")
    assert session.last_sent == "M"
    assert session.last_sender == "app"
    assert session.last_sent_secret is False


def test_send_secret_redacts_last_sent(tmp_path, monkeypatch):
    monkeypatch.setattr(TelnetConnection, "send_text", lambda *a, **k: None)
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    session.send("hunter2", secret=True, sender="app")
    assert session.last_sent == "<redacted>"
    assert session.last_sent_secret is True


def test_send_raw_sends_immediately_when_control_lock_is_none(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(TelnetConnection, "send_bytes", lambda self, data, secret=False: sent.append(data))
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))

    session.send_raw(b"H")

    assert sent == [b"H"]
    assert session.last_sender == "human"


def test_send_raw_sends_immediately_when_the_lock_is_not_fenced(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(TelnetConnection, "send_bytes", lambda self, data, secret=False: sent.append(data))
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))

    session.send_raw(b"H", control_lock=_FenceStub(fenced=False))

    assert sent == [b"H"]


def test_send_raw_waits_for_the_fence_to_clear_before_sending(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(TelnetConnection, "send_bytes", lambda self, data, secret=False: sent.append(data))
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    lock = _FenceStub(fenced=True)

    result = {}

    def send_call():
        session.send_raw(b"H", control_lock=lock)
        result["done"] = True

    t = threading.Thread(target=send_call)
    t.start()
    time.sleep(0.2)

    assert "done" not in result
    assert sent == []

    lock.clear()
    t.join(timeout=2.0)

    assert result.get("done") is True
    assert sent == [b"H"]


def test_send_raw_fence_wait_is_bounded_and_sends_anyway_once_the_bound_expires(tmp_path, monkeypatch):
    monkeypatch.setattr(session_module, "_FENCE_WAIT_TIMEOUT_S", 0.1)
    monkeypatch.setattr(session_module, "_FENCE_WAIT_POLL_S", 0.02)
    sent = []
    monkeypatch.setattr(TelnetConnection, "send_bytes", lambda self, data, secret=False: sent.append(data))
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    lock = _FenceStub(fenced=True)  # never cleared

    session.send_raw(b"H", control_lock=lock)

    assert sent == [b"H"]


def test_send_raw_waits_for_a_preempted_auto_loop_hold_to_actually_release(tmp_path, monkeypatch):
    """WO-CONTROL-LOCK-AUTOLOOP-FENCE, proved against the REAL collaborator
    (not the duck-typed stub the tests above use). `daemon.py`'s human-
    attach keystroke forwarder (`_handle_attach`) is `send_raw`'s only
    production caller with `sender="human"`, and its whole reason to gate
    on `is_driver_fenced()` is to give an in-flight App step a beat to
    actually finish before a human byte can interleave with it on the
    wire.

    Before this WO, `ControlLock.take_human()` preempting a running
    auto_loop hold cleared it silently -- `is_driver_fenced()` never rose,
    so this exact sequence would have sent the byte immediately, racing
    whatever step the loop was mid-send-then-settle on. Here it must wait,
    and must resume the instant the run's OWN release path
    (`leave_auto_loop()`, never `release_driver()` -- that clears the
    OTHER fence) actually fires, not merely once the bound expires (that
    other case is `test_send_raw_fence_wait_is_bounded_and_sends_anyway_
    once_the_bound_expires` above)."""
    sent = []
    monkeypatch.setattr(TelnetConnection, "send_bytes", lambda self, data, secret=False: sent.append(data))
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    lock = ControlLock()
    token = lock.enter_auto_loop()
    lock.take_human()  # preempts the hold -- fences it, does not merely revoke it
    assert lock.is_driver_fenced() is True
    assert lock.mode == "human"  # the human already has the keyboard, unconditionally

    result = {}

    def send_call():
        session.send_raw(b"H", control_lock=lock)
        result["done"] = True

    t = threading.Thread(target=send_call)
    t.start()
    time.sleep(0.2)

    assert "done" not in result
    assert sent == []

    lock.leave_auto_loop(token)
    t.join(timeout=2.0)

    assert result.get("done") is True
    assert sent == [b"H"]


def test_send_raw_passes_secret_true_to_send_bytes_at_a_password_prompt(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        TelnetConnection, "send_bytes", lambda self, data, secret=False: calls.append((data, secret))
    )
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    session.terminal.feed(b"Password:")

    session.send_raw(b"H")

    assert calls == [(b"H", True)]
    assert session.last_sent_secret is True


def test_send_raw_redacts_last_sent_at_a_password_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(TelnetConnection, "send_bytes", lambda self, data, secret=False: None)
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    session.terminal.feed(b"Password:")

    session.send_raw(b"H")

    assert session.last_sent == "<redacted>"


def test_send_raw_passes_secret_false_at_an_ordinary_prompt(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        TelnetConnection, "send_bytes", lambda self, data, secret=False: calls.append((data, secret))
    )
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    session.terminal.feed(b"Command [TL=00:00:00]:[1] (?=Help)? :")

    session.send_raw(b"H")

    assert calls == [(b"H", False)]
    assert session.last_sent_secret is False
    assert session.last_sent == "H"


def test_send_raw_uses_the_current_screen_at_send_time_not_a_stale_pre_wait_snapshot(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        TelnetConnection, "send_bytes", lambda self, data, secret=False: calls.append((data, secret))
    )
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    became_secret = threading.Event()
    monkeypatch.setattr(
        session,
        "render",
        lambda: ["Enter PIN:"] if became_secret.is_set() else ["Command [TL=00:00:00]:[1] (?=Help)? :"],
    )
    lock = _FenceStub(fenced=True)

    result = {}

    def send_call():
        session.send_raw(b"1", control_lock=lock)
        result["done"] = True

    t = threading.Thread(target=send_call)
    t.start()
    time.sleep(0.15)
    assert "done" not in result

    became_secret.set()
    lock.clear()
    t.join(timeout=2.0)

    assert result.get("done") is True
    assert calls == [(b"1", True)]
    assert session.last_sent_secret is True


def test_valid_senders_are_app_human_dev_only():
    assert VALID_SENDERS == ("app", "human", "dev")


def test_record_history_caps_at_history_cap(tmp_path):
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    session._history_cap = 3
    for i in range(5):
        session.record_history("do", {"i": i}, ">", "unknown", "idle")
    assert len(session.history) == 3
    assert session.history[0]["args"]["i"] == 2
