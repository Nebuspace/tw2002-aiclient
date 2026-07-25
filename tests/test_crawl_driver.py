"""Live-crawl driver tests — canon K3's two structural legs.

No network, no live daemon, mock session factory only. The crawler's own
correctness (the safety vocabulary, the never-commit guarantee across an
adversarial graph) is covered by tests/test_menu_crawler.py; the
chokepoint sweep and the adversarial allowlist attempts live in
tests/test_menu_crawl_chokepoint.py. What is proven HERE is what canon
locates in the driver rather than in the crawler
(canon/doctrine/action-safety-guards.md, "Read-only, never-commit crawl
gate (K3)"):

  Leg 1 — the sacrificial-only startup gate refuses "before opening a
          single connection or invoking the session factory even once".
          Proven by a session-factory SPY whose call count must be exactly
          zero at the moment of refusal, plus the absence of any file the
          driver would have created. Source order is not proof; a spy at
          zero is.

  Leg 2 — a stop signal lands at the next screen BOUNDARY, never mid-send.
          Proven by a shared event stream in which every send records its
          own start and end: at the instant the abort fires, every send
          that had begun had also finished, and no send ever follows.
"""

import json

import pytest

from tw2002_aiclient.menu.crawl_driver import (
    CrawlAborted,
    CrawlSafetyError,
    run_live_crawl,
)
from tw2002_aiclient.menu.knowledge import get_crawl_status, list_menu_nodes


class _EventLog:
    """A shared ordered record of everything the fixture observes, across
    every session the factory hands out. The ordering between `send_start`
    / `send_end` and the stop signal is what makes "never mid-send"
    falsifiable rather than asserted."""

    def __init__(self):
        self.events = []

    def record(self, kind, detail=None):
        self.events.append((kind, detail))

    def kinds(self):
        return [kind for kind, _ in self.events]

    def count(self, kind):
        return self.kinds().count(kind)


class _FakeCrawlSession:
    """A deterministic 3-screen graph: a root menu with one SAFE option
    ("V"iew -> a leaf), one HELP option ("H"elp -> a leaf), and one DENY
    option ("B"uy -> must never be sent, so it needs no transition).

    Deferred advance on `sleep()` — the convention `settle.send_and_confirm`
    and `settle.wait_until_settled` rely on. `rx_count`/`last_rx` start
    already settled, modelling a session handed over at a fully-rendered
    quiescent screen (login/negotiation already done)."""

    SCREENS = {
        "root": "(V)iew Something\n(H)elp\n(B)uy Fighters",
        "view_screen": "Just a status readout.\nNothing else to do here.",
        "help_screen": "Help text here.\nNothing else to do here.",
    }
    TRANSITIONS = {
        ("root", "V"): "view_screen",
        ("root", "H"): "help_screen",
        # deliberately no ("root", "B") -- it must never be sent
    }

    def __init__(self, event_log=None):
        self.t = 0.0
        self.rx_count = 1
        self.last_rx = -1.0
        self._id = "root"
        self.sent = []
        self._pending = None
        self._events = event_log

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self._pending is not None:
            key = self._pending
            self._pending = None
            self._id = self.TRANSITIONS.get((self._id, key), self._id)
            self.rx_count += 1
            self.last_rx = self.t

    def render(self):
        return self.SCREENS[self._id].split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self.SCREENS[self._id]

    def send(self, text, enter=True, secret=False):
        if self._events is not None:
            self._events.record("send_start", text)
        self.sent.append((text, enter, secret))
        self._pending = text
        if self._events is not None:
            self._events.record("send_end", text)


class _Profile:
    """Minimal profile stand-in.

    The driver reads the flag off whatever object it is handed and never
    imports the credentials module, so the gate is provable without any
    profile type existing — which is exactly the situation in this tree
    (see this file's companion note in the WO report: nothing currently
    plumbs `crawl_sacrificial` onto a profile object, so the gate refuses
    every live crawl, fail-closed and on purpose)."""

    def __init__(self, name="crawl_test_profile", crawl_sacrificial=False):
        self.name = name
        self.crawl_sacrificial = crawl_sacrificial


