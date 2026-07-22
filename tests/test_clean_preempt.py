"""WO-CLEANPREEMPT: control_lock.ControlLock.take_human() fences an
in-flight ai_pilot dispatch instead of ignoring it (mack's TW-04-Axis-2
finding, tests/test_tw04_toctou.py) -- proving the two DIRECT
consequences of a fence at the protocol.py/ledger.py level, synchronous
and deterministic (no real threads/sockets; the real-timing "no human
byte precedes the AI stop" proof lives in test_tw04_toctou.py's own
flipped Axis-2 test, and the `Session.send_raw()` bounded-wait mechanics
are unit-tested directly in test_session.py):

  1. A do/send/haggle dispatch that gets fenced mid-flight (a human
     attaches WHILE its own `wait_settle()` is still open) flags its
     OWN Trace-Ledger entry `interrupted_by_human=True` -- with a
     sensitivity control proving an UN-fenced dispatch does NOT (so the
     green result above is a real signal, not a check that always
     reads True).
  2. A `tw attach` keystroke (protocol.record_attach_keystroke(), the
     daemon-side sink daemon.py's CommandHandler._handle_attach calls
     right after session.send_raw()) writes its own row with
     `actor="human"` via a REAL `ledger.LedgerWriter` -- redacted (TW-02b
     invariant) whenever the caller passes `secret=True`. The secret
     DECISION itself (send-time, from the current screen) is made by
     `Session.send_raw()`/`classify.is_probable_secret_prompt()` --
     proven in tests/test_session.py/tests/test_classify.py/
     tests/test_connection.py/tests/test_attach_redaction.py (the
     secret sub-diff) -- this file only proves `record_attach_keystroke`'s
     own mechanical redaction given that decision.

**REVISE pass (adversarial wave + hub ruling):**
  3. FIX 1 (cipher's Concern-1, confirmed WITH a real consumer --
     spectate_layout.compute_autonomy_ratio() -- corrupted by it): a
     fenced `do`/`send` row now reads `actor="ai"` (explicit, mirroring
     haggle's own `actor="trainer"`), never the live-mode-derived
     `"human"` misread the original WO-CLEANPREEMPT pass left as a
     Concern. See the updated assertion in test 1 above.
  4. FIX 2 (mack's quantified multi-step repro): protocol.py's
     `_dispatch_replay`/`_dispatch_play`/`_dispatch_crawl_start` all wire
     `is_driver_fenced=lambda: _driver_was_fenced(server)` through to
     `skills.replay_skill`/`play_skill`/`crawl_driver.run_live_crawl` --
     the PRIMARY, precise proofs of the fence-stop mechanism itself live
     in tests/test_skills.py (replay_skill/play_skill) and
     tests/test_crawl_driver.py (run_live_crawl); this file adds only
     the protocol.py WIRING proof (the lambda genuinely reaches the
     callee) for each of the three verbs.
"""

from twclient import protocol
from twclient.control_lock import MODE_HUMAN, ControlLock
from twclient.ledger import LedgerWriter, read_entries

from .test_actor_attribution import FakeSession, _FakeLogger

SENTINEL_KEY = "S"

# -- 1. do-verb interrupted_by_human flagging -------------------------------


class _FenceOnSettleSession(FakeSession):
    """`FakeSession` (test_actor_attribution.py) plus one change:
    `wait_settle()` calls `control_lock.take_human()` as a side effect --
    standing in for "a `tw attach` connects WHILE this dispatch's own
    send-then-settle window is still open", the exact scenario
    test_tw04_toctou.py proves end-to-end over real threads/sockets.
    Deterministic and synchronous here: no timing race needed to prove
    the LEDGER-side half of the fix (the ledger entry's flag), only the
    ordering half (no human byte precedes the AI stop) needs real
    threads."""

    def __init__(self, control_lock, **kwargs):
        super().__init__(**kwargs)
        self._control_lock = control_lock

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350):
        self._control_lock.take_human()
        return "idle", 0.0


class FakeServer:
    """Same bare-by-default convention as test_actor_attribution.py's
    own FakeServer -- attributes set explicitly per test."""


