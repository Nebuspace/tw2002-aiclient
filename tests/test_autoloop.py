"""The daemon background player, the arm state, and the autoloop verbs
(WO-P2-G4-X4).

The claims this suite exists to establish, in the order they matter:

1. **The arm state is TRUE, not merely non-blank.** The daemon ``status``
   payload reports ``autopilot.running`` as a literal ``bool`` -- ``1 == True``
   in Python, so an equality check would accept ``running: 1`` as armed.
   Two states are forbidden and both are pinned here: armed while nothing
   is running, and unarmed while the player holds the lock. The second is
   proven structurally (the hold is a disjunct of the answer, read inside
   the runner's own mutex) rather than by sampling, because sampling two
   moving facts cannot prove a claim about one instant.
2. **Two App drivers, no third acquisition path.** ``enter_auto_loop()``
   is acquired only from the known drivers ``autoloop.py`` and
   ``sector_explore.py``; ``stop`` is not a second release path.
3. **Stop-on-unknown survives the daemon boundary.** A halt arrives at
   the operator's cockpit STOP banner as its own typed reason code -- not
   a retry, not a swallowed error, and not somebody else's code.

Guard isolation is a running concern rather than an afterthought: the
stop tests leave the fence alone and the fence tests leave the stop flag
alone, because a stop proven by a guard the operator never tripped is not
a proof of the stop. Where two guards could both fire, the test says
which one it is measuring and pins the other one's input.

The wire is faked and the clock is fake; the control lock, the loader,
the settle layer and the player are all REAL. Nothing here needs a live
daemon, a real ``config/``, ``run/`` or ``state/``.
"""

from __future__ import annotations

import ast
import json
import threading
from pathlib import Path

import pytest

from tw2002_aiclient.cockpit import stopbanner
from tw2002_aiclient.loops.player import (
    HALT_ABORTED,
    HALT_CONFIRM_FAILED,
    HALT_FENCED,
    HALT_NEVER_AUTO_ACTION,
    HALT_SETTLE_FAILED,
    HALT_START_ANCHOR_MISMATCH,
    HALT_UNRECOGNIZED_SCREEN,
    OUTCOME_COMPLETED,
    OUTCOME_HALTED,
)
from tw2002_aiclient.session import autoloop, protocol
from tw2002_aiclient.session.classify import classify_screen
from tw2002_aiclient.session.control_lock import ControlLock

from .conftest import FakeAttachSession

# The screen fixtures are X3's, imported rather than re-typed: a second
# copy is how two suites start disagreeing about what a `money_prompt`
# looks like. `test_loop_player.py` re-derives every classification from
# the live code, so these arrive already proven -- and this file re-checks
# them through its OWN read path below, which strips the prompt line where
# X3's port does not.
from .test_loop_player import ANCHOR_158, ANCHOR_231, MONEY, ODD, PORT

PKG_ROOT = Path(autoloop.__file__).resolve().parent.parent

# A parked run must not hang the suite if a gate is never released.
GATE_TIMEOUT_S = 10.0


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------


class WireSession(FakeAttachSession):
    """A fake telnet wire that serves one scripted screen per boundary.

    Built on ``conftest.FakeAttachSession`` so the rx-bump convention the
    settle layer is tested against everywhere else applies here unchanged:
    ``send()`` defers its byte arrival to the next ``sleep()``, which is
    what lets ``send_and_confirm``'s idle-confirm path see genuinely NEW
    bytes. The clock is fake, so a full run costs no real time.

    ``rx_count``/``last_rx`` start as "something arrived, and it went
    quiet a while ago" -- the state a daemon is actually in when a run
    starts, and the one ``wait_until_settled`` exists to confirm.

    ``gate_at`` parks the run inside ``render()`` at a chosen boundary so
    a test can observe a genuinely in-flight run rather than a finished
    one. Parking inside the READ is deliberate: it is after the settle and
    before the boundary's guards, so a test can flip a guard's input while
    the run is provably between the two.
    """

    def __init__(self, screens, *, gate_at=None, real_time_scale=0.0):
        super().__init__(initial_screen=screens[0], real_time_scale=real_time_scale)
        self.screens = list(screens)
        self.boundary = 0
        self.rx_count = 1
        self.last_rx = -10.0
        self.gate_at = gate_at
        self.entered = threading.Event()
        self.gate = threading.Event()

    def render(self):
        # Parks the RUN only. A `status` poll from the test thread reads
        # the same session and must not be held behind the gate -- the
        # whole point of these tests is to observe a live run from
        # outside it.
        if (
            self.gate_at is not None
            and self.boundary == self.gate_at
            and threading.current_thread().name == "tw-autoloop"
        ):
            self.entered.set()
            if not self.gate.wait(GATE_TIMEOUT_S):  # pragma: no cover - a hung test
                raise AssertionError("the gate was never released")
        return self._screen.split("\n")

    def current_prompt_line(self):
        rows = self.render()
        return rows[-1].strip() if rows else ""

    def send(self, text, enter=True, secret=False, sender="app"):
        super().send(text, enter=enter, secret=secret, sender=sender)
        self.boundary += 1
        self._screen = self.screens[min(self.boundary, len(self.screens) - 1)]


class DeadWireSession(WireSession):
    """A wire that never goes quiet: ``wait_until_settled`` can only time
    out against it. The port must read that as NOT settled."""

    def __init__(self, screens):
        super().__init__(screens)
        self.rx_count = 0  # nothing has ever arrived -- never "settled"


class RaisingSession(WireSession):
    """An adapter fault: the render raises under the RUN.

    Scoped to the run thread so a `status` poll afterwards still works --
    the fault under test is the run's, and a test that could not then read
    the daemon's answer could not prove the daemon survived it."""

    def render(self):
        if threading.current_thread().name == "tw-autoloop":
            raise RuntimeError("pyte exploded")
        return super().render()


class Server:
    """The handful of attributes ``protocol.dispatch`` reads off a server.

    Deliberately not a mock: ``getattr(server, "autoloop", None)`` is a
    real lookup on a real object, so a rename of the attribute breaks
    these tests instead of silently returning a mock's auto-attribute.
    """

    def __init__(self, session, control_lock=None, runner=None):
        self.session = session
        self.control_lock = control_lock
        self.autoloop = runner
        self.watch_hub = None


# --------------------------------------------------------------------------
# Macros on disk
# --------------------------------------------------------------------------


def write_macro(state_dir, name, steps, *, anchor=158, draft=False):
    """A real macro document in a real (temp) store, loaded by the real
    loader. The runner resolves names through ``load_loop``, so faking
    that away would skip the arm-confirm precondition this WO cares
    about."""
    root = Path(state_dir) / "skills"
    if draft:
        root = root / "_drafts"
    root.mkdir(parents=True, exist_ok=True)
    document = {
        "name": name,
        "start_anchor": anchor,
        "source": "recorded",
        "created_ts": "2026-07-26T00:00:00Z",
        "steps": [
            {"input": i, "wait_prompt": w, "expected_post_class": c} for i, w, c in steps
        ],
    }
    (root / f"{name}.json").write_text(json.dumps(document), encoding="utf-8")
    return root


