"""tests/test_trade_driver.py -- WO-FA4 trade_driver.py: the money-path
chain-execution driver. No network, no real telnet: a scripted,
deferred-bump `FakeChainSession` (mirrors `tests/test_skills.py`'s own
`FakeReplaySession`/`ObservingFakeReplaySession` conventions exactly --
see that class's own docstring for why the rx_count bump must be
deferred to the NEXT `sleep()` call, not synchronous inside `send()`)
drives every scripted screen transition; `autopilot.EconCaps` is the
real production type (duck-typed by trade_driver.py, see its own module
docstring) so these tests exercise the actual cross-module contract, not
a hand-rolled stand-in.

Every test below threads `should_abort`/`is_armed` explicitly (both
REQUIRED, fail-closed keyword-only params on `run_chain()` -- A-M1/A-C1)
-- `_run()` supplies the ordinary "never abort, always armed" defaults
for tests that aren't themselves exercising those two gates.
"""

import time
from dataclasses import dataclass

import pytest

from tw2002_aiclient import world_model
from tw2002_aiclient.chains import ProfitChain, TradeHop
from tw2002_aiclient.session.state_parser import OUTCOME_READ, read_credits_balance
from tw2002_aiclient.trade_driver import (
    DEFAULT_MAX_STEPS,
    PaladinViolation,
    TradeDriverConfig,
    _ALLOWED_LETTER_SENDS,
    _StepCtx,
    _send_letter,
    run_chain,
)


@dataclass(frozen=True)
class EconCaps:
    cash_floor: int
    turn_reserve: int
    credits_stale_ms: int


class FakeChainSession:
    """`screens[0]` is the CURRENT screen before any send(); each send()
    advances (deferred to the next sleep()) to the next entry, staying on
    the final one once exhausted -- exact same convention as
    `tests/test_skills.py`'s `FakeReplaySession`.

    `credits_snapshot()` mirrors the REAL `Session.credits_snapshot()`'s
    shape (`(last_credits, last_credits_ts)`), auto-refreshed by
    `_maybe_observe_credits()` on every advance whenever the newly-current
    screen carries a `state_parser.credits_balance()`-recognized "You have
    N credits" line -- a lightweight stand-in for what the REAL `Session.
    observe_credits()` would do if trade_driver.py's own per-step sends
    called it (they don't, by design -- only the outer `AutopilotEngine.
    live_tick()`/`dry_run_tick()` tick boundary does, see that module's
    WO-FA7a comments), so a multi-send chain run still sees a reasonably
    fresh cached balance at every fallback read, exactly as it would in
    real play where the credits line is shown at each accept."""

    def __init__(self, screens, *, initial_credits=None):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._screens = screens
        self._i = 0
        self.sent = []
        self._pending_advance = False
        self.last_credits = initial_credits
        self.last_credits_ts = time.monotonic() if initial_credits is not None else None

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
            self._maybe_observe_credits()

    def render(self):
        return self._screens[self._i].split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._screens[self._i]

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))
        self._pending_advance = True

    def credits_snapshot(self):
        return self.last_credits, self.last_credits_ts

    def _maybe_observe_credits(self):
        read = read_credits_balance(self._screens[self._i])
        if read.outcome == OUTCOME_READ:
            self.last_credits = read.balance
            self.last_credits_ts = time.monotonic()


def _caps(**over):
    kwargs = dict(cash_floor=1000, turn_reserve=10, credits_stale_ms=60_000)
    kwargs.update(over)
    return EconCaps(**kwargs)


def _run(session, chain, world_id, state_dir, turns_left, caps=None, **kwargs):
    """Thin wrapper supplying the ordinary "never abort, always armed"
    defaults for tests that aren't themselves exercising should_abort/
    is_armed (A-M1/A-C1) -- both stay REQUIRED on `run_chain()` itself,
    this is purely test-file convenience."""
    kwargs.setdefault("should_abort", lambda: False)
    kwargs.setdefault("is_armed", lambda: True)
    return run_chain(
        session,
        chain,
        world_id=world_id,
        state_dir=state_dir,
        turns_left=turns_left,
        caps=caps if caps is not None else _caps(),
        **kwargs,
    )


def _seed_two_sector_graph(world_id, state_dir):
    world_model.upsert_sector(world_id, {"sector_id": 1, "warps": [2]}, state_dir=state_dir)
    world_model.upsert_sector(world_id, {"sector_id": 2, "warps": [1]}, state_dir=state_dir)


