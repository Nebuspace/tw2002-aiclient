"""Cross-lane integration proof (P0 safety batch, 2026-07-19 INTEGRATION
wave): LANE-A (haggle/settle/state_parser), LANE-B (skills/loop_player
TW-03 start-anchor + TW-04 replay-ledgering), and LANE-C (ledger/
control_lock/protocol actor+session_id attribution) were built as three
disjoint, independently-tested lanes -- this file is the ONE new test
proving the full chain joins correctly end-to-end through the REAL wire
dispatch: `protocol.dispatch(..., "replay", ...)` -> `skills.replay_skill`
(TW-03 anchor check + TW-04 ledger forwarding) -> a REAL
`ledger.LedgerWriter` row with `actor="trainer"` + the caller's
`session_id` -- never a hand-rolled fake standing in for any of the three
lanes' own real code.
"""

from twclient import protocol, skills
from twclient.ledger import LedgerWriter, read_entries

_ANCHOR_SECTOR = 100
_SCREEN = f"Sector : {_ANCHOR_SECTOR}\nCommand [TL=00753:0/0/0/850] (?=Help)? : "


class _FakeSession:
    """Minimal do/send/replay surface (same convention as
    test_actor_attribution.py's FakeSession) -- a single static screen
    that is simultaneously anchor-matching (TW-03) and post-classifies
    as the skill step's `expected_post_class`, so a real `send()` neither
    trips the anchor guard nor a post-class divergence.

    TW-02: `skills.replay_skill` now routes its send through
    `settle.send_and_confirm`, which needs the full settle-detection
    protocol surface (`clock()`/`rx_count`/`last_rx`/`sleep()`), not just
    `send()`/`wait_settle()`/`render()`. `send()`'s rx_count/last_rx bump
    is DEFERRED to the next `sleep()` call (matching this codebase's
    other post-TW-02 fakes) so `send_and_confirm`'s idle-based confirm
    path can actually observe a fresh arrival rather than always
    resolving to "timeout"."""

    def __init__(self, session_id):
        self.logger = _FakeLogger(session_id)
        self.sent = []
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._pending_advance = False

    def render(self):
        return _SCREEN.splitlines()

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else _SCREEN

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self._pending_advance:
            self._pending_advance = False
            self.rx_count += 1
            self.last_rx = self.t

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))
        self._pending_advance = True

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350):
        return "idle", 0.0


class _FakeLogger:
    def __init__(self, session_id):
        self.session_id = session_id


class _FakeServer:
    """Bare dispatch harness (no `.control_lock`) -- `_driving_dispatch`'s
    documented "unrestricted" convention -- plus a REAL `LedgerWriter` so
    this proves the actual TW-04 sink, not a stand-in."""


def test_replay_verb_writes_a_real_ledger_row_with_actor_trainer_and_session_id(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(skills, "SKILLS_DIR", skills_dir)
    skills.save_skill(
        "join-check",
        [{"input": "d", "wait_prompt": None, "expected_post_class": "main_command"}],
        source="recorded",
        start_anchor=_ANCHOR_SECTOR,
    )

    session = _FakeSession(session_id="s-join-1")
    server = _FakeServer()
    ledger_path = tmp_path / "ledger.jsonl"
    server.ledger = LedgerWriter(path=ledger_path)

    resp = protocol.dispatch(session, "replay", {"name": "join-check"}, server)

    assert resp["ok"] is True
    assert resp["results"][0]["actual"] == "main_command"
    assert session.sent == [("d", True, False)]

    entries = read_entries(path=ledger_path)
    assert len(entries) == 1
    assert entries[0]["actor"] == "trainer"
    assert entries[0]["session_id"] == "s-join-1"
    assert entries[0]["input"] == "d"
    assert entries[0]["settled_class"] == "main_command"


def test_replay_verb_refuses_a_mismatched_start_anchor_before_any_ledger_row(tmp_path, monkeypatch):
    """The TW-03 guard fires BEFORE the first send when the CURRENT
    sector disagrees with the skill's start_anchor -- no ledger row is
    written for a refused replay (nothing was actually sent)."""
    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(skills, "SKILLS_DIR", skills_dir)
    skills.save_skill(
        "wrong-anchor",
        [{"input": "d", "wait_prompt": None, "expected_post_class": "main_command"}],
        source="recorded",
        start_anchor=_ANCHOR_SECTOR + 1,  # deliberately doesn't match _SCREEN's sector
    )

    session = _FakeSession(session_id="s-join-2")
    server = _FakeServer()
    ledger_path = tmp_path / "ledger.jsonl"
    server.ledger = LedgerWriter(path=ledger_path)

    resp = protocol.dispatch(session, "replay", {"name": "wrong-anchor"}, server)

    assert resp["ok"] is False
    assert resp["error"] == "divergence"
    assert resp["reason"] == "start_anchor_mismatch"
    assert session.sent == []
    assert read_entries(path=ledger_path) == []


def test_replay_verb_force_waives_a_missing_legacy_start_anchor(tmp_path, monkeypatch):
    """A skill saved before TW-03 existed (`start_anchor: None`) refuses
    by default even through the real dispatch path, and only proceeds
    (still writing a real actor="trainer" ledger row) when the caller
    explicitly passes force=True -- proving cli.py's new `--force`
    plumbing reaches all the way through to skills._check_start_anchor."""
    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(skills, "SKILLS_DIR", skills_dir)
    skills.save_skill(
        "legacy-unanchored",
        [{"input": "d", "wait_prompt": None, "expected_post_class": "main_command"}],
        source="recorded",
        # start_anchor omitted -- defaults to None, the pre-TW-03 shape.
    )

    session = _FakeSession(session_id="s-join-3")
    server = _FakeServer()
    ledger_path = tmp_path / "ledger.jsonl"
    server.ledger = LedgerWriter(path=ledger_path)

    refused = protocol.dispatch(session, "replay", {"name": "legacy-unanchored"}, server)
    assert refused["ok"] is False
    assert "missing_start_anchor" in refused["error"]
    assert read_entries(path=ledger_path) == []

    resp = protocol.dispatch(session, "replay", {"name": "legacy-unanchored", "force": True}, server)
    assert resp["ok"] is True
    entries = read_entries(path=ledger_path)
    assert len(entries) == 1
    assert entries[0]["actor"] == "trainer"
    assert entries[0]["session_id"] == "s-join-3"
