"""WO-FA7a dispatch-level proof: the passive credits-supervision surface --
`session.last_credits`/`last_credits_ts` (session.py), the
`Session.observe_credits()` capture point (fed from both
`build_response()`'s do/read/screen path and the `state` verb), and
`status`'s `credits`/`credits_ts`/`credits_age_ms` fields -- driven through
the real `protocol.dispatch()` with a scripted bare-dispatch-harness
FakeSession/FakeServer (same idiom as test_world_model_integration.py's/
test_protocol_haggle.py's own fakes). Audit-discovered prerequisite for
WO-FA7b (the E2 money-doubling supervised run, where the hub polls `tw
status` each window to rule the 2x stop) -- this file only proves the
surface itself, PASSIVELY: no new send, no polling loop, no history.

REVISE (team-lead-confirmed defect): the capture sources from
`state_parser.credits_balance()` -- the STRICT "you have N credits"
balance -- not `parse_state()`'s own looser `credits` field, which falls
back to a bare "N credits" mention and would misread a port's own price
quote as a real balance on a balance-less haggle screen.
`test_price_quote_screen_does_not_pollute_the_last_known_balance` below
is the regression proof for exactly that failure mode.

REVISE 2 (team-lead-caught contract gap): `status`'s raw `credits_ts` is a
daemon-monotonic value with no meaning to an external caller (a separate
process, or a fresh `tw` invocation, has no reference to diff it against)
-- `credits_age_ms` is the actual externally-meaningful staleness signal,
mirroring `idle_ms`'s own computed-age shape.
`test_credits_age_ms_grows_across_a_later_non_balance_screen` and
`test_credits_age_ms_is_none_when_no_balance_ever_captured` below prove it.

REVISE 3 (mack-confirmed CRITICAL): the capture logic moved from a
protocol.py-only free function into `Session.observe_credits()` (session.py)
so skills.py's replay_skill/play_skill (the AUTO-LOOP driver's actual
per-step engine) can call it too, without a protocol.py<->skills.py
circular import. `FakeSession` below reuses the REAL `Session.
observe_credits` method directly (`observe_credits = Session.observe_credits`)
rather than duplicating its logic, so these tests exercise the actual
production capture code, not a parallel reimplementation of it.
"""

import threading
import time as _real_time

from twclient import protocol, skills
from twclient.session import Session
from twclient.settle import wait_for_settle


class _FakeConn:
    """Just enough of TelnetConnection's surface for the `status` verb
    (`session.conn.connected`) -- mirrors tests/conftest.py's own
    `_FakeConn`."""

    def __init__(self):
        self.connected = True


class FakeSession:
    """Minimal bare-dispatch-harness session covering `build_response()`'s
    do/read/screen path, the `state` verb, and the `status` verb -- the
    combination WO-FA7a's capture point + serving surface needs. Screen
    text is mutable (`set_screen`) so one test can drive successive
    settled screens through the SAME session, exactly as a real daemon
    would across successive `tw do` calls.

    `observe_credits` is the REAL `Session.observe_credits` (assigned
    directly off the class, not reimplemented) -- see this module's own
    docstring."""

    observe_credits = Session.observe_credits

    def __init__(self, initial_text):
        self._text = initial_text
        self.conn = _FakeConn()
        self.host = "bat.example.com"
        self.port = 23
        self.name = "alice"
        self.rx_count = 1
        self.last_rx = 0.0
        self.t = 0.0
        self.sent = []
        self.history = []

    def set_screen(self, text):
        self._text = text

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


class FakeServer:
    """Deliberately bare -- every optional server surface protocol.py
    reads for `do`/`state`/`status` (`control_lock`/`ledger`/
    `skill_recorder`/`watch_hub`/`loop_player`/`autopilot_engine`) is
    getattr-guarded to a clean no-op, same convention
    test_world_model_integration.py's own FakeServer relies on."""


