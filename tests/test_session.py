"""Session (twclient/session.py) unit tests -- no network. Constructing
a bare `Session` never touches the network (only `.start()`/
`.reconnect()` do, via `TelnetConnection.connect()`), so `test_reconnect_
resets_game_select_answered` monkeypatches that one method to a no-op
rather than pulling in a real socket -- same discipline as this
project's other fakes that stay network-free."""

from twclient.connection import TelnetConnection
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
