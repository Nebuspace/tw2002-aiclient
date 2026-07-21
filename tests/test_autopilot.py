"""WO-P1 autopilot tests (§22/§23 Phase 1) -- deterministic scoring/
interrupt coverage with real numbers, the fail-closed gate, the dry-run
decision-trace proof surface, and the 2026-07-20 adversarial-review
fixes (HIGH-1 EV-unit, HIGH-2 classify-gate, HIGH-3 interrupt-history
isolation, plus the MED fail-closed/confirmed/thread-death fixes). No
network, no real telnet -- a deferred-bump fake session (mirrors
test_loop_player.py's own FakeLoopSession, needed for
`send_and_confirm`'s confirm_prompt=None idle-settle path -- see that
fake's docstring) and a real `ControlLock`/`credentials.Profile` for the
gate/mode-transition proofs.
"""

import math
import threading
import time

import pytest

from twclient import autopilot as autopilot_mod
from twclient.autopilot import (
    EXPLORE_BASELINE_EV,
    AutopilotEngine,
    AutopilotGateError,
    AutopilotLoop,
    AutopilotLoopError,
    Candidate,
    EconCaps,
    WorldSnapshot,
    assess,
    decision_to_trace,
    maybe_auto_start,
    select,
)
from twclient.chains import ProfitChain, TradeHop
from twclient.control_lock import MODE_AI_PILOT, MODE_AUTO_LOOP, MODE_HUMAN, ControlLock
from twclient.credentials import Profile
from twclient.session import Session
from twclient.ship_upgrade_decision import LoopEconomics, ShipSpec, UpgradeDecision
from twclient.state_parser import parse_state
from twclient.trade_driver import ChainRunResult

_MAIN_COMMAND_SCREEN = "Command [TL=00:00:08]:[100] (?=Help)? :"


def _wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


class FakeAutopilotSession:
    """Deferred-bump fake -- `send_and_confirm`'s confirm_prompt=None
    (TW-02 idle-settle) path needs `rx_count` to increase AFTER
    `wait_for_settle()` starts counting, not synchronously inside
    `send()` itself (a synchronous bump is already "stale" by the time
    `wait_for_settle` captures its own baseline) -- exactly
    test_loop_player.py's FakeLoopSession's own rationale, reused here."""

    def __init__(self, text=_MAIN_COMMAND_SCREEN):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._text = text
        self.sent = []
        self._pending_advance = False

    def clock(self):
        return self.t

    def sleep(self, seconds):
        if self._pending_advance:
            self._pending_advance = False
            self.t += seconds
            self.rx_count += 1
            self.last_rx = self.t
        else:
            self.t += seconds

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))
        self._pending_advance = True

    def render(self):
        return self._text.split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._text


class ObservingFakeAutopilotSession(FakeAutopilotSession):
    """WO-FA7a round 5: `FakeAutopilotSession` + the REAL `Session.
    observe_credits`/`credits_snapshot` wired in (assigned directly off the
    class, not reimplemented -- same convention as test_loop_player.py's
    own `ObservingFakeLoopSession`/test_credits_supervision.py's fakes), so
    a test using this session exercises the same hasattr-guarded
    `observe_credits()`/`credits_snapshot()` calls `dry_run_tick()`/
    `live_tick()`'s `_fresh_credits()` (WO-FA-SAFE) now make against a real
    `Session`. Plain `FakeAutopilotSession` predates the credits-
    supervision surface entirely and has no `last_credits`/
    `last_credits_ts`/`lock` at all, so the hasattr guards silently skip it
    -- every other existing test in this file keeps using the plain fake
    unchanged. `self.lock` (WO-FA-SAFE, Rook must-fix #3) is a plain
    `threading.Lock`, the same shape `Session.lock` is."""

    observe_credits = Session.observe_credits
    credits_snapshot = Session.credits_snapshot

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.lock = threading.Lock()
        self.last_credits = None
        self.last_credits_ts = None

    observe_credits = Session.observe_credits


class NeverSettlesSession(FakeAutopilotSession):
    """Every `sleep()` call produces a fresh byte -- the screen never
    genuinely quiesces (`last_rx` keeps chasing `now`, so idle's debounce
    window never satisfies, and `wait_for_settle` eventually times out).
    `send_and_confirm(confirm_prompt=None)` can only report
    `confirmed=True` off a genuinely stable idle -- this fake proves the
    MED "honor `confirmed`" fix: a persistent settle desync must be
    reported as `send_outcome="unconfirmed"`, never silently treated as
    a successful send. All simulated time -- costs no real wall-clock."""

    def sleep(self, seconds):
        self.t += seconds
        self.rx_count += 1
        self.last_rx = self.t


class ClearsAfterFirstRenderSession(FakeAutopilotSession):
    """Simulates a screen-clear landing between `live_tick()`'s two
    renders (the tick-start `pre_text` render, then the HIGH-2 gate-check
    render) -- e.g. a hub-warp CLS mid-transition. The FIRST `render()`
    call returns the configured (settled) screen; every call after that
    returns blank rows -- proves the gate must HOLD on its own fresh
    render rather than trusting a stale earlier one plus a fresh-but-
    blank prompt line (cipher's TOCTOU PoC)."""

    def __init__(self, text=_MAIN_COMMAND_SCREEN):
        super().__init__(text=text)
        self._render_calls = 0

    def render(self):
        self._render_calls += 1
        if self._render_calls == 1:
            return super().render()
        return []


class FakeLedger:
    def __init__(self):
        self.calls = []

    def record_do(self, pre_text, input_text, secret, post_text, settled_class, capture=None,
                   actor="ai", session_id=None, intent=None):
        self.calls.append(
            {
                "input_text": input_text,
                "settled_class": settled_class,
                "actor": actor,
                "session_id": session_id,
                "intent": intent,
            }
        )


def _loop_econ():
    return LoopEconomics(margin_per_hold=100, turns_per_cycle=10, stock_capacity=100)


def _barge():
    return ShipSpec(name="Prison Barge", cost=0, holds=20, turns_per_warp=6, fighters=10, shields=0)


def _galleon_hull():
    """Same holds/fighters/shields as the barge -- ONLY turns_per_warp
    differs -- isolating the travel-turn-cost variable precisely."""
    return ShipSpec(name="Imperial Galleon", cost=0, holds=20, turns_per_warp=3, fighters=10, shields=0)


def _cruiser():
    return ShipSpec(name="Merchant Cruiser", cost=50_000, holds=75, turns_per_warp=3, fighters=100, shields=50)


def _profit_chain_hops(margin=50):
    # A trivial 2-sector round trip, cr/turn = (margin*2)/(1+1) = margin.
    return [
        TradeHop(frm=100, to=200, commodity="Fuel Ore", margin=margin, turns=1),
        TradeHop(frm=200, to=100, commodity="Organics", margin=margin, turns=1),
    ]


def _make_profile(name="t", autonomous=False):
    return Profile(name=name, host="h", port=1, game_letter="A", handle="X", autonomous=autonomous)


# -- SELECT: scoring with real numbers ---------------------------------


def test_select_picks_the_known_chain_when_nothing_else_beats_it():
    snap = WorldSnapshot(
        sector=None, credits=None, turns_left=1000,
        hops=tuple(_profit_chain_hops(margin=50)),
        explore_next_sector=999,
    )
    decision = select(snap)
    assert decision.chosen is not None
    assert decision.chosen.kind == "run_chain"
    assert decision.chosen.ev_per_turn == 50.0
    kinds = {c.kind for c in decision.candidates}
    assert kinds == {"run_chain", "explore"}  # no upgrade candidate: empty ship_catalog