class _ProfileWithoutTheField:
    """A profile representation that has never heard of the flag — the
    real shape in this tree today."""

    def __init__(self, name="legacy_profile"):
        self.name = name


class _HostileBool:
    """An object whose truthiness cannot be evaluated. A gate that reaches
    for `bool()` would raise here instead of refusing."""

    def __bool__(self):
        raise RuntimeError("truthiness is not available")


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _paths(tmp_path):
    return tmp_path / "game_knowledge.json", tmp_path / "crawl.jsonl"


# -- Leg 1: the sacrificial-only startup gate ---------------------------------


def test_leg1_refusal_happens_with_the_session_factory_spy_at_exactly_zero(tmp_path):
    """Canon: the refusal happens "before opening a single connection or
    invoking the session factory even once". The spy counts every
    invocation; the assertion is that the count is zero, not that the
    check appears earlier in the source."""
    calls = []

    def spy_factory():
        calls.append(1)
        return _FakeCrawlSession()

    kpath, log_path = _paths(tmp_path)

    with pytest.raises(CrawlSafetyError):
        run_live_crawl(_Profile(crawl_sacrificial=False), spy_factory, path=kpath, log_path=log_path)

    assert calls == []


def test_leg1_refusal_leaves_no_file_the_driver_would_have_created(tmp_path):
    """The other half of "before opening a single connection": a refusal
    produces no log file and no knowledge store — zero side effects."""
    kpath, log_path = _paths(tmp_path)

    with pytest.raises(CrawlSafetyError):
        run_live_crawl(_Profile(crawl_sacrificial=False), _FakeCrawlSession, path=kpath, log_path=log_path)

    assert not log_path.exists()
    assert not kpath.exists()


def test_leg1_refusal_never_consults_the_caller_supplied_stop_hooks(tmp_path):
    """The gate is checked before abort_check / is_driver_fenced are ever
    consulted — a non-sacrificial profile refuses without touching any
    caller-supplied hook."""
    abort_calls = []
    fence_calls = []
    kpath, log_path = _paths(tmp_path)

    with pytest.raises(CrawlSafetyError):
        run_live_crawl(
            _Profile(crawl_sacrificial=False),
            _FakeCrawlSession,
            path=kpath,
            log_path=log_path,
            abort_check=lambda: abort_calls.append(1) or False,
            is_driver_fenced=lambda: fence_calls.append(1) or False,
        )

    assert abort_calls == []
    assert fence_calls == []


def test_leg1_profile_that_has_never_heard_of_the_flag_refuses(tmp_path):
    """Fail-closed by omission. This is the real shape in this tree today:
    no profile object carries `crawl_sacrificial` at all, so every live
    crawl refuses — which is the correct posture, not a gap."""
    calls = []
    kpath, log_path = _paths(tmp_path)

    with pytest.raises(CrawlSafetyError):
        run_live_crawl(
            _ProfileWithoutTheField(),
            lambda: calls.append(1),
            path=kpath,
            log_path=log_path,
        )

    assert calls == []
    assert not log_path.exists()


@pytest.mark.parametrize(
    "flag_value",
    [
        False,
        None,
        0,
        "",
        "false",   # a truthy STRING -- the archived `if not getattr(...)` shape would have let this crawl
        "true",    # likewise: a config value that never got coerced to a bool
        "yes",
        1,         # truthy int, still not an explicit True
        1.0,
        [1],
        object(),
    ],
)
def test_leg1_only_an_explicit_true_opens_the_gate(flag_value, tmp_path):
    """Fail-closed against a merely-truthy stand-in. A string `"false"` is
    truthy in Python; a gate written as `if not flag` would have opened on
    it. Only `True` is consent to press keys in a live world."""
    calls = []
    kpath, log_path = _paths(tmp_path)

    with pytest.raises(CrawlSafetyError):
        run_live_crawl(
            _Profile(crawl_sacrificial=flag_value),
            lambda: calls.append(1),
            path=kpath,
            log_path=log_path,
        )

    assert calls == []
    assert not log_path.exists()