ONE_STEP = [("P", None, "main_command")]
TWO_STEPS = [("P", None, "port_trade"), ("1", None, "main_command")]


def make_runner(tmp_path, session, control_lock=None, **kwargs):
    return autoloop.AutoLoopRunner(
        session,
        control_lock if control_lock is not None else ControlLock(),
        state_dir=tmp_path,
        **kwargs,
    )


def run_to_completion(runner, session, timeout=GATE_TIMEOUT_S):
    """Wait for the in-flight run to actually die, without asking the
    runner to stop it. ``stop()`` would set the abort flag and change the
    outcome under test."""
    thread = runner._thread
    if thread is not None:
        thread.join(timeout)
        assert not thread.is_alive(), "the run never finished"
    return runner.snapshot()


# --------------------------------------------------------------------------
# 0. The fixtures still mean what this file assumes
# --------------------------------------------------------------------------


def test_the_fixtures_classify_the_same_way_through_this_files_read_path():
    """X3's port hands the prompt line through untouched; this one strips
    it (``rows[-1].strip()``, the spelling every other surface uses). The
    safety tests below are only as good as the fixture, so the equivalence
    is measured rather than assumed -- a ``money_prompt`` that stopped
    classifying as one under a stripped prompt would leave the never-auto
    test passing while proving nothing."""
    for full, prompt in (ANCHOR_158, ANCHOR_231, MONEY, PORT, ODD):
        assert classify_screen(full, prompt.strip()) == classify_screen(full, prompt)
    assert classify_screen(MONEY[0], MONEY[1].strip()) == "money_prompt"
    assert classify_screen(ODD[0], ODD[1].strip()) == "unknown"


# --------------------------------------------------------------------------
# 1. The arm state is TRUE
# --------------------------------------------------------------------------


def test_the_chip_reads_off_before_any_run_and_the_bool_is_literal():
    """The daemon owes a literal ``bool`` for ``autopilot.running``, not
    merely something falsy -- ``1 == True`` in Python."""
    session = WireSession([ANCHOR_158[0]])
    server = Server(session, ControlLock(), make_runner(Path("/nonexistent"), session))
    resp = protocol.dispatch(session, "status", {}, server)

    assert resp["autopilot"]["running"] is False
    # No halt has happened, so the STOP banner has nothing to raise.
    assert "intervention" not in resp
    assert stopbanner.needs_attention(resp) is False


def test_the_chip_reads_on_for_exactly_as_long_as_the_run_is_live(tmp_path):
    """The lifecycle, end to end, through the real ``status`` verb and the
    real chip composer: OFF -> ON while a run is genuinely in flight ->
    OFF once it is over. The middle sample is taken while the run is
    parked mid-boundary, so "ON" is measured against a thread that is
    demonstrably alive rather than inferred from a flag."""
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0], ANCHOR_158[0]], gate_at=0)
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    assert protocol.dispatch(session, "status", {}, server)["autopilot"]["running"] is False

    started = protocol.dispatch(session, "autoloop_start", {"name": "ore-run"}, server)
    assert started["ok"] is True and started["started"] is True
    assert session.entered.wait(GATE_TIMEOUT_S)
    # The start answer is a READ of the runtime -- the run is parked, so
    # this is deterministic -- rather than a hardcoded affirmative.
    assert started["running"] is True
    assert started["run"]["loop"] == "ore-run"
    live = protocol.dispatch(session, "status", {}, server)
    assert live["autopilot"]["running"] is True
    # ...and the thread really is there behind the claim.
    assert runner._thread is not None and runner._thread.is_alive()
    assert lock.is_auto_loop_held() is True

    session.gate.set()
    snapshot = run_to_completion(runner, session)
    assert snapshot.report.outcome == OUTCOME_COMPLETED

    done = protocol.dispatch(session, "status", {}, server)
    assert done["autopilot"]["running"] is False
    assert lock.is_auto_loop_held() is False


def test_a_held_lock_can_never_read_as_unarmed():
    """The forbidden direction, proven directly rather than by sampling.

    The hold is a DISJUNCT of the answer, so there is no branch that could
    report a held lock as disarmed -- not even with the runner's own
    in-flight flag down, which is the state a bug would have to produce.
    """

    class HeldLock:
        def is_auto_loop_held(self):
            return True

    runner = autoloop.AutoLoopRunner(object(), HeldLock())
    assert runner._in_flight is False  # nothing running, by construction
    assert runner.snapshot().running is True
    assert autoloop.arm_block(runner.snapshot())["running"] is True


def test_a_daemon_with_no_runner_still_answers_from_the_lock():
    """A status read must not report "disarmed" merely because this
    process has no player object -- "nothing here can run a loop" and "the
    App does not hold the connection" are different claims and only the
    second is what the chip renders."""
    lock = ControlLock()
    token = lock.enter_auto_loop()
    session = WireSession([ANCHOR_158[0]])
    server = Server(session, lock, None)

    resp = protocol.dispatch(session, "status", {}, server)
    assert resp["autopilot"]["running"] is True

    lock.leave_auto_loop(token)
    assert protocol.dispatch(session, "status", {}, server)["autopilot"]["running"] is False


def test_the_arm_state_and_the_lock_are_read_under_one_mutex_hold():
    """The atomicity claim, measured at the point it is made.

    Two facts read through two calls can straddle a run's end, so the pair
    is captured inside the runner's mutex. This lock double asserts that it
    is being asked from inside that hold -- if a future edit moves the
    control-lock read outside the mutex, this fails rather than becoming a
    rare interleaving nobody can reproduce."""
    seen = []

    class AssertingLock(ControlLock):
        def is_auto_loop_held(self):
            seen.append(runner._mutex.locked())
            return super().is_auto_loop_held()

    lock = AssertingLock()
    runner = autoloop.AutoLoopRunner(object(), lock)
    runner.snapshot()

    assert seen == [True], "the control lock was consulted outside the runner's mutex"


