"""WO-CHAINS-LIVE-REFRESH — the always-on readouts refresh without `L`.

The defect: `world_stats` refreshed on the `L` keypress and on explore
completion; `chain_scalars` refreshed on the `L` keypress and nowhere else.
An operator exploring for ten minutes watched an empty GOALS chain row the
whole time, because the surface that was supposed to be always-on only
updated when a modal was opened.

The pins below are grouped by the four Accept properties, kept separate
because they fail for different reasons: refresh-without-`L`, `L` still
works and still never auto-arms, no draw-path recompute, and the budget.

The budget is the half worth reading carefully. `chain_search.recompute` is
O(ports²) and measured at 9.4 s on a 320-port world (module docstring of
`cockpit/live_refresh.py` carries the table), and the play loop is
single-threaded at 1 Hz. A throttle would have bounded how OFTEN that
9-second freeze happened, which is the wrong axis, so the refresh measures
its own cost and retires when it breaches.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.cockpit import live_refresh
from tw2002_aiclient.cockpit.live_refresh import LiveRefresh


class _Clock:
    """Injected monotonic. The budget is a claim about elapsed time; a test
    that proved it by actually sleeping 250 ms would be slow AND flaky."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class _Stats:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def refresh(self, world_id: object, **_kw) -> None:
        # Optional ``status=`` / ``state_dir=`` (WO-COACH-HAS-PORT) must not
        # break this spy — production refresh gained kwargs, not new positionals.
        self.calls.append(world_id)


class _Scalars:
    def __init__(self) -> None:
        self.updates: list[object] = []

    def update(self, discovered: object) -> None:
        self.updates.append(discovered)


class _Play:
    def __init__(self) -> None:
        self.world_stats = _Stats()
        self.chain_scalars = _Scalars()


class _Profile:
    host, game_letter, handle = "demo-a.example", "B", "Alpha"


@pytest.fixture
def play() -> _Play:
    return _Play()


@pytest.fixture
def clock() -> _Clock:
    return _Clock()


def _recompute_costing(clock: _Clock, seconds: float, result: object = "CHAINS"):
    """A fake `chain_search.recompute` that *spends* `seconds` on the
    injected clock. The budget reads elapsed time around the call, so a fake
    that returned instantly would make every budget assertion below vacuous
    — it would prove only that 0.0 is under the budget."""

    def _fake(world_id, **_kw):
        clock.advance(seconds)
        return result

    return _fake


# -- Accept 1: the readouts refresh without `L` -------------------------------


def test_the_first_tick_refreshes_both_without_any_keypress(play, clock, monkeypatch) -> None:
    """The whole WO in one assertion: no `L`, and both surfaces update."""
    monkeypatch.setattr(
        "tw2002_aiclient.chain_search.recompute", _recompute_costing(clock, 0.01)
    )
    LiveRefresh().tick(play, _Profile(), now=clock)
    assert play.world_stats.calls, "sector count never refreshed"
    assert play.chain_scalars.updates == ["CHAINS"]


def test_the_world_id_handed_over_is_the_one_derived_from_the_profile(play, clock, monkeypatch) -> None:
    """A refresh against the wrong world is worse than no refresh: it fills
    the operator's screen with another character's numbers. `world_id` is
    the anti-galaxy-bleed key, so pin that it is actually derived."""
    from tw2002_aiclient import world_identity

    monkeypatch.setattr(
        "tw2002_aiclient.chain_search.recompute", _recompute_costing(clock, 0.01)
    )
    LiveRefresh().tick(play, _Profile(), now=clock)
    expected = world_identity.world_id_from_profile(_Profile())
    assert play.world_stats.calls == [expected]


def test_a_tick_before_the_interval_does_not_refresh_again(play, clock, monkeypatch) -> None:
    monkeypatch.setattr(
        "tw2002_aiclient.chain_search.recompute", _recompute_costing(clock, 0.01)
    )
    live = LiveRefresh()
    live.tick(play, _Profile(), now=clock)
    clock.advance(0.5)
    live.tick(play, _Profile(), now=clock)
    assert len(play.world_stats.calls) == 1, "idle tick re-counted within the interval"