def test_do_verb_flags_interrupted_by_human_when_fenced_mid_flight(tmp_path):
    lock = ControlLock()
    server = FakeServer()
    server.control_lock = lock
    ledger_path = tmp_path / "ledger.jsonl"
    server.ledger = LedgerWriter(path=ledger_path)
    session = _FenceOnSettleSession(lock, logger=_FakeLogger("s-fence"))

    resp = protocol.dispatch(session, "do", {"input": "ai-action"}, server)

    # take_human() succeeded -- no refusal, exactly as WO-CLEANPREEMPT
    # requires -- and the dispatch itself completed normally, unaware it
    # was fenced (the invariant: the human always wins immediately,
    # never blocked on this call).
    assert resp["ok"] is True
    assert lock.mode == MODE_HUMAN

    entries = read_entries(path=ledger_path)
    assert len(entries) == 1
    assert entries[0]["interrupted_by_human"] is True
    # FIX 1 (cipher-confirmed Concern-1, resolved in the REVISE pass):
    # `do`/`send` now pass an explicit actor="ai" to `_record_ledger`,
    # mirroring haggle's own explicit actor="trainer" -- never
    # `_current_actor()`'s live-mode derivation, which used to misread
    # this exact row as actor="human" (mode had already flipped to
    # MODE_HUMAN by ledger-write time) and corrupted
    # spectate_layout.compute_autonomy_ratio()'s denominator.
    assert entries[0]["actor"] == "ai"


def test_do_verb_leaves_interrupted_by_human_false_when_never_fenced_sensitivity_control(tmp_path):
    """Sensitivity control for the test above: identical shape, but
    `wait_settle()` never calls take_human() -- proving the green
    `interrupted_by_human=True` result above is a real signal reflecting
    an actual fence event, not a check that reads True unconditionally."""
    lock = ControlLock()
    server = FakeServer()
    server.control_lock = lock
    ledger_path = tmp_path / "ledger.jsonl"
    server.ledger = LedgerWriter(path=ledger_path)
    session = FakeSession(logger=_FakeLogger("s-nofence"))

    resp = protocol.dispatch(session, "do", {"input": "ai-action"}, server)

    assert resp["ok"] is True
    assert lock.mode != MODE_HUMAN
    entries = read_entries(path=ledger_path)
    assert entries[0]["interrupted_by_human"] is False


def test_do_verb_explicit_actor_human_for_spectate_idle_overlay(tmp_path):
    """Spectate idle-prompt overlay passes actor=human so autonomy
    human-count increments; must NOT fall back to the hardcoded ai
    default (and must still ignore live-mode derivation)."""
    lock = ControlLock()
    server = FakeServer()
    server.control_lock = lock
    ledger_path = tmp_path / "ledger.jsonl"
    server.ledger = LedgerWriter(path=ledger_path)
    session = FakeSession(logger=_FakeLogger("s-overlay-human"))

    resp = protocol.dispatch(
        session, "do", {"input": "A", "actor": "human"}, server,
    )

    assert resp["ok"] is True
    entries = read_entries(path=ledger_path)
    assert entries[0]["actor"] == "human"


def test_send_verb_also_flags_interrupted_by_human_when_fenced_mid_flight(tmp_path):
    """The `send` verb shares `_record_ledger`'s same `interrupted_by_
    human` wiring (via `_driver_was_fenced()`) as `do` -- proven
    separately since `send` never calls `wait_settle()` at all, so the
    settle-time-side-effect trick the `do`-verb test above uses doesn't
    apply here; a real `ControlLock` mid-`send`-dispatch would refuse a
    concurrent `acquire_driver()` re-entry to simulate this from outside
    (the slot's already held), so this uses a minimal stand-in
    (`_AlwaysFencedLock`) exposing only `_driving_dispatch`'s/
    `_driver_was_fenced()`'s own required surface, unrestricted like a
    bare dispatch harness but reporting fenced=True -- scoped to proving
    `_record_ledger`'s wiring, not the guard/fence mechanism itself
    (already proven directly against the real ControlLock above and in
    test_control_lock.py)."""
    server = FakeServer()
    server.control_lock = _AlwaysFencedLock()
    ledger_path = tmp_path / "ledger.jsonl"
    server.ledger = LedgerWriter(path=ledger_path)
    session = FakeSession(logger=_FakeLogger("s-send-fence"))

    resp = protocol.dispatch(session, "send", {"input": "ai-action"}, server)

    assert resp["ok"] is True
    entries = read_entries(path=ledger_path)
    assert entries[0]["interrupted_by_human"] is True


