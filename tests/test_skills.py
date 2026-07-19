"""Skill record/replay + playback tests (DESIGN-v2 §3 v2.1 item 11b/11d,
C3) -- no network. FakeReplaySession walks an ordered list of screens
keyed by send(), mirroring FakeLoginSession's settle-detection surface
(tests/test_login.py) but without the expect-assertion machinery replay
doesn't need."""

import time

import pytest

from twclient import skills
from twclient.settle import wait_for_settle


class FakeReplaySession:
    """`screens[0]` is the CURRENT screen before any send(); each send()
    advances to the next entry in `screens[1:]`. Once exhausted, stays on
    the final screen (models a settled target that doesn't change
    further, same convention as FakeLoginSession).

    The advance is DEFERRED to the next `sleep()` call rather than
    applied synchronously inside `send()` -- matching the more realistic
    async-response convention `test_settle.py`'s `StagedSession` already
    uses (a real Session's response bytes arrive later, over a separate
    reader path, never instantly at send()-time). This is load-bearing
    for `settle.send_and_confirm`'s idle-detection path (used by
    replay_skill for a step with no explicit `wait_prompt`, TW-02):
    `wait_for_settle` can only see an "idle" settle if `session.rx_count`
    genuinely increases AFTER its own polling starts -- a synchronous
    same-call bump (the old convention) would already be reflected in
    the `start_rx_count` it captures at its own start, so it would never
    observe a NEW arrival and would spin to "timeout" every time."""

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


class _RecordingLedger:
    """Stands in for the `ledger.LedgerWriter`-shaped object LANE-C
    (this project's sibling P0 lane) is extending `record_do()` with --
    `actor`/`session_id` (+ optional `intent`), all backward-compatible
    keyword defaults. This worktree's ledger.py doesn't have them yet
    (that lands from the sibling lane, proven at integration), so this
    fake pins down the EXACT interface skills.py codes against and lets
    a test assert on it directly, per the TW-04 interface contract."""

    def __init__(self):
        self.calls = []

    def record_do(self, pre_text, input_text, secret, post_text, settled_class, capture=None, actor=None, session_id=None):
        self.calls.append(
            dict(
                pre_text=pre_text,
                input_text=input_text,
                secret=secret,
                post_text=post_text,
                settled_class=settled_class,
                capture=capture,
                actor=actor,
                session_id=session_id,
            )
        )


# -- SkillRecorder (11b) ---------------------------------------------------


def test_skill_recorder_not_recording_by_default():
    recorder = skills.SkillRecorder()
    assert recorder.recording is False
    assert recorder.stop() is None  # no-op, not an error


def test_skill_recorder_start_stop_round_trip(tmp_path):
    recorder = skills.SkillRecorder(skills_dir=tmp_path)
    name = recorder.start("demo_trade_loop")
    assert name == "demo_trade_loop"
    assert recorder.recording is True

    recorder.record_step("T", None, "port_trade")
    recorder.record_step("B", None, "port_trade")
    recorder.record_step("hunter2", None, "main_command", secret=True)  # must be dropped

    result = recorder.stop()
    assert result["name"] == "demo_trade_loop"
    assert result["steps"] == 2  # the secret step never got recorded
    assert recorder.recording is False

    saved = skills.load_skill("demo_trade_loop", skills_dir=tmp_path)
    assert saved["source"] == "recorded"
    assert [s["input"] for s in saved["steps"]] == ["T", "B"]


def test_skill_recorder_start_while_recording_raises():
    recorder = skills.SkillRecorder()
    recorder.start("a")
    with pytest.raises(skills.SkillError):
        recorder.start("b")


def test_skill_recorder_auto_generates_name_when_omitted():
    recorder = skills.SkillRecorder()
    name = recorder.start(None)
    assert name.startswith("capture-")


def test_record_step_no_op_when_not_recording():
    recorder = skills.SkillRecorder()
    recorder.record_step("X", None, "unknown")  # must not raise, must not accumulate
    assert recorder._steps == []


# -- start_anchor persistence (TW-03) ---------------------------------------


def test_skill_recorder_persists_start_anchor_from_start_call(tmp_path):
    recorder = skills.SkillRecorder(skills_dir=tmp_path)
    recorder.start("anchored_capture", start_anchor=55)
    recorder.record_step("T", None, "port_trade")
    recorder.stop()
    loaded = skills.load_skill("anchored_capture", skills_dir=tmp_path)
    assert loaded["start_anchor"] == 55