def test_leg1_unevaluable_truthiness_refuses_rather_than_raising_through(tmp_path):
    """A profile whose flag cannot be coerced to a bool must REFUSE, not
    blow up: the gate never invokes `__bool__`, so a hostile object lands
    on the typed CrawlSafetyError like any other non-True value."""
    calls = []
    kpath, log_path = _paths(tmp_path)

    with pytest.raises(CrawlSafetyError):
        run_live_crawl(
            _Profile(crawl_sacrificial=_HostileBool()),
            lambda: calls.append(1),
            path=kpath,
            log_path=log_path,
        )

    assert calls == []


def test_leg1_refusal_survives_a_profile_with_no_name_attribute(tmp_path):
    """The refusal message must not itself raise on a profile object that
    lacks `.name` — a fail-closed gate that crashes with AttributeError
    instead of CrawlSafetyError is a gate a caller cannot handle."""

    class _Nameless:
        crawl_sacrificial = False

    kpath, log_path = _paths(tmp_path)

    with pytest.raises(CrawlSafetyError):
        run_live_crawl(_Nameless(), _FakeCrawlSession, path=kpath, log_path=log_path)


def test_leg1_gate_opens_for_a_genuinely_sacrificial_profile(tmp_path):
    """Non-vacuity for the whole Leg 1 block: the gate is not simply
    refusing everything unconditionally — an explicit True does crawl."""
    kpath, log_path = _paths(tmp_path)

    result = run_live_crawl(
        _Profile(crawl_sacrificial=True), _FakeCrawlSession, path=kpath, log_path=log_path, max_nodes=50
    )

    assert result["aborted"] is False
    assert result["nodes_visited"] == 3  # root + view_screen + help_screen
    assert log_path.exists()


# -- Leg 2: boundary-aligned abort --------------------------------------------


def test_leg2_abort_lands_between_sends_never_mid_send(tmp_path):
    """The load-bearing Leg 2 proof.

    Every send records `send_start` then `send_end` into one shared event
    stream; the stop signal records `abort_fired` into the same stream at
    the moment it first returns True. Three assertions together mean "at a
    screen boundary, never mid-send":

      * at least one send had already completed (non-vacuous — an abort on
        the very first factory call would prove nothing about mid-send);
      * at the abort's index every started send had finished;
      * no send event occurs after the abort at all.
    """
    events = _EventLog()
    real_factory_calls = []
    wrapper_calls = [0]

    def factory():
        real_factory_calls.append(1)
        return _FakeCrawlSession(event_log=events)

    def abort_check():
        wrapper_calls[0] += 1
        # Call 1 = the crawl's root open; call 2 = the first BFS replay;
        # call 3 = the re-anchor AFTER the first safe key was emitted, so
        # a completed send is already in the stream when this fires.
        fired = wrapper_calls[0] >= 3
        if fired:
            events.record("abort_fired")
        return fired

    kpath, log_path = _paths(tmp_path)
    result = run_live_crawl(
        _Profile(crawl_sacrificial=True),
        factory,
        path=kpath,
        log_path=log_path,
        abort_check=abort_check,
        max_nodes=50,
    )

    assert result["aborted"] is True

    kinds = events.kinds()
    abort_index = kinds.index("abort_fired")
    before = kinds[:abort_index]
    after = kinds[abort_index + 1:]

    assert before.count("send_end") >= 1, "vacuous: the abort fired before any send completed"
    assert before.count("send_start") == before.count("send_end"), "abort landed mid-send"
    assert "send_start" not in after and "send_end" not in after, "a send followed the abort"


