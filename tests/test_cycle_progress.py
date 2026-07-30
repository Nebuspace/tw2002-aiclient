"""WO-AUTOLOOP-CYCLE-PROGRESS — Play hint-band cycle chrome."""

from __future__ import annotations

from tw2002_aiclient.cockpit import cycle_progress
from tw2002_aiclient.session import autoloop, protocol
from tw2002_aiclient.session.control_lock import ControlLock

from .test_autoloop import (
    ANCHOR_158,
    ONE_STEP,
    Server,
    WireSession,
    make_runner,
    run_to_completion,
    write_macro,
)


def test_composer_unicode_and_ascii():
    u = cycle_progress.compose_cycle_progress("ore-run", 2, 5, unicode_ok=True)
    assert u == "Playing ore-run ▸ 2/5 [██░░░]"
    a = cycle_progress.compose_cycle_progress("ore-run", 2, 5, unicode_ok=False)
    assert a == "Playing ore-run > 2/5 [##...]"


def test_composer_one_pass_is_full_bar():
    line = cycle_progress.compose_cycle_progress("dock", 1, 1, unicode_ok=True)
    assert line == "Playing dock ▸ 1/1 [█████]"


def test_composer_omits_unknown():
    assert cycle_progress.compose_cycle_progress("", 1, 1) is None
    assert cycle_progress.compose_cycle_progress("x", None, 3) is None
    assert cycle_progress.compose_cycle_progress("x", 1, 0) is None
    assert cycle_progress.compose_cycle_progress("x", True, 3) is None


def test_status_exposes_cycle_and_cycles(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    started = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "cycles": 3}, server
    )
    assert started["ok"] is True
    assert started["run"]["cycles"] == 3
    assert started["run"]["cycle"] == 1

    # Mid-run: wait until pass 1 has published, then read status.
    status = protocol.dispatch(session, "autoloop_status", {}, server)
    assert status["ok"] is True
    assert status["run"]["cycle"] >= 1
    assert status["run"]["cycles"] == 3

    run_to_completion(runner, session)
    done = protocol.dispatch(session, "autoloop_status", {}, server)
    assert done["running"] is False
    assert done["run"]["cycle"] == 3
    assert done["run"]["outcome"] == "completed"


def test_apply_band_clears_when_idle():
    from tw2002_aiclient import app as app_mod

    play = object.__new__(app_mod.PlayShellScreen)
    play.explore_band = "stale"
    keep = app_mod._apply_autoloop_cycle_band(
        play, {"running": False, "run": {"loop": "x", "cycle": 1, "cycles": 1}}
    )
    assert keep is False
    assert play.explore_band is None


def test_apply_band_sets_progress_when_running():
    from tw2002_aiclient import app as app_mod

    play = object.__new__(app_mod.PlayShellScreen)
    play.explore_band = None
    keep = app_mod._apply_autoloop_cycle_band(
        play,
        {
            "running": True,
            "stand_down": None,
            "run": {"loop": "ore-run", "cycle": 1, "cycles": 1},
        },
    )
    assert keep is True
    assert play.explore_band is not None
    assert "Playing ore-run" in play.explore_band
    assert "1/1" in play.explore_band
