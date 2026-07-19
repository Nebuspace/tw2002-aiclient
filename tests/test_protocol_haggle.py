"""protocol.py's `haggle` verb dispatch -- no network, a scripted fake
session (same reactive-send pattern as tests/test_haggle.py's
FakePortSession, extended with the render_with_color()/build_response()
surface protocol.py itself needs)."""

from twclient import protocol
from twclient.ledger import LedgerWriter, read_entries


class FakeSession:
    def __init__(self, initial_text, respond=None):
        self._text = initial_text
        self._respond = respond or (lambda _sent, _round_i: initial_text)
        self.round_i = 0
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
        self.round_i += 1
        self._text = self._respond(text, self.round_i)
        self.rx_count += 1
        self.last_rx = self.t


class FakeServer:
    """Deliberately bare -- no `.ledger`/`.skill_recorder` attributes,
    matching protocol.py's own documented "bare dispatch harness"
    convention (`_record_ledger`/`_record_skill_step` both no-op when
    the corresponding server attribute is absent)."""


def _scripted(responses):
    def respond(_sent, round_i):
        return responses[round_i - 1]

    return respond


def test_haggle_verb_runs_the_negotiation_and_reports_the_outcome():
    responses = [
        "We'll buy them for 2,216 credits.\nYour offer [2,216] ? ",
        "Done, we'll take the lot.\n\nCommand [TL=00:00:00]:[1] (?=Help)? : ",
    ]
    session = FakeSession("We'll buy them for 2,214 credits.\nYour offer [2,214] ? ", _scripted(responses))

    resp = protocol.dispatch(session, "haggle", {}, FakeServer())

    assert resp["ok"] is True
    assert resp["haggle"]["outcome"] == "accepted"
    assert resp["haggle"]["final_price"] == 2216
    assert resp["classification"] == "main_command"  # settled back at Command [TL=


def test_haggle_verb_no_active_haggle_still_returns_ok_with_the_current_screen():
    session = FakeSession("Command [TL=00753:0/0/0/850] (?=Help)? : ")

    resp = protocol.dispatch(session, "haggle", {}, FakeServer())

    assert resp["ok"] is True
    assert resp["haggle"]["outcome"] == "no_active_haggle"
    assert session.sent == []


def test_haggle_verb_honors_explicit_strategy_overrides_from_args():
    responses = [
        "We'll buy them for 3,010 credits.\nYour offer [3,010] ? ",
        "Done, we'll take the lot.\n\nCommand [TL=00:00:00]:[1] (?=Help)? : ",
    ]
    session = FakeSession("We'll buy them for 2,000 credits.\nYour offer [2,000] ? ", _scripted(responses))

    resp = protocol.dispatch(
        session,
        "haggle",
        {"fair_value": 3000, "open_aggression_pct": 0.0, "round_cap": 2, "accept_threshold_pct": 5.0},
        FakeServer(),
    )

    assert resp["ok"] is True
    assert session.sent[0][0] == "3000"  # open_aggression_pct=0 -> round 1's ask IS fair_value
    assert resp["haggle"]["fair_value"] == 3000


def test_haggle_verb_records_exactly_one_ledger_entry_when_a_ledger_is_wired(tmp_path):
    responses = ["Done, we'll take the lot.\n\nCommand [TL=00:00:00]:[1] (?=Help)? : "]
    session = FakeSession("We'll buy them for 1,000 credits.\nYour offer [1,000] ? ", _scripted(responses))

    server = FakeServer()
    ledger_path = tmp_path / "ledger.jsonl"
    server.ledger = LedgerWriter(path=ledger_path)

    resp = protocol.dispatch(session, "haggle", {}, server)

    assert resp["ok"] is True
    entries = read_entries(path=ledger_path)
    assert len(entries) == 1  # the WHOLE haggle is one ledger entry, not one per round
    assert entries[0]["input"].startswith("<haggle:")
    assert entries[0]["settled_class"] == resp["classification"]