def test_the_world_count_refreshes_again_once_its_interval_passes(play, clock, monkeypatch) -> None:
    monkeypatch.setattr(
        "tw2002_aiclient.chain_search.recompute", _recompute_costing(clock, 0.01)
    )
    live = LiveRefresh()
    live.tick(play, _Profile(), now=clock)
    clock.advance(live_refresh.WORLD_STATS_INTERVAL_S + 0.1)
    live.tick(play, _Profile(), now=clock)
    assert len(play.world_stats.calls) == 2


def test_chains_refresh_on_a_slower_interval_than_the_sector_count(play, clock, monkeypatch) -> None:
    """Not a style preference: even a cheap recompute is hundreds of times a
    directory count, so the two cadences are deliberately different. If they
    were ever equalised, the chain cost would ride the cheap cadence."""
    monkeypatch.setattr(
        "tw2002_aiclient.chain_search.recompute", _recompute_costing(clock, 0.01)
    )
    live = LiveRefresh()
    live.tick(play, _Profile(), now=clock)
    clock.advance(live_refresh.WORLD_STATS_INTERVAL_S + 0.1)
    live.tick(play, _Profile(), now=clock)
    assert len(play.world_stats.calls) == 2
    assert len(play.chain_scalars.updates) == 1, "chain discovery rode the cheap cadence"
    assert live_refresh.CHAIN_INTERVAL_S > live_refresh.WORLD_STATS_INTERVAL_S


# -- Accept 4: the budget, and its honest fallback -----------------------------


def test_an_over_budget_recompute_retires_automatic_chain_refresh(play, clock, monkeypatch) -> None:
    """The hazard this WO exists to avoid: a 9-second synchronous recompute
    freezing the cockpit mid-explore. One breach and the session stops doing
    it automatically."""
    monkeypatch.setattr(
        "tw2002_aiclient.chain_search.recompute",
        _recompute_costing(clock, live_refresh.CHAIN_BUDGET_S + 0.1),
    )
    live = LiveRefresh()
    live.tick(play, _Profile(), now=clock)
    assert live.chain_auto_retired is True
    clock.advance(live_refresh.CHAIN_INTERVAL_S * 10)
    live.tick(play, _Profile(), now=clock)
    assert len(play.chain_scalars.updates) == 1, "retired refresh ran again"


def test_the_over_budget_result_is_still_applied(play, clock, monkeypatch) -> None:
    """Retire AFTER applying. The operator already waited for that result;
    discarding it would charge them the freeze and give nothing back."""
    monkeypatch.setattr(
        "tw2002_aiclient.chain_search.recompute",
        _recompute_costing(clock, live_refresh.CHAIN_BUDGET_S + 0.1, result="EXPENSIVE"),
    )
    live = LiveRefresh()
    live.tick(play, _Profile(), now=clock)
    assert play.chain_scalars.updates == ["EXPENSIVE"]


def test_an_under_budget_recompute_does_not_retire(play, clock, monkeypatch) -> None:
    """The other direction, which is what makes the guard adaptive rather
    than a one-shot disable: a cheap early-explore world keeps refreshing."""
    monkeypatch.setattr(
        "tw2002_aiclient.chain_search.recompute",
        _recompute_costing(clock, live_refresh.CHAIN_BUDGET_S / 2),
    )
    live = LiveRefresh()
    live.tick(play, _Profile(), now=clock)
    assert live.chain_auto_retired is False
    clock.advance(live_refresh.CHAIN_INTERVAL_S + 0.1)
    live.tick(play, _Profile(), now=clock)
    assert len(play.chain_scalars.updates) == 2


def test_retiring_chains_does_not_stop_the_sector_count(play, clock, monkeypatch) -> None:
    """The two halves retire independently. `known_sector_count` is a
    directory count and was never the expensive one -- letting it die with
    the chain half would lose a live readout for no reason."""
    monkeypatch.setattr(
        "tw2002_aiclient.chain_search.recompute",
        _recompute_costing(clock, live_refresh.CHAIN_BUDGET_S + 0.1),
    )
    live = LiveRefresh()
    live.tick(play, _Profile(), now=clock)
    clock.advance(live_refresh.WORLD_STATS_INTERVAL_S + 0.1)
    live.tick(play, _Profile(), now=clock)
    assert live.chain_auto_retired is True
    assert len(play.world_stats.calls) == 2, "sector count died with the chain half"