def test_dry_run_tick_chooses_run_chain_and_never_sends():
    """WO-FA4 dry-run accept criterion: a synthetic priced world (a known
    profitable chain, ship sitting at the chain's own start sector) makes
    `dry_run_tick()` CHOOSE `run_chain` -- and never sends a single byte,
    regardless (the pre-enablement proof surface stays true even now that
    `_execute()` can drive a whole multi-send chain)."""
    session = FakeAutopilotSession(text="Sector  : 100\n1000 turns left.\nCommand [TL=00:00:08]:[100] (?=Help)? :")
    profile = _make_profile(autonomous=False)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    decision = engine.dry_run_tick(hops=tuple(_profit_chain_hops(margin=50)))

    assert decision.chosen is not None
    assert decision.chosen.kind == "run_chain"
    assert decision.chosen.next_sector == 200  # sitting at chain.sectors[0]==100
    assert session.sent == []


def test_select_picks_explore_when_no_chain_or_upgrade_known_no_idle():
    snap = WorldSnapshot(sector=None, credits=None, turns_left=1000, explore_next_sector=42, explore_mode="mapfill")
    decision = select(snap)
    assert decision.chosen is not None
    assert decision.chosen.kind == "explore"
    assert decision.chosen.next_sector == 42


def test_select_reports_no_candidates_when_truly_nothing_available():
    snap = WorldSnapshot(sector=None, credits=None, turns_left=1000)
    decision = select(snap)
    assert decision.chosen is None
    assert decision.reason == "no_candidates"


def test_select_picks_upgrade_over_a_weak_chain_when_upgrade_ev_is_higher():
    snap = WorldSnapshot(
        sector=None, credits=60_000, turns_left=5000,
        current_ship=_barge(),
        ship_catalog=(_cruiser(),),
        loop=_loop_econ(),
        hops=tuple(_profit_chain_hops(margin=50)),  # weak chain: 50 cr/turn
        stardock_route=(100, 150, 999),  # 2 hops to StarDock
        explore_next_sector=1,
    )
    decision = select(snap)
    assert decision.chosen is not None
    assert decision.chosen.kind == "upgrade"
    # HIGH-1 formula: (75-20 holds) * 100 margin / 10 turns_per_cycle = 550 cr/turn, well above the 50cr/turn chain.
    assert decision.chosen.ev_per_turn == 550.0
    kinds = {c.kind for c in decision.candidates}
    assert kinds == {"run_chain", "upgrade", "explore"}


def test_select_skips_upgrade_when_stardock_prices_are_unknown():
    """WO hard rule: empty ship_catalog (no introspected StarDock prices
    yet -- P1-b's job) must skip the upgrade branch outright, never guess
    a spend."""
    snap = WorldSnapshot(
        sector=None, credits=60_000, turns_left=5000,
        current_ship=_barge(), loop=_loop_econ(),
        stardock_route=(100, 150, 999),
        explore_next_sector=1,
    )
    decision = select(snap)
    assert all(c.kind != "upgrade" for c in decision.candidates)
    assert any("prices unknown" in s for s in decision.skipped)


def test_select_skips_upgrade_below_the_cash_floor():
    snap = WorldSnapshot(
        sector=None, credits=5_000, turns_left=5000,  # below DEFAULT_CASH_FLOOR (10,000)
        current_ship=_barge(), ship_catalog=(_cruiser(),), loop=_loop_econ(),
        stardock_route=(100, 150, 999),
    )
    decision = select(snap)
    assert all(c.kind != "upgrade" for c in decision.candidates)
    assert any("cash floor" in s for s in decision.skipped)


def test_upgrade_travel_cost_uses_current_ships_turns_per_warp_not_a_constant():
    """Decision #2 (CONFIRMED CORRECT, keep) -- the turn-cost to reach
    StarDock must use the CURRENT ship's turns-per-warp, never a
    hardcoded constant (game-D: Prison Barge 6/warp vs Galleon 3/warp).
    Same route, same candidate ship, same turns_left -- ONLY the current
    ship's turns_per_warp differs between the two calls, and it alone
    flips recommend/HOLD. (Post-HIGH-1, the reported EV itself is now
    warp-STABLE at 550 in both cases -- it's the FEASIBILITY gate, not
    the ranking score, that must vary with the real ship.)"""
    route = (100, 150, 999)  # 2 hops

    def snapshot_for(current_ship):
        return WorldSnapshot(
            sector=None, credits=60_000, turns_left=330,  # productive = 330 - 50 = 280
            current_ship=current_ship, ship_catalog=(_cruiser(),), loop=_loop_econ(),
            stardock_route=route,
        )

    fast_decision = select(snapshot_for(_galleon_hull()))  # 3/warp: 2*3=6t travel; 272.7+6=278.7 <= 280 -> fits
    slow_decision = select(snapshot_for(_barge()))  # 6/warp: 2*6=12t travel; 272.7+12=284.7 > 280 -> blows budget

    fast_upgrade = next((c for c in fast_decision.candidates if c.kind == "upgrade"), None)
    slow_upgrade = next((c for c in slow_decision.candidates if c.kind == "upgrade"), None)

    assert fast_upgrade is not None, "3t/warp ship: payback + travel fits the turn budget"
    assert fast_upgrade.ev_per_turn == 550.0  # holds-only delta -- warp-stable (HIGH-1)
    assert slow_upgrade is None, "6t/warp ship: the SAME route costs double the travel turns and blows the budget"
    assert any("12t travel" in s and "HOLD" in s for s in slow_decision.skipped)


def test_select_respects_turn_reserve_floor_for_chains():
    snap = WorldSnapshot(
        sector=None, credits=None, turns_left=52,  # productive = 52 - 50(default reserve) = 2 == chain.turns (2)
        hops=tuple(_profit_chain_hops(margin=50)),
    )
    # Exactly at the edge (productive == chain.turns) must still be eligible.
    decision = select(snap)
    assert any(c.kind == "run_chain" for c in decision.candidates)

    tight = WorldSnapshot(sector=None, credits=None, turns_left=51, hops=tuple(_profit_chain_hops(margin=50)))
    decision2 = select(tight, EconCaps(turn_reserve=50))
    assert all(c.kind != "run_chain" for c in decision2.candidates)
    assert any("turn-reserve floor" in s for s in decision2.skipped)


# -- MED fail-closed: an UNKNOWN input must skip, never bypass a gate ----


def test_select_fails_closed_on_unknown_turns_left_for_chains():
    """mack M-a: `turns_left=None` (a parse hiccup) used to skip the
    turn-BUDGET check entirely and let the chain through with the
    turn-reserve floor silently disabled. Must now skip the candidate
    outright instead."""
    hops = (
        TradeHop(frm=100, to=200, commodity="Fuel Ore", margin=50, turns=200),
        TradeHop(frm=200, to=100, commodity="Organics", margin=50, turns=200),
    )  # chain.turns = 400 -- would need an enormous budget
    snap = WorldSnapshot(sector=None, credits=None, turns_left=None, hops=hops)
    decision = select(snap)
    assert all(c.kind != "run_chain" for c in decision.candidates)
    assert any("turns_left unknown" in s for s in decision.skipped)
    assert decision.chosen is None  # no explore/upgrade input supplied either -- nothing to fall back to


def test_select_fails_closed_on_unknown_credits_for_upgrade():
    """mack M-b / cipher: `credits=None` used to bypass the cash-floor
    check (only a KNOWN too-low balance was rejected). Must now skip."""
    snap = WorldSnapshot(
        sector=None, credits=None, turns_left=5000,
        current_ship=_barge(), ship_catalog=(_cruiser(),), loop=_loop_econ(),
        stardock_route=(100, 150, 999),
    )
    decision = select(snap)
    assert all(c.kind != "upgrade" for c in decision.candidates)
    assert any("credits unknown" in s for s in decision.skipped)


def test_select_excludes_a_cost_zero_sentinel_ship_never_a_phantom_free_upgrade():
    """mack M-c: a cost<=0 sentinel (an unpriced ship) used to yield a
    trivially-fast payback and get recommended as a phantom free
    upgrade. Must be excluded per-ship, before it ever reaches
    choose_upgrade()."""
    zero_cost_ship = ShipSpec(name="Mystery Ship", cost=0, holds=50, turns_per_warp=6, fighters=10, shields=0)
    snap = WorldSnapshot(
        sector=None, credits=60_000, turns_left=5000,
        current_ship=_barge(), ship_catalog=(zero_cost_ship,), loop=_loop_econ(),
    )
    decision = select(snap)
    assert all(c.kind != "upgrade" for c in decision.candidates)
    assert any("priced" in s for s in decision.skipped)