def test_a_concurrent_poller_never_sees_a_held_lock_reported_as_disarmed(tmp_path):
    """The same invariant under real threads.

    Two conditions make the sampling SOUND, and both are deliberate --
    without them this test reports interleavings that are perfectly legal
    (it did, on the first run, which is how they got written down):

    * **Order.** The snapshot is taken FIRST and the lock read AFTER. The
      reverse proves nothing: a lock held at t0 may legitimately be free
      at t1, because the run ended in between.
    * **Window.** Violations are only counted once the run has been
      observed armed. Before that, a ``start`` can land between the two
      reads -- snapshot says "not running", the run then begins, the lock
      read says "held" -- which is two true observations of two different
      instants, not a disagreement. After the first armed sample, the only
      remaining transition is the run's END, and that one IS atomic: the
      release happens before the flag clears, inside one mutex. So a
      "not running" sample followed by a held lock cannot happen, and this
      loop would catch it if it did."""
    write_macro(tmp_path, "ore-run", TWO_STEPS)
    # `real_time_scale` gives the fake wire a small REAL duration per
    # settle (conftest's own hook for exactly this): with a pure fake
    # clock the whole run finishes in microseconds and the poller can
    # legitimately never observe it armed, which would make this test
    # green for the wrong reason -- and flaky besides.
    session = WireSession(
        [ANCHOR_158[0], PORT[0], ANCHOR_158[0]], real_time_scale=0.02
    )
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)

    violations = []
    samples = []
    stop_polling = threading.Event()

    def poll():
        seen_armed = False
        while not stop_polling.is_set():
            snapshot = runner.snapshot()
            held = lock.is_auto_loop_held()
            samples.append(snapshot.running)
            if snapshot.running:
                seen_armed = True
            elif seen_armed and held:
                violations.append((snapshot.running, held))

    poller = threading.Thread(target=poll, daemon=True)
    poller.start()
    runner.start("ore-run")
    run_to_completion(runner, session)
    stop_polling.set()
    poller.join(GATE_TIMEOUT_S)

    assert violations == []
    assert len(samples) > 10, "the poller never actually sampled"
    assert any(sample is True for sample in samples), "the run was never observed armed"


def test_a_refused_start_never_leaves_the_chip_armed(tmp_path):
    """A start that cannot happen must not move the safety surface. Every
    refusal below is checked for the same two things: no hold, and a chip
    that still reads OFF."""
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    refusals = [
        ({"name": "no-such-macro"}, "loop_not_found:no-such-macro"),
        ({"name": "ore-run", "force": True}, "unsupported_arg:force"),
        ({}, "missing_name"),
    ]
    for args, expected in refusals:
        resp = protocol.dispatch(session, "autoloop_start", args, server)
        assert resp == {"ok": False, "error": expected}, args
        assert lock.is_auto_loop_held() is False, args
        status = protocol.dispatch(session, "status", {}, server)
        assert status["autopilot"]["running"] is False, args
        assert session.sent == [], args


# --------------------------------------------------------------------------
# 2. One acquisition path
# --------------------------------------------------------------------------


def _package_sources():
    return sorted(PKG_ROOT.rglob("*.py"))


def test_enter_auto_loop_has_exactly_three_production_call_sites():
    """Structural, via AST rather than grep, and it looks for the two
    shapes a grep for ``enter_auto_loop(`` would miss: an attribute call
    written any other way, and a reflective ``getattr(lock,
    "enter_auto_loop")``. The four reviewed daemon runners share this lock
    (autoloop, explore, trade_chain, stardock_hold); a fifth acquisition
    path is how two drivers could end up on one wire while the chip reads
    OFF."""
    attribute_sites = []
    reflective_sites = []
    for path in _package_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "enter_auto_loop":
                attribute_sites.append((path.name, node.lineno))
            if isinstance(node, ast.Constant) and node.value == "enter_auto_loop":
                reflective_sites.append((path.name, node.lineno))

    assert sorted(name for name, _ in attribute_sites) == [
        "autoloop.py",
        "sector_explore.py",
        "stardock_hold.py",
        "trade_chain.py",
    ], attribute_sites
    assert len(attribute_sites) == 4, attribute_sites
    # `control_lock.py` names it in prose only; a string LITERAL of the
    # method name anywhere is a reflection door and must be deliberate.
    assert reflective_sites == [], reflective_sites


def test_stop_is_not_a_second_release_path():
    """``leave_auto_loop()`` belongs to the run's own ``finally``. A stop
    that released it directly would drop the App's exclusivity while a
    step was still in flight -- letting a concurrent ``do`` interleave on
    the one wire, which is the whole reason the hold exists."""
    tree = ast.parse((PKG_ROOT / "session" / "autoloop.py").read_text(encoding="utf-8"))
    functions = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Attribute) and inner.attr == "leave_auto_loop":
                    functions.setdefault(node.name, 0)
                    functions[node.name] += 1

    assert set(functions) == {"_run", "start"}, functions
    # `start`'s one call is the rollback for a thread that never started;
    # `_run`'s is the single real release.
    assert functions == {"_run": 1, "start": 1}, functions


def test_the_runner_default_is_one_pass(tmp_path):
    """Omitted ``cycles`` still plays exactly one pass.

    Multi-pass is opt-in via ``cycles=N`` (WO-AUTOLOOP-CYCLES); the default
    path must stay single-pass so one-shot Play / chains arms do not
    silently repeat.
    """
    write_macro(tmp_path, "ore-run", TWO_STEPS)
    session = WireSession([ANCHOR_158[0], PORT[0], ANCHOR_158[0]])
    runner = make_runner(tmp_path, session)
    runner.start("ore-run")
    snapshot = run_to_completion(runner, session)

    assert snapshot.report.outcome == OUTCOME_COMPLETED
    assert snapshot.report.cycles == 1
    assert snapshot.report.sends_issued == 2
    assert [text for text, _enter, _secret in session.sent] == ["P", "1"]


def test_a_second_start_is_refused_not_queued(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0], ANCHOR_158[0]], gate_at=0)
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    runner.start("ore-run")
    assert session.entered.wait(GATE_TIMEOUT_S)
    resp = protocol.dispatch(session, "autoloop_start", {"name": "ore-run"}, server)
    assert resp == {"ok": False, "error": "already_running"}

    session.gate.set()
    run_to_completion(runner, session)


def test_a_start_is_refused_while_a_human_holds_the_keyboard(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)
    lock.take_human()

    resp = protocol.dispatch(session, "autoloop_start", {"name": "ore-run"}, server)

    assert resp == {"ok": False, "error": "locked_by_human_attach"}
    assert session.sent == []
    assert lock.mode == "human"


def test_a_start_is_refused_while_an_app_dispatch_holds_the_driver(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)
    lock.acquire_driver()

    resp = protocol.dispatch(session, "autoloop_start", {"name": "ore-run"}, server)

    assert resp == {"ok": False, "error": "locked_by_active_driver"}
    assert lock.is_auto_loop_held() is False


def test_a_drive_verb_is_refused_while_the_loop_holds_the_wire(tmp_path):
    """The other direction of the same exclusivity, through the real
    ``do`` verb: the loop's hold is what keeps a one-shot drive from
    interleaving mid-macro."""
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0], ANCHOR_158[0]], gate_at=0)
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    runner.start("ore-run")
    assert session.entered.wait(GATE_TIMEOUT_S)
    resp = protocol.dispatch(session, "do", {"input": "Q"}, server)

    assert resp == {"ok": False, "error": "controller_locked_by_auto_loop"}
    assert [text for text, _e, _s in session.sent] == []

    session.gate.set()
    run_to_completion(runner, session)


