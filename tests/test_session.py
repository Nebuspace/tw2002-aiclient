"""Session (twclient/session.py) unit tests -- no network. Constructing
a bare `Session` never touches the network (only `.start()`/
`.reconnect()` do, via `TelnetConnection.connect()`), so `test_reconnect_
resets_game_select_answered` monkeypatches that one method to a no-op
rather than pulling in a real socket -- same discipline as this
project's other fakes that stay network-free."""

import threading
import time

from twclient import session as session_module
from twclient.connection import TelnetConnection
from twclient.control_lock import ControlLock
from twclient.session import Session

from .conftest import FAKE_HOST, FAKE_PORT


def _noop_connect(self, timeout=10):
    self.connected = True


def test_game_select_answered_defaults_false(tmp_path):
    session = Session(FAKE_HOST, FAKE_PORT, None, tmp_path)
    assert session.game_select_answered is False


def test_reconnect_resets_game_select_answered_even_if_it_was_set(tmp_path, monkeypatch):
    """Safety fix: the per-CONNECTION game-select allowance must come
    back on a fresh connection -- guardian's D9 reconnect-replay (and a
    fresh cold-start login) still need to answer a genuine game-select
    prompt normally after a drop, even though the PRIOR connection had
    already answered its own."""
    monkeypatch.setattr(TelnetConnection, "connect", _noop_connect)
    session = Session(FAKE_HOST, FAKE_PORT, None, tmp_path)
    session.game_select_answered = True  # models the prior connection's real answer

    session.reconnect()

    assert session.game_select_answered is False


# -- WO-CLEANPREEMPT: send_raw()'s bounded fence-wait -----------------------
#
# Direct unit tests against the REAL Session.send_raw() (not the
# FakeAttachSession stand-in tests/conftest.py mirrors it with, and not
# the full-daemon e2e proof in test_tw04_toctou.py) -- monkeypatches
# TelnetConnection.send_bytes to a recording stub (bare `Session(...)`
# construction never touches the network, same discipline as this
# module's other tests) so the wait mechanics themselves are proven
# against production code, isolated from any daemon/socket wiring.