def test_select_fails_closed_when_choose_upgrade_returns_an_unknown_payback(monkeypatch):
    """Class-invariant guard alongside (a)/(b)/(c) above: `decision.projected_payback
    or 0.0` used to coerce an unknown payback to 0 -- the single BEST possible
    outcome (free) -- instead of skipping. Not reachable through today's real
    `choose_upgrade()` (its own contract guarantees a real payback whenever
    `recommend` is True), so this forces the shape via a monkeypatched
    `choose_upgrade` to prove the defensive guard actually fires rather than
    silently trusting that contract forever."""

    def fake_choose_upgrade(catalog, player, loop, *, defense_floor_fighters):
        return UpgradeDecision(
            recommend=True,
            ship=catalog[0],
            rationale="forced test recommend with unknown payback",
            projected_payback=None,
        )

    monkeypatch.setattr(autopilot_mod, "choose_upgrade", fake_choose_upgrade)
    snap = WorldSnapshot(
        sector=None, credits=60_000, turns_left=5000,
        current_ship=_barge(), ship_catalog=(_cruiser(),), loop=_loop_econ(),
        stardock_route=(1,),  # at-dock (known, len==1) -- reach the payback check, not the route-unknown skip
    )
    decision = select(snap)
    assert all(c.kind != "upgrade" for c in decision.candidates)
    assert any("payback unknown" in s for s in decision.skipped)


def test_select_fails_closed_when_stardock_route_is_unknown():
    """cipher re-verify (2026-07-20): `stardock_route=None` (route
    UNKNOWN) used to collapse to the SAME `travel_turns = 0` as a genuine
    known 1-entry (already-at-dock) route -- an unknown feasibility
    silently read as the single BEST case (free travel). Must skip
    instead, same never-guess discipline as the payback/cost-zero fixes."""
    snap = WorldSnapshot(
        sector=None, credits=60_000, turns_left=5000,
        current_ship=_barge(), ship_catalog=(_cruiser(),), loop=_loop_econ(),
        # stardock_route intentionally omitted -- defaults to None (unknown)
    )
    decision = select(snap)
    assert all(c.kind != "upgrade" for c in decision.candidates)
    assert any("stardock route unknown" in s for s in decision.skipped)


# -- HIGH-1: cross-kind EV must be genuine, warp-stable cr/turn ----------


def test_high1_poc1_underrank_true_delta_beats_a_weak_chain():
    current = ShipSpec(name="Slow Hauler", cost=0, holds=10, turns_per_warp=10, fighters=10, shields=0)
    candidate = ShipSpec(name="Big Hauler", cost=50_000, holds=30, turns_per_warp=10, fighters=10, shields=0)
    loop = _loop_econ()
    true_delta = (candidate.holds - current.holds) * loop.margin_per_hold / loop.turns_per_cycle  # 200
    snap = WorldSnapshot(
        sector=None, credits=60_000, turns_left=5000,
        current_ship=current, ship_catalog=(candidate,), loop=loop,
        hops=tuple(_profit_chain_hops(margin=25)),  # weak chain, deliberately below the true delta
        stardock_route=(1,),  # known, at-dock -- this test is about the EV ranking, not travel feasibility
        explore_next_sector=1,
    )
    decision = select(snap)
    upgrade = next(c for c in decision.candidates if c.kind == "upgrade")
    assert upgrade.ev_per_turn == true_delta == 200.0
    assert decision.chosen.kind == "upgrade"


def test_high1_poc5_over_rank_a_trivial_upgrade_never_beats_a_real_chain():
    # Different warp speeds either side of the subtraction is the trap:
    # a glacial current ship vs a barely-bigger-but-blazing-fast
    # candidate used to inflate the coded delta to 505 (vs a true 10).
    current = ShipSpec(name="Glacial Behemoth", cost=0, holds=50, turns_per_warp=100, fighters=10, shields=0)
    candidate = ShipSpec(name="Barely-Bigger Skiff", cost=100, holds=51, turns_per_warp=1, fighters=10, shields=0)
    loop = _loop_econ()
    true_delta = (candidate.holds - current.holds) * loop.margin_per_hold / loop.turns_per_cycle  # 10
    snap = WorldSnapshot(
        sector=None, credits=60_000, turns_left=5000,
        current_ship=current, ship_catalog=(candidate,), loop=loop,
        hops=tuple(_profit_chain_hops(margin=50)),  # a real chain, 5x the true upgrade delta
        stardock_route=(1,),  # known, at-dock -- this test is about the EV ranking, not travel feasibility
        explore_next_sector=1,
    )
    decision = select(snap)
    upgrade = next(c for c in decision.candidates if c.kind == "upgrade")
    assert upgrade.ev_per_turn == true_delta == 10.0
    assert decision.chosen.kind == "run_chain", "the real 50cr/turn chain must beat the trivial +1-hold upgrade"


def test_high1_poc6_ranking_is_stable_regardless_of_current_ships_warp():
    candidate = ShipSpec(name="Merchant Cruiser", cost=1_000, holds=75, turns_per_warp=3, fighters=10, shields=0)
    loop = _loop_econ()
    chain_cr_per_turn = 200  # fixed, deliberately between the two OLD (buggy) coded deltas
    hops = tuple(_profit_chain_hops(margin=chain_cr_per_turn))
    true_delta = (candidate.holds - 20) * loop.margin_per_hold / loop.turns_per_cycle  # 550

    for current in (
        ShipSpec(name="current@3warp", cost=0, holds=20, turns_per_warp=3, fighters=10, shields=0),
        ShipSpec(name="current@6warp", cost=0, holds=20, turns_per_warp=6, fighters=10, shields=0),
    ):
        snap = WorldSnapshot(
            sector=None, credits=60_000, turns_left=5000,
            current_ship=current, ship_catalog=(candidate,), loop=loop,
            hops=hops, stardock_route=(1,), explore_next_sector=1,
        )
        decision = select(snap)
        upgrade = next(c for c in decision.candidates if c.kind == "upgrade")
        assert upgrade.ev_per_turn == true_delta == 550.0, (
            f"EV must be warp-stable regardless of current ship ({current.name})"
        )
        assert decision.chosen.kind == "upgrade", f"upgrade (550) must beat the chain (200) for {current.name}"


# -- HIGH-2: classify-gate before every send -----------------------------


def test_live_tick_holds_the_send_when_the_live_screen_is_not_the_command_prompt():
    """A stale 'Sector : 100' block sits above a LIVE haggle 'Your offer
    [500] ?' prompt -- a bare sector-number send must never fire into
    that dialogue (both a haggle-bid and a colonist-qty/fighter-deploy
    prompt take a bare number + Enter)."""
    text = "Sector : 100\nSome narrative line\nYour offer [500] ?"
    session = FakeAutopilotSession(text=text)
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    ledger = FakeLedger()
    engine = AutopilotEngine(session, profile, lock, ledger=ledger)

    decision = engine.live_tick(explore_next_sector=200)
    assert decision.chosen.kind == "explore"
    assert decision.chosen.next_sector == 200
    assert session.sent == [], "must NOT fire the bare sector-number send onto a live non-movement prompt"
    assert decision.send_outcome is not None and decision.send_outcome.startswith("held:")
    assert "held" in ledger.calls[0]["intent"]


def test_live_tick_sends_normally_when_the_live_screen_is_the_command_prompt():
    session = FakeAutopilotSession()  # default screen classifies as main_command
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    decision = engine.live_tick(explore_next_sector=42)
    assert decision.send_outcome == "sent"
    assert session.sent == [("42", True, False)]
    # Also the positive control for the TOCTOU fix below: both of
    # live_tick()'s renders return the SAME non-blank main_command screen
    # here, proving the refactored one-fresh-render gate still sends
    # normally when the screen genuinely IS settled and unchanged.