def test_leg2_the_mid_send_detector_actually_detects_a_mid_send_stop():
    """Falsification of the detector above, not of the driver.

    The balanced-send assertion is only worth anything if it goes red on a
    stream where the stop genuinely landed between a send's start and its
    end. Run the identical comparison against exactly that synthetic
    stream and confirm it does."""
    kinds = ["send_start", "send_end", "send_start", "abort_fired", "send_end"]
    abort_index = kinds.index("abort_fired")
    before = kinds[:abort_index]

    assert before.count("send_start") != before.count("send_end")


def test_leg2_stop_signal_is_checked_ahead_of_the_real_session_factory(tmp_path):
    """Canon: "the driver adds the abort check *ahead* of the real session
    factory". The aborting invocation must therefore never reach the real
    factory — proven by the spy's count staying at the pre-abort value."""
    real_factory_calls = []
    wrapper_calls = [0]

    def factory():
        real_factory_calls.append(1)
        return _FakeCrawlSession()

    def abort_check():
        wrapper_calls[0] += 1
        return wrapper_calls[0] >= 3

    kpath, log_path = _paths(tmp_path)
    result = run_live_crawl(
        _Profile(crawl_sacrificial=True),
        factory,
        path=kpath,
        log_path=log_path,
        abort_check=abort_check,
        max_nodes=50,
    )

    assert result["aborted"] is True
    # 3 wrapper calls, but the 3rd aborted ahead of the real factory.
    assert wrapper_calls[0] == 3
    assert len(real_factory_calls) == 2


def test_leg2_abort_on_the_very_first_boundary_stops_before_any_send(tmp_path):
    """The earliest possible stop: fired on the crawl's own root open, so
    nothing is ever sent and only the connect phase was logged."""
    events = _EventLog()
    result = run_live_crawl(
        _Profile(crawl_sacrificial=True),
        lambda: _FakeCrawlSession(event_log=events),
        path=tmp_path / "game_knowledge.json",
        log_path=tmp_path / "crawl.jsonl",
        abort_check=lambda: True,
        max_nodes=50,
    )

    assert result["aborted"] is True
    assert result["screens_seen"] == 0
    assert events.count("send_start") == 0


def test_leg2_abort_reports_a_clean_stop_not_an_error(tmp_path):
    """An abort is the expected clean-stop path: it returns a result,
    never raises CrawlAborted out of the driver."""
    wrapper_calls = [0]

    def abort_check():
        wrapper_calls[0] += 1
        return wrapper_calls[0] >= 2

    kpath, log_path = _paths(tmp_path)
    result = run_live_crawl(
        _Profile(crawl_sacrificial=True),
        _FakeCrawlSession,
        path=kpath,
        log_path=log_path,
        abort_check=abort_check,
        max_nodes=50,
    )

    assert result["aborted"] is True
    assert result["aborted_reason"] == "abort_check requested a stop"
    assert result["nodes_visited"] is None
    assert result["emitted_keys"] == []
    assert result["send_log"] == []
    assert result["screens_seen"] == 1

    phases = [e["phase"] for e in _read_jsonl(log_path) if e["event"] == "phase"]
    assert phases == ["connect", "registered", "crawl_start", "aborted"]
    assert "done" not in phases
    assert not any(e["event"] == "summary" for e in _read_jsonl(log_path))


def test_leg2_driver_fence_is_an_independent_trigger_landing_the_same_way(tmp_path):
    """A human `tw attach` fencing the driver mid-crawl stops it at the
    next boundary via the identical clean path, with abort_check never
    tripping at all."""
    events = _EventLog()
    wrapper_calls = [0]

    def is_driver_fenced():
        wrapper_calls[0] += 1
        fired = wrapper_calls[0] >= 3
        if fired:
            events.record("abort_fired")
        return fired

    kpath, log_path = _paths(tmp_path)
    result = run_live_crawl(
        _Profile(crawl_sacrificial=True),
        lambda: _FakeCrawlSession(event_log=events),
        path=kpath,
        log_path=log_path,
        abort_check=lambda: False,
        is_driver_fenced=is_driver_fenced,
        max_nodes=50,
    )

    assert result["aborted"] is True
    assert "fenced" in result["aborted_reason"]

    kinds = events.kinds()
    abort_index = kinds.index("abort_fired")
    before, after = kinds[:abort_index], kinds[abort_index + 1:]
    assert before.count("send_end") >= 1
    assert before.count("send_start") == before.count("send_end")
    assert "send_start" not in after