class _FakeAutoLoopSession:
    """Minimal replay-capable session for `skills.replay_skill()`/
    `play_skill()` -- same deferred-advance-on-sleep convention as
    tests/test_skills.py's own `FakeReplaySession` (`screens[0]` is the
    current screen; each `send()` only advances to the NEXT entry on the
    FOLLOWING `sleep()` call, matching `settle.send_and_confirm()`'s
    idle-detection needs -- a synchronous same-call bump would already be
    reflected in the `start_rx_count` `wait_for_settle` captures at its own
    start, so it would never observe a NEW arrival). `observe_credits` is
    the REAL `Session.observe_credits` (see `FakeSession` above) -- this
    class exists locally (not cross-imported from test_skills.py, matching
    this repo's own one-fixture-per-file convention) purely to drive
    `replay_skill`/`play_skill` through a credits-bearing screen
    transition."""

    observe_credits = Session.observe_credits

    def __init__(self, screens):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._screens = screens
        self._i = 0
        self.sent = []
        self._pending_advance = False

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self._pending_advance:
            self._pending_advance = False
            if self._i < len(self._screens) - 1:
                self._i += 1
            self.rx_count += 1
            self.last_rx = self.t

    def render(self):
        return self._screens[self._i].split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._screens[self._i]

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350):
        return wait_for_settle(self, wait_prompt=wait_prompt, timeout_s=timeout, debounce_ms=debounce_ms)

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, secret))
        self._pending_advance = True


CREDITS_SCREEN = "You have 100,000 credits.\nCommand [TL=00:12:34]:[100] (?=Help)? : "
NO_CREDITS_SCREEN = "Sector : 200\nCommand [TL=00:12:35]:[200] (?=Help)? : "
# A port price-quote screen with NO "you have N credits" balance line at
# all -- exactly haggle.py's dominant screen shape mid-dialogue. Deliberately
# DOES carry a bare "N credits" mention (parse_state()'s looser
# `_CREDITS_AMOUNT_FIRST_RE` fallback would misread the 2214 as a real
# balance here) so this fixture actually exercises the polluting shape the
# strict credits_balance() source defends against.
PORT_PRICE_QUOTE_SCREEN = "We'll sell them for 2,214 credits.\nYour offer [2214] ? "


def test_credits_bearing_screen_populates_status_credits_and_ts():
    session = FakeSession(CREDITS_SCREEN)

    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())
    assert resp["ok"] is True

    status = protocol.dispatch(session, "status", {}, FakeServer())
    assert status["credits"] == 100000
    assert status["credits_ts"] is not None


def test_following_non_credits_screen_does_not_clobber_prior_credits():
    session = FakeSession(CREDITS_SCREEN)
    protocol.dispatch(session, "do", {"input": ""}, FakeServer())
    first_status = protocol.dispatch(session, "status", {}, FakeServer())
    first_credits, first_ts = first_status["credits"], first_status["credits_ts"]
    assert first_credits == 100000
    assert first_ts is not None

    session.set_screen(NO_CREDITS_SCREEN)
    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())
    assert resp["ok"] is True
    assert resp["state"].get("credits") is None  # sanity: this screen truly has no credits mention

    second_status = protocol.dispatch(session, "status", {}, FakeServer())
    assert second_status["credits"] == first_credits
    assert second_status["credits_ts"] == first_ts, "a non-credits screen must not clobber the prior reading"


def test_state_verb_also_feeds_the_credits_capture():
    """`tw state` is the cheap-polling verb (mack Finding 5's own
    precedent for the world-model write-hook) -- it must feed the
    credits-supervision surface too, not just build_response()'s
    do/read/screen path."""
    session = FakeSession(CREDITS_SCREEN)

    resp = protocol.dispatch(session, "state", {}, FakeServer())
    assert resp["ok"] is True
    assert resp["state"]["credits"] == 100000

    status = protocol.dispatch(session, "status", {}, FakeServer())
    assert status["credits"] == 100000
    assert status["credits_ts"] is not None


def test_fresh_session_with_no_credits_ever_parsed_serves_none():
    session = FakeSession(NO_CREDITS_SCREEN)

    status = protocol.dispatch(session, "status", {}, FakeServer())
    assert status["credits"] is None
    assert status["credits_ts"] is None
    assert status["credits_age_ms"] is None