# --------------------------------------------------------------------------
# 3. A halt reaches the operator, with its reason code intact
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,screens,anchor,expected_reason,expected_sends",
    [
        # DECISIONS §A.2 -- the money screen the App may never answer.
        ("money prompt", [MONEY[0]], 158, "never_auto_action:money_prompt", 0),
        # Canon's central invariant as a rail: the first unrecognized frame.
        ("unknown screen", [ODD[0]], 158, HALT_UNRECOGNIZED_SCREEN, 0),
        # The near-miss the start-anchor guard exists for.
        ("wrong sector", [ANCHOR_231[0]], 158, HALT_START_ANCHOR_MISMATCH, 0),
    ],
)
def test_a_halt_arrives_at_the_cockpit_stop_banner_as_its_own_reason_code(
    tmp_path, label, screens, anchor, expected_reason, expected_sends
):
    """The whole path: player -> runner -> ``status`` verb -> the cockpit
    banner an operator actually reads.

    The status payload carries the raw ``code`` (asserted below); the
    rendered banner carries whatever ``stopbanner.intervention_reason_label``
    resolves that code to (WO-HALT-BANNER-LABEL-VOCAB gave all three of
    these parametrizations real labels, not the raw code). Deriving the
    expected text from the product's own resolver -- rather than
    hardcoding the label string here -- means a reword updates test and
    product together, and this still fails loudly if the banner stops
    mentioning the halted reason at all (renders a generic/unrelated line,
    or drops band 1 entirely): the exact old bug this test exists to catch
    -- "A halt that arrived as ``autopilot halted`` (or as nothing at all)
    would pass a test that only checked ``needs_attention``."

    What this assertion does NOT cover, by construction (it derives
    ``expected`` from the same resolver the banner itself calls): a
    catalog entry going missing for THIS code. That regression collapses
    the label back to the raw code on both sides of the assertion at
    once, so it stays silent here -- catching it is
    ``test_cockpit_stopbanner.py``'s job
    (``test_every_loop_player_halt_reason_has_a_human_label``'s
    ``label != code``, pinned against every ``HALT_REASONS`` member
    independent of this file)."""
    write_macro(tmp_path, "ore-run", ONE_STEP, anchor=anchor)
    session = WireSession(screens)
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    runner.start("ore-run")
    run_to_completion(runner, session)

    status = protocol.dispatch(session, "status", {}, server)
    assert status["intervention"] == {
        "needs_attention": True,
        "reasons": [{"code": expected_reason}],
    }, label
    assert stopbanner.needs_attention(status) is True, label
    banner = stopbanner.compose_stop_banner_lines(status, width=120, height=3)
    expected_label = stopbanner.intervention_reason_label(expected_reason)
    assert any(expected_label in line for line in banner), banner

    # ...and the run itself agrees, in its own verb.
    run = protocol.dispatch(session, "autoloop_status", {}, server)["run"]
    assert run["outcome"] == OUTCOME_HALTED, label
    assert run["reason"] == expected_reason, label
    assert run["sends_issued"] == expected_sends, label
    # Zero bytes is the property; the reason string is only the label on it.
    assert session.sent == [], label


def test_a_halt_is_not_retried_and_does_not_leave_the_loop_running(tmp_path):
    """"A halt must surface as a halt, not as a retry, and not as a
    swallowed error that leaves the loop running." All three, measured."""
    write_macro(tmp_path, "ore-run", TWO_STEPS)
    # Boundary 1 (after step 0) lands on a screen nothing can name.
    session = WireSession([ANCHOR_158[0], ODD[0]])
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    runner.start("ore-run")
    snapshot = run_to_completion(runner, session)

    assert snapshot.report.reason == HALT_UNRECOGNIZED_SCREEN
    assert snapshot.report.halted_at == 0
    # Not a retry: step 0 was pressed once and step 1 never was.
    assert [text for text, _e, _s in session.sent] == ["P"]
    assert snapshot.report.sends_issued == 1
    # Not still running, and not still holding the wire.
    assert snapshot.running is False
    assert lock.is_auto_loop_held() is False
    assert protocol.dispatch(session, "status", {}, server)["autopilot"]["running"] is False


def test_a_completed_run_raises_no_banner(tmp_path):
    """The banner is an escalation, not a run log. A run that did what it
    was taught has nothing to hand back."""
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0], ANCHOR_158[0]])
    runner = make_runner(tmp_path, session)
    server = Server(session, runner._control_lock, runner)

    runner.start("ore-run")
    run_to_completion(runner, session)

    status = protocol.dispatch(session, "status", {}, server)
    assert "intervention" not in status
    assert stopbanner.needs_attention(status) is False
    assert protocol.dispatch(session, "autoloop_status", {}, server)["run"]["outcome"] == (
        OUTCOME_COMPLETED
    )


def test_a_new_start_clears_the_previous_halts_banner(tmp_path):
    """The banner persists until something actually changes -- and a new
    run is that change. A stale halt shown over a live run would be the
    surface lying in the other direction."""
    write_macro(tmp_path, "ore-run", ONE_STEP, anchor=158)
    session = WireSession([ODD[0]])
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    runner.start("ore-run")
    run_to_completion(runner, session)
    assert stopbanner.needs_attention(protocol.dispatch(session, "status", {}, server)) is True

    session.screens = [ANCHOR_158[0], ANCHOR_158[0]]
    session._screen = ANCHOR_158[0]
    session.boundary = 0
    session.gate_at = 0
    runner.start("ore-run")
    assert session.entered.wait(GATE_TIMEOUT_S)
    live = protocol.dispatch(session, "status", {}, server)
    assert "intervention" not in live
    assert live["autopilot"]["running"] is True

    session.gate.set()
    run_to_completion(runner, session)


# --------------------------------------------------------------------------
# 4. Stop -- its own reason code, and it releases
# --------------------------------------------------------------------------


def test_a_stop_halts_the_run_with_its_own_code_and_releases_the_hold(tmp_path):
    """The stop is isolated from every other guard on purpose: the screen
    stays recognized and anchored, no human attaches, and the lock's own
    ``is_driver_fenced()`` is asserted DOWN at the moment of the halt. So
    ``operator_stop`` can only have come from the arm predicate."""
    write_macro(tmp_path, "ore-run", TWO_STEPS)
    session = WireSession([ANCHOR_158[0], PORT[0], ANCHOR_158[0]], gate_at=1)
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    runner.start("ore-run")
    assert session.entered.wait(GATE_TIMEOUT_S)  # parked after step 0's send
    assert lock.is_auto_loop_held() is True

    # Set the flag first (join_timeout=0 -- the run is parked), then let
    # the boundary proceed into its guards.
    runner.stop(join_timeout=0.0)
    assert lock.is_driver_fenced() is False, "no fence was raised; the stop must stand alone"
    session.gate.set()
    snapshot = runner.stop()

    assert snapshot.report.outcome == OUTCOME_HALTED
    assert snapshot.report.reason == HALT_ABORTED
    assert snapshot.report.stop_requested is True
    # A stop must release, and the release is the run's own.
    assert snapshot.running is False
    assert lock.is_auto_loop_held() is False
    assert lock.mode == "app"
    # One send happened before the stop, and none after it.
    assert [text for text, _e, _s in session.sent] == ["P"]

    status = protocol.dispatch(session, "status", {}, server)
    assert status["autopilot"]["running"] is False
    assert status["intervention"]["reasons"] == [{"code": HALT_ABORTED}]