def test_live_tick_holds_a_non_adjacent_explore_target_the_live_screen_positively_contradicts():
    """HIGH backstop sensitivity control (mack/cipher adversarial
    re-verify, 2026-07-21): the live screen POSITIVELY shows the current
    sector's own warps (12, 45, 99) via a real "Warps to Sector(s)" line
    -- a forced explore target (777) that ISN'T among them must HOLD as
    `held:non_adjacent`, never fire the bare send. RED if
    `_explore_target_confirmed_non_adjacent`'s check is removed (would
    otherwise send "777" through unconditionally, exactly like
    `test_live_tick_sends_normally_when_the_live_screen_is_the_command_prompt`
    above does for an unconstrained target)."""
    text = "Warps to Sector(s) :  12 - 45 - 99\n" + _MAIN_COMMAND_SCREEN
    session = FakeAutopilotSession(text=text)
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    ledger = FakeLedger()
    engine = AutopilotEngine(session, profile, lock, ledger=ledger)

    decision = engine.live_tick(explore_next_sector=777)
    assert decision.chosen.kind == "explore"
    assert decision.send_outcome == "held:non_adjacent"
    assert session.sent == [], "must NOT fire a bare warp the live screen positively contradicts"
    assert "held" in ledger.calls[0]["intent"]


def test_live_tick_sends_an_explore_target_the_live_screen_confirms_is_adjacent():
    """Positive control for the same backstop: when the live screen's
    own warps DO include the candidate's target, the send proceeds
    normally -- the guard only ever refuses a POSITIVELY confirmed
    mismatch, never a merely-plausible one."""
    text = "Warps to Sector(s) :  12 - 45 - 99\n" + _MAIN_COMMAND_SCREEN
    session = FakeAutopilotSession(text=text)
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    decision = engine.live_tick(explore_next_sector=45)
    assert decision.send_outcome == "sent"
    assert session.sent == [("45", True, False)]


# -- WO-FA7a round 5: the LAST autonomous credits-render gap (mack's
# -- completeness sweep, repro scratchpad/repro_fa7a_round4_autopilot_gap.
# -- py) -- dry_run_tick()/live_tick() render the current settled screen
# -- every tick, the SAME class of autonomous per-tick screen read
# -- replay_skill/play_skill/LoopPlayer were already fixed for, but never
# -- fed the credits-supervision surface at all until now. WO-FA-SAFE has
# -- since landed: `assess()`'s own credits decision is no longer the loose
# -- `parse_state()` read this note originally deferred -- see
# -- `AutopilotEngine._fresh_credits()`'s own docstring for the strict,
# -- freshness-gated source it's fed from now.


def test_dry_run_tick_feeds_the_credits_supervision_surface():
    """RED without the fix: `ObservingFakeAutopilotSession` starts at
    `last_credits=None` and nothing else in a dry-run (zero sends) would
    ever set it otherwise."""
    text = "You have 300,000 credits.\nCommand [TL=00:00:08]:[100] (?=Help)? :"
    session = ObservingFakeAutopilotSession(text=text)
    profile = _make_profile(autonomous=False)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    engine.dry_run_tick()

    assert session.last_credits == 300000
    assert session.last_credits_ts is not None
    assert session.sent == [], "sanity: dry_run_tick must still never send"


def test_live_tick_feeds_the_credits_supervision_surface():
    """Same proof through `live_tick()` -- a real send fires (this screen
    classifies as the main command prompt, matching
    `test_live_tick_sends_normally_when_the_live_screen_is_the_command_prompt`
    above), so both the pre-execute AND post-execute render sites get
    exercised; either is sufficient to satisfy this assertion since both
    read the identical screen text here."""
    text = "You have 300,000 credits.\nCommand [TL=00:00:08]:[100] (?=Help)? :"
    session = ObservingFakeAutopilotSession(text=text)
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    decision = engine.live_tick(explore_next_sector=42)

    assert decision.send_outcome == "sent"
    assert session.last_credits == 300000
    assert session.last_credits_ts is not None


# -- WO-FA-SAFE (hub-signed-off design + Rook must-fix #1/#3/#4): assess()'s
# -- credits kwarg is now REQUIRED, strict, and freshness-gated -----------


def test_assess_raises_when_credits_is_omitted():
    """Rook must-fix #1: `assess()`'s `credits` is a REQUIRED keyword-only
    argument with NO default and NO `parse_state()` fallback -- a caller
    that omits it must fail LOUD, never silently revert to the loose
    screen-scraped source this WO removed."""
    try:
        assess(_MAIN_COMMAND_SCREEN)
        assert False, "assess() must raise when credits is omitted"
    except TypeError as e:
        assert "credits" in str(e)


def test_dry_run_tick_price_mask_below_cash_floor_poc_reads_the_strict_balance():
    """THE HUB'S MANDATORY PoC (tick-level twin of loop_player.py's own):
    a real, prior balance BELOW `cash_floor` sits in `session.last_credits`
    (captured moments earlier, e.g. the crawl login/dock screen); the
    CURRENT screen is a pure port price-quote with NO balance line of its
    own, quoting a price >= `cash_floor`. `assess()`'s strict `credits`
    (`AutopilotEngine._fresh_credits()` -> `session.credits_snapshot()`)
    must still see the real sub-floor balance (non-clobber: this screen has
    nothing to overwrite it with) and `_score_upgrade()` must skip the
    upgrade candidate on its cash-floor gate -- contrasted directly against
    the pre-fix loose reader (`state_parser.parse_state()`'s own `credits`
    field, sourced from THIS screen), which this fixture proves WOULD have
    read the price quote as a comfortably-above-floor balance and let the
    candidate through."""
    price_quote_screen = "We'll sell them for 60,000 credits.\n5,000 turns left.\nYour offer [60000] ? "
    session = ObservingFakeAutopilotSession(text=price_quote_screen)
    session.observe_credits("You have 5,000 credits.\nCommand [TL=00:00:06]:[100] (?=Help)? :")  # real bal < cash_floor

    # Sanity: the fixture genuinely exercises the masking shape -- the OLD
    # loose reader IS fooled by this screen's price quote.
    assert parse_state(price_quote_screen).get("credits") == 60000

    profile = _make_profile(autonomous=False)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    decision = engine.dry_run_tick(
        current_ship=_barge(), ship_catalog=(_cruiser(),), loop=_loop_econ(), stardock_route=(100, 150, 999),
    )

    assert all(c.kind != "upgrade" for c in decision.candidates), (
        "the strict source must see the real 5,000cr balance (< cash_floor) and skip upgrade, "
        "never the price-quote-polluted 60,000 a loose reader would have let through"
    )
    assert any("cash floor" in s for s in decision.skipped)
    assert decision.snapshot.credits == 5000


def test_dry_run_tick_skips_upgrade_when_no_balance_was_ever_observed():
    """Fail-closed on `None`: a session that never captured any balance
    must skip the upgrade candidate on the SAME `credits unknown` gate a
    genuine parse gap already uses (mack M-b) -- never treated as "assume
    it's fine"."""
    text = "5,000 turns left.\n" + _MAIN_COMMAND_SCREEN  # no "You have N credits" line anywhere
    session = ObservingFakeAutopilotSession(text=text)
    profile = _make_profile(autonomous=False)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    decision = engine.dry_run_tick(
        current_ship=_barge(), ship_catalog=(_cruiser(),), loop=_loop_econ(), stardock_route=(100, 150, 999),
    )

    assert all(c.kind != "upgrade" for c in decision.candidates)
    assert any("credits unknown" in s for s in decision.skipped)
    assert decision.snapshot.credits is None