def test_the_measured_cost_is_recorded_for_diagnosis(play, clock, monkeypatch) -> None:
    """A guard that stands down silently is a guard nobody can explain."""
    monkeypatch.setattr(
        "tw2002_aiclient.chain_search.recompute", _recompute_costing(clock, 0.5)
    )
    live = LiveRefresh()
    live.tick(play, _Profile(), now=clock)
    assert live.last_chain_cost_s == pytest.approx(0.5)


def test_the_budget_is_a_real_fraction_of_the_idle_tick() -> None:
    """The constant is chosen against the 1 Hz `stdscr.timeout(1000)` tick,
    not picked to make the tests pass. If it ever exceeds the tick itself the
    guard has stopped meaning "the operator never waits on a frame"."""
    assert 0 < live_refresh.CHAIN_BUDGET_S <= 0.5


# -- never raises: it runs on the loop's idle tick -----------------------------


def test_an_unusable_profile_does_not_raise(play, clock) -> None:
    """`world_identity.world_id` RAISES on an empty host. Resolving it at the
    call site instead of in here would take the whole cockpit down on a
    malformed profile — this is the pin for keeping it inside."""

    class _Bad:
        host, game_letter, handle = "", "B", "Alpha"

    LiveRefresh().tick(play, _Bad(), now=clock)
    assert play.world_stats.calls == []


@pytest.mark.parametrize(
    "profile", [None, object(), "not-a-profile", 7], ids=["none", "bare", "str", "int"]
)
def test_junk_in_place_of_a_profile_never_raises(play, clock, profile) -> None:
    LiveRefresh().tick(play, profile, now=clock)


def test_a_raising_world_model_does_not_raise_or_spin(play, clock, monkeypatch) -> None:
    """And is stamped, so a broken world model does not turn the 1 Hz loop
    into a retry storm."""
    calls: list[int] = []

    def _boom(world_id: object, **_kw) -> None:
        calls.append(1)
        raise OSError("world model unreadable")

    monkeypatch.setattr(play.world_stats, "refresh", _boom)
    monkeypatch.setattr(
        "tw2002_aiclient.chain_search.recompute", _recompute_costing(clock, 0.01)
    )
    live = LiveRefresh()
    live.tick(play, _Profile(), now=clock)
    clock.advance(0.5)
    live.tick(play, _Profile(), now=clock)
    assert len(calls) == 1, "a raising refresh was retried on the next tick"


def test_a_raising_recompute_does_not_retire_the_refresh(play, clock, monkeypatch) -> None:
    """A raise is not a cost signal. Retiring on it would let one transient
    read error silently switch the feature off for the session."""

    def _boom(world_id, **_kw):
        raise RuntimeError("finder exploded")

    monkeypatch.setattr("tw2002_aiclient.chain_search.recompute", _boom)
    live = LiveRefresh()
    live.tick(play, _Profile(), now=clock)
    assert live.chain_auto_retired is False
    assert play.chain_scalars.updates == []


def test_a_raising_clock_does_not_raise(play) -> None:
    def _boom() -> float:
        raise OSError("no clock")

    LiveRefresh().tick(play, _Profile(), now=_boom)


def test_a_backwards_clock_is_treated_as_due_not_as_a_lockout(play, clock, monkeypatch) -> None:
    """If a clock ever went backwards, comparing `now - last >= interval`
    would be false for as long as the jump lasted — the readouts would
    silently freeze rather than refresh."""
    monkeypatch.setattr(
        "tw2002_aiclient.chain_search.recompute", _recompute_costing(clock, 0.01)
    )
    live = LiveRefresh()
    live.tick(play, _Profile(), now=clock)
    clock.t -= 10_000
    live.tick(play, _Profile(), now=clock)
    assert len(play.world_stats.calls) == 2, "a backwards clock froze the readouts"