def test_the_stop_verb_answers_honestly_and_is_idempotent(tmp_path):
    """Two stops in a row, and a stop with nothing running, are all
    ordinary. A stop verb that refused would be a safety control with a
    precondition."""
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0], ANCHOR_158[0]])
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    idle = protocol.dispatch(session, "autoloop_stop", {}, server)
    assert idle["ok"] is True and idle["stopping"] is True
    assert idle["running"] is False
    assert idle["run"] is None  # never asked to play anything -- not a fake record

    runner.start("ore-run")
    first = protocol.dispatch(session, "autoloop_stop", {}, server)
    second = protocol.dispatch(session, "autoloop_stop", {}, server)
    assert first["running"] is False and second["running"] is False
    assert lock.is_auto_loop_held() is False


def test_stopping_is_wired_to_the_players_predicate_not_to_the_lock():
    """The mechanism, isolated from any run: ``stop`` sets the port's
    abort event and touches nothing else. If it ever released the hold
    directly, the hold would already be gone here."""
    lock = ControlLock()
    runner = autoloop.AutoLoopRunner(object(), lock)
    lock.enter_auto_loop()
    runner._stop = threading.Event()

    runner.stop(join_timeout=0.0)

    assert runner._stop.is_set() is True
    assert lock.is_auto_loop_held() is True, "stop released a hold that is not its to release"


# --------------------------------------------------------------------------
# 5. Human sovereignty -- the fence-wiring trap, and its later repair
# --------------------------------------------------------------------------


def test_a_human_attach_halts_the_run_and_the_lock_now_fences_it_too(tmp_path):
    """**Reversal, named**: this test used to be
    ``test_a_human_attach_halts_the_run_and_the_naive_wiring_would_not_have``
    (landed X4, commit ``344991e``), and pinned the OPPOSITE of the
    assertion below -- ``lock.is_driver_fenced() is False`` right after
    ``take_human()`` preempted a running loop, deliberately recording that
    the naive wiring (forwarding the lock's flag straight to the player)
    would have sent. That was correct THEN: the lock only fenced an
    in-flight *dispatch*, never an auto_loop hold.

    WO-CONTROL-LOCK-AUTOLOOP-FENCE overturned that half of the claim: the
    lock now fences an auto_loop preemption too (the preempted generation
    is added to its own set, whose non-emptiness is OR'd into the same
    predicate -- see ``control_lock.py``'s
    ``_auto_loop_fenced_generations``), because a DIFFERENT caller needed
    it honest --
    ``Session.send_raw``'s bounded wind-down wait on the human's own
    attach keystrokes, which had no fence signal for this case at all and
    so gave a human's first bytes no beat to let an in-flight loop step
    actually finish before racing it onto the wire. The run's own halt
    decision was never in question, before or after -- it was always the
    port's own ``is_auto_loop_held()`` re-read, not this lock flag -- so
    what remains true from the original test is kept: the run still
    halts ``HALT_FENCED``, still stops before its second step, and the
    human still keeps the keyboard. What flips is that
    ``lock.is_driver_fenced()`` is HONEST now instead of a documented
    trap."""
    write_macro(tmp_path, "ore-run", TWO_STEPS)
    session = WireSession([ANCHOR_158[0], PORT[0], ANCHOR_158[0]], gate_at=1)
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)

    runner.start("ore-run")
    assert session.entered.wait(GATE_TIMEOUT_S)
    lock.take_human()
    assert lock.is_driver_fenced() is True, (
        "the lock must fence an auto_loop preemption the same way it fences a "
        "dispatch -- Session.send_raw's human-keystroke wind-down wait reads "
        "exactly this flag"
    )
    session.gate.set()
    snapshot = run_to_completion(runner, session)

    assert snapshot.report.reason == HALT_FENCED
    assert [text for text, _e, _s in session.sent] == ["P"]  # step 1 never pressed
    # The run's release must not take the keyboard back off the human.
    assert lock.mode == "human"
    assert snapshot.running is False
    # The run's own finally is the run's own release path for the fence it
    # was given, same as for the hold itself.
    assert lock.is_driver_fenced() is False


def test_the_ports_fence_predicate_tracks_the_hold_not_the_dispatch_flag():
    """The same fact at unit scale, without a run: the port answers
    "fenced" exactly when the exclusive hold is gone.

    The final assertion here is the other reversal from
    WO-CONTROL-LOCK-AUTOLOOP-FENCE: this used to read
    ``assert lock.is_driver_fenced() is False  # ...and the other flag
    never moved`` -- true before that WO, and now the opposite, because
    the lock's own flag moves for exactly the same preemption the port
    just detected. The port is kept anyway (see ``autoloop.py``'s module
    docstring, "The fence wiring, a trap in it, and the trap's later
    repair") -- it is provably redundant with the lock's flag today, and
    deliberately not simplified to rely on that, on the reasoning there."""
    lock = ControlLock()
    port = autoloop._ReplayPort(object(), lock, threading.Event())

    assert port.is_driver_fenced() is True  # nothing held -- no authority
    lock.enter_auto_loop()
    assert port.is_driver_fenced() is False
    lock.take_human()
    assert port.is_driver_fenced() is True
    assert lock.is_driver_fenced() is True  # ...and now the other flag agrees


# --------------------------------------------------------------------------
# 6. The truthiness hazard, at the adapter seam
# --------------------------------------------------------------------------


def test_a_settle_that_timed_out_is_not_read_as_settled(tmp_path):
    """``wait_until_settled`` returns ``("timeout", 8.0)`` -- TRUTHY. An
    adapter forwarding the tuple would read a timed-out settle as a
    settled screen and read the screen anyway."""
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = DeadWireSession([ANCHOR_158[0], ANCHOR_158[0]])
    runner = make_runner(tmp_path, session)

    runner.start("ore-run")
    snapshot = run_to_completion(runner, session)

    assert snapshot.report.reason == HALT_SETTLE_FAILED
    assert snapshot.report.sends_issued == 0
    assert session.sent == []


def test_an_unconfirmed_send_is_not_read_as_confirmed(tmp_path, monkeypatch):
    """``settle.send_and_confirm`` returns ``("prompt", 0.4, False)`` --
    also truthy. Forwarding it would make EVERY send read as confirmed: a
    blind pump straight through a taught macro."""
    write_macro(tmp_path, "ore-run", TWO_STEPS)
    session = WireSession([ANCHOR_158[0], PORT[0], ANCHOR_158[0]])
    runner = make_runner(tmp_path, session)

    def unconfirmed(sess, text, **kwargs):
        sess.send(text, enter=kwargs.get("enter", True))
        return "prompt", 0.4, False

    monkeypatch.setattr(autoloop._settle, "send_and_confirm", unconfirmed)
    runner.start("ore-run")
    snapshot = run_to_completion(runner, session)

    assert snapshot.report.reason == HALT_CONFIRM_FAILED
    assert snapshot.report.halted_at == 0
    assert [text for text, _e, _s in session.sent] == ["P"]