def test_skill_recorder_start_anchor_defaults_to_none_when_omitted(tmp_path):
    recorder = skills.SkillRecorder(skills_dir=tmp_path)
    recorder.start("no_anchor_capture")
    recorder.record_step("T", None, "port_trade")
    recorder.stop()
    loaded = skills.load_skill("no_anchor_capture", skills_dir=tmp_path)
    assert loaded["start_anchor"] is None


def test_save_skill_persists_start_anchor(tmp_path):
    skills.save_skill(
        "anchored",
        [{"input": "A", "wait_prompt": None, "expected_post_class": "menu"}],
        start_anchor=7,
        skills_dir=tmp_path,
    )
    loaded = skills.load_skill("anchored", skills_dir=tmp_path)
    assert loaded["start_anchor"] == 7


def test_save_skill_start_anchor_defaults_to_none(tmp_path):
    skills.save_skill("unanchored", [], skills_dir=tmp_path)
    loaded = skills.load_skill("unanchored", skills_dir=tmp_path)
    assert loaded["start_anchor"] is None


# -- save/load + name safety -----------------------------------------------


def test_save_and_load_skill_round_trip(tmp_path):
    path = skills.save_skill("my_skill", [{"input": "A", "wait_prompt": None, "expected_post_class": "menu"}],
                              skills_dir=tmp_path)
    assert path.exists()
    loaded = skills.load_skill("my_skill", skills_dir=tmp_path)
    assert loaded["name"] == "my_skill"
    assert loaded["steps"][0]["input"] == "A"


def test_load_missing_skill_raises():
    with pytest.raises(skills.SkillError):
        skills.load_skill("does_not_exist", skills_dir="/nonexistent")


def test_skill_name_sanitized_for_path_traversal(tmp_path):
    path = skills.skill_path("../../etc/passwd", skills_dir=tmp_path)
    assert path.parent == tmp_path  # traversal characters stripped, stays inside skills_dir


def test_draft_and_real_skills_live_in_separate_dirs(tmp_path):
    skills_dir = tmp_path / "skills"
    drafts_dir = tmp_path / "skills" / "_drafts"
    skills.save_skill("real", [], skills_dir=skills_dir)
    skills.save_skill("draft", [], draft=True, drafts_dir=drafts_dir)
    assert (skills_dir / "real.json").exists()
    assert (drafts_dir / "draft.json").exists()


def test_record_then_replay_round_trip(tmp_path):
    """The full 11b loop, now including TW-03's start_anchor: SkillRecorder
    captures live steps (as protocol.py's `do` dispatch would feed them via
    `_record_skill_step`), tagged with the sector recording began in ->
    stop() persists it into the saved skill -> load_skill + replay_skill
    re-drives a FRESH fake session standing in that SAME sector and
    actually re-sends the same inputs."""
    recorder = skills.SkillRecorder(skills_dir=tmp_path)
    recorder.start("aegis_loop", start_anchor=42)
    recorder.record_step("T", None, "port_trade")
    recorder.record_step("B", None, "port_trade")
    recorder.record_step("Q", None, "sector_display")
    recorder.stop()

    skill = skills.load_skill("aegis_loop", skills_dir=tmp_path)
    assert skill["start_anchor"] == 42
    replay_session = FakeReplaySession(
        ["Sector : 42\nCommand [TL=00753:0/0/0/850]", "Fuel Ore trading port", "Fuel Ore trading port", "Sector : 42"]
    )
    results = skills.replay_skill(replay_session, skill)
    assert replay_session.sent == [("T", False), ("B", False), ("Q", False)]
    assert [r["actual"] for r in results] == ["port_trade", "port_trade", "sector_display"]


# -- replay_skill (11b) ------------------------------------------------------


def _skill(steps, start_anchor=None):
    return {"name": "t", "source": "recorded", "steps": steps, "start_anchor": start_anchor}


# These pre-date TW-03's start_anchor guard and aren't testing it -- every
# call below passes force=True (skills.SkillError's documented, explicit
# bypass for a skill with no start_anchor at all) purely to keep exercising
# the replay-mechanics behavior each test actually targets. The anchor
# guard itself gets its own dedicated tests further down.


def test_replay_skill_succeeds_when_every_step_matches_expected():
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]", "Sector : 100", "Command [TL=00753:0/0/0/849]"])
    skill = _skill(
        [
            {"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"},
            {"input": "Q", "wait_prompt": None, "expected_post_class": "main_command"},
        ]
    )
    results = skills.replay_skill(session, skill, force=True)
    assert [r["actual"] for r in results] == ["sector_display", "main_command"]
    assert session.sent == [("M", False), ("Q", False)]