def test_dry_run_tick_credits_none_still_explores_never_halts():
    """Phase-A explore-only-witness ARMING INVARIANT (mack's live repro,
    made permanent): the ruled asymmetry between the two credit-gated
    stop sites is loop_player HALTs on an unknown balance (a real per-
    spend stop-loss), but the autopilot tick only skip-SPENDs -- it must
    KEEP EXPLORING, never halt or no-op, when credits are unknown.
    `explore` spends nothing (EXECUTE is navigation-only, see module
    docstring), so a `None` balance has no reason to block it; only the
    credits-gated `upgrade` candidate is skipped. Untested before this
    revise despite being load-bearing for the hub's Phase-A witness."""
    text = "5,000 turns left.\n" + _MAIN_COMMAND_SCREEN  # no "You have N credits" line anywhere
    session = ObservingFakeAutopilotSession(text=text)
    profile = _make_profile(autonomous=False)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    decision = engine.dry_run_tick(
        current_ship=_barge(), ship_catalog=(_cruiser(),), loop=_loop_econ(), stardock_route=(100, 150, 999),
        explore_next_sector=999,
    )

    assert decision.chosen is not None, "credits-unknown must not silently produce a no-op tick"
    assert decision.chosen.kind == "explore", "explore spends nothing -- a None balance must not block it"
    assert decision.snapshot.credits is None
    assert all(c.kind != "upgrade" for c in decision.candidates)
    assert any("credits unknown" in s for s in decision.skipped)


def test_dry_run_tick_skips_upgrade_on_a_stale_balance():
    """Rook must-fix #4: a real, KNOWN balance older than
    `caps.credits_stale_ms` must be treated as unknown, never trusted no
    matter how comfortably above the cash floor it is -- proves the
    freshness gate actually fires end to end through `dry_run_tick()`, not
    just in `_fresh_credits()` isolation."""
    text = "5,000 turns left.\n" + _MAIN_COMMAND_SCREEN
    session = ObservingFakeAutopilotSession(text=text)
    session.observe_credits("You have 60,000 credits.\nCommand [TL=00:00:06]:[100] (?=Help)? :")
    time.sleep(0.05)  # the only known balance is now at least 50ms old
    profile = _make_profile(autonomous=False)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock, caps=EconCaps(credits_stale_ms=1))

    decision = engine.dry_run_tick(
        current_ship=_barge(), ship_catalog=(_cruiser(),), loop=_loop_econ(), stardock_route=(100, 150, 999),
    )

    assert all(c.kind != "upgrade" for c in decision.candidates)
    assert any("credits unknown" in s for s in decision.skipped)
    assert decision.snapshot.credits is None


def test_dry_run_tick_credits_stale_ms_is_config_driven_not_hardcoded():
    """The same stale reading `test_dry_run_tick_skips_upgrade_on_a_stale_
    balance` above rejects at `credits_stale_ms=1` must be ACCEPTED as
    fresh at a generous window -- proving the threshold genuinely comes
    from `EconCaps`, not a hardcoded constant that happens to match the
    default."""
    text = "5,000 turns left.\n" + _MAIN_COMMAND_SCREEN
    session = ObservingFakeAutopilotSession(text=text)
    session.observe_credits("You have 60,000 credits.\nCommand [TL=00:00:06]:[100] (?=Help)? :")
    time.sleep(0.05)
    profile = _make_profile(autonomous=False)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock, caps=EconCaps(credits_stale_ms=60_000))

    decision = engine.dry_run_tick(
        current_ship=_barge(), ship_catalog=(_cruiser(),), loop=_loop_econ(), stardock_route=(100, 150, 999),
    )

    assert decision.chosen is not None and decision.chosen.kind == "upgrade"
    assert decision.snapshot.credits == 60000


def test_live_tick_holds_on_a_blank_gate_render_rather_than_trusting_the_stale_pre_text():
    """cipher re-verify (2026-07-20), HIGH-2 TOCTOU + blank-screen bypass:
    the OLD code classified against the STALE tick-start `pre_text` render
    combined with a prompt_line from a SECOND, later render -- if a
    screen-clear lands between the two (a hub-warp CLS mid-transition),
    that second render is blank, and classify.py's own last-resort
    fallback (`if not prompt_line: <gate-scan the WHOLE full_text>`) would
    find the STALE main_command string still sitting in `pre_text` and
    green-light a send onto a screen that was never actually confirmed
    settled at all -- cipher's PoC fired a real send this way. The gate
    must derive BOTH full_text and prompt_line from ONE fresh render, and
    a blank gate render must itself HOLD."""
    session = ClearsAfterFirstRenderSession()  # settled main_command on the 1st render, blank on the 2nd (gate) render
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    decision = engine.live_tick(explore_next_sector=42)
    assert decision.send_outcome == "held:blank_screen"
    assert session.sent == [], "must NOT fire a send off a stale pre_text plus a blank gate render"


# -- MED: honor send_and_confirm's `confirmed` ---------------------------


def test_live_tick_marks_an_unconfirmed_send_rather_than_treating_it_as_success():
    session = NeverSettlesSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    ledger = FakeLedger()
    engine = AutopilotEngine(session, profile, lock, ledger=ledger)

    decision = engine.live_tick(explore_next_sector=42)
    assert decision.send_outcome == "unconfirmed"
    assert ledger.calls[0]["settled_class"] == "autopilot_tick_unconfirmed"


def test_autopilot_loop_halts_after_an_unconfirmed_tick_rather_than_ticking_blindly_on():
    session = NeverSettlesSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    loop = AutopilotLoop(engine, lambda: {"explore_next_sector": 1}, tick_interval_s=0.01)
    loop.start()

    assert _wait_until(lambda: not loop.running)
    assert loop.ticks_done == 1
    assert loop.last_error is not None and "unconfirmed" in loop.last_error
    assert lock.mode == MODE_AI_PILOT  # released cleanly, not wedged


# -- A-M1: AutopilotLoop installs its own stop-Event as the engine's -----
# -- should_abort kill switch for a whole-chain run_chain tick -----------


def test_autopilot_loop_start_installs_its_stop_event_as_the_engines_abort_seam():
    """WO-FA4 (A-M1): `AutopilotLoop.start()` must install `self._stop.
    is_set` onto the engine (never leave `_abort_requested` at its
    permanently-False `None` default) -- this is the ONLY real kill
    switch for an in-flight `run_chain` tick under MODE_AUTO_LOOP (see
    `AutopilotEngine._chain_abort_requested()`'s own docstring for why
    `control_lock.is_driver_fenced()` can never fire here)."""
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    assert engine._abort_requested is None

    loop = AutopilotLoop(engine, lambda: {"explore_next_sector": 1}, tick_interval_s=0.01)
    loop.start()
    try:
        assert engine._abort_requested == loop._stop.is_set
        assert engine._chain_abort_requested() is False
        loop._stop.set()
        assert engine._chain_abort_requested() is True
    finally:
        loop.stop()
    assert _wait_until(lambda: not loop.running)
    # Cleared on the way out -- a stale callable must never survive this
    # loop's own lifetime (e.g. a later standalone `_execute()` call on
    # the same engine after this loop has stopped).
    assert engine._abort_requested is None


def test_autopilot_engine_chain_abort_requested_is_false_with_no_loop_installed():
    """A caller driving `_execute()`/`live_tick()` standalone (no
    `AutopilotLoop` ever called `start()`) must get a permanently-False
    abort predicate, never a crash."""
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    assert engine._chain_abort_requested() is False


# -- MED: a background crash must not die silently -----------------------


def test_autopilot_loop_records_last_error_and_releases_the_lock_on_a_crash():
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    ledger = FakeLedger()
    engine = AutopilotEngine(session, profile, lock, ledger=ledger)

    def boom():
        raise RuntimeError("snapshot_provider blew up (e.g. a world-model read failed)")

    loop = AutopilotLoop(engine, boom, tick_interval_s=0.01)
    loop.start()

    assert _wait_until(lambda: not loop.running)
    assert loop.ticks_done == 0
    assert loop.last_error is not None and "RuntimeError" in loop.last_error
    assert lock.mode == MODE_AI_PILOT, "must release MODE_AUTO_LOOP even after a crash"
    assert len(ledger.calls) == 1
    assert ledger.calls[0]["settled_class"] == "autopilot_crashed"
    assert "CRASHED" in ledger.calls[0]["intent"]


# -- LOW: AutopilotLoop clamps its own run bounds ------------------------