# -- wired into the real loop, not merely tested ------------------------------
#
# Everything above exercises `LiveRefresh` directly. All of it passes on a
# tree where `_run_play` never calls it — a module that is tested, hardened,
# and dead. These drive the real loop.


class _Result:
    def __init__(self, ok=True, classification="main_command"):
        self.ok, self.classification = ok, classification
        self.reason = self.detail = None


class _Stdscr:
    """`getch` returns -1 (the idle tick, what `stdscr.timeout(1000)`
    produces on a quiet session) before Esc ends the loop."""

    def __init__(self, keys):
        self._keys = list(keys) + [27, 27]
        self.rows, self.cols = 40, 160

    def getmaxyx(self): return (self.rows, self.cols)
    def getch(self): return self._keys.pop(0) if self._keys else 27
    def timeout(self, ms): pass
    def erase(self): pass
    def refresh(self): pass
    def addstr(self, *a, **k): pass
    def addnstr(self, *a, **k): pass
    def attron(self, a): pass
    def attroff(self, a): pass
    def hline(self, *a, **k): pass
    def vline(self, *a, **k): pass
    def border(self, *a, **k): pass
    def chgat(self, *a, **k): pass
    def keypad(self, flag): pass
    def nodelay(self, flag): pass


def _drive(monkeypatch, keys):
    """Run the real `_run_play`, recording every `LiveRefresh.tick`."""
    from tw2002_aiclient import adapters, app as app_mod

    ticks: list = []
    monkeypatch.setattr(adapters, "ensure_session", lambda name, **kw: _Result())
    monkeypatch.setattr(app_mod.curses, "has_colors", lambda: False, raising=False)

    real_tick = LiveRefresh.tick

    def _spy(self, play_arg, profile_arg, **kw):
        ticks.append((play_arg, profile_arg))
        return real_tick(self, play_arg, profile_arg, **kw)

    monkeypatch.setattr(app_mod._live_refresh.LiveRefresh, "tick", _spy)

    class _Quiet(app_mod.PlayShellScreen):
        def draw(self):
            pass

    monkeypatch.setattr(app_mod, "PlayShellScreen", _Quiet)
    profile = app_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    try:
        app_mod._run_play(_Stdscr(keys), profile)
    except Exception:
        pass
    return ticks, profile


def test_the_idle_tick_actually_reaches_live_refresh(monkeypatch) -> None:
    """The wiring pin. Delete the `live.tick(...)` line in `app._run_play`
    and every other test in this file still passes."""
    ticks, _profile = _drive(monkeypatch, [-1])
    assert ticks, "the play loop's idle tick never refreshed the readouts"


def test_the_loop_hands_over_the_profile_not_a_resolved_world_id(monkeypatch) -> None:
    """`world_id_from_profile` raises on an unusable host. Resolving at the
    call site would put that raise outside `LiveRefresh`'s containment and
    cost the operator the cockpit, so the seam takes the profile itself."""
    ticks, profile = _drive(monkeypatch, [-1])
    assert ticks[0][1] is profile


def test_no_recompute_on_the_draw_path(monkeypatch) -> None:
    """Accept 3, for the expensive half. `test_draw_path_does_not_call_known_
    sector_count` already covers the sector count; this is its chain twin,
    and the one that matters — a per-frame O(ports²) discovery would be a
    9-second freeze every frame, not merely a slow one."""
    from tw2002_aiclient import app as app_mod

    calls: list = []

    def _boom(world_id, **_kw):
        calls.append(world_id)
        raise AssertionError("draw path must not run chain discovery")

    monkeypatch.setattr("tw2002_aiclient.chain_search.recompute", _boom)

    class _Win(_Stdscr):
        pass

    profile = app_mod.ProfileRow(
        name="a", handle="A", server="s", host="h.example", game_letter="B")
    monkeypatch.setattr(app_mod.curses, "has_colors", lambda: False, raising=False)
    play = app_mod.PlayShellScreen(_Win([]), profile)
    play.spectating = play.attached = False
    play.status_provider = lambda: {"ok": True, "connected": True, "log_tail": []}
    play.draw()
    assert calls == []