def test_replay_skill_halts_on_post_class_divergence():
    # Step 1 expects "port_trade" but the second screen is a menu instead.
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]", "(A) Foo\n(B) Bar\nEnter your choice:"])
    skill = _skill([{"input": "T", "wait_prompt": None, "expected_post_class": "port_trade"}])
    with pytest.raises(skills.ReplayDivergence) as exc_info:
        skills.replay_skill(session, skill, force=True)
    err = exc_info.value
    assert err.step_i == 0
    assert err.expected == "port_trade"
    assert err.actual == "menu"
    assert err.reason == "post_class"
    assert err.as_dict()["step_i"] == 0


def test_replay_skill_halts_on_unmodeled_screen_even_without_expected():
    # No expected_post_class recorded, but the actual screen classifies
    # as "unknown" -- still a surprise (DESIGN-v2 11d).
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]", "some totally unrecognized gibberish screen"])
    skill = _skill([{"input": "Z", "wait_prompt": None, "expected_post_class": None}])
    with pytest.raises(skills.ReplayDivergence) as exc_info:
        skills.replay_skill(session, skill, force=True)
    assert exc_info.value.actual == "unknown"


def test_replay_skill_applies_params_via_format_substitution():
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]", "Sector : 500"])
    skill = _skill([{"input": "{qty}", "wait_prompt": None, "expected_post_class": "sector_display"}])
    skills.replay_skill(session, skill, params={"qty": "42"}, force=True)
    assert session.sent == [("42", False)]


def test_replay_skill_falls_back_to_literal_when_no_matching_param():
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]", "Sector : 500"])
    skill = _skill([{"input": "{unbound}", "wait_prompt": None, "expected_post_class": "sector_display"}])
    skills.replay_skill(session, skill, params={"other": "1"}, force=True)
    assert session.sent == [("{unbound}", False)]  # sent verbatim, never raised


# -- play_skill (11d) --------------------------------------------------------


def test_play_skill_runs_requested_cycles_and_reports_cycles_complete():
    # A 1-step skill cycled 3x -- screens list just needs enough entries
    # to keep classifying as sector_display through every send().
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]"] + ["Sector : 100"] * 3)
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"}])
    result = skills.play_skill(session, skill, cycles=3, force=True)
    assert result["halted"] == "cycles_complete"
    assert result["cycles_completed"] == 3
    assert len(result["trace"]) == 3


def test_play_skill_halts_on_surprise_mid_run():
    session = FakeReplaySession(
        ["Command [TL=00753:0/0/0/850]", "Sector : 100", "(A) Foo\n(B) Bar\nEnter your choice:"]
    )
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"}])
    result = skills.play_skill(session, skill, cycles=5, force=True)
    assert result["halted"] == "surprise"
    assert result["cycles_completed"] == 1  # cycle 0 (screen->sector_display) succeeded, cycle 1 diverged
    assert result["divergence"]["actual"] == "menu"


def test_play_skill_halts_on_floor_stop_loss():
    session = FakeReplaySession(["You have 40 credits."])  # already at/below floor before cycle 0 even starts
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": None}])
    result = skills.play_skill(session, skill, cycles=5, floor=50)
    assert result["halted"] == "floor_reached"
    assert result["cycles_completed"] == 0
    assert session.sent == []  # never even sent -- checked before the cycle ran


def test_play_skill_rejects_cycles_over_the_hard_cap():
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]"])
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": None}])
    with pytest.raises(skills.SkillError):
        skills.play_skill(session, skill, cycles=51)


# -- TW-03: start_anchor guard -----------------------------------------------


def test_replay_skill_refuses_when_current_sector_mismatches_start_anchor():
    # Recorded from sector 100; currently sitting in sector 200 -- the
    # exact near-miss shape (replayed verbatim from the wrong sector).
    session = FakeReplaySession(["Sector : 200\nCommand [TL=00753:0/0/0/850]", "Sector : 999"])
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"}], start_anchor=100)
    with pytest.raises(skills.ReplayDivergence) as exc_info:
        skills.replay_skill(session, skill)
    err = exc_info.value
    assert err.step_i == -1
    assert err.reason == "start_anchor_mismatch"
    assert err.expected == "sector:100"
    assert err.actual == "sector:200"
    assert session.sent == []  # zero keystrokes sent


def test_replay_skill_refuses_when_current_sector_cannot_be_determined():
    # The current screen has no "Sector :" text at all -- can't confirm
    # safety, so this is treated the same as a mismatch, not "assume ok".
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]", "Sector : 999"])
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"}], start_anchor=100)
    with pytest.raises(skills.ReplayDivergence) as exc_info:
        skills.replay_skill(session, skill)
    assert exc_info.value.actual == "sector:unknown"
    assert session.sent == []