def test_autopilot_loop_clamps_max_ticks_to_the_hard_cap():
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    loop = AutopilotLoop(engine, lambda: {"explore_next_sector": 1}, max_ticks=999_999)
    assert loop.max_ticks == 500


def test_autopilot_loop_floors_a_non_positive_tick_interval():
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    loop = AutopilotLoop(engine, lambda: {"explore_next_sector": 1}, tick_interval_s=-5.0)
    assert loop.tick_interval_s > 0


def test_autopilot_loop_floors_non_finite_tick_intervals():
    """mack re-verify (2026-07-20): `max(nan, x)` returns `nan` (a NaN-
    compare quirk) -- the OLD floor let NaN (and +-inf) straight through
    to `time.sleep()` in `_run()`'s tick loop, OUTSIDE that method's own
    try/except, killing the thread with `last_error` left at None (the
    exact silent-death class this revision's MED fix exists to close).
    `math.isfinite()` must catch NaN AND +-inf uniformly at construction."""
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    for bad_value in (float("nan"), float("inf"), float("-inf")):
        engine = AutopilotEngine(session, profile, lock)
        loop = AutopilotLoop(engine, lambda: {"explore_next_sector": 1}, tick_interval_s=bad_value)
        assert math.isfinite(loop.tick_interval_s), f"tick_interval_s={bad_value} must be floored to finite"
        assert loop.tick_interval_s > 0


def test_autopilot_loop_with_a_nan_tick_interval_does_not_die_silently():
    """The deeper end-to-end proof for the fix above: the loop must
    actually keep ticking rather than dying on its first `time.sleep()`
    with an unset `last_error` (indistinguishable from "never ticked
    yet" -- exactly the silent-death failure mode)."""
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    loop = AutopilotLoop(engine, lambda: {"explore_next_sector": 1}, tick_interval_s=float("nan"))
    loop.start()

    assert _wait_until(lambda: loop.ticks_done >= 2)
    loop.stop()
    assert _wait_until(lambda: not loop.running)
    assert loop.last_error is None  # ticked fine -- the NaN never reached time.sleep() at all


def test_autopilot_loop_floors_a_non_positive_max_ticks_to_at_least_one():
    """cipher re-verify (2026-07-20): a negative/zero `max_ticks` survived
    the old `min(int(max_ticks), _MAX_TICKS)` unchanged (`min(-10, 500) ==
    -10`), and `range(-10)` is empty -- a silently-"successful" 0-tick
    no-op run that masks whatever caller bug passed a negative value."""
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    loop = AutopilotLoop(engine, lambda: {"explore_next_sector": 1}, max_ticks=-10)
    assert loop.max_ticks == 1


# -- HIGH-3: interrupt-history is LIVE-tick only, dry-run never pollutes -


def test_interrupt_history_tracks_only_live_ticks_never_dry_run_previews():
    # A parseable turn count is required -- _score_chain fails CLOSED
    # (MED fix) on an unknown turns_left, so the default bare screen
    # (no "turns left" text) would skip the chain candidate outright.
    session = FakeAutopilotSession(text="5,000 turns left.\n" + _MAIN_COMMAND_SCREEN)
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    t1 = engine.live_tick(hops=tuple(_profit_chain_hops(margin=50)), explore_next_sector=999)
    assert t1.chosen.kind == "run_chain"
    assert t1.interrupted is False  # first live tick, nothing to interrupt

    # An unrelated PREVIEW call on the SAME engine (e.g. a status/preview
    # verb) -- must NOT pollute the LIVE interrupt history (HIGH-3).
    t2 = engine.dry_run_tick(explore_next_sector=999)
    assert t2.chosen.kind == "explore"

    t3 = engine.live_tick(hops=tuple(_profit_chain_hops(margin=50)), explore_next_sector=999)
    assert t3.chosen.kind == "run_chain"
    assert t3.interrupted is False, (
        "the real driven history never left run_chain -- the intervening dry-run preview must not count"
    )


def test_interrupt_fires_across_consecutive_live_ticks_when_ev_ranking_changes():
    # See the fail-closed note above -- a parseable turns_left is needed
    # for the chain candidate to be scored at all.
    session = FakeAutopilotSession(text="5,000 turns left.\n" + _MAIN_COMMAND_SCREEN)
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    t1 = engine.live_tick(explore_next_sector=999)  # only candidate: explore
    assert t1.chosen.kind == "explore"
    assert t1.interrupted is False

    t2 = engine.live_tick(hops=tuple(_profit_chain_hops(margin=50)), explore_next_sector=999)
    assert t2.chosen.kind == "run_chain"
    assert t2.interrupted is True, "a higher-EV chain must INTERRUPT the prior explore pursuit"