def test_leg2_abort_check_and_fence_report_distinguishable_reasons(tmp_path):
    kpath, log_path = _paths(tmp_path)

    aborted = run_live_crawl(
        _Profile(crawl_sacrificial=True), _FakeCrawlSession,
        path=kpath, log_path=log_path, abort_check=lambda: True,
    )
    fenced = run_live_crawl(
        _Profile(crawl_sacrificial=True), _FakeCrawlSession,
        path=tmp_path / "k2.json", log_path=tmp_path / "l2.jsonl", is_driver_fenced=lambda: True,
    )

    assert aborted["aborted_reason"] != fenced["aborted_reason"]
    assert "abort_check" in aborted["aborted_reason"]
    assert "fenced" in fenced["aborted_reason"]


def test_leg2_crawl_aborted_never_escapes_the_driver(tmp_path):
    """CrawlAborted is an internal signal; a caller never has to catch it."""
    kpath, log_path = _paths(tmp_path)
    try:
        run_live_crawl(
            _Profile(crawl_sacrificial=True), _FakeCrawlSession,
            path=kpath, log_path=log_path, abort_check=lambda: True,
        )
    except CrawlAborted:  # pragma: no cover -- the failure this test exists to catch
        pytest.fail("CrawlAborted escaped run_live_crawl")


# -- the honest map: a partial crawl says so ----------------------------------


def test_completed_crawl_stamps_the_map_complete(tmp_path):
    kpath, log_path = _paths(tmp_path)
    run_live_crawl(
        _Profile(crawl_sacrificial=True), _FakeCrawlSession, path=kpath, log_path=log_path, max_nodes=50
    )

    status = get_crawl_status(kpath)
    assert status["status"] == "complete"
    assert status["nodes_visited"] == 3
    assert status["frontier_remaining"] == 0


def test_aborted_crawl_leaves_a_map_that_says_it_is_partial(tmp_path):
    """A half-completed crawl persists whatever it discovered. Without the
    stamp, an unvisited frontier node is indistinguishable from a genuine
    dead-end — the map would silently read as complete."""
    wrapper_calls = [0]

    def abort_check():
        wrapper_calls[0] += 1
        return wrapper_calls[0] >= 3

    kpath, log_path = _paths(tmp_path)
    result = run_live_crawl(
        _Profile(crawl_sacrificial=True),
        _FakeCrawlSession,
        path=kpath,
        log_path=log_path,
        abort_check=abort_check,
        max_nodes=50,
    )

    assert result["aborted"] is True
    # It really is a partial map: nodes were discovered before the stop.
    assert len(list_menu_nodes(kpath)) >= 1

    status = get_crawl_status(kpath)
    assert status["status"] == "aborted"
    assert status["reason"] == "abort_check requested a stop"


def test_truncated_crawl_is_stamped_truncated_not_complete(tmp_path):
    """The max_nodes rail stopping a walk with frontier still queued is
    the other way a map ends up partial."""
    kpath, log_path = _paths(tmp_path)
    result = run_live_crawl(
        _Profile(crawl_sacrificial=True), _FakeCrawlSession, path=kpath, log_path=log_path, max_nodes=1
    )

    assert result["truncated"] is True
    assert result["frontier_remaining"] > 0
    assert get_crawl_status(kpath)["status"] == "truncated"


def test_a_refused_crawl_never_stamps_anything(tmp_path):
    """The refusal path writes nothing at all, so it cannot leave a stamp
    claiming a crawl happened."""
    kpath, log_path = _paths(tmp_path)
    with pytest.raises(CrawlSafetyError):
        run_live_crawl(_Profile(crawl_sacrificial=False), _FakeCrawlSession, path=kpath, log_path=log_path)

    assert not kpath.exists()