_MENU = "\n<A> Attack this Port\n<T> Trade at this Port\n<Q> Quit, nevermind\n\nEnter your choice [T] ? "


def _two_port_loop_screens():
    """The full, hand-verified 2-port loop: buy 405 Fuel Ore @1 (budget
    9000, price 20), sell @2; buy 200 Equipment @2 (budget 9900, price
    40), sell @1. 19 entries -- 18 sends total (4 docks x (P+T) + 4
    qty-sends + 4 accepts + 2 nav)."""
    return [
        "Sector  : 1\nCommand [TL=00:00:08]:[1] (?=Help)? : ",  # 0
        _MENU,  # 1 (after P @1, hop0 buy)
        (
            "<Port>\n\nDocking...\nOne turn deducted, 99 turns left.\n\n"
            "Commerce report for PortA: 12:00:00 AM Mon Jan 01, 2054\n\n"
            " Items     Status  Trading % of max OnBoard\n"
            " -----     ------  ------- -------- -------\n"
            "Fuel Ore   Selling    500     100%       0\n"
            "Organics   Buying     300      50%       0\n"
            "Equipment  Buying     200      50%       0\n\n"
            "How many holds of Fuel Ore [500] ? "
        ),  # 2 (after T @1)
        "We'll sell them for 8100 credits.\nYour offer [8100] ? ",  # 3 (after qty 405 @ 20/unit)
        "You have 1,900 credits and 50 empty cargo holds.\n\nCommand [TL=00:00:08]:[1] (?=Help)? : ",  # 4 (after accept, 10000-8100)
        "Sector  : 2\nCommand [TL=00:00:08]:[2] (?=Help)? : ",  # 5 (after nav to 2)
        _MENU,  # 6 (after P @2, hop0 sell)
        (
            "<Port>\n\nDocking...\nOne turn deducted, 97 turns left.\n\n"
            "Commerce report for PortB: 12:00:00 AM Mon Jan 01, 2054\n\n"
            " Items     Status  Trading % of max OnBoard\n"
            " -----     ------  ------- -------- -------\n"
            "Fuel Ore   Buying     500     100%       0\n"
            "Organics   Selling    300      50%       0\n"
            "Equipment  Selling    200      50%       0\n\n"
            "How many holds of Fuel Ore [500] ? "
        ),  # 7 (after T @2)
        "We'll buy them for 9000 credits.\nYour offer [9000] ? ",  # 8 (after qty 405, sell)
        "You have 10,900 credits and 50 empty cargo holds.\n\nCommand [TL=00:00:08]:[2] (?=Help)? : ",  # 9 (after accept, 1900+9000)
        _MENU,  # 10 (after P @2, hop1 buy)
        (
            "<Port>\n\nDocking...\nOne turn deducted, 96 turns left.\n\n"
            "Commerce report for PortB: 12:00:00 AM Mon Jan 01, 2054\n\n"
            " Items     Status  Trading % of max OnBoard\n"
            " -----     ------  ------- -------- -------\n"
            "Fuel Ore   Buying     500     100%       0\n"
            "Organics   Selling    300      50%       0\n"
            "Equipment  Selling    200     100%       0\n\n"
            "How many holds of Equipment [200] ? "
        ),  # 11 (after T @2)
        "We'll sell them for 8000 credits.\nYour offer [8000] ? ",  # 12 (after qty 200 @ 40/unit)
        "You have 2,900 credits and 50 empty cargo holds.\n\nCommand [TL=00:00:08]:[2] (?=Help)? : ",  # 13 (after accept, 10900-8000)
        "Sector  : 1\nCommand [TL=00:00:08]:[1] (?=Help)? : ",  # 14 (after nav to 1)
        _MENU,  # 15 (after P @1, hop1 sell)
        (
            "<Port>\n\nDocking...\nOne turn deducted, 94 turns left.\n\n"
            "Commerce report for PortA: 12:00:00 AM Mon Jan 01, 2054\n\n"
            " Items     Status  Trading % of max OnBoard\n"
            " -----     ------  ------- -------- -------\n"
            "Fuel Ore   Selling    500     100%       0\n"
            "Organics   Buying     300      50%       0\n"
            "Equipment  Buying     200     100%       0\n\n"
            "How many holds of Equipment [200] ? "
        ),  # 16 (after T @1)
        "We'll buy them for 10000 credits.\nYour offer [10000] ? ",  # 17 (after qty 200, sell)
        "You have 12,900 credits and 50 empty cargo holds.\n\nCommand [TL=00:00:08]:[1] (?=Help)? : ",  # 18 (after accept, 2900+10000)
    ]