def test_concurrent_dry_run_and_live_ticks_do_not_corrupt_decisions_or_crash():
    """HIGH-3's lock-guard proof (mack poc2's concurrency half, previously
    untested): a background `AutopilotLoop` thread continuously driving
    `live_tick()` while several foreground threads hammer `dry_run_tick()`
    on the SAME engine (exactly the "status/preview verb polled while
    auto-loop drives" scenario this module's own class docstring calls
    out) must never raise or corrupt `self.decisions` -- the bounded ring
    stays within its own maxlen throughout."""
    session = FakeAutopilotSession(text="5,000 turns left.\n" + _MAIN_COMMAND_SCREEN)
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    loop = AutopilotLoop(engine, lambda: {"explore_next_sector": 1}, tick_interval_s=0.002)
    loop.start()

    errors: list[Exception] = []

    def hammer():
        try:
            for _ in range(100):
                engine.dry_run_tick(explore_next_sector=2)
        except Exception as exc:  # noqa: BLE001 -- captured, asserted below
            errors.append(exc)

    threads = [threading.Thread(target=hammer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    loop.stop()
    assert _wait_until(lambda: not loop.running)
    assert errors == [], f"concurrent dry_run_tick raised: {errors!r}"
    assert len(engine.decisions) <= 200  # _MAX_DECISIONS_KEPT bound respected under concurrent writers


# -- Cross-seat trace schema (2026-07-20 supplement) ---------------------


def test_decision_to_trace_matches_the_cross_seat_schema_on_a_multi_candidate_dry_run():
    """The headline dry-run trace, re-rendered through the cross-seat
    schema a sibling seat's Decisions-box viewer consumes: exact field
    names, genuine cr/turn for every scored candidate (never 0/guessed),
    gated=False for all three (nothing here was skipped or held), and the
    correct winning `chosen` kind.

    WO-FA-SAFE: `ObservingFakeAutopilotSession` (not the plain fake) --
    `assess()`'s `credits` now comes from `_fresh_credits()`'s strict
    `credits_snapshot()` read, fed by THIS tick's own `observe_credits()`
    call on this same screen text, so the fixture needs the credits-
    supervision surface wired to still resolve `cash=60_000`."""
    session = ObservingFakeAutopilotSession(
        text="You have 60,000 credits.\n5,000 turns left.\n" + _MAIN_COMMAND_SCREEN
    )
    profile = _make_profile()
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    decision = engine.dry_run_tick(
        current_ship=_barge(), ship_catalog=(_cruiser(),), loop=_loop_econ(),
        hops=tuple(_profit_chain_hops(margin=50)), stardock_route=(100, 150, 999),
        explore_next_sector=5,
    )
    trace = decision_to_trace(decision)

    assert trace["tick"] == 1
    assert trace["context"] == {"turns_left": 5000, "cash": 60_000, "sector": None}
    assert trace["chosen"] == "upgrade"

    by_kind = {c["kind"]: c for c in trace["candidates"]}
    assert set(by_kind) == {"run_chain", "upgrade", "explore"}
    assert by_kind["upgrade"]["ev_cr_per_turn"] == 550.0
    assert by_kind["upgrade"]["gated"] is False
    assert by_kind["upgrade"]["gate_reason"] is None
    assert by_kind["run_chain"]["ev_cr_per_turn"] == 50.0
    assert by_kind["run_chain"]["gated"] is False  # a valid, scored candidate that simply lost -- not gated
    assert by_kind["explore"]["ev_cr_per_turn"] == EXPLORE_BASELINE_EV


def test_decision_to_trace_represents_a_select_time_skip_as_gated_with_no_guessed_ev():
    snap = WorldSnapshot(
        sector=None, credits=5_000, turns_left=5000,  # below DEFAULT_CASH_FLOOR (10,000)
        current_ship=_barge(), ship_catalog=(_cruiser(),), loop=_loop_econ(),
        stardock_route=(100, 150, 999),
    )
    decision = select(snap)
    trace = decision_to_trace(decision)

    by_kind = {c["kind"]: c for c in trace["candidates"]}
    assert by_kind["upgrade"]["gated"] is True
    assert by_kind["upgrade"]["ev_cr_per_turn"] is None, "an unknown/skipped EV must never render as 0 or a guess"
    assert "cash floor" in by_kind["upgrade"]["gate_reason"]


def test_decision_to_trace_marks_a_held_send_as_gated_with_chosen_none():
    """HIGH-2's classify-hold rendered through the trace: `explore` DID win
    the score (still shown, EV intact) but the live screen wasn't the
    movement prompt, so nothing actually executed -- `chosen` must go to
    None (a HOLD), and the winning candidate's own entry flips to gated."""
    text = "Sector : 100\nSome narrative line\nYour offer [500] ?"
    session = FakeAutopilotSession(text=text)
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    decision = engine.live_tick(explore_next_sector=200)
    trace = decision_to_trace(decision)

    assert trace["chosen"] is None
    explore_entry = next(c for c in trace["candidates"] if c["kind"] == "explore")
    assert explore_entry["gated"] is True
    assert explore_entry["gate_reason"].startswith("held:")
    assert explore_entry["ev_cr_per_turn"] == EXPLORE_BASELINE_EV


def test_decision_to_trace_marks_an_unconfirmed_send_as_gated_with_chosen_none():
    session = NeverSettlesSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    decision = engine.live_tick(explore_next_sector=42)
    trace = decision_to_trace(decision)

    assert trace["chosen"] is None
    explore_entry = next(c for c in trace["candidates"] if c["kind"] == "explore")
    assert explore_entry["gated"] is True
    assert explore_entry["gate_reason"] == "unconfirmed"


def test_tick_counter_is_monotonic_across_dry_run_and_live_calls_on_one_engine():
    session = FakeAutopilotSession(text="5,000 turns left.\n" + _MAIN_COMMAND_SCREEN)
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    d1 = engine.live_tick(explore_next_sector=1)
    d2 = engine.dry_run_tick(explore_next_sector=2)
    d3 = engine.live_tick(explore_next_sector=3)
    assert (d1.tick, d2.tick, d3.tick) == (1, 2, 3)


def test_engine_trace_log_returns_the_bounded_recent_history_as_trace_dicts():
    session = FakeAutopilotSession(text="5,000 turns left.\n" + _MAIN_COMMAND_SCREEN)
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    for i in range(3):
        engine.live_tick(explore_next_sector=i)

    log = engine.trace_log()
    assert [t["tick"] for t in log] == [1, 2, 3]
    assert all(t["chosen"] == "explore" for t in log)


def test_autopilot_loop_snapshot_exposes_the_last_ticks_trace():
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    loop = AutopilotLoop(engine, lambda: {"explore_next_sector": 9}, tick_interval_s=0.01)
    loop.start()

    assert _wait_until(lambda: loop.ticks_done >= 1)
    loop.stop()
    assert _wait_until(lambda: not loop.running)

    snap = loop.snapshot()
    assert snap["last_trace"] is not None
    assert snap["last_trace"]["chosen"] == "explore"


# -- GATE: fail-closed, dry-run never sends ------------------------------


def test_disabled_profile_refuses_live_tick_and_sends_nothing():
    session = FakeAutopilotSession()
    profile = _make_profile()  # autonomous default False
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    assert engine.enabled is False

    try:
        engine.live_tick(explore_next_sector=42)
        assert False, "live_tick must refuse when profile.autonomous is False"
    except AutopilotGateError:
        pass
    assert session.sent == []


def test_disabled_profile_dry_run_tick_still_produces_a_full_decision_trace():
    # turns_left must be screen-derived (state_parser), same as every other
    # consumer -- unlike hops/catalog/loop (world-model/game-data-derived,
    # so caller-supplied), so this session's text carries a real parseable
    # turn count. credits is WO-FA-SAFE's strict `_fresh_credits()` source
    # (session.credits_snapshot(), fed by this tick's own observe_credits()
    # call below) -- ObservingFakeAutopilotSession, not the plain fake, so
    # this screen's real balance actually reaches the decision.
    session = ObservingFakeAutopilotSession(
        text="You have 60,000 credits.\n5,000 turns left.\n" + _MAIN_COMMAND_SCREEN
    )
    profile = _make_profile()
    lock = ControlLock()
    ledger = FakeLedger()
    engine = AutopilotEngine(session, profile, lock, ledger=ledger, session_id="sess-1")

    decision = engine.dry_run_tick(
        current_ship=_barge(), ship_catalog=(_cruiser(),), loop=_loop_econ(),
        hops=tuple(_profit_chain_hops(margin=50)), stardock_route=(100, 150, 999),
        explore_next_sector=5,
    )

    # Headline dry-run proof: all three candidate kinds scored, the
    # correct one won, ZERO sends, and it's ledgered (actor=trainer).
    kinds = {c.kind for c in decision.candidates}
    assert kinds == {"run_chain", "upgrade", "explore"}
    assert decision.chosen.kind == "upgrade"
    assert decision.chosen.ev_per_turn == 550.0
    assert session.sent == []
    assert len(ledger.calls) == 1
    assert ledger.calls[0]["actor"] == "trainer"
    assert ledger.calls[0]["input_text"] == "<dry-run:no-send>"
    assert "DRY-RUN" in ledger.calls[0]["intent"]
    assert "upgrade" in ledger.calls[0]["intent"]


def test_enabled_profile_live_tick_actually_sends_through_send_and_confirm():
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    ledger = FakeLedger()
    engine = AutopilotEngine(session, profile, lock, ledger=ledger, session_id="sess-2")
    assert engine.enabled is True

    decision = engine.live_tick(explore_next_sector=777)
    assert decision.chosen.kind == "explore"
    assert session.sent == [("777", True, False)]
    assert ledger.calls[0]["input_text"] == "777"
    assert ledger.calls[0]["actor"] == "trainer"


def test_econcaps_rejects_negative_floors_and_nonpositive_stale_ms():
    """Cipher FA4: a socket-tunable EconCaps must fail loud rather than
    silently disable the stop-loss / freshness / realized-margin floors
    it exists to enforce."""
    with pytest.raises(ValueError, match="cash_floor"):
        EconCaps(cash_floor=-1)
    with pytest.raises(ValueError, match="turn_reserve"):
        EconCaps(turn_reserve=-1)
    with pytest.raises(ValueError, match="credits_stale_ms"):
        EconCaps(credits_stale_ms=0)
    with pytest.raises(ValueError, match="min_margin_per_hop"):
        EconCaps(min_margin_per_hop=-1)


# -- WO-FA4: `run_chain` wiring at the `_execute()` choke point ----------


def test_execute_run_chain_wires_live_is_armed_and_should_abort_and_min_margin(monkeypatch):
    """WO-FA4: `_execute()`'s `run_chain` routing must hand `trade_driver.
    run_chain()` the ENGINE's OWN live `is_armed`/`should_abort`
    predicates (never a value captured once, and never the dead
    `control_lock.is_driver_fenced()` -- see `_chain_abort_requested()`'s
    own docstring) and thread `caps.min_margin_per_hop` into a fresh
    `TradeDriverConfig` -- proven by capturing the exact kwargs
    `run_chain()` was called with, not just its return value."""
    captured = {}

    def fake_run_chain(session, chain, **kwargs):
        captured.update(kwargs)
        return ChainRunResult(
            completed=True, hops_completed=2, steps=10, credits_delta=1234, stop_reason="completed"
        )

    monkeypatch.setattr(autopilot_mod, "run_chain", fake_run_chain)

    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock, caps=EconCaps(min_margin_per_hop=77))
    chain = ProfitChain(
        sectors=(100, 200, 100), hops=tuple(_profit_chain_hops(margin=50)),
        overall_profit=100.0, turns=2, cr_per_turn=50.0, cr_per_execution=100.0,
    )
    candidate = Candidate(kind="run_chain", ev_per_turn=50.0, rationale="r", next_sector=200, chain=chain)
    snapshot = WorldSnapshot(sector=100, credits=None, turns_left=500, world_id="w1", state_dir=None)

    engine._abort_requested = lambda: False
    confirmed, outcome = engine._execute(candidate, snapshot)

    assert confirmed is True
    assert outcome == "sent:credits_delta=+1234"
    assert captured["world_id"] == "w1"
    assert captured["turns_left"] == 500
    assert captured["config"].min_margin_per_hop == 77
    assert captured["is_armed"]() is True  # reflects engine.enabled live
    assert captured["should_abort"]() is False

    # should_abort is read LIVE (a bound method), not captured once at
    # _execute()-call time -- flipping the loop-installed predicate AFTER
    # the call must still show up.
    engine._abort_requested = lambda: True
    assert captured["should_abort"]() is True


def test_execute_run_chain_holds_when_snapshot_lacks_world_id_or_turns_left():
    """`run_chain()` must never even be CALLED with an unresolvable
    world/turns -- fails closed to a HOLD, never a guess."""
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    chain = ProfitChain(
        sectors=(100, 200, 100), hops=tuple(_profit_chain_hops(margin=50)),
        overall_profit=100.0, turns=2, cr_per_turn=50.0, cr_per_execution=100.0,
    )
    candidate = Candidate(kind="run_chain", ev_per_turn=50.0, rationale="r", next_sector=200, chain=chain)

    confirmed, outcome = engine._execute(candidate, None)
    assert (confirmed, outcome) == (False, "held:run_chain_unavailable")

    confirmed, outcome = engine._execute(
        candidate, WorldSnapshot(sector=100, credits=None, turns_left=None, world_id="w1")
    )
    assert (confirmed, outcome) == (False, "held:run_chain_unavailable")
    assert session.sent == []


def test_execute_run_chain_holds_with_the_stop_reason_when_the_chain_never_completes(monkeypatch):
    def fake_run_chain(session, chain, **kwargs):
        return ChainRunResult(
            completed=False, hops_completed=0, steps=3, credits_delta=None, stop_reason="cargo_stranded:0:sell:X"
        )

    monkeypatch.setattr(autopilot_mod, "run_chain", fake_run_chain)

    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    chain = ProfitChain(
        sectors=(100, 200, 100), hops=tuple(_profit_chain_hops(margin=50)),
        overall_profit=100.0, turns=2, cr_per_turn=50.0, cr_per_execution=100.0,
    )
    candidate = Candidate(kind="run_chain", ev_per_turn=50.0, rationale="r", next_sector=200, chain=chain)
    snapshot = WorldSnapshot(sector=100, credits=None, turns_left=500, world_id="w1")

    confirmed, outcome = engine._execute(candidate, snapshot)
    assert confirmed is False
    assert outcome == "held:cargo_stranded:0:sell:X"


def test_live_tick_run_chain_candidate_drives_the_trade_driver_and_records_credits_delta(monkeypatch):
    """WO-FA4 end-to-end at `live_tick()`: a chosen `run_chain` candidate
    must actually route through `trade_driver.run_chain()` (never a bare
    single-keystroke `send_and_confirm`), and its realized `credits_delta`
    must surface in `send_outcome`/the ledgered intent."""

    def fake_run_chain(session, chain, **kwargs):
        return ChainRunResult(
            completed=True, hops_completed=2, steps=8, credits_delta=500, stop_reason="completed",
            trace=("hop0 ...",),
        )

    monkeypatch.setattr(autopilot_mod, "run_chain", fake_run_chain)

    session = FakeAutopilotSession(text="Sector : 100\n1000 turns left.\n" + _MAIN_COMMAND_SCREEN)
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    ledger = FakeLedger()
    engine = AutopilotEngine(session, profile, lock, ledger=ledger, session_id="s1")

    decision = engine.live_tick(hops=tuple(_profit_chain_hops(margin=50)), world_id="w1", state_dir=None)

    assert decision.chosen.kind == "run_chain"
    assert decision.send_outcome == "sent:credits_delta=+500"
    # trade_driver.run_chain was faked -- never a bare nav send_and_confirm.
    assert session.sent == []
    assert "credits_delta=+500" in ledger.calls[-1]["intent"]


def test_live_tick_run_chain_candidate_holds_when_world_id_unresolved():
    """Without a resolvable `world_id` (protocol.py's trade lane not
    wired, or a bare fake-session test double), a chosen `run_chain`
    candidate must HOLD rather than crash or fall back to a bare send."""
    session = FakeAutopilotSession(text="Sector : 100\n1000 turns left.\n" + _MAIN_COMMAND_SCREEN)
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)

    decision = engine.live_tick(hops=tuple(_profit_chain_hops(margin=50)))

    assert decision.chosen.kind == "run_chain"
    assert decision.send_outcome == "held:run_chain_unavailable"
    assert session.sent == []


