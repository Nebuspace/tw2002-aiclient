"""WO-SEND-HISTORY-RING — raw protocol `send` files the session history ring.

Banked gap from #225: `do` and `read` called `record_history`; raw `send`
did not. An operator-driven `tw send` (or any client using the verb) left no
row, so `tw history` could not show what was typed. Armed-run history is a
separate verb (`HISTORY_VERB_AUTOLOOP`) and is not this file's concern.
"""

from __future__ import annotations

from tw2002_aiclient.session import protocol
from tw2002_aiclient.session.control_lock import ControlLock

from .test_autoloop import WireSession
from .test_loop_player import ANCHOR_158


class _Server:
    def __init__(self, session, lock):
        self.session = session
        self.control_lock = lock


def _send_rows(session):
    return [e for e in session.history if e["verb"] == "send"]


def test_raw_send_appends_a_send_history_row():
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()

    protocol.dispatch(session, "send", {"input": "P"}, _Server(session, lock))

    rows = _send_rows(session)
    assert len(rows) == 1
    assert rows[0]["args"]["input"] == "P"
    assert rows[0]["settled_reason"] is None
    assert rows[0]["verb"] == "send"


def test_secret_send_redacts_input_like_do():
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()

    protocol.dispatch(
        session,
        "send",
        {"input": "s3cret-password", "secret": True},
        _Server(session, lock),
    )

    rows = _send_rows(session)
    assert len(rows) == 1
    assert rows[0]["args"]["input"] == "<redacted>"
    assert "s3cret-password" not in str(session.history)


def test_send_does_not_file_as_do_or_autoloop():
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()

    protocol.dispatch(session, "send", {"input": "x"}, _Server(session, lock))

    assert [e for e in session.history if e["verb"] == "do"] == []
    assert [e for e in session.history if e["verb"] != "send"] == []