def _two_port_loop_chain():
    hop0 = TradeHop(frm=1, to=2, commodity="Fuel Ore", margin=10.0, turns=1)
    hop1 = TradeHop(frm=2, to=1, commodity="Equipment", margin=10.0, turns=1)
    return ProfitChain(
        sectors=(1, 2, 1), hops=(hop0, hop1), overall_profit=20.0, turns=2, cr_per_turn=10.0, cr_per_execution=20.0
    )


# -- happy path -----------------------------------------------------------


def test_run_chain_completes_a_scripted_two_port_loop_with_exact_credits_math(tmp_path):
    """Landmine coverage: auto-haggle-off (every accept is a blank line,
    never a counter), computed buy-qty (never buy-max: 405 < the port's
    own [500] bracket, 200 == live_max under a profitable sell), turns-
    budget reconciliation at every hop boundary, PALADIN (only "P"/"T"
    letters ever sent)."""
    world_id = "test-two-port-loop"
    _seed_two_sector_graph(world_id, tmp_path)
    session = FakeChainSession(_two_port_loop_screens(), initial_credits=10_000)

    result = _run(session, _two_port_loop_chain(), world_id, tmp_path, 100)

    assert result.completed is True
    assert result.stop_reason == "completed"
    assert result.hops_completed == 2
    # -8100 (buy Fuel Ore) +9000 (sell) -8000 (buy Equipment) +10000 (sell)
    assert result.credits_delta == 2900

    # Never buy-max: the qty actually SENT at each buy leg is strictly
    # below the port's own bracket default (500/200).
    qty_sends = [int(text) for text, enter, secret in session.sent if text.isdigit() and len(text) < 4]
    assert 405 in qty_sends and 200 in qty_sends
    assert all(q < 500 for q in qty_sends)

    # PALADIN: the only letters ever sent are "P"/"T" -- never "A"ttack.
    letters_sent = {text for text, enter, secret in session.sent if text in ("P", "T", "A", "Q")}
    assert letters_sent == {"P", "T"}

    # Auto-haggle off: every accept is a bare blank line, never a counter
    # figure distinct from the port's own offer.
    accepts = [text for text, enter, secret in session.sent if text == ""]
    assert len(accepts) == 4


def test_realized_losing_hop_aborts_before_the_next_buy(tmp_path):
    """FA3 ranks on an explicitly unverified pct curve; FA4 must treat
    live transaction totals as authoritative. A hop ranked profitable
    but realized at a loss aborts before the next hop can compound it."""
    world_id = "test-realized-loss"
    _seed_two_sector_graph(world_id, tmp_path)
    screens = _two_port_loop_screens()[:10]
    screens[8] = "We'll buy them for 4455 credits.\nYour offer [4455] ? "
    screens[9] = (
        "You have 6,355 credits and 50 empty cargo holds.\n\n"
        "Command [TL=00:00:08]:[2] (?=Help)? : "
    )
    session = FakeChainSession(screens, initial_credits=10_000)

    result = _run(session, _two_port_loop_chain(), world_id, tmp_path, 100)

    assert result.completed is False
    assert result.hops_completed == 1
    assert result.credits_delta == -3645
    assert result.stop_reason == "realized_margin_below_floor:0:-3645"
    assert "realized-loss" in result.trace[-1]
    assert len(session.sent) == 9
    assert all(text != "200" for text, _enter, _secret in session.sent)


# -- A-M1: should_abort -- interruptible within one send-step -------------


def test_should_abort_true_at_hop_entry_produces_zero_sends(tmp_path):
    """The whole-chain tick's kill switch must be able to abort BEFORE
    the very first send if it's already true at hop entry."""
    world_id = "test-m1-abort-before-any-send"
    _seed_two_sector_graph(world_id, tmp_path)
    session = FakeChainSession(
        ["Sector  : 1\nCommand [TL=00:00:08]:[1] (?=Help)? : "], initial_credits=10_000
    )

    result = _run(
        session, _two_port_loop_chain(), world_id, tmp_path, 100,
        should_abort=lambda: True,
    )

    assert result.completed is False
    assert result.stop_reason == "aborted"
    assert session.sent == []