def test_execute_refuses_a_candidate_kind_outside_the_scorer_whitelist():
    """Belt-and-braces: `select()` can never actually produce this, but
    `_execute()`'s own whitelist must refuse rather than silently trust
    an unknown kind."""
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    try:
        engine._execute(Candidate(kind="genesis_deploy", ev_per_turn=999.0, rationale="nope", next_sector=1))
        assert False, "must refuse a non-whitelisted candidate kind"
    except AutopilotGateError:
        pass
    assert session.sent == []


# -- maybe_auto_start (P1-d) ----------------------------------------------


def test_maybe_auto_start_never_starts_for_the_default_disabled_profile():
    session = FakeAutopilotSession()
    profile = _make_profile()  # autonomous default False
    lock = ControlLock()
    loop = maybe_auto_start(session, profile, lock, lambda: {"explore_next_sector": 1})
    assert loop is None
    assert lock.mode == MODE_AI_PILOT
    assert session.sent == []


def test_maybe_auto_start_never_starts_under_a_human_attach():
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    lock.take_human()
    loop = maybe_auto_start(session, profile, lock, lambda: {"explore_next_sector": 1})
    assert loop is None
    assert lock.mode == MODE_HUMAN  # untouched -- never clobbered by the hook
    assert session.sent == []


def test_maybe_auto_start_drives_when_enabled_and_control_lock_is_free():
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    loop = maybe_auto_start(
        session, profile, lock, lambda: {"explore_next_sector": 555}, tick_interval_s=0.01
    )
    assert loop is not None
    assert loop.running is True
    assert lock.mode == MODE_AUTO_LOOP

    assert _wait_until(lambda: loop.ticks_done >= 2)
    assert "555" in [s[0] for s in session.sent]

    loop.stop()
    assert _wait_until(lambda: not loop.running)
    assert lock.mode == MODE_AI_PILOT  # leave_auto_loop() fired exactly once, on stop


def test_autopilot_loop_refuses_start_when_engine_is_disabled():
    session = FakeAutopilotSession()
    profile = _make_profile()  # disabled
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    loop = AutopilotLoop(engine, lambda: {"explore_next_sector": 1})
    try:
        loop.start()
        assert False, "must refuse to start a disabled engine"
    except AutopilotGateError:
        pass
    assert lock.mode == MODE_AI_PILOT


def test_autopilot_loop_refuses_double_start():
    session = FakeAutopilotSession()
    profile = _make_profile(autonomous=True)
    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    loop = AutopilotLoop(engine, lambda: {"explore_next_sector": 1}, tick_interval_s=0.05)
    loop.start()
    try:
        loop.start()
        assert False, "must refuse a second concurrent start"
    except AutopilotLoopError:
        pass
    finally:
        loop.stop()
        assert _wait_until(lambda: not loop.running)