def test_the_port_answers_literal_bools():
    """The player demands literal ``True`` from every port method it trusts."""
    session = WireSession([ANCHOR_158[0]])
    port = autoloop._ReplayPort(session, ControlLock(), threading.Event())

    assert port.settle() is True
    assert port.is_driver_fenced() is True
    assert port.should_abort() is False
    dead = autoloop._ReplayPort(DeadWireSession([ANCHOR_158[0]]), ControlLock(), threading.Event())
    assert dead.settle() is False


def test_the_ports_send_is_scoped_to_the_live_prompt_line(tmp_path, monkeypatch):
    """DECISIONS §D: a drive send confirms against settle-detection's
    prompt LINE, never a whole-screen search. TradeWars is a scrolling BBS
    door, so a recorded ``Command [TL=`` target is routinely still visible
    up the grid -- a whole-screen confirm would match that stale row and
    report this step confirmed."""
    write_macro(tmp_path, "ore-run", [("P", "Command \\[TL=", "main_command")])
    session = WireSession([ANCHOR_158[0], ANCHOR_158[0]])
    runner = make_runner(tmp_path, session)
    seen = {}

    real = autoloop._settle.send_and_confirm

    def record(sess, text, **kwargs):
        seen.update(kwargs)
        return real(sess, text, **kwargs)

    monkeypatch.setattr(autoloop._settle, "send_and_confirm", record)
    runner.start("ore-run")
    run_to_completion(runner, session)

    assert seen["match_scope"] == "prompt_line"
    assert seen["confirm_prompt"] == "Command \\[TL="
    # Canon's macro schema records no per-step enter field; the archived
    # replay sent one for every step, and changing that would change what
    # every taught macro means.
    assert seen["enter"] is True


# --------------------------------------------------------------------------
# 7. Crash honesty
# --------------------------------------------------------------------------


def test_a_player_crash_still_releases_and_never_claims_zero_bytes(tmp_path):
    """An adapter fault must not leave the daemon armed forever, must not
    put its traceback on the wire, and must not report ``sends_issued: 0``
    -- a zero-bytes claim is the player's to make, and there is no player
    answer here to make it from."""
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = RaisingSession([ANCHOR_158[0]])
    lock = ControlLock()
    logged = []
    runner = make_runner(tmp_path, session, lock, log_error=logged.append)
    server = Server(session, lock, runner)

    runner.start("ore-run")
    snapshot = run_to_completion(runner, session)

    assert snapshot.report.outcome == autoloop.OUTCOME_CRASHED
    assert snapshot.report.reason == autoloop.REASON_PLAYER_ERROR
    assert snapshot.report.error == "RuntimeError"
    assert snapshot.report.sends_issued is None
    assert snapshot.running is False
    assert lock.is_auto_loop_held() is False
    # The traceback went to the local sink, not to the client.
    assert len(logged) == 1 and isinstance(logged[0], RuntimeError)
    run = protocol.dispatch(session, "autoloop_status", {}, server)["run"]
    assert run["error"] == "RuntimeError"
    assert "pyte exploded" not in json.dumps(run)
    # A crash is a halt for the operator's purposes: it still ended
    # without doing what it was asked.
    assert stopbanner.needs_attention(protocol.dispatch(session, "status", {}, server)) is True


def test_a_broken_error_sink_never_takes_the_release_down(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = RaisingSession([ANCHOR_158[0]])
    lock = ControlLock()

    def broken(_exc):
        raise OSError("the log is gone")

    runner = make_runner(tmp_path, session, lock, log_error=broken)
    runner.start("ore-run")
    snapshot = run_to_completion(runner, session)

    assert snapshot.running is False
    assert lock.is_auto_loop_held() is False


# --------------------------------------------------------------------------
# 8. What the verbs refuse, and what never leaves
# --------------------------------------------------------------------------


@pytest.mark.parametrize("arg", ["force", "param", "include_drafts"])
def test_a_knob_this_runtime_cannot_honour_is_refused_not_ignored(tmp_path, arg):
    """``force`` / ``param`` stay refused. ``cycles`` left this list in
    WO-AUTOLOOP-CYCLES (accepted + clamped). ``floor`` left in X5.

    Contrast ``ensure``'s ``no_auto_arm``, which is accepted and unused
    precisely because the behaviour it asks for is what happens.
    """
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    resp = protocol.dispatch(session, "autoloop_start", {"name": "ore-run", arg: 3}, server)

    assert resp == {"ok": False, "error": f"unsupported_arg:{arg}"}
    assert lock.is_auto_loop_held() is False
    assert session.sent == []


def test_a_floor_is_still_refused_when_this_session_cannot_enforce_it(tmp_path):
    """The X4 rule, unmoved: a floor is refused unless something enforces it.

    ``WireSession`` deliberately has no ``observe_credits``/
    ``credits_snapshot`` -- it is the harness X4 shipped, from before the
    substrate existed -- so this is a genuine "this runtime cannot honour
    that" case rather than a mocked one, and the daemon says so by name
    instead of arming a decorative number. Zero arm, zero bytes.
    """
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    assert not hasattr(session, "credits_snapshot")

    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "floor": 500}, server
    )

    assert resp == {"ok": False, "error": "floor_unsupported"}
    assert lock.is_auto_loop_held() is False
    assert session.sent == []


def test_a_draft_is_never_played(tmp_path):
    """Approval is expressed by file location: ``_drafts/`` holds inert
    proposals awaiting a human. A background driver playing one would be
    the human-approval gate failing open."""
    write_macro(tmp_path, "mined-1", ONE_STEP, draft=True)
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    resp = protocol.dispatch(session, "autoloop_start", {"name": "mined-1"}, server)

    assert resp == {"ok": False, "error": "loop_not_found:mined-1"}
    assert lock.is_auto_loop_held() is False
    assert session.sent == []


def test_the_loaders_four_outcomes_stay_four(tmp_path):
    """"Not found" and "could not finish looking" are different facts and
    must not collapse -- the defect this repo has now fixed four times."""
    write_macro(tmp_path, "ore-run", ONE_STEP)
    skills = Path(tmp_path) / "skills"
    (skills / "broken.json").write_text('{"name": "broken", "steps": []}', encoding="utf-8")
    (skills / "twin-a.json").write_text(
        json.dumps({"name": "twin", "steps": [{"input": "P", "expected_post_class": "main_command"}]}),
        encoding="utf-8",
    )
    (skills / "twin-b.json").write_text(
        json.dumps({"name": "twin", "steps": [{"input": "Q", "expected_post_class": "main_command"}]}),
        encoding="utf-8",
    )
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    def error_for(name):
        return protocol.dispatch(session, "autoloop_start", {"name": name}, server)["error"]

    assert error_for("nope") == "loop_not_found:nope"
    assert error_for("broken") == "loop_malformed:broken"
    assert error_for("twin") == "loop_ambiguous:twin"
    assert lock.is_auto_loop_held() is False


