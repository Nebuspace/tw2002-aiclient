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
    further, same convention as FakeLoginSession)."""

    def __init__(self, screens):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._screens = screens
        self._i = 0
        self.sent = []

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds

    def render(self):
        return self._screens[self._i].split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._screens[self._i]

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350):
        return wait_for_settle(self, wait_prompt=wait_prompt, timeout_s=timeout, debounce_ms=debounce_ms)

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, secret))
        if self._i < len(self._screens) - 1:
            self._i += 1
        self.rx_count += 1
        self.last_rx = self.t


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
    """The full 11b loop: SkillRecorder captures live steps (as
    protocol.py's `do` dispatch would feed them via `_record_skill_step`)
    -> stop() saves the skill -> load_skill + replay_skill re-drives a
    FRESH fake session and actually re-sends the same inputs."""
    recorder = skills.SkillRecorder(skills_dir=tmp_path)
    recorder.start("aegis_loop")
    recorder.record_step("T", None, "port_trade")
    recorder.record_step("B", None, "port_trade")
    recorder.record_step("Q", None, "sector_display")
    recorder.stop()

    skill = skills.load_skill("aegis_loop", skills_dir=tmp_path)
    replay_session = FakeReplaySession(
        ["Command [TL=00753:0/0/0/850]", "Fuel Ore trading port", "Fuel Ore trading port", "Sector : 42"]
    )
    results = skills.replay_skill(replay_session, skill)
    assert replay_session.sent == [("T", False), ("B", False), ("Q", False)]
    assert [r["actual"] for r in results] == ["port_trade", "port_trade", "sector_display"]


# -- replay_skill (11b) ------------------------------------------------------


def _skill(steps):
    return {"name": "t", "source": "recorded", "steps": steps}


def test_replay_skill_succeeds_when_every_step_matches_expected():
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]", "Sector : 100", "Command [TL=00753:0/0/0/849]"])
    skill = _skill(
        [
            {"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"},
            {"input": "Q", "wait_prompt": None, "expected_post_class": "main_command"},
        ]
    )
    results = skills.replay_skill(session, skill)
    assert [r["actual"] for r in results] == ["sector_display", "main_command"]
    assert session.sent == [("M", False), ("Q", False)]


def test_replay_skill_halts_on_post_class_divergence():
    # Step 1 expects "port_trade" but the second screen is a menu instead.
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]", "(A) Foo\n(B) Bar\nEnter your choice:"])
    skill = _skill([{"input": "T", "wait_prompt": None, "expected_post_class": "port_trade"}])
    with pytest.raises(skills.ReplayDivergence) as exc_info:
        skills.replay_skill(session, skill)
    err = exc_info.value
    assert err.step_i == 0
    assert err.expected == "port_trade"
    assert err.actual == "menu"
    assert err.as_dict()["step_i"] == 0


def test_replay_skill_halts_on_unmodeled_screen_even_without_expected():
    # No expected_post_class recorded, but the actual screen classifies
    # as "unknown" -- still a surprise (DESIGN-v2 11d).
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]", "some totally unrecognized gibberish screen"])
    skill = _skill([{"input": "Z", "wait_prompt": None, "expected_post_class": None}])
    with pytest.raises(skills.ReplayDivergence) as exc_info:
        skills.replay_skill(session, skill)
    assert exc_info.value.actual == "unknown"


def test_replay_skill_applies_params_via_format_substitution():
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]", "Sector : 500"])
    skill = _skill([{"input": "{qty}", "wait_prompt": None, "expected_post_class": "sector_display"}])
    skills.replay_skill(session, skill, params={"qty": "42"})
    assert session.sent == [("42", False)]


def test_replay_skill_falls_back_to_literal_when_no_matching_param():
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]", "Sector : 500"])
    skill = _skill([{"input": "{unbound}", "wait_prompt": None, "expected_post_class": "sector_display"}])
    skills.replay_skill(session, skill, params={"other": "1"})
    assert session.sent == [("{unbound}", False)]  # sent verbatim, never raised


# -- play_skill (11d) --------------------------------------------------------


def test_play_skill_runs_requested_cycles_and_reports_cycles_complete():
    # A 1-step skill cycled 3x -- screens list just needs enough entries
    # to keep classifying as sector_display through every send().
    session = FakeReplaySession(["Command [TL=00753:0/0/0/850]"] + ["Sector : 100"] * 3)
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"}])
    result = skills.play_skill(session, skill, cycles=3)
    assert result["halted"] == "cycles_complete"
    assert result["cycles_completed"] == 3
    assert len(result["trace"]) == 3


def test_play_skill_halts_on_surprise_mid_run():
    session = FakeReplaySession(
        ["Command [TL=00753:0/0/0/850]", "Sector : 100", "(A) Foo\n(B) Bar\nEnter your choice:"]
    )
    skill = _skill([{"input": "M", "wait_prompt": None, "expected_post_class": "sector_display"}])
    result = skills.play_skill(session, skill, cycles=5)
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