class _AlwaysFencedLock:
    """Minimal stand-in for `_driver_was_fenced(server)`'s own surface
    (`getattr(server, "control_lock", None)`, then `.is_driver_fenced()`)
    -- always reports fenced, without needing a real acquire/take/
    release choreography for this narrow `send`-verb wiring proof.
    `ai_may_send()`/`acquire_driver()`/`release_driver()` are exercised
    by `_driving_dispatch` too, so this mirrors the REAL ControlLock's
    unrestricted-ai_pilot shape rather than refusing everything."""

    def ai_may_send(self):
        return True

    @property
    def mode(self):
        return "ai_pilot"

    def acquire_driver(self):
        pass

    def release_driver(self):
        pass

    def is_driver_fenced(self):
        return True


# -- 2. attach-keystroke ledger routing (record_attach_keystroke) ----------


class _AttachFakeSession:
    """Just enough surface for `record_attach_keystroke()`: render()/
    render_text() (the post-send screen it reads itself, see its own
    docstring) plus an optional `.logger.session_id`."""

    def __init__(self, post_screen, logger=None):
        self._post_screen = post_screen
        self.logger = logger

    def render(self):
        return self._post_screen.splitlines()

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._post_screen


def test_record_attach_keystroke_writes_actor_human_row_via_real_ledger(tmp_path):
    server = FakeServer()
    ledger_path = tmp_path / "ledger.jsonl"
    server.ledger = LedgerWriter(path=ledger_path)
    session = _AttachFakeSession(
        "Command [TL=00:00:00]:[1] (?=Help)? :", logger=_FakeLogger("s-attach")
    )
    pre_text = "Command [TL=00:00:00]:[1] (?=Help)? :"

    protocol.record_attach_keystroke(server, session, pre_text, "H", secret=False)

    entries = read_entries(path=ledger_path)
    assert len(entries) == 1
    assert entries[0]["actor"] == "human"
    assert entries[0]["input"] == "H"
    assert entries[0]["session_id"] == "s-attach"
    assert entries[0]["interrupted_by_human"] is False  # this IS the human's own row


def test_record_attach_keystroke_is_a_no_op_when_server_has_no_ledger():
    server = FakeServer()  # no .ledger -- getattr(..., None) convention
    session = _AttachFakeSession("Command [TL=00:00:00]:[1] (?=Help)? :")
    # must not raise
    protocol.record_attach_keystroke(server, session, "Command [TL=00:00:00]:[1] (?=Help)? :", "H", secret=False)


def test_record_attach_keystroke_redacts_when_told_secret_is_true(tmp_path):
    """WO-CLEANPREEMPT (secret sub-diff): `secret` is now a REQUIRED
    parameter this function never derives itself -- mack's staleness
    finding showed deriving it from `pre_text` (captured before send_
    raw()'s own up-to-10s fence-wait) could under-redact against a
    screen that transitioned to a secret prompt DURING the wait. The
    caller (daemon.py) passes `session.last_sent_secret` -- the SAME
    send-time decision (`classify.is_probable_secret_prompt()`, proven
    directly in tests/test_classify.py) that already gated the
    transcript LOG sink (tests/test_connection.py). This test proves
    only the MECHANICAL redaction given that decision -- TW-02b
    invariant, preserved on the attach-ledger path."""
    server = FakeServer()
    ledger_path = tmp_path / "ledger.jsonl"
    server.ledger = LedgerWriter(path=ledger_path)
    session = _AttachFakeSession("Password?")

    protocol.record_attach_keystroke(server, session, "Password?", SENTINEL_KEY, secret=True)

    entries = read_entries(path=ledger_path)
    assert len(entries) == 1
    assert entries[0]["input"] == "<redacted>"
    assert entries[0]["prompt"] == "<redacted>"
    raw = open(ledger_path, encoding="utf-8").read()
    assert SENTINEL_KEY not in raw


