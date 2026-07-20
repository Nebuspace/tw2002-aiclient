"""protocol.py's `ensure` verb dispatch -- the control-lock gate (safety
fix: `ensure` drives the login automaton, a keystroke-sending verb same
as do/send/replay/play/haggle, but was previously dispatched with no
control_lock gate at all -- see `_driving_dispatch`'s docstring). No
network -- same bare dispatch-harness convention as
tests/test_crawl_start_protocol.py; `FakeAttachSession` (conftest.py) is
reused rather than a bespoke double since `_dispatch_ensure` needs the
full `.conn.connected`/`.render()`/`.record_history()` surface it already
provides, and its default screen already classifies `main_command` --
exercising the already_there fast path with zero login-automaton
complexity."""

import pytest

from twclient import credentials, protocol
from twclient.control_lock import ControlLock

from .conftest import FakeAttachSession


class FakeServer:
    """Deliberately bare by default -- no `.control_lock`, matching
    protocol.py's documented bare-dispatch-harness convention
    (`_driving_dispatch` treats a missing control_lock as
    unrestricted)."""


@pytest.fixture
def profiles_toml(tmp_path, monkeypatch):
    p = tmp_path / "profiles.toml"
    p.write_text(
        "[default]\n"
        'host = "test.example"\n'
        "port = 2002\n"
        'game_letter = "A"\n'
        'handle = "Trader1"\n'
    )
    monkeypatch.setattr(credentials, "PROFILES_PATH", p)
    return p


# -- control-lock gating (same guard do/send/replay/play/haggle share) ------


def test_ensure_refused_while_human_is_attached(profiles_toml):
    session = FakeAttachSession()
    server = FakeServer()
    server.control_lock = ControlLock()
    server.control_lock.take_human()

    resp = protocol.dispatch(session, "ensure", {"profile": "default"}, server)

    assert resp == {"ok": False, "error": "controller_locked_by_human"}
    assert session.sent == []  # _dispatch_ensure never ran -- zero keystrokes


# -- the gate must not regress ensure's documented, everyday use ------------


def test_ensure_still_drives_normally_under_ai_pilot(profiles_toml):
    session = FakeAttachSession()  # default screen already classifies main_command
    server = FakeServer()
    server.control_lock = ControlLock()  # explicit ai_pilot, not just "missing"

    resp = protocol.dispatch(session, "ensure", {"profile": "default"}, server)

    assert resp["ok"] is True
    assert resp["already_there"] is True
    assert resp["steps"] == 0
    assert session.sent == []  # already at target -- the automaton never ran


def test_ensure_still_drives_normally_with_no_control_lock_at_all(profiles_toml):
    """The pre-existing bare-dispatch-harness convention (no
    `server.control_lock` attribute at all) must keep working too."""
    session = FakeAttachSession()

    resp = protocol.dispatch(session, "ensure", {"profile": "default"}, FakeServer())

    assert resp["ok"] is True
    assert resp["already_there"] is True