def test_price_quote_screen_does_not_pollute_the_last_known_balance():
    """The regression proof for the team-lead-confirmed defect: a mid-
    haggle port price-quote screen with no balance line of its own must
    NEVER overwrite the last known REAL balance, even though
    `parse_state()`'s own looser `credits` field would have been fooled by
    it (asserted directly below as the sanity check that this fixture
    actually exercises the polluting shape)."""
    session = FakeSession(CREDITS_SCREEN)
    protocol.dispatch(session, "do", {"input": ""}, FakeServer())
    first_status = protocol.dispatch(session, "status", {}, FakeServer())
    assert first_status["credits"] == 100000
    first_ts = first_status["credits_ts"]

    session.set_screen(PORT_PRICE_QUOTE_SCREEN)
    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())
    assert resp["ok"] is True
    # Sanity: parse_state()'s own looser `credits` field IS fooled by this
    # price quote -- confirms the fixture is a real repro of the polluting
    # shape, not an inert screen the fix happens to pass on by accident.
    assert resp["state"].get("credits") == 2214

    status = protocol.dispatch(session, "status", {}, FakeServer())
    assert status["credits"] == 100000, "a port price quote must never overwrite the last known real balance"
    assert status["credits_ts"] == first_ts, "the ts must stay pinned to the last REAL balance reading too"


def test_credits_age_ms_is_none_when_no_balance_ever_captured():
    """`credits_age_ms` (WO-FA7a revise 2) mirrors the getattr-guarded
    None-ness of `credits`/`credits_ts` on a fresh session -- no divide/
    subtract-against-None crash."""
    session = FakeSession(NO_CREDITS_SCREEN)

    status = protocol.dispatch(session, "status", {}, FakeServer())
    assert status["credits_age_ms"] is None


def test_credits_age_ms_grows_across_a_later_non_balance_screen():
    """The externally-meaningful staleness proof this field exists for:
    unlike the raw `credits_ts` (a daemon-monotonic value with no meaning
    to an external caller), `credits_age_ms` is a COMPUTED age an external
    `tw status` caller can read on its own -- and it must keep growing
    while an intervening non-balance screen leaves `credits` itself
    unchanged (the non-clobber gate), exactly the FA7b hub scenario: a
    forced refresh that landed on a price/non-balance screen is
    detectable by a large age, not by `credits` alone."""
    session = FakeSession(CREDITS_SCREEN)
    protocol.dispatch(session, "do", {"input": ""}, FakeServer())
    first_status = protocol.dispatch(session, "status", {}, FakeServer())
    assert isinstance(first_status["credits_age_ms"], int)
    assert first_status["credits_age_ms"] >= 0

    _real_time.sleep(0.05)  # real wall-clock: observe_credits() stamps via time.monotonic(), not the fake clock
    session.set_screen(NO_CREDITS_SCREEN)
    resp = protocol.dispatch(session, "do", {"input": ""}, FakeServer())
    assert resp["state"].get("credits") is None  # sanity: this screen truly has no balance

    second_status = protocol.dispatch(session, "status", {}, FakeServer())
    assert second_status["credits"] == first_status["credits"]  # non-clobber: balance itself is untouched
    assert second_status["credits_age_ms"] > first_status["credits_age_ms"], (
        "credits_age_ms must grow across an intervening non-balance screen -- the externally "
        "meaningful staleness signal `credits_ts` alone cannot provide"
    )


# -- WO-FA7a revise 3, FIX 1 (mack-confirmed CRITICAL): AUTO-LOOP coverage --


_AUTOLOOP_SKILL = {
    "name": "test-skill",
    "start_anchor": None,
    "steps": [{"input": "d", "expected_post_class": None}],
}


def test_replay_skill_feeds_the_credits_supervision_surface_mid_run():
    """mack's CRITICAL repro (scratchpad/repro_fa7a_replay_gap.py),
    formalized: `replay_skill` is the AUTO-LOOP driver's actual per-step
    engine (`loop_player.py` calls it directly every cycle) -- it renders
    and classifies every screen WITHOUT ever routing through protocol.py's
    `build_response()`, so before this fix a real balance appearing on a
    post-step screen never reached `session.last_credits` at all, leaving
    `tw status` credits permanently stale/None for the ENTIRE duration of
    an E2 supervised run."""
    session = _FakeAutoLoopSession([
        "Command [TL=00:12:30]:[100] (?=Help)? : ",
        "You have 250,000 credits.\nCommand [TL=00:12:31]:[100] (?=Help)? : ",
    ])

    results = skills.replay_skill(session, _AUTOLOOP_SKILL, force=True)

    assert len(results) == 1
    assert session.last_credits == 250000
    assert session.last_credits_ts is not None