# -- 4. protocol.py wiring proofs: replay/play/crawl_start pass
#    is_driver_fenced through to their respective callees ------------------
#
# The PRECISE fence-stop mechanism (does it actually stop firing sends,
# is the right step's ledger row flagged, etc.) is proven directly against
# skills.replay_skill/play_skill (tests/test_skills.py) and
# crawl_driver.run_live_crawl (tests/test_crawl_driver.py) -- these three
# tests only prove protocol.py's own dispatch code genuinely THREADS the
# lambda through to each callee, using `_AlwaysFencedLock` (defined above)
# so the fence reads True from the very first check, no timing/threading
# needed.

from twclient import credentials, skills  # noqa: E402 -- grouped near point of use, matching this module's own style

from .test_crawl_start_protocol import FakeSession as _CrawlWiringSession
from .test_skills import FakeReplaySession as _ReplayWiringSession


def test_dispatch_replay_wires_is_driver_fenced_through_to_replay_skill(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(skills, "SKILLS_DIR", skills_dir)
    skills.save_skill(
        "wiring-check-replay",
        [{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"} for _ in range(3)],
        source="recorded",
    )
    session = _ReplayWiringSession(["Command [TL=00753:0/0/0/850]"] + ["Sector : 100"] * 3)
    server = FakeServer()
    server.control_lock = _AlwaysFencedLock()

    resp = protocol.dispatch(session, "replay", {"name": "wiring-check-replay", "force": True}, server)

    assert resp["ok"] is False
    assert resp["error"] == "human_fenced"
    # Only step 0 was ever sent -- proves the lambda genuinely reached
    # replay_skill() and stopped it, not just that dispatch returned an
    # error for some unrelated reason.
    assert session.sent == [("M", False)]


def test_dispatch_play_wires_is_driver_fenced_through_to_play_skill(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(skills, "SKILLS_DIR", skills_dir)
    skills.save_skill(
        "wiring-check-play",
        [{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"}],
        source="recorded",
    )
    session = _ReplayWiringSession(["Command [TL=00753:0/0/0/850]"] + ["Sector : 100"] * 3)
    server = FakeServer()
    server.control_lock = _AlwaysFencedLock()

    resp = protocol.dispatch(session, "play", {"name": "wiring-check-play", "cycles": 5, "force": True}, server)

    assert resp["ok"] is True
    assert resp["halted"] == "human_fenced"
    assert resp["cycles_completed"] == 0
    assert session.sent == [("M", False)]


def test_dispatch_crawl_start_wires_is_driver_fenced_through_to_run_live_crawl(tmp_path, monkeypatch):
    profiles_path = tmp_path / "profiles.toml"
    profiles_path.write_text(
        '[sacrificial]\nhost = "test.example"\nport = 2002\ngame_letter = "A"\nhandle = "Sacrifice1"\n'
        "crawl_sacrificial = true\n"
    )
    monkeypatch.setattr(credentials, "PROFILES_PATH", profiles_path)
    session = _CrawlWiringSession()
    server = FakeServer()
    server.control_lock = _AlwaysFencedLock()

    resp = protocol.dispatch(
        session,
        "crawl_start",
        {
            "profile": "sacrificial",
            "path": str(tmp_path / "gk.json"),
            "log_path": str(tmp_path / "crawl.jsonl"),
        },
        server,
    )

    assert resp["ok"] is True
    assert resp["aborted"] is True
    assert "fenced" in resp["aborted_reason"]


def test_record_attach_keystroke_does_not_redact_when_told_secret_is_false(tmp_path):
    """Sensitivity control for the redaction test above: `secret=False`
    must NOT redact -- proving the mechanical redaction above is a real
    signal keyed on the passed-in flag, not a check that always
    redacts."""
    server = FakeServer()
    ledger_path = tmp_path / "ledger.jsonl"
    server.ledger = LedgerWriter(path=ledger_path)
    session = _AttachFakeSession("Command [TL=00:00:00]:[1] (?=Help)? :")

    protocol.record_attach_keystroke(server, session, "Command [TL=00:00:00]:[1] (?=Help)? :", "H", secret=False)

    entries = read_entries(path=ledger_path)
    assert entries[0]["input"] == "H"
    assert entries[0]["prompt"] != "<redacted>"
