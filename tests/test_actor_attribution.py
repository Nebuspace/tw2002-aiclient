"""TW-05 actor attribution (knowledge/architecture/autonomy-loop.md) --
protocol.py's `_current_actor()`/`_current_session_id()` helpers and
their wiring into the `do`/`send` dispatch choke point
(protocol.py:234->248's `_record_ledger()`). No network -- same bare
dispatch-harness convention as tests/test_protocol_haggle.py (FakeServer
deliberately missing optional attributes so the getattr(..., None)
fallbacks are exercised too)."""

from twclient import protocol
from twclient.control_lock import ControlLock
from twclient.ledger import LedgerWriter, read_entries


class FakeSession:
    """Same minimal surface as test_protocol_haggle.py's FakeSession,
    plus an optional `.logger.session_id` (TranscriptLogger's real
    surface -- session.py) so `_current_session_id()` has something to
    read."""

    def __init__(self, initial_text="Command [TL=00753:0/0/0/850] (?=Help)? : ", logger=None):
        self._text = initial_text
        self.logger = logger
        self.sent = []
        self.rx_count = 1
        self.last_rx = 0.0
        self.t = 0.0

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds

    def render(self):
        return self._text.splitlines()

    def render_with_color(self):
        return self.render(), None

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._text

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))
        self.rx_count += 1
        self.last_rx = self.t

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350):
        return "idle", 0.0

    def record_history(self, *a, **kw):
        pass


class _FakeLogger:
    def __init__(self, session_id):
        self.session_id = session_id


class FakeServer:
    """Deliberately bare by default -- no `.control_lock`, matching
    protocol.py's documented "bare dispatch harness" convention."""


# -- _current_actor() -----------------------------------------------------


def test_current_actor_defaults_to_ai_with_no_control_lock():
    assert protocol._current_actor(FakeServer()) == "ai"


def test_current_actor_is_ai_when_mode_is_ai_pilot():
    server = FakeServer()
    server.control_lock = ControlLock()
    assert protocol._current_actor(server) == "ai"


def test_current_actor_is_human_when_mode_is_human():
    server = FakeServer()
    server.control_lock = ControlLock()
    server.control_lock.take_human()
    assert protocol._current_actor(server) == "human"


# -- _current_session_id() -------------------------------------------------


def test_current_session_id_none_when_session_has_no_logger():
    assert protocol._current_session_id(FakeSession()) is None


def test_current_session_id_reads_the_sessions_transcript_logger_id():
    session = FakeSession(logger=_FakeLogger("s-42"))
    assert protocol._current_session_id(session) == "s-42"


# -- wired end-to-end through do/send --------------------------------------


def test_do_verb_records_actor_ai_and_session_id_from_the_session(tmp_path):
    session = FakeSession(logger=_FakeLogger("s-1"))
    server = FakeServer()
    server.ledger = LedgerWriter(path=tmp_path / "ledger.jsonl")

    resp = protocol.dispatch(session, "do", {"input": "d"}, server)

    assert resp["ok"] is True
    entries = read_entries(path=tmp_path / "ledger.jsonl")
    assert len(entries) == 1
    assert entries[0]["actor"] == "ai"
    assert entries[0]["session_id"] == "s-1"


def test_send_verb_records_actor_ai_and_session_id_from_the_session(tmp_path):
    session = FakeSession(logger=_FakeLogger("s-2"))
    server = FakeServer()
    server.ledger = LedgerWriter(path=tmp_path / "ledger.jsonl")

    resp = protocol.dispatch(session, "send", {"input": "d"}, server)

    assert resp["ok"] is True
    entries = read_entries(path=tmp_path / "ledger.jsonl")
    assert entries[0]["actor"] == "ai"
    assert entries[0]["session_id"] == "s-2"


def test_do_verb_records_no_session_id_when_session_has_no_logger(tmp_path):
    session = FakeSession()
    server = FakeServer()
    server.ledger = LedgerWriter(path=tmp_path / "ledger.jsonl")

    protocol.dispatch(session, "do", {"input": "d"}, server)

    entries = read_entries(path=tmp_path / "ledger.jsonl")
    assert entries[0]["session_id"] is None