def test_play_skill_auto_loop_entry_point_also_feeds_the_credits_capture():
    """`play_skill` (what `LoopPlayer` actually calls every AUTO-LOOP
    cycle, per `loop_player.py:25,193`) delegates each cycle to
    `replay_skill` -- proves the capture survives through that OUTER
    entry point too, `floor=None` so only replay_skill's own per-step
    capture is exercised (the separate floor-check render path is its own
    site, proven independently -- see this module's docstring)."""
    session = _FakeAutoLoopSession([
        "Command [TL=00:12:30]:[100] (?=Help)? : ",
        "You have 250,000 credits.\nCommand [TL=00:12:31]:[100] (?=Help)? : ",
    ])

    result = skills.play_skill(session, _AUTOLOOP_SKILL, cycles=1, force=True)

    assert result["halted"] == "cycles_complete"
    assert session.last_credits == 250000


def test_play_skill_floor_check_render_also_feeds_the_credits_capture():
    """`play_skill`'s own pre-cycle floor-check render (skills.py, only
    taken when `floor` is set) is a distinct settled-screen site from
    `replay_skill`'s per-step loop -- proven independently here: the
    STARTING screen alone (before any step ever sends) already carries a
    balance, and `floor` is set well ABOVE it (500,000 <= floor) so the
    run halts on cycle 0, on the floor check itself, before `replay_skill`
    ever fires a single send."""
    session = _FakeAutoLoopSession(["You have 500,000 credits.\nCommand [TL=00:00:00]:[100] (?=Help)? : "])

    result = skills.play_skill(session, _AUTOLOOP_SKILL, cycles=5, floor=1_000_000, force=True)

    assert result["halted"] == "floor_reached"
    assert session.last_credits == 500000


# -- WO-FA7a revise 3, FIX 2 (mack-confirmed HIGH): negative-age race -------


def test_credits_age_ms_never_goes_negative_under_concurrent_access():
    """mack's HIGH thread-stress repro (scratchpad/repro_fa7a_race.py),
    formalized: a writer thread hammering `observe_credits()` concurrently
    with a reader thread hammering the `status` verb's `credits_age_ms`
    computation must never observe a negative age. protocol.py's fix
    snapshots `last_credits_ts` into a local ONCE, before reading
    `time.monotonic()`, so a race can only ever bias the reported age
    LARGER (staler), never negative."""
    session = FakeSession("You have 1 credits.\nCommand [TL=00:00:00]:[100] (?=Help)? : ")
    stop = threading.Event()
    negative_ages = []
    crashes = []
    reads = [0]

    def writer():
        n = 1
        while not stop.is_set():
            n += 1
            session.set_screen(f"You have {n} credits.\nCommand [TL=00:00:00]:[100] (?=Help)? : ")
            session.observe_credits(session.render_text(session.render()))

    def reader():
        while not stop.is_set():
            try:
                status = protocol.dispatch(session, "status", {}, FakeServer())
                reads[0] += 1
                age = status["credits_age_ms"]
                if age is not None and age < 0:
                    negative_ages.append(age)
            except Exception as e:  # noqa: BLE001 -- a crash under the race is itself a failure this test must catch
                crashes.append(repr(e))

    writer_thread = threading.Thread(target=writer)
    reader_thread = threading.Thread(target=reader)
    writer_thread.start()
    reader_thread.start()
    _real_time.sleep(1.0)
    stop.set()
    writer_thread.join()
    reader_thread.join()

    assert reads[0] > 0, "sanity: the reader thread must have actually gotten some status reads in"
    assert not crashes, f"status dispatch must never crash under concurrent observe_credits writes: {crashes}"
    assert not negative_ages, f"credits_age_ms must never go negative: {negative_ages}"