def test_a_structural_failure_is_stamped_error_and_re_raised(tmp_path):
    """A genuine failure is observed and stamped, then re-raised — never
    swallowed into a result that looks like a finished crawl."""

    def exploding_factory():
        raise RuntimeError("the world went away")

    kpath, log_path = _paths(tmp_path)
    with pytest.raises(RuntimeError, match="the world went away"):
        run_live_crawl(
            _Profile(crawl_sacrificial=True), exploding_factory, path=kpath, log_path=log_path
        )

    status = get_crawl_status(kpath)
    assert status["status"] == "error"
    assert "the world went away" in status["reason"]

    phases = [e["phase"] for e in _read_jsonl(log_path) if e["event"] == "phase"]
    assert phases[-1] == "error"


# -- the live JSONL log --------------------------------------------------------


def test_log_is_well_formed_jsonl_with_the_expected_phase_sequence(tmp_path):
    kpath, log_path = _paths(tmp_path)
    run_live_crawl(
        _Profile(crawl_sacrificial=True), _FakeCrawlSession, path=kpath, log_path=log_path, max_nodes=50
    )

    events = _read_jsonl(log_path)
    assert events
    for e in events:
        assert "ts" in e and "event" in e

    phases = [e["phase"] for e in events if e["event"] == "phase"]
    assert phases == ["connect", "registered", "crawl_start", "done"]

    assert len([e for e in events if e["event"] == "screen"]) > 0
    summaries = [e for e in events if e["event"] == "summary"]
    assert len(summaries) == 1
    assert summaries[0]["nodes_visited"] == 3


def test_log_appends_across_repeated_runs_never_truncates(tmp_path):
    kpath, log_path = _paths(tmp_path)
    run_live_crawl(
        _Profile(crawl_sacrificial=True), _FakeCrawlSession, path=kpath, log_path=log_path, max_nodes=50
    )
    first = len(_read_jsonl(log_path))
    run_live_crawl(
        _Profile(crawl_sacrificial=True), _FakeCrawlSession, path=kpath, log_path=log_path, max_nodes=50
    )
    assert len(_read_jsonl(log_path)) > first


def test_the_driver_never_logs_a_password_shaped_field(tmp_path):
    """The log is an operator-tailed artifact; nothing about a crawl needs
    a credential in it. The driver is not handed one, and does not put the
    profile's own attributes into the log either."""
    kpath, log_path = _paths(tmp_path)
    profile = _Profile(crawl_sacrificial=True)
    profile.password = "hunter2-should-never-appear"  # noqa: S105 -- test-only sentinel

    run_live_crawl(profile, _FakeCrawlSession, path=kpath, log_path=log_path, max_nodes=50)

    assert "hunter2-should-never-appear" not in log_path.read_text(encoding="utf-8")


# -- the end-to-end never-commit guarantee still holds through this wiring ----


def test_driver_run_never_emits_a_state_changing_category(tmp_path):
    from tw2002_aiclient.menu import crawler

    kpath, log_path = _paths(tmp_path)
    result = run_live_crawl(
        _Profile(crawl_sacrificial=True), _FakeCrawlSession, path=kpath, log_path=log_path, max_nodes=50
    )

    # Non-vacuity: the fixture DOES offer a deny-classified option, and
    # the crawl DID press safe keys -- so the two assertions below are
    # about a real opportunity that was refused, not an empty run.
    assert crawler.classify_option_label("B", "Buy Fighters") == "buy"
    assert result["emitted_keys"]

    assert set(result["emitted_keys"]) <= crawler.SAFE_ALLOWLIST
    assert set(result["emitted_keys"]) & crawler.STATE_CHANGING_KEYS == set()
    assert kpath.exists()
    assert len(list_menu_nodes(kpath)) >= 3