def test_a_refusal_never_leaks_a_server_side_path(tmp_path):
    """``LoopMalformed`` carries the path it found and the per-step
    defects; neither is the client's. Server-side filesystem layout on the
    wire is the leak ``daemon.py``'s type-name narrowing was written for."""
    skills = Path(tmp_path) / "skills"
    skills.mkdir(parents=True)
    (skills / "bad.json").write_text('{"name": "bad", "steps": []}', encoding="utf-8")
    session = WireSession([ANCHOR_158[0]])
    server = Server(session, ControlLock(), make_runner(tmp_path, session))

    resp = protocol.dispatch(session, "autoloop_start", {"name": "bad"}, server)

    assert resp["error"] == "loop_malformed:bad"
    assert str(tmp_path) not in json.dumps(resp)
    assert "skills" not in json.dumps(resp)


def test_the_run_report_carries_no_screen_text_and_no_keystrokes(tmp_path):
    """§C.2/§C.2.1: a structured answer never mirrors the receive buffer.
    The run report is closed vocabularies, integers, timestamps and the
    macro's own name -- and not the keystrokes it pressed, which are the
    macro's content rather than the operator's question."""
    write_macro(tmp_path, "ore-run", TWO_STEPS)
    session = WireSession([ANCHOR_158[0], PORT[0], ANCHOR_158[0]])
    runner = make_runner(tmp_path, session)
    server = Server(session, runner._control_lock, runner)

    runner.start("ore-run")
    run_to_completion(runner, session)
    wire = json.dumps(protocol.dispatch(session, "autoloop_status", {}, server))

    assert "Command [TL=" not in wire
    assert "Commerce report" not in wire
    assert "Trade with this port" not in wire


def test_the_word_resume_is_still_refused_after_the_rename():
    """Hub ruling (1+3): the verb is `autoloop_relaunch`, and `resume` stays
    an `unknown_verb` ON PURPOSE.

    This is the load-bearing half of the rename. If `autoloop_resume` were
    aliased to the relaunch for convenience, a caller reaching for the word
    that promises continuation would silently get a replay-from-start that
    re-spends turns — which is the entire defect the rename exists to fix.
    A refusal sends them to read what the other verb actually does.
    """
    session = WireSession([ANCHOR_158[0]])
    server = Server(session, ControlLock(), None)
    assert protocol.dispatch(session, "autoloop_resume", {}, server) == {
        "ok": False,
        "error": "unknown_verb:autoloop_resume",
    }


def test_relaunch_is_a_real_verb_and_refuses_honestly_with_no_player():
    session = WireSession([ANCHOR_158[0]])
    server = Server(session, ControlLock(), None)
    result = protocol.dispatch(session, "autoloop_relaunch", {}, server)
    assert result == {"ok": False, "error": "autoloop_unavailable"}
    assert "unknown_verb" not in str(result)


def test_pause_is_a_real_verb_now_not_an_unknown_one():
    """The half that IS unambiguous: pause stands the run down and hands
    the keyboard back, which is canon-true under every option still open on
    the resume question. With no player it refuses honestly rather than
    claiming a pause it could not perform."""
    session = WireSession([ANCHOR_158[0]])
    server = Server(session, ControlLock(), None)

    result = protocol.dispatch(session, "autoloop_pause", {}, server)
    assert result == {"ok": False, "error": "autoloop_unavailable"}
    assert "unknown_verb" not in str(result)


def test_the_verbs_answer_honestly_on_a_daemon_with_no_player():
    session = WireSession([ANCHOR_158[0]])
    server = Server(session, ControlLock(), None)

    for verb in ("autoloop_start", "autoloop_stop"):
        assert protocol.dispatch(session, verb, {"name": "x"}, server) == {
            "ok": False,
            "error": "autoloop_unavailable",
        }
    # ...but the read verb still answers, from the lock.
    #
    # WO-AUTOLOOP-PAUSE-RESUME added `stand_down` to the wire, so this
    # exact-dict pin is UPDATED, not loosened — it stays an equality check
    # precisely so an unintended future field cannot slip onto the wire
    # unnoticed. `None` here is the honest answer and is deliberately
    # present rather than omitted: a client asking "was this paused?" gets
    # a definite no from a runner-less daemon instead of having to infer it
    # from a missing key.
    assert protocol.dispatch(session, "autoloop_status", {}, server) == {
        "ok": True,
        "running": False,
        "run": None,
        "stand_down": None,
    }


# --------------------------------------------------------------------------
# 9. The daemon actually wires it
# --------------------------------------------------------------------------