def test_replay_skill_proceeds_when_current_sector_matches_start_anchor():
    session = FakeReplaySession(["Sector : 100\nCommand [TL=00753:0/0/0/850]", "Sector : 100"])
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"}], start_anchor=100)
    results = skills.replay_skill(session, skill)
    assert session.sent == [("M", False)]
    assert results[0]["actual"] == "sector_display"


def test_replay_skill_refuses_unanchored_skill_by_default():
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]", "Sector : 1"])
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": None}])  # start_anchor=None
    with pytest.raises(skills.SkillError) as exc_info:
        skills.replay_skill(session, skill)
    assert "missing_start_anchor" in str(exc_info.value)
    assert session.sent == []  # zero keystrokes sent -- never silently replayed unanchored


def test_replay_skill_force_bypasses_a_missing_start_anchor():
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]", "Sector : 1"])
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"}])
    results = skills.replay_skill(session, skill, force=True)
    assert session.sent == [("M", False)]
    assert results[0]["actual"] == "sector_display"


def test_replay_skill_force_does_not_bypass_a_detected_mismatch():
    # force=True is documented to waive ONLY the missing-anchor case --
    # it must never let a caller force past an actual detected mismatch.
    session = FakeReplaySession(["Sector : 200\nCommand [TL=00753:0/0/0/850]", "Sector : 999"])
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"}], start_anchor=100)
    with pytest.raises(skills.ReplayDivergence):
        skills.replay_skill(session, skill, force=True)
    assert session.sent == []


def test_play_skill_halts_on_start_anchor_mismatch_mid_run():
    """The loop returns to a DIFFERENT sector than it started in --
    TW-03's guard re-fires at the top of cycle 1 too (not just cycle 0),
    halting exactly like any other mid-run surprise rather than blindly
    sending cycle 1's first keystroke from the wrong place."""
    session = FakeReplaySession(["Sector : 100\nCommand [TL=00753:0/0/0/850]", "Sector : 105"])
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"}], start_anchor=100)
    result = skills.play_skill(session, skill, cycles=5)
    assert result["halted"] == "surprise"
    assert result["cycles_completed"] == 1  # cycle 0 succeeded (and left sector 105 behind)
    assert result["divergence"]["reason"] == "start_anchor_mismatch"
    assert session.sent == [("M", False)]  # cycle 1's send never happened


# -- TW-04: replay/play ledgering --------------------------------------------


def test_replay_skill_writes_one_ledger_row_per_step_with_trainer_actor():
    ledger = _RecordingLedger()
    session = FakeReplaySession(["Sector : 100\nCommand [TL=00753:0/0/0/850]", "Sector : 100", "Sector : 100"])
    skill = _skill(
        [
            {"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"},
            {"input": "Q", "wait_prompt": None, "expected_post_class": "sector_display"},
        ],
        start_anchor=100,
    )
    skills.replay_skill(session, skill, ledger=ledger, session_id="s-42")
    assert len(ledger.calls) == 2
    assert [c["input_text"] for c in ledger.calls] == ["M", "Q"]
    assert all(c["actor"] == "trainer" for c in ledger.calls)
    assert all(c["session_id"] == "s-42" for c in ledger.calls)
    assert all(c["secret"] is False for c in ledger.calls)
    # Never tagged with `capture` -- that field means "the live `tw
    # record` window" elsewhere in the ledger, and reusing it here would
    # corrupt protocol.py's demo-profit accounting (see replay_skill's
    # docstring).
    assert all(c["capture"] is None for c in ledger.calls)


def test_replay_skill_records_a_ledger_row_even_for_the_diverging_step():
    ledger = _RecordingLedger()
    session = FakeReplaySession(["Sector : 100\nCommand [TL=00753:0/0/0/850]", "(A) Foo\n(B) Bar\nEnter your choice:"])
    skill = _skill([{"input": "T", "wait_prompt": None, "expected_post_class": "port_trade"}], start_anchor=100)
    with pytest.raises(skills.ReplayDivergence):
        skills.replay_skill(session, skill, ledger=ledger, session_id="s-1")
    assert len(ledger.calls) == 1  # the surprising send is exactly the one worth a row
    assert ledger.calls[0]["settled_class"] == "menu"
    assert ledger.calls[0]["actor"] == "trainer"


def test_replay_skill_ledger_stays_a_no_op_when_not_provided():
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]", "Sector : 1"])
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": None}])
    # No ledger passed -- must not raise just because ledger is absent.
    skills.replay_skill(session, skill, force=True)