def test_should_abort_mid_chain_halts_at_the_next_send_step_not_chain_end(tmp_path):
    """A-M1 (the #1 arm-prerequisite): the abort predicate flipping True
    mid-chain must halt at the NEXT `_confirmed_send` -- not at chain
    end (18 sends when the full loop completes) and not zero (the abort
    wasn't already true at hop entry). Mirrors `AutopilotLoop._stop`
    firing partway through a live `run_chain` tick."""
    world_id = "test-m1-mid-chain-abort"
    _seed_two_sector_graph(world_id, tmp_path)
    session = FakeChainSession(_two_port_loop_screens(), initial_credits=10_000)

    result = _run(
        session, _two_port_loop_chain(), world_id, tmp_path, 100,
        should_abort=lambda: len(session.sent) >= 4,  # true right after hop0's buy-accept
    )

    assert result.completed is False
    assert result.stop_reason == "aborted"
    assert result.hops_completed == 0
    assert len(session.sent) == 4


# -- A-C1: is_armed -- required, fail-closed -------------------------------


def test_is_armed_false_produces_zero_sends_fail_closed(tmp_path):
    world_id = "test-c1-unarmed"
    _seed_two_sector_graph(world_id, tmp_path)
    session = FakeChainSession(
        ["Sector  : 1\nCommand [TL=00:00:08]:[1] (?=Help)? : "], initial_credits=10_000
    )

    result = _run(
        session, _two_port_loop_chain(), world_id, tmp_path, 100,
        is_armed=lambda: False,
    )

    assert result.completed is False
    assert result.stop_reason == "armed_off"
    assert session.sent == []


def test_start_anchor_mismatch_produces_zero_sends(tmp_path):
    world_id = "test-start-anchor"
    _seed_two_sector_graph(world_id, tmp_path)
    session = FakeChainSession(
        ["Sector  : 2\nCommand [TL=00:00:08]:[2] (?=Help)? : "],
        initial_credits=10_000,
    )

    result = _run(session, _two_port_loop_chain(), world_id, tmp_path, 100)

    assert result.stop_reason == "start_anchor_mismatch:2:1"
    assert result.steps == 0
    assert session.sent == []


# -- A-M2: sell-side genuine [0] must never strand cargo -------------------


def test_sell_side_genuine_zero_bracket_holds_cargo_stranded_never_completes(tmp_path):
    """A-M2 (CRITICAL, mack's exact repro): buy 45 Fuel Ore @ PortA (900cr),
    sail to PortB where Fuel Ore shows a genuine `[0]` bracket -- must HOLD
    `cargo_stranded`, never silently decline-and-count-the-hop-done (which
    would strand the cargo we already paid for while reporting a
    profitable round trip that never happened)."""
    world_id = "test-m2-cargo-stranded"
    _seed_two_sector_graph(world_id, tmp_path)
    screens = [
        "Sector  : 1\nCommand [TL=00:00:08]:[1] (?=Help)? : ",
        _MENU,
        (
            "<Port>\n\nDocking...\nOne turn deducted, 99 turns left.\n\n"
            "Commerce report for PortA: 12:00:00 AM Mon Jan 01, 2054\n\n"
            " Items     Status  Trading % of max OnBoard\n"
            " -----     ------  ------- -------- -------\n"
                "Fuel Ore   Selling    500     100%       0\n"
                "Organics   Buying     300      50%       0\n"
                "Equipment  Buying     200      50%       0\n\n"
            "How many holds of Fuel Ore [500] ? "
        ),
        "We'll sell them for 900 credits.\nYour offer [900] ? ",
        "You have 1,100 credits and 50 empty cargo holds.\n\nCommand [TL=00:00:08]:[1] (?=Help)? : ",
        "Sector  : 2\nCommand [TL=00:00:08]:[2] (?=Help)? : ",
        _MENU,
        (
            "<Port>\n\nDocking...\nOne turn deducted, 97 turns left.\n\n"
            "Commerce report for PortB: 12:00:00 AM Mon Jan 01, 2054\n\n"
            " Items     Status  Trading % of max OnBoard\n"
            " -----     ------  ------- -------- -------\n"
                "Fuel Ore   Selling      0     100%       0\n"
                "Organics   Selling    300      50%       0\n"
                "Equipment  Buying     200      50%       0\n\n"
            "How many holds of Fuel Ore [0] ? "
        ),
        "Command [TL=00:00:08]:[2] (?=Help)? : ",  # after decline("0")
    ]
    session = FakeChainSession(screens, initial_credits=2_000)
    chain = ProfitChain(
        sectors=(1, 2, 1),
        hops=(TradeHop(frm=1, to=2, commodity="Fuel Ore", margin=5.0, turns=1),),
        overall_profit=5.0, turns=1, cr_per_turn=5.0, cr_per_execution=5.0,
    )

    result = _run(session, chain, world_id, tmp_path, 100)

    assert result.completed is False
    assert result.stop_reason == "cargo_stranded:0:sell:Fuel Ore"
    assert result.hops_completed == 0
    # Bought (900cr spent) and never recovered -- the whole point of this
    # fix: never silently report this as a completed, profitable loop.
    assert result.credits_delta == -900