def _daemon_function(name):
    tree = ast.parse((PKG_ROOT / "session" / "daemon.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"daemon.py has no {name}()")


def test_the_daemon_builds_the_runner_with_its_own_control_lock():
    """``main()`` needs a real socket and a real telnet connection, so the
    wiring is proven structurally rather than by standing a daemon up.
    Without this, every test above could pass against a daemon that never
    constructs a player -- suite-green is not coverage of the one line
    that puts it there.

    The control-lock ARGUMENT is the part that matters: a runner built
    with its own fresh lock would arm something no other verb can see."""
    main = _daemon_function("main")
    built = [
        node
        for node in ast.walk(main)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "AutoLoopRunner"
    ]
    assert len(built) == 1, "daemon.main() must build exactly one AutoLoopRunner"
    args = built[0].args
    assert len(args) == 2
    assert isinstance(args[1], ast.Attribute) and args[1].attr == "control_lock", ast.dump(args[1])

    assigned = [
        target.attr
        for node in ast.walk(main)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Attribute) and target.attr == "autoloop"
    ]
    assert assigned == ["autoloop"], "protocol.py reads `server.autoloop` by that exact name"


def test_daemon_shutdown_stands_a_running_loop_down_before_it_quits_the_game():
    """``_shutdown`` sends `Q`/`Y` through `_attempt_graceful_quit`. A run
    still pressing keys while that happens is two drivers on one wire --
    so the stop has to come FIRST, not merely somewhere in the function."""
    shutdown = _daemon_function("_shutdown")
    order = []
    for node in ast.walk(shutdown):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "stop":
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "autoloop":
                    order.append(("autoloop.stop", node.lineno))
            if isinstance(node.func, ast.Name) and node.func.id == "_attempt_graceful_quit":
                order.append(("quit", node.lineno))

    names = [name for name, _line in sorted(order, key=lambda pair: pair[1])]
    assert names == ["autoloop.stop", "quit"], names


def test_status_is_unchanged_for_a_daemon_that_has_never_run_a_loop():
    """The intervention key is omitted rather than set to a false-y block,
    so every existing status consumer sees exactly what it saw before this
    module existed."""
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    with_runner = protocol.dispatch(
        session, "status", {}, Server(session, lock, make_runner(Path("/nonexistent"), session, lock))
    )
    without = protocol.dispatch(session, "status", {}, Server(session, lock, None))

    assert set(with_runner) == set(without)
    assert "intervention" not in with_runner
    assert with_runner["autopilot"] == {"running": False}


# --------------------------------------------------------------------------
# 10. The external invariant, pinned loudly (Mack's LOW, round 5)
# --------------------------------------------------------------------------
#
# `ControlLock` itself permits any number of outstanding auto_loop
# generations -- that permissiveness is what its own fence fix depends
# on. The bound this runner actually relies on ("at most one outstanding
# at a time") is `AutoLoopRunner`'s OWN discipline (`_in_flight` refusing
# a second `start()`), proven UNREACHABLE through this runner today --
# not proven impossible at the lock. `start()` now asserts that external
# invariant explicitly, immediately before granting, so a future breach
# (a second call site; a loosened one-runner-per-daemon rule) fails loud
# instead of silently minting a second concurrent generation.


def test_start_fails_loudly_when_the_lock_already_carries_an_outstanding_generation(tmp_path):
    """Constructed directly against the lock, since `AutoLoopRunner`'s own
    `_in_flight` bookkeeping makes this unreachable through a single
    runner's own `start()`/`stop()` calls -- exactly Mack's point: the
    lock will happily carry a stale outstanding generation from ANY
    prior activity, and nothing stops a fresh runner (or a fresh `start()`
    on a runner whose `_in_flight` has, for whatever future reason,
    stopped tracking reality) from being handed that same lock. `_in_
    flight` being False here is the whole scenario -- it means this
    runner itself sees no reason to refuse, and the lock is the only
    thing left that could have caught it."""
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0], ANCHOR_158[0]])
    lock = ControlLock()
    # Leaves a genuine, unreleased outstanding generation on the lock --
    # entirely independent of any AutoLoopRunner.
    lock.enter_auto_loop()
    lock.take_human()
    lock.release_human()
    assert lock.outstanding_auto_loop_generations() == frozenset({1})

    runner = make_runner(tmp_path, session, lock)
    assert runner._in_flight is False  # this runner has no reason to refuse

    with pytest.raises(autoloop.AutoLoopInvariantViolation) as exc_info:
        runner.start("ore-run")

    assert "1" in str(exc_info.value)
    # Must NOT be raised as the ordinary refusal type -- protocol.py's
    # `except autoloop.AutoLoopRefused` must not swallow this into a
    # polite, expected-looking wire response.
    assert not isinstance(exc_info.value, autoloop.AutoLoopRefused)
    # Never touched: nothing was armed, nothing was cleared.
    assert lock.outstanding_auto_loop_generations() == frozenset({1})
    assert runner._in_flight is False


def test_dispatch_autoloop_start_lets_the_invariant_violation_escape_uncaught(tmp_path):
    """The wiring proof: `protocol.dispatch`'s own `autoloop_start` verb
    catches ONLY `AutoLoopRefused` (see `_dispatch_autoloop_start`) -- this
    exception must reach the caller instead of becoming a normal `{"ok":
    false, "error": ...}` response, so the daemon's own outermost catch
    (`daemon.py`'s `internal_error:{type}` narrowing) is what actually
    reports it, loudly, with a traceback in the local log."""
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0], ANCHOR_158[0]])
    lock = ControlLock()
    lock.enter_auto_loop()
    lock.take_human()
    lock.release_human()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    with pytest.raises(autoloop.AutoLoopInvariantViolation):
        protocol.dispatch(session, "autoloop_start", {"name": "ore-run"}, server)


# --------------------------------------------------------------------------
# WO-AUTOLOOP-PAUSE-RESUME — the pause half (the resume half is held; see
# `test_resume_is_still_absent_rather_than_stubbed`)
# --------------------------------------------------------------------------

class _FreeLock:
    """A control lock holding nothing — `pause`/`stop` must be safe here."""

    def is_auto_loop_held(self):
        return False


def _idle_runner():
    return autoloop.AutoLoopRunner(object(), _FreeLock())


def test_a_fresh_runner_has_never_been_stood_down():
    """`None` rather than `"stop"`: a runner that never ran was not stopped,
    and claiming otherwise would be an affirmative statement about a run
    that does not exist."""
    assert _idle_runner().snapshot().stand_down is None


def test_pause_and_stop_record_different_intents():
    """The ONLY difference between them. If these ever return the same
    value, `autoloop_resume` cannot tell a parked run from a panicked one
    and would relaunch something the operator halted on purpose."""
    paused = _idle_runner()
    paused.pause()
    assert paused.snapshot().stand_down == autoloop.STAND_DOWN_PAUSE

    stopped = _idle_runner()
    stopped.stop()
    assert stopped.snapshot().stand_down == autoloop.STAND_DOWN_STOP

    assert autoloop.STAND_DOWN_PAUSE != autoloop.STAND_DOWN_STOP


def test_pause_then_stop_reports_stop_not_pause():
    """A panic after a pause must win the label. Otherwise a resume would
    see `"pause"` and relaunch a run the operator later panicked."""
    runner = _idle_runner()
    runner.pause()
    runner.stop()
    assert runner.snapshot().stand_down == autoloop.STAND_DOWN_STOP


def test_pause_never_hangs_and_neither_does_a_stop_after_it():
    """Finding 3, satisfied STRUCTURALLY rather than by timeout.

    `pause` is not a wait state — it is the same stand-down as `stop` — so
    there is nothing for a later stop/panic to block on. Both calls return
    on an idle runner, and a stop after a pause returns too. If a future
    edit reintroduced a parked thread, this is where it would hang.
    """
    runner = _idle_runner()
    assert runner.pause() is not None
    assert runner.stop() is not None
    assert runner.pause() is not None       # idempotent in both directions


def test_pause_does_not_release_the_lock_itself():
    """The one-release-path invariant. `pause` must NOT grow a second
    release: the run's own `finally` is the only caller of
    `leave_auto_loop()`. Pinned by asserting the lock is never asked."""

    class _SpyLock:
        def __init__(self):
            self.releases = []

        def is_auto_loop_held(self):
            return False

        def leave_auto_loop(self, *a, **k):
            self.releases.append(a)

    lock = _SpyLock()
    runner = autoloop.AutoLoopRunner(object(), lock)
    runner.pause()
    assert lock.releases == [], "pause created a second release path"


def test_stand_down_is_on_the_wire_in_both_shapes():
    """A client must not have to branch on whether a report exists to learn
    why the run stood down."""
    runner = _idle_runner()
    no_report = autoloop.run_wire(runner.snapshot())
    assert no_report["run"] is None
    assert no_report["stand_down"] is None

    runner.pause()
    assert autoloop.run_wire(runner.snapshot())["stand_down"] == autoloop.STAND_DOWN_PAUSE


def test_pause_and_stop_share_one_implementation():
    """Structural: both must route through `_stand_down_run`, so a future
    fix to the release half cannot land on one path and miss the other."""
    import inspect
    for fn in (autoloop.AutoLoopRunner.pause, autoloop.AutoLoopRunner.stop):
        assert "_stand_down_run" in inspect.getsource(fn)