def test_play_skill_forwards_ledger_and_session_id_across_every_cycle():
    ledger = _RecordingLedger()
    session = FakeReplaySession(["Sector : 100\nCommand [TL=00753:0/0/0/850]"] + ["Sector : 100"] * 3)
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"}], start_anchor=100)
    result = skills.play_skill(session, skill, cycles=3, ledger=ledger, session_id="s-loop")
    assert result["halted"] == "cycles_complete"
    assert len(ledger.calls) == 3  # one row per cycle's one step
    assert all(c["actor"] == "trainer" and c["session_id"] == "s-loop" for c in ledger.calls)


# -- TW-02: send/settle race, routed through settle.send_and_confirm --------
#
# _AnimatedSession models a scripted (arrival_time, text) timeline WITHIN
# a single send() -- unlike FakeReplaySession's one-shot-per-send advance,
# this can represent a multi-stage transition (an animation, a slow
# multi-part redraw), which is what these two live incidents actually
# need. Kept local to this section rather than folded into the shared
# FakeReplaySession, which many unrelated tests above depend on for its
# simpler one-shot-per-send shape.


class _AnimatedSession:
    def __init__(self, pre_text, stages):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._text = pre_text
        self._stages = sorted(stages)
        self.sent = []

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        while self._stages and self._stages[0][0] <= self.t:
            _, text = self._stages.pop(0)
            self._text = text
            self.rx_count += 1
            self.last_rx = self.t

    def render(self):
        return self._text.split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._text

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, secret))


def test_replay_skill_mid_animation_screen_change_halts_cleanly_not_a_misfire():
    """TW-02 (the -75-alignment/false-halt class, settle.py's own module
    docstring): a still-transitioning screen (an animation, a slow
    multi-part redraw) can go quiet just long enough to satisfy the
    debounce window mid-transition, then keep changing. Before this
    fix, replay_skill classified whatever text happened to be on screen
    at that premature quiet moment and either pressed the NEXT step's
    send against it, or coincidentally matched expected_post_class --
    both a silent misfire. send_and_confirm's stability re-check must
    catch the continued change and refuse to confirm, so the step halts
    cleanly as its own distinct surprise (reason="confirm_failed"), not
    misclassified as an ordinary post_class divergence, and never
    pressed onward to a second send."""
    session = _AnimatedSession(
        "Command [TL=00753:0/0/0/850]",
        stages=[(0.05, "Docking sequence initiated..."), (0.5, "Docking sequence continues...")],
    )
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"}])
    with pytest.raises(skills.ReplayDivergence) as exc_info:
        skills.replay_skill(session, skill, force=True)
    err = exc_info.value
    assert err.step_i == 0
    assert err.reason == "confirm_failed"
    assert "unconfirmed_settle" in err.actual
    assert session.sent == [("M", False)]  # exactly one send -- never a misfired second step


def test_replay_skill_slow_hub_warp_does_not_false_halt_on_premature_idle():
    """TW-02 companion: a warp-animation frame goes quiet just long
    enough to satisfy debounce_ms mid-transition, well before the
    recorded step's own wait_prompt target text ever arrives.
    send_and_confirm must not treat that premature idle as proof
    nothing more is coming -- the step still succeeds once the real
    confirm evidence lands, however late (no false halt)."""
    session = _AnimatedSession(
        "Sector : 100\nCommand [TL=00753:0/0/0/850]",
        stages=[(0.05, "Warping...\nHub drive engaged."), (0.9, "Sector : 200")],
    )
    skill = _skill(
        [{"input": "M", "wait_prompt": r"Sector\s*:\s*200", "expected_post_class": "sector_display"}],
        start_anchor=100,
    )
    results = skills.replay_skill(session, skill)
    assert session.sent == [("M", False)]
    assert results[0]["actual"] == "sector_display"


def test_play_skill_treats_a_confirm_failure_as_a_surprise_halt():
    """play_skill wraps replay_skill in a generic `except
    ReplayDivergence` -- proves a confirm_failed divergence (not just an
    ordinary post_class divergence) is caught the same way, halting the
    loop cleanly with the trace-so-far intact rather than an uncaught
    exception escaping an unattended AUTO-LOOP-style run."""
    session = _AnimatedSession(
        "Command [TL=00753:0/0/0/850]",
        stages=[(0.05, "Docking sequence initiated..."), (0.5, "Docking sequence continues...")],
    )
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"}])
    result = skills.play_skill(session, skill, cycles=5, force=True)
    assert result["halted"] == "surprise"
    assert result["cycles_completed"] == 0
    assert result["divergence"]["reason"] == "confirm_failed"