# -- A-M3: the dock itself must be turn-floor-gated, not just nav warps ----


def test_dock_turn_floor_gates_the_actual_sell_dock_not_just_the_upfront_estimate(tmp_path):
    """A-M3 (HIGH, mack's exact repro numbers): a hop whose discovery-time
    `hop.turns` undercounts the LIVE route (the known graph grew since
    discovery -- here, a declared turns=1 direct hop vs. an actual 2-warp
    route with no direct edge) must HOLD at the sell dock's own turn-floor
    re-check, never fire the dock unconditionally past the reserve."""
    world_id = "test-m3-dock-turn-floor"
    world_model.upsert_sector(world_id, {"sector_id": 1, "warps": [2]}, state_dir=tmp_path)
    world_model.upsert_sector(world_id, {"sector_id": 2, "warps": [1, 3]}, state_dir=tmp_path)
    world_model.upsert_sector(world_id, {"sector_id": 3, "warps": [2]}, state_dir=tmp_path)
    screens = [
        "Sector  : 1\nCommand [TL=00:00:08]:[1] (?=Help)? : ",  # 0
        _MENU,  # 1 (after P @1)
        (
            "<Port>\n\nDocking...\nOne turn deducted, 12 turns left.\n\n"
            "Commerce report for PortA: 12:00:00 AM Mon Jan 01, 2054\n\n"
            " Items     Status  Trading % of max OnBoard\n"
            " -----     ------  ------- -------- -------\n"
                "Fuel Ore   Selling    500     100%       0\n"
                "Organics   Buying     300      50%       0\n"
                "Equipment  Buying     200      50%       0\n\n"
            "How many holds of Fuel Ore [500] ? "
        ),  # 2 (after T @1)
        "We'll sell them for 900 credits.\nYour offer [900] ? ",  # 3 (after qty 45)
        "You have 1,100 credits and 50 empty cargo holds.\n\nCommand [TL=00:00:08]:[1] (?=Help)? : ",  # 4 (after accept)
        "Sector  : 2\nCommand [TL=00:00:08]:[2] (?=Help)? : ",  # 5 (after nav "2")
        "Sector  : 3\nCommand [TL=00:00:08]:[3] (?=Help)? : ",  # 6 (after nav "3")
    ]
    session = FakeChainSession(screens, initial_credits=2_000)
    # Declared turns=1 as if 1<->3 were directly adjacent at discovery
    # time; the known graph only has the 1<->2<->3 route (no direct edge).
    chain = ProfitChain(
        sectors=(1, 3, 1),
        hops=(TradeHop(frm=1, to=3, commodity="Fuel Ore", margin=5.0, turns=1),),
        overall_profit=5.0, turns=1, cr_per_turn=5.0, cr_per_execution=5.0,
    )

    # 13 turns left, reserve floor 10, dock_turn_cost 1 (default): the
    # upfront estimate (13 - (1 + 2*1) = 10, not < 10) passes; the REAL
    # 2-warp nav (13 -> 12 dock -> 11 -> 10) leaves exactly 10 turns, and
    # the sell dock's OWN turn cost would breach the reserve by 1 (9 < 10).
    result = _run(session, chain, world_id, tmp_path, 13, caps=_caps(turn_reserve=10))

    assert result.completed is False
    assert result.stop_reason == "turn_floor:0:predock"
    assert result.hops_completed == 0
    # Exactly the buy leg (P, T, qty, accept) + the two nav warps -- HOLD
    # BEFORE the sell dock, never "P"/"T" sent past the breach.
    assert len(session.sent) == 6
    assert session.sent[-2][0] == "2"
    assert session.sent[-1][0] == "3"
    assert all(text not in ("P", "T") for text, _e, _s in session.sent[4:])