def test_send_raw_sends_immediately_when_control_lock_is_none(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(TelnetConnection, "send_bytes", lambda self, data, secret=False: sent.append(data))
    session = Session(FAKE_HOST, FAKE_PORT, None, tmp_path)

    session.send_raw(b"H")  # no control_lock -- must be a complete no-op wait

    assert sent == [b"H"]


def test_send_raw_sends_immediately_when_the_lock_is_not_fenced(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(TelnetConnection, "send_bytes", lambda self, data, secret=False: sent.append(data))
    session = Session(FAKE_HOST, FAKE_PORT, None, tmp_path)
    lock = ControlLock()

    session.send_raw(b"H", control_lock=lock)

    assert sent == [b"H"]


def test_send_raw_waits_for_the_fence_to_clear_before_sending(tmp_path, monkeypatch):
    """The core WO-CLEANPREEMPT mechanic: a fenced dispatch holds the
    keystroke off the wire until it releases -- proven here against the
    real production `send_raw()`/`ControlLock`, independent of the
    full-daemon e2e proof (test_tw04_toctou.py) or the FakeAttachSession
    mirror (conftest.py)."""
    sent = []
    monkeypatch.setattr(TelnetConnection, "send_bytes", lambda self, data, secret=False: sent.append(data))
    session = Session(FAKE_HOST, FAKE_PORT, None, tmp_path)
    lock = ControlLock()
    lock.acquire_driver()
    lock.take_human()  # fences the in-flight "dispatch"
    assert lock.is_driver_fenced() is True

    result = {}

    def send_call():
        session.send_raw(b"H", control_lock=lock)
        result["done"] = True

    t = threading.Thread(target=send_call)
    t.start()
    time.sleep(0.2)  # generous margin, matches this codebase's own convention

    assert "done" not in result
    assert sent == []

    lock.release_driver()  # the fenced dispatch finally releases
    t.join(timeout=2.0)

    assert result.get("done") is True
    assert sent == [b"H"]


def test_send_raw_fence_wait_is_bounded_and_sends_anyway_once_the_bound_expires(tmp_path, monkeypatch):
    """The wait is a courtesy ORDERING wait, never a second refusal path
    -- a dispatch that never releases (already a violation of every
    OTHER try/finally-paired guarantee in this codebase) can't strand a
    human keystroke forever. Shrinks the bound/poll constants via
    monkeypatch so this resolves fast rather than actually waiting the
    real 10s default."""
    monkeypatch.setattr(session_module, "_FENCE_WAIT_TIMEOUT_S", 0.1)
    monkeypatch.setattr(session_module, "_FENCE_WAIT_POLL_S", 0.02)
    sent = []
    monkeypatch.setattr(TelnetConnection, "send_bytes", lambda self, data, secret=False: sent.append(data))
    session = Session(FAKE_HOST, FAKE_PORT, None, tmp_path)
    lock = ControlLock()
    lock.acquire_driver()
    lock.take_human()  # fenced, and deliberately NEVER released in this test

    session.send_raw(b"H", control_lock=lock)  # must not hang forever

    assert sent == [b"H"]


# -- WO-CLEANPREEMPT (secret sub-diff): send_raw()'s send-time secret
# decision (cipher's proven leak: every attach keystroke was previously
# logged unredacted regardless of what prompt it was answering) --------


def test_send_raw_passes_secret_true_to_send_bytes_at_a_password_prompt(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        TelnetConnection, "send_bytes", lambda self, data, secret=False: calls.append((data, secret))
    )
    session = Session(FAKE_HOST, FAKE_PORT, None, tmp_path)
    session.terminal.feed(b"Password:")

    session.send_raw(b"H")

    assert calls == [(b"H", True)]
    assert session.last_sent_secret is True


def test_send_raw_redacts_last_sent_at_a_password_prompt_the_third_sink(tmp_path, monkeypatch):
    """The THIRD sink (hub-caught, follow-up to the log/ledger fix
    above): `last_sent` feeds `protocol.build_response()`'s `sent_input`
    field directly -- `tw watch`/`tw spectate`'s TX-channel and any
    build_response-based verb read a secret keystroke through exactly
    this attribute (see tests/test_attach_redaction.py's own protocol-
    level proof). Mirrors `send()`'s own existing `"<redacted>" if
    secret else text` redaction -- send_raw() already computes the same
    `secret` reading for the log/ledger sinks; this is the SAME reading,
    not a new derivation."""
    monkeypatch.setattr(TelnetConnection, "send_bytes", lambda self, data, secret=False: None)
    session = Session(FAKE_HOST, FAKE_PORT, None, tmp_path)
    session.terminal.feed(b"Password:")

    session.send_raw(b"H")

    assert session.last_sent == "<redacted>"


def test_send_raw_passes_secret_false_at_an_ordinary_prompt_sensitivity_control(tmp_path, monkeypatch):
    """Sensitivity control for the test above: an ordinary screen must
    NOT be redacted -- proving the green result is a real signal keyed
    on the screen's shape, not a check that always redacts."""
    calls = []
    monkeypatch.setattr(
        TelnetConnection, "send_bytes", lambda self, data, secret=False: calls.append((data, secret))
    )
    session = Session(FAKE_HOST, FAKE_PORT, None, tmp_path)
    session.terminal.feed(b"Command [TL=00:00:00]:[1] (?=Help)? :")

    session.send_raw(b"H")

    assert calls == [(b"H", False)]
    assert session.last_sent_secret is False
    assert session.last_sent == "H"  # the third sink: not redacted here either


def test_send_raw_uses_the_current_screen_at_send_time_not_a_stale_pre_wait_snapshot(tmp_path, monkeypatch):
    """mack's staleness finding: the screen can transition to a secret
    prompt DURING send_raw()'s fence-wait -- the secret decision must
    reflect the screen AT THE MOMENT THE BYTE IS SENT (right after the
    wait resolves), never whatever it looked like before the wait
    started. Simulated by mutating the session's own render() mid-wait,
    proven against the real production send_raw()."""
    calls = []
    monkeypatch.setattr(
        TelnetConnection, "send_bytes", lambda self, data, secret=False: calls.append((data, secret))
    )
    session = Session(FAKE_HOST, FAKE_PORT, None, tmp_path)
    became_secret = threading.Event()
    monkeypatch.setattr(
        session,
        "render",
        lambda: ["Enter PIN:"] if became_secret.is_set() else ["Command [TL=00:00:00]:[1] (?=Help)? :"],
    )
    lock = ControlLock()
    lock.acquire_driver()
    lock.take_human()  # fences the in-flight "dispatch"

    result = {}

    def send_call():
        session.send_raw(b"1", control_lock=lock)
        result["done"] = True

    t = threading.Thread(target=send_call)
    t.start()
    time.sleep(0.15)  # still fenced -- the screen is still the ORDINARY one at this point
    assert "done" not in result

    became_secret.set()  # the screen transitions to a secret prompt WHILE still fenced
    lock.release_driver()  # NOW the fence clears -- send_raw's render() happens after this
    t.join(timeout=2.0)

    assert result.get("done") is True
    # Redacted -- reflects the CURRENT (post-transition) screen, not the
    # stale pre-wait one, which would have wrongly read secret=False.
    assert calls == [(b"1", True)]
    assert session.last_sent_secret is True