def test_low_turns_holds_before_the_stranding_hop(tmp_path):
    """The pre-hop upfront turn-floor check must refuse before ANY send
    if the hop's own cost (plus dock overhead) would breach the reserve
    floor -- never strand at 0 turns."""
    world_id = "test-low-turns"
    _seed_two_sector_graph(world_id, tmp_path)
    session = FakeChainSession(["Sector  : 1\nCommand [TL=00:00:08]:[1] (?=Help)? : "], initial_credits=2_000)
    chain = ProfitChain(
        sectors=(1, 2, 1),
        hops=(TradeHop(frm=1, to=2, commodity="Fuel Ore", margin=5.0, turns=5),),
        overall_profit=5.0, turns=5, cr_per_turn=1.0, cr_per_execution=5.0,
    )

    # 12 turns left, reserve floor 10 -- the hop needs 5 (warp) + 2 (both
    # docks) = 7, leaving only 5 productive, under the 10t floor.
    result = _run(session, chain, world_id, tmp_path, 12, caps=_caps(turn_reserve=10))

    assert result.completed is False
    assert result.stop_reason.startswith("turn_floor:")
    assert session.sent == []  # never sent a single keystroke


# -- A-C4: post-accept sanity check validates MAGNITUDE, not just direction -


def test_credit_delta_anomaly_fires_on_a_magnitude_mismatch_even_with_correct_direction(tmp_path):
    """A-C4: the original check only verified the DIRECTION of the drop
    (buy: after<=before); a magnitude mismatch in the SAME direction (a
    real overcharge/mis-parse) must still be caught."""
    world_id = "test-c4-magnitude"
    _seed_two_sector_graph(world_id, tmp_path)
    screens = [
        "Sector  : 1\nCommand [TL=00:00:08]:[1] (?=Help)? : ",
        _MENU,
        (
            "<Port>\n\nDocking...\nOne turn deducted, 99 turns left.\n\n"
            "Commerce report for PortA: 12:00:00 AM Mon Jan 01, 2054\n\n"
            " Items     Status  Trading % of max OnBoard\n"
            " -----     ------  ------- -------- -------\n"
                "Fuel Ore   Selling    500     100%       0\n"
                "Organics   Buying     300      50%       0\n"
                "Equipment  Buying     200      50%       0\n\n"
            "How many holds of Fuel Ore [500] ? "
        ),
        "We'll sell them for 900 credits.\nYour offer [900] ? ",
        # Direction is correct (a real drop, 2000 -> 1150 = -850) but the
        # MAGNITUDE doesn't match the live total (900) -- exactly the
        # mis-parse/overcharge shape a direction-only check would miss.
        "You have 1,150 credits and 50 empty cargo holds.\n\nCommand [TL=00:00:08]:[1] (?=Help)? : ",
    ]
    session = FakeChainSession(screens, initial_credits=2_000)
    chain = ProfitChain(
        sectors=(1, 2, 1),
        hops=(TradeHop(frm=1, to=2, commodity="Fuel Ore", margin=5.0, turns=1),),
        overall_profit=5.0, turns=1, cr_per_turn=5.0, cr_per_execution=5.0,
    )

    result = _run(session, chain, world_id, tmp_path, 100)

    assert result.completed is False
    assert result.stop_reason == "credit_delta_anomaly:0:buy:Fuel Ore"


# -- other landmines (unchanged behavior, re-verified against the current
# -- should_abort/is_armed signature) --------------------------------------


def test_buy_quantity_is_computed_from_budget_never_the_ports_own_max_default(tmp_path):
    """`parse_haggle`'s totals are per-TRANSACTION, not per-unit -- this
    asserts the SENT qty is sized off our own price-estimate/budget math
    (well under the port's [500] bracket), not a blind accept of that
    bracket's own default."""
    world_id = "test-buy-qty"
    _seed_two_sector_graph(world_id, tmp_path)
    screens = [
        "Sector  : 1\nCommand [TL=00:00:08]:[1] (?=Help)? : ",
        _MENU,
        (
            "<Port>\n\nDocking...\nOne turn deducted, 99 turns left.\n\n"
            "Commerce report for PortA: 12:00:00 AM Mon Jan 01, 2054\n\n"
            " Items     Status  Trading % of max OnBoard\n"
            " -----     ------  ------- -------- -------\n"
                "Fuel Ore   Selling    500     100%       0\n"
                "Organics   Buying     300      50%       0\n"
                "Equipment  Buying     200      50%       0\n\n"
            "How many holds of Fuel Ore [500] ? "
        ),
        "We'll sell them for 900 credits.\nYour offer [900] ? ",
        "You have 1,100 credits and 50 empty cargo holds.\n\nCommand [TL=00:00:08]:[1] (?=Help)? : ",
        # hop.to's port has nothing tradeable -- ends the run cleanly via
        # "depleted", the focus here is purely the BUY leg's own sizing.
        "Sector  : 2\nCommand [TL=00:00:08]:[2] (?=Help)? : ",
        _MENU,
        "<Port>\n\nDocking...\nOne turn deducted, 97 turns left.\n\nYou don't have anything they want, and they don't have anything you can buy.\n\nYou have 1,100 credits and 50 empty cargo holds.\n\nCommand [TL=00:00:08]:[2] (?=Help)? : ",
    ]
    session = FakeChainSession(screens, initial_credits=2_000)
    chain = ProfitChain(
        sectors=(1, 2, 1),
        hops=(TradeHop(frm=1, to=2, commodity="Fuel Ore", margin=5.0, turns=1),),
        overall_profit=5.0, turns=1, cr_per_turn=5.0, cr_per_execution=5.0,
    )

    result = _run(session, chain, world_id, tmp_path, 100)

    # budget = 2000-1000 = 1000; price = floor(20) since pct=100; qty =
    # int(1000/20*0.9) = 45 -- well under the port's own [500] default.
    qty_sends = [text for text, enter, secret in session.sent if text.isdigit() and text not in ("0",)]
    assert "45" in qty_sends
    assert result.stop_reason.startswith("depleted:")


def test_over_budget_offer_holds_without_ever_accepting(tmp_path):
    """A live total that comes back over (credits - cash_floor) must
    HOLD -- never accept, never counter (bounded-HOLD backstop)."""
    world_id = "test-over-budget"
    _seed_two_sector_graph(world_id, tmp_path)
    screens = [
        "Sector  : 1\nCommand [TL=00:00:08]:[1] (?=Help)? : ",
        _MENU,
        (
            "<Port>\n\nDocking...\nOne turn deducted, 99 turns left.\n\n"
            "Commerce report for PortA: 12:00:00 AM Mon Jan 01, 2054\n\n"
            " Items     Status  Trading % of max OnBoard\n"
            " -----     ------  ------- -------- -------\n"
                "Fuel Ore   Selling    500     100%       0\n"
                "Organics   Buying     300      50%       0\n"
                "Equipment  Buying     200      50%       0\n\n"
            "How many holds of Fuel Ore [500] ? "
        ),
        # A live total far above what our own price estimate/budget
        # expected -- a price surprise the offer prompt is the only place
        # this could ever be caught.
        "We'll sell them for 999999 credits.\nYour offer [999999] ? ",
    ]
    session = FakeChainSession(screens, initial_credits=2_000)
    chain = ProfitChain(
        sectors=(1, 2, 1),
        hops=(TradeHop(frm=1, to=2, commodity="Fuel Ore", margin=5.0, turns=1),),
        overall_profit=5.0, turns=1, cr_per_turn=5.0, cr_per_execution=5.0,
    )

    result = _run(session, chain, world_id, tmp_path, 100)

    assert result.completed is False
    assert result.stop_reason.startswith("over_budget:")
    # Never accepted -- the last send is the qty, never a blank accept.
    assert session.sent[-1][0] != ""


def test_depleted_stock_stops_the_chain_cleanly(tmp_path):
    """If the commodity cascade never shows our target commodity at all
    (the live, authoritative signal that it isn't tradeable right now),
    stop cleanly rather than guessing/forcing a trade."""
    world_id = "test-depleted"
    _seed_two_sector_graph(world_id, tmp_path)
    screens = [
        "Sector  : 1\nCommand [TL=00:00:08]:[1] (?=Help)? : ",
        _MENU,
        (
            "<Port>\n\nDocking...\nOne turn deducted, 99 turns left.\n\n"
            "You don't have anything they want, and they don't have anything you can buy.\n\n"
            "You have 2,000 credits and 50 empty cargo holds.\n\n"
            "Command [TL=00:00:08]:[1] (?=Help)? : "
        ),
    ]
    session = FakeChainSession(screens, initial_credits=2_000)
    chain = ProfitChain(
        sectors=(1, 2, 1),
        hops=(TradeHop(frm=1, to=2, commodity="Fuel Ore", margin=5.0, turns=1),),
        overall_profit=5.0, turns=1, cr_per_turn=5.0, cr_per_execution=5.0,
    )

    result = _run(session, chain, world_id, tmp_path, 100)

    assert result.completed is False
    assert result.stop_reason == "depleted:0:buy:Fuel Ore"


def test_unexpected_screen_holds_instead_of_retry_spinning(tmp_path):
    """A screen that matches NONE of the recognized shapes must HOLD
    immediately -- never spin retrying the same send."""
    world_id = "test-unexpected"
    _seed_two_sector_graph(world_id, tmp_path)
    screens = [
        "Sector  : 1\nCommand [TL=00:00:08]:[1] (?=Help)? : ",
        "Something has gone terribly wrong here.",  # never confirms the port-menu shape
    ]
    session = FakeChainSession(screens, initial_credits=2_000)
    chain = ProfitChain(
        sectors=(1, 2, 1),
        hops=(TradeHop(frm=1, to=2, commodity="Fuel Ore", margin=5.0, turns=1),),
        overall_profit=5.0, turns=1, cr_per_turn=5.0, cr_per_execution=5.0,
    )

    result = _run(session, chain, world_id, tmp_path, 100)

    assert result.completed is False
    assert result.stop_reason.startswith("unconfirmed_send:") or result.stop_reason.startswith("unexpected_screen:")
    # Bounded: exactly one send attempted ("P"), never a retry-spin up to
    # the step cap.
    assert result.steps <= 1
    assert result.steps < DEFAULT_MAX_STEPS


def test_paladin_send_letter_refuses_any_letter_outside_the_allowlist():
    """PALADIN: no combat/attack/genesis verb reachable -- `_send_letter`
    is the one place a single-letter command could ever be sent, and it
    refuses anything outside the allowlist (never `"A"`ttack, never
    `"Q"`uit-as-a-driver-choice). `"Y"` is WO-WARP-CONFIRM-Y only."""
    assert _ALLOWED_LETTER_SENDS == {"P", "T", "Y"}

    class _NeverSendsSession:
        def render(self):
            return ["Command [TL=00:00:08]:[1] (?=Help)? : "]

        def render_text(self, rows=None):
            return "\n".join(rows) if rows is not None else ""

    ctx = _StepCtx(_NeverSendsSession(), TradeDriverConfig(), lambda: False, lambda: True)
    with pytest.raises(PaladinViolation):
        _send_letter(ctx, "A", r"Enter\s+your\s+choice")


# -- A-PROG: progress events are UX parity, never a chain-execution gate ---


def test_on_progress_fires_at_each_hop_boundary_and_once_more_at_chain_end(tmp_path):
    world_id = "test-progress"
    _seed_two_sector_graph(world_id, tmp_path)
    session = FakeChainSession(_two_port_loop_screens(), initial_credits=10_000)
    events = []

    result = _run(session, _two_port_loop_chain(), world_id, tmp_path, 100, on_progress=events.append)

    assert result.completed is True
    # One event per completed hop (done=False) plus one final event
    # (done=True) -- mirrors loop_player.LoopPlayer's own per-cycle +
    # final-call shape.
    assert len(events) == 3
    assert [e["done"] for e in events] == [False, False, True]
    assert [e["hop_index"] for e in events[:2]] == [0, 1]
    assert events[-1]["stop_reason"] == "completed"
    assert all(e["kind"] == "chain_progress" for e in events)


def test_on_progress_callback_exception_is_swallowed_never_aborts_the_chain(tmp_path):
    world_id = "test-progress-exception"
    _seed_two_sector_graph(world_id, tmp_path)
    session = FakeChainSession(_two_port_loop_screens(), initial_credits=10_000)

    def boom(event):
        raise RuntimeError("telemetry sink is down")

    result = _run(session, _two_port_loop_chain(), world_id, tmp_path, 100, on_progress=boom)

    assert result.completed is True  # a pure telemetry failure must never halt the money path
