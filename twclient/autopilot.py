"""twclient/autopilot.py — §22/§23 Phase 1 autonomous goal-orchestrator
(WO-P1 sub-parts P1-a scheduler core, P1-c gate + dry-run, P1-d
auto-start hook). Deterministic, NO LLM. See the ratified design at
`.samantha/plans/tw2002-phase1-orchestrator-design-2026-07-20.md`
(gitignored internal planning doc) for the full rationale this module
implements.

**The tick loop (design doc's ASSESS -> SELECT -> EXECUTE -> RECORD),
actor="trainer":**

1. **ASSESS** — `assess()` turns the CURRENT rendered screen (via
   `state_parser.parse_state()`, already anchored to the LAST match --
   see that module's docstring) plus caller-supplied world-model-derived
   inputs (known trade hops, the current ship spec, an upgrade candidate
   catalog + loop economics, an explore/StarDock plan) into one
   `WorldSnapshot`. `chains.py`/`ship_upgrade_decision.py`/`explore.py`
   are all deliberately decoupled from the world-model by their own
   design ("mockable input, wire the adapter later" -- see each module's
   docstring); this module wires them via explicit caller-supplied
   inputs rather than inventing a new world-model-to-hops/catalog bridge
   that doesn't exist anywhere else in this codebase yet.
2. **SELECT** — `select()` is a CONTINUOUS cost-benefit scorer (the
   ratified refinement, decision #2 below), never a fixed sequence: every
   candidate action is scored by expected value (cr/turn) from scratch,
   every tick, with NO persisted "committed pursuit" state carried
   between ticks. This is what makes interruption structural rather than
   a special case: a lower-EV pursuit is naturally abandoned the instant
   a higher-EV one out-scores it on the very next tick, because nothing
   about a previous tick's pick constrains the next one.
3. **EXECUTE** — gated by BOTH the per-profile `autonomous` opt-in flag
   (fail-closed, default False -- see `credentials.Profile`) and dry-run:
   `AutopilotEngine.dry_run_tick()` NEVER sends, regardless of the flag
   (the pre-enablement proof surface, decision #5); `live_tick()` refuses
   outright (`AutopilotGateError`) unless `profile.autonomous` is True,
   and even then only ever sends ONE plain sector-number navigation
   keystroke per tick, gated on the CURRENT screen actually classifying
   as the main sector command prompt (see "HIGH-2" note below), via
   `settle.send_and_confirm` (the Phase-0 net -- never a bare
   `session.send()`). See this module's own docstring section "Scope:
   EXECUTE is navigation-only" below for why a fuller dock/trade/haggle
   driver is NOT built here.
4. **RECORD** — every tick's decision (dry-run or live) is ledgered via
   `ledger.LedgerWriter.record_do()`, `actor="trainer"`, so the autonomy
   gauge/session-retro can see it regardless of whether it drove.

**Scope: EXECUTE is navigation-only (a deliberate, surfaced scope cut).**
The design doc's goal-set wiring table describes "run the trade loop" as
`loop_player` replay / a deterministic trade driver + `haggle` -- but
`loop_player.py` only replays an ALREADY-RECORDED skill (`tw record`),
and no generic "drive an arbitrary freshly-discovered `ProfitChain`
end-to-end (navigate, dock, buy/sell to a haggle target, undock, repeat)"
primitive exists anywhere in this codebase yet. Building that generic
trade-automation driver is a substantially bigger, separate engineering
effort than "wire the already-built engines into a scorer" -- so EXECUTE
here is deliberately narrowed to the one action every candidate kind
converges on safely: send the next navigation hop's sector number via
`send_and_confirm(confirm_prompt=None)` (TW-02's own convention for a
caller with no single known target regex -- see settle.py's module
docstring). This is provably safe (a bare sector-number send can never
trigger a destructive/Genesis/PvP/colonist-commitment prompt) and is
enough to prove the gate + control-lock discipline end to end; a fuller
haggle-wired trade-loop driver is a natural follow-up, not invented here
unreviewed. `run_chain`'s `next_sector` is populated only when the
player is CURRENTLY SITTING at the chain's normalized start sector (see
`_score_chain`) -- navigating TO an off-position chain's start first is
the same follow-up, and would reuse `explore.path_to_sector`.

**HIGH-2 (adversarial-review fix, 2026-07-20): a classify-gate on the
LIVE screen before every send.** `next_sector` rides `assess().sector`,
which is `state_parser`'s whole-buffer LAST-match "Sector : N" --
correct for `state_parser` (that anchoring is a deliberate stale-
scrollback fix, never to be "simplified" back to first-match -- see that
module's own docstring), but it means a STALE "Sector : 100" block can
still be sitting in scrollback above a LIVE, totally different blocking
prompt (a haggle "Your offer [500] ?", a colonist-quantity/fighter-
deploy prompt) that also happens to take a bare number + Enter. Sending
a candidate's `next_sector` with zero regard for what's actually
live on screen would fire that number into whatever's really being
asked. `live_tick()` therefore reclassifies the CURRENT screen via
`classify.classify_screen()` immediately before every send and refuses
(HOLDS the tick, no send, `Decision.send_outcome` records why) unless
the live classification is exactly `"main_command"` -- the one prompt
where a bare sector number is a genuine warp command.

**Hard safety (independent of the Moderate econ caps below -- design
decision #3):** `select()` structurally only ever emits `"run_chain"` /
`"upgrade"` / `"explore"` candidates -- Genesis / colonist-load / planet
commitment and PvP-initiate are never candidate kinds this scorer can
produce, so `_execute()`'s kind-whitelist can never reach one. Never a
bypass of `send_and_confirm`.

**Cross-seat trace schema (2026-07-20 supplement).** `decision_to_trace()`
renders any `Decision` into one structured dict a sibling seat's
"Decisions-box" viewer consumes directly -- `{"tick", "context"
{"turns_left"/"cash"/"sector"}, "candidates" [{"kind", "ev_cr_per_turn",
"rationale", "gated", "gate_reason"}, ...], "chosen"}`. One source (the
`Decision` object itself, now carrying its own `tick` + originating
`snapshot`), two renders: this structured dict, and the pre-existing
human-readable ledger `intent` string `_record()` already builds --
deliberately left as its own separate, already-tested string-builder
rather than rederived from the trace dict, so this supplement changes
no existing ledger-text behavior. `AutopilotEngine.trace_log()` (the
bounded recent history) and `AutopilotLoop.snapshot()["last_trace"]`
(the single latest tick) are the two read transports.

**WO-FA-SAFE (hub-signed-off design + Rook architecture-approved): a
strict, fail-closed credits source for `assess()`.** `assess()`'s
`credits` kwarg is now REQUIRED (Rook must-fix #1) -- no default, no
internal `parse_state()` fallback, a caller that omits it gets a loud
`TypeError`. `AutopilotEngine.dry_run_tick()`/`live_tick()` feed it via
`_fresh_credits()` (see that method's own docstring): `session.
credits_snapshot()` (session.py, Rook must-fix #3's ATOMIC
`(last_credits, last_credits_ts)` read), gated fresh only when no older
than `caps.credits_stale_ms` (default 15s -- `DEFAULT_CREDITS_STALE_MS`,
config-driven per `EconCaps`, never hardcoded). `_score_upgrade()`'s
existing `credits is None` fail-closed skip then handles a stale/unknown
reading exactly as it already handles a genuine parse gap.
`_score_chain()` is NOT credits-gated at all (Rook must-fix #2 -- see that
function's own comment: not a live spend-defeat today since `run_chain`'s
candidate only MOVES, never buys in-line; FA4's future buy-flow owns the
real per-spend gate). `sector`/`turns_left` stay `parse_state()`-sourced
inside `assess()` -- only `credits` has a documented same-screen
price-quote-shaped lookalike (`state_parser.py`'s module docstring), so
only it needed the strict-source swap.

Multiplayer arming-gate (Rook must-fix #6, written, not a footnote): this
inherits `credits_balance()`'s documented FORGED-BALANCE residual
(state_parser.py, FA9-class roadmap prerequisite) -- SOLO-safe today (no
other player exists on a crawl_sacrificial game to author such a forgery);
arming this engine's credits-gated candidates in multiplayer REQUIRES
WO-FA9 first. `loop_player.LoopPlayer`'s own sibling floor-check
(loop_player.py) shares this same `EconCaps.credits_stale_ms` field and
the same arming-gate.
"""

from __future__ import annotations

import contextlib
import dataclasses
import math
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from .chains import ProfitChain, TradeHop, longest_profit_chain
from .classify import classify_screen
from .control_lock import MODE_HUMAN, ControlModeConflict
from .fighter_toll_policy import (
    DEFAULT_AUTO_ATTACK_MAX_ENEMY,
    DEFAULT_FIGHTER_RESERVE,
    decide_from_screen,
)
from .settle import send_and_confirm
from .ship_upgrade_decision import (
    LoopEconomics,
    PlayerState,
    ShipSpec,
    UpgradeDecision,
    choose_upgrade,
    remaining_productive_turns,
)
from .state_parser import parse_state
from .trade_driver import ChainRunResult, TradeDriverConfig, run_chain

ACTOR = "trainer"


def _is_unconfirmed_outcome(outcome: Optional[str]) -> bool:
    """True for a bare `"unconfirmed"` or an instrumented
    `"unconfirmed:<settle_reason>:<elapsed>"` (WO-SETTLE-FALSEPOS)."""
    return outcome == "unconfirmed" or (
        isinstance(outcome, str) and outcome.startswith("unconfirmed:")
    )


# The one live classification a bare sector-number send is safe against
# -- see this module's own "HIGH-2" docstring note.
_MOVEMENT_PROMPT_CLASS = "main_command"


def _explore_target_confirmed_non_adjacent(gate_full: str, next_sector: int) -> bool:
    """HIGH backstop (mack/cipher adversarial re-verify, 2026-07-21): the
    PRIMARY fix for a non-adjacent explore warp lives in `explore.py`'s
    `_adjacent_hop_toward()` -- a frontier edge's `frm` can be several
    known hops from the ship's actual current sector, so the OLD code
    (handing back the frontier's own far-side `to` sector directly)
    could fire a bare warp at a target the ship can't reach in one hop.
    This is the independent backstop for that fix regressing or being
    bypassed by a caller that supplies `explore_next_sector` directly
    (see e.g. this module's own tests): whenever the LIVE gate screen
    POSITIVELY shows the current sector's own warps (the same "Warps to
    Sector(s)" line/anchor `state_parser`/`explore` both already use),
    `next_sector` must be a member of it.

    Deliberately never true merely because no warps are parseable on
    THIS particular render (`state_parser.parse_state()`'s `"warps"` key
    absent) -- that would fail-closed on the vast majority of ordinary
    ticks whose live screen doesn't happen to redisplay the sector-status
    block at this exact moment, a much more aggressive gate than this
    backstop is meant to be (unlike the turns_left/credits MED fixes in
    `_score_chain`/`_score_upgrade`, which fail-closed on unknown because
    THOSE candidates have no other adjacency-equivalent primary
    correctness mechanism -- this one does, in `explore.py`). Only ever
    refuses on a POSITIVELY confirmed mismatch."""
    live_warps = parse_state(gate_full).get("warps")
    return live_warps is not None and next_sector not in live_warps


# -- Moderate econ caps (design decision #3 -- "looser economics, HARD
# safety stops stay regardless of Moderate"). Module constants, tunable
# by a caller via EconCaps below; these are the WO's proposed defaults.
DEFAULT_TURN_RESERVE = 50
DEFAULT_CASH_FLOOR = 10_000
DEFAULT_KEEP_MIN_DEFENSE_FIGHTERS = 20
# Reserved for a future buy/spend driver (Phase 1 has none -- EXECUTE is
# navigation-only, see module docstring): the threshold above which a
# planned spend should be surfaced to the operator rather than fired
# autonomously. Unused this phase; kept here (not deleted) so a later
# spend-capable EXECUTE inherits the cap rather than reinventing it.
DEFAULT_SURFACE_BEFORE_SPEND = 50_000
# WO-FA-SAFE: the credit-floor stop-loss's freshness bound (Rook must-fix
# #4) -- how old a `session.last_credits` reading is allowed to be before
# `dry_run_tick()`/`live_tick()` must treat it as unknown rather than
# trust it. This is a TIME backstop, not per-spend precision: it can trust
# ONE balance across a whole macro-cycle's worth of spends (the reading
# may predate the cycle's own last buy) -- a genuinely per-spend
# "confirmed since the last buy" gate is FA4's buy-flow's own job, not
# this module's. Config-driven (an `EconCaps` field, never hardcoded at a
# call site) -- honesty note (mack LOW a, hub-ratified revise item 4): a
# supervisor CAN tune it live, without a rebuild, via THIS module's own
# `tw autopilot start --credits-stale-ms` (protocol.py's
# `_dispatch_autopilot_start` threads it into a fresh `EconCaps`, exactly
# like `cash_floor`). The SAME `EconCaps` field is also read by
# `loop_player.LoopPlayer`'s sibling floor-check and `skills.play_skill()`
# (its own `credits_stale_ms` parameter, defaulted from this constant) --
# those two do NOT yet have CLI/dispatch-level tunability of their own
# (`tw play`/`tw play_start` have no `--credits-stale-ms` flag); every
# real caller there gets this 15s default until that follow-on lands. Do
# not describe those two paths as "supervisor-tunable live" -- only the
# autopilot arm path is, today.
DEFAULT_CREDITS_STALE_MS = 15_000

# Exploration's baseline EV (§11 "no idle", decision #4): picked whenever
# nothing else scores higher, so a tick always has SOMETHING to do even
# with zero known chains/eligible upgrades. Deliberately tiny and
# strictly positive (never zero -- a zero-EV candidate racing a bare "do
# nothing" would be an arbitrary tie) and small enough it can never
# outrank a genuine discovered chain/upgrade.
EXPLORE_BASELINE_EV = 0.01

# Hard cap on ticks a single AutopilotLoop background run will execute
# before stopping on its own -- this repo's established ethos (mirrors
# loop_player.py's own _MAX_CYCLES): an unattended background scheduler
# must never be unbounded regardless of caller intent. `AutopilotLoop`
# also clamps any caller-supplied `max_ticks` to this ceiling -- see its
# own `__init__`.
_MAX_TICKS = 500

# In-memory decision-trace bound (mack MED finding): `AutopilotEngine`
# accumulates a `Decision` every tick for as long as it's alive -- an
# unbounded list is a slow leak for a long-running background loop.
# Kept as a bounded ring (most-recent-`_MAX_DECISIONS_KEPT` only); the
# ledger (when wired) is the durable, unbounded record -- this in-memory
# trace is a debugging/preview convenience, not the record of truth.
_MAX_DECISIONS_KEPT = 200

# Floor for a caller-supplied tick_interval_s (LOW, cipher): a zero/
# negative interval would busy-loop the background thread pointlessly.
_MIN_TICK_INTERVAL_S = 0.001


class AutopilotGateError(Exception):
    """Raised by `AutopilotEngine.live_tick()`/`AutopilotLoop.start()`
    when the profile's `autonomous` flag isn't True -- fail-closed (see
    module docstring). Also raised for a candidate kind outside the
    scorer's own whitelist (belt-and-braces; `select()` can't actually
    produce one -- see module docstring's Hard safety section)."""


class AutopilotLoopError(Exception):
    """A start/stop request that doesn't apply to the loop's current
    state (e.g. starting while already running) -- mirrors
    `loop_player.LoopPlayerError`'s own shape."""


@dataclass(frozen=True)
class EconCaps:
    """Moderate-risk economic caps (design decision #3). Bounds on
    candidate SELECTION/EXECUTION only -- never on the hard safety stops
    in the module docstring, which apply regardless of these values."""

    turn_reserve: int = DEFAULT_TURN_RESERVE
    cash_floor: int = DEFAULT_CASH_FLOOR
    keep_min_defense_fighters: int = DEFAULT_KEEP_MIN_DEFENSE_FIGHTERS
    surface_before_spend: int = DEFAULT_SURFACE_BEFORE_SPEND
    # WO-FA-SAFE: the credit-floor stop-loss's freshness bound, shared by
    # both decision sites (this module's own dry_run_tick()/live_tick() and
    # loop_player.LoopPlayer's floor-check) -- see DEFAULT_CREDITS_STALE_MS
    # above for the one-macro-cycle exposure this bound accepts.
    credits_stale_ms: int = DEFAULT_CREDITS_STALE_MS
    # WO-FA4: after each hop's live buy+sell totals, `trade_driver.run_chain()`
    # aborts the whole chain when realized margin falls at/below this floor
    # (default 0 = any non-profitable hop) -- distinct from cash_floor, this
    # stops a mis-ranked losing chain even while still above the reserve.
    # Threaded straight into a fresh `TradeDriverConfig` at `_execute()`'s
    # own `run_chain` call site -- see that method's docstring.
    min_margin_per_hop: int = 0
    # WO-FIGHTER-FLOOR-TOLL: small aboard reserve for deploy/sell clamps +
    # Option? auto-resolve knobs (see fighter_toll_policy.py). Distinct from
    # keep_min_defense_fighters (upgrade-path hostile floor, default 20).
    fighter_reserve: int = DEFAULT_FIGHTER_RESERVE
    fighter_auto_attack_max_enemy: int = DEFAULT_AUTO_ATTACK_MAX_ENEMY

    def __post_init__(self) -> None:
        # Cipher FA4: a negative cash_floor/turn_reserve, or a non-positive
        # credits_stale_ms, silently defeats the stop-loss / turn-reserve /
        # freshness gates via ordinary caller-supplied EconCaps kwargs (e.g.
        # protocol.py's `autopilot_start` socket args) -- fail loud at
        # construction rather than ever arming an unbound floor.
        if self.cash_floor < 0:
            raise ValueError("cash_floor must be >= 0")
        if self.turn_reserve < 0:
            raise ValueError("turn_reserve must be >= 0")
        if self.credits_stale_ms <= 0:
            raise ValueError("credits_stale_ms must be > 0")
        if self.min_margin_per_hop < 0:
            raise ValueError("min_margin_per_hop must be >= 0")
        if self.fighter_reserve < 0:
            raise ValueError("fighter_reserve must be >= 0")
        if self.fighter_auto_attack_max_enemy < 0:
            raise ValueError("fighter_auto_attack_max_enemy must be >= 0")


@dataclass(frozen=True)
class WorldSnapshot:
    """ASSESS output. `sector`/`credits`/`turns_left` come from
    `state_parser.parse_state()` off the CURRENT rendered screen;
    everything else is caller-supplied world-model-derived input (see
    module docstring for why chains/explore/ship_upgrade_decision are
    wired this way rather than each growing its own world-model
    adapter here)."""

    sector: Optional[int]
    credits: Optional[int]
    turns_left: Optional[int]
    current_ship: Optional[ShipSpec] = None
    hops: tuple[TradeHop, ...] = field(default_factory=tuple)
    ship_catalog: tuple[ShipSpec, ...] = field(default_factory=tuple)
    loop: Optional[LoopEconomics] = None
    stardock_route: Optional[tuple[int, ...]] = None  # known-graph path to StarDock, incl. current sector first
    explore_next_sector: Optional[int] = None  # next frontier hop (map-fill / StarDock hunt), if any
    explore_mode: str = "explore"  # label only, for the decision trace rationale
    hostile_or_pvp: bool = False
    # WO-FA4: threaded straight through from `_autopilot_snapshot_kwargs()`
    # (protocol.py), never derived from `rendered_text` -- a chosen
    # `run_chain` candidate needs these to actually DRIVE
    # (`trade_driver.run_chain()`'s own `world_id`/`state_dir` params) since
    # a bare `chains.TradeHop`/`ProfitChain` carries neither. `None` (no
    # resolvable world_id yet) means `_execute()` can't drive a `run_chain`
    # candidate this tick -- fails closed to a HOLD, never a guess at which
    # world to read/write.
    world_id: Optional[str] = None
    state_dir: Optional[object] = None


def assess(
    rendered_text: str,
    *,
    credits: Optional[int],
    current_ship: Optional[ShipSpec] = None,
    hops: Sequence[TradeHop] = (),
    ship_catalog: Sequence[ShipSpec] = (),
    loop: Optional[LoopEconomics] = None,
    stardock_route: Optional[Sequence[int]] = None,
    explore_next_sector: Optional[int] = None,
    explore_mode: str = "explore",
    hostile_or_pvp: bool = False,
    world_id: Optional[str] = None,
    state_dir: Optional[object] = None,
) -> WorldSnapshot:
    """Read the CURRENT screen via `state_parser.parse_state()` and fold
    it together with the caller-supplied world-model-derived inputs into
    one `WorldSnapshot` -- SELECT never re-reads live state mid-decision,
    it only ever sees this one immutable snapshot.

    `credits` (WO-FA-SAFE, Rook must-fix #1): a REQUIRED keyword-only
    argument with NO default and NO `parse_state()` fallback -- a caller
    that omits it gets a loud `TypeError`, never a silent revert to the
    loose source. This used to be `state.get("credits")`, sourced from
    this same `parse_state()` call like `sector`/`turns_left` still are
    below -- but `parse_state()`'s `credits` field falls back to a bare
    "N credits" mention, which a port's own price quote satisfies just as
    well as a real balance (see `state_parser.py`'s module docstring and
    `session.observe_credits()`'s own docstring for the full rationale).
    `sector`/`turns_left` stay `parse_state()`-sourced deliberately: unlike
    credits, neither has a documented same-screen price-quote-shaped
    lookalike that would misreport a wrong-but-plausible value, so the
    asymmetry is a fix targeted at the actual pollutable field, not a
    blanket credits/sector/turns policy change.

    The caller (`AutopilotEngine.dry_run_tick()`/`live_tick()`) sources
    this from `session.credits_snapshot()` -- the STRICT, freshness-gated
    last-known balance -- never from this function's own `rendered_text`.
    `_score_upgrade()`'s existing `credits is None` fail-closed skip then
    applies unchanged to a stale/never-observed reading, exactly as it
    already does to a genuine parse gap."""
    state = parse_state(rendered_text)
    return WorldSnapshot(
        sector=state.get("sector"),
        credits=credits,
        turns_left=state.get("turns_left"),
        current_ship=current_ship,
        hops=tuple(hops),
        ship_catalog=tuple(ship_catalog),
        loop=loop,
        stardock_route=tuple(stardock_route) if stardock_route is not None else None,
        explore_next_sector=explore_next_sector,
        explore_mode=explore_mode,
        hostile_or_pvp=hostile_or_pvp,
        world_id=world_id,
        state_dir=state_dir,
    )


@dataclass(frozen=True)
class Candidate:
    """One scored SELECT option. `next_sector` is the concrete sector
    number EXECUTE would send this tick, or `None` when this candidate
    has nothing concrete to send yet (e.g. an upgrade recommendation with
    no known route to StarDock, or a chain whose start isn't the current
    sector -- see module docstring's Scope section)."""

    kind: str  # "run_chain" | "upgrade" | "explore"
    ev_per_turn: float
    rationale: str
    next_sector: Optional[int] = None
    chain: Optional[ProfitChain] = None
    upgrade: Optional[UpgradeDecision] = None


@dataclass(frozen=True)
class Decision:
    """SELECT's full output for one tick -- also the dry-run proof
    surface (design decision #5): every candidate considered, whichever
    (if any) was skipped and why, which one won, and why.

    `send_outcome` is filled in by `AutopilotEngine.live_tick()` AFTER
    SELECT (never by `select()`/`dry_run_tick()`, which never send):
    `None` (nothing sent -- dry-run, or the chosen candidate had no
    concrete `next_sector`), `"held:not_main_command:<cls>"` (HIGH-2's
    classify-gate refused -- the live screen wasn't the movement prompt),
    `"sent"` (a confirmed send), or `"unconfirmed"` (settle.py's
    `send_and_confirm` reported a desync -- see that module's docstring
    for why this must never be silently treated as success).

    `tick`/`snapshot` (2026-07-20 cross-seat trace supplement): `tick` is
    this ENGINE instance's own monotonic counter (stamped by
    `AutopilotEngine` under `self._lock`, dry-run and live ticks sharing
    one sequence -- see `decision_to_trace()` below, the one place these
    two fields get read). `snapshot` is the exact `WorldSnapshot` SELECT
    scored this tick, kept so a later renderer never has to re-derive
    ASSESS's output from anything but this one `Decision` object (one
    source, two renders: this dataclass, and whatever a caller renders
    from it -- a human-readable string or `decision_to_trace()`'s dict)."""

    ts: float
    candidates: tuple[Candidate, ...]
    chosen: Optional[Candidate]
    reason: str
    skipped: tuple[str, ...] = field(default_factory=tuple)
    interrupted: bool = False  # True when `chosen.kind` differs from the last LIVE tick's chosen kind
    send_outcome: Optional[str] = None
    tick: int = 0  # this engine's own monotonic tick counter -- see class docstring note above
    snapshot: Optional[WorldSnapshot] = None  # the WorldSnapshot SELECT scored this tick -- see class docstring note above


def _score_chain(snapshot: WorldSnapshot, caps: EconCaps) -> tuple[Optional[Candidate], Optional[str]]:
    # WO-FA-SAFE (Rook must-fix #2): this function never reads
    # `snapshot.credits` at all -- a None/stale balance does NOT skip a
    # `run_chain` candidate today. That's NOT currently a live spend-
    # defeat: `run_chain`'s chosen candidate only MOVES one hop
    # (`live_tick()`'s EXECUTE is navigation-only, see module docstring),
    # never an in-line buy. It becomes load-bearing the moment a real
    # trade-loop driver exists -- FA4's buy-flow MUST gate the actual buy
    # on the strict `credits_snapshot()` source + re-confirm the balance
    # per-buy (the real per-spend precision belongs there, not here). Do
    # NOT read this as "run_chain is credit-gated" -- it isn't.
    if not snapshot.hops:
        return None, None
    chain = longest_profit_chain(snapshot.hops)
    if chain is None:
        return None, "run_chain: no profitable cycle in known hops"
    # MED fail-closed fix (mack M-a): an UNKNOWN turn budget must skip
    # this candidate outright, never silently disable the turn-reserve
    # floor the way `if turns_left is not None: <only then check>` used
    # to -- DEFAULT_TURN_RESERVE exists specifically to prevent turn-
    # exhaustion/forced-logout, so a parse hiccup must not bypass it.
    if snapshot.turns_left is None:
        return None, "run_chain: turns_left unknown -- skipped (fail-closed, turn-reserve floor can't be verified)"
    productive = snapshot.turns_left - caps.turn_reserve
    if productive < chain.turns:
        return None, (
            f"run_chain: needs {chain.turns}t > {productive}t productive "
            f"(turn-reserve floor {caps.turn_reserve}t)"
        )
    next_sector = None
    if (
        snapshot.sector is not None
        and len(chain.sectors) > 1
        and chain.sectors[0] == snapshot.sector
    ):
        next_sector = chain.sectors[1]
    path = "→".join(str(s) for s in chain.sectors)
    return (
        Candidate(
            kind="run_chain",
            ev_per_turn=chain.cr_per_turn,
            rationale=f"run known chain {path}: {chain.cr_per_turn:.1f} cr/turn",
            next_sector=next_sector,
            chain=chain,
        ),
        None,
    )


def _score_upgrade(snapshot: WorldSnapshot, caps: EconCaps) -> tuple[Optional[Candidate], Optional[str]]:
    # StarDock prices absent from game_data (P1-b captures them
    # separately) -> treat price as UNKNOWN -> skip the branch entirely,
    # NEVER guess a spend (WO hard rule).
    if not snapshot.ship_catalog:
        return None, "upgrade: StarDock prices unknown (ship_catalog empty) -- skipped, never guessed"
    if snapshot.loop is None or snapshot.current_ship is None or snapshot.turns_left is None:
        return None, "upgrade: missing loop-economics/current-ship/turns_left input -- skipped"
    # MED fail-closed fix (mack M-b, cipher): an UNKNOWN balance must
    # skip, exactly like a known-too-low balance already did -- treating
    # "we don't know" as "assume it's fine" would bypass the cash floor
    # on a parse hiccup.
    if snapshot.credits is None:
        return None, "upgrade: credits unknown -- skipped (fail-closed, cash floor can't be verified)"
    if snapshot.credits < caps.cash_floor:
        return None, f"upgrade: credits below cash floor ({caps.cash_floor}cr) -- skipped"
    if snapshot.loop.turns_per_cycle <= 0:
        return None, "upgrade: invalid loop economics (turns_per_cycle<=0) -- skipped"

    # MED fail-closed fix (mack M-c): "never guess a spend" must also
    # hold PER-SHIP, not just at whole-catalog emptiness -- an unpriced
    # ship sentineled as cost<=0 (or one that isn't actually bigger than
    # the current hull) is filtered out here before it ever reaches
    # `choose_upgrade()`, rather than trusting that engine's own
    # payback math to happen to reject it. CONTRACT for the future P1-b
    # price feed: it must OMIT unpriced ships from the catalog entirely,
    # never sentinel one in as cost=0.
    priced_catalog = tuple(
        s for s in snapshot.ship_catalog if s.cost > 0 and s.holds > snapshot.current_ship.holds
    )
    if not priced_catalog:
        return None, (
            "upgrade: no priced, strictly-bigger ship in catalog "
            "(cost<=0 sentinels / non-larger hulls excluded) -- skipped"
        )

    player = PlayerState(
        turns_left=snapshot.turns_left,
        current_holds=snapshot.current_ship.holds,
        turn_reserve=caps.turn_reserve,
        hostile_or_pvp=snapshot.hostile_or_pvp,
        current_fighters=snapshot.current_ship.fighters,
        current_shields=snapshot.current_ship.shields,
    )
    decision = choose_upgrade(
        priced_catalog,
        player,
        snapshot.loop,
        defense_floor_fighters=caps.keep_min_defense_fighters,
    )
    if not decision.recommend or decision.ship is None:
        return None, f"upgrade: {decision.rationale}"

    # Decision #2 -- the TURN-COST to travel to StarDock uses the CURRENT
    # ship's turns-per-warp, never a constant (game-D: Prison Barge
    # 6/warp vs Galleon 3/warp is the whole reason). `choose_upgrade`'s
    # own payback gate above has NO idea about StarDock distance at all
    # (ship_upgrade_decision.py is travel-agnostic by design -- see its
    # own docstring); this is the extra, travel-INCLUSIVE feasibility
    # check this module layers on top. CONFIRMED CORRECT under
    # adversarial review (2026-07-20) -- this is the legitimate per-ship
    # warp use; do not touch it when fixing HIGH-1 below.
    #
    # MED fail-closed fix (cipher re-verify, 2026-07-20): `stardock_route
    # is None` (route UNKNOWN -- no path to StarDock computed yet) used to
    # collapse to the exact SAME `travel_turns = 0` as "already AT
    # StarDock" (a genuine known 1-entry route) -- an unknown feasibility
    # silently read as the single BEST case (free travel), the same
    # never-guess-a-spend/never-guess-feasibility violation the
    # `payback or 0.0` fix above closes. Only a KNOWN route may compute
    # travel: `None` (or a malformed empty tuple) -> skip the candidate
    # outright; a genuine 1-entry route (current sector only) IS
    # legitimately 0 travel (already at dock); len>1 is real hops.
    if not snapshot.stardock_route:
        return None, "upgrade: stardock route unknown -- skipped (never guess travel-feasibility)"
    travel_turns = 0
    if len(snapshot.stardock_route) > 1:
        hops_to_dock = len(snapshot.stardock_route) - 1
        travel_turns = hops_to_dock * snapshot.current_ship.turns_per_warp

    # LOW fix (mack): reuse ship_upgrade_decision's own CLAMPED helper
    # instead of duplicating `turns_left - turn_reserve` unclamped here.
    productive = remaining_productive_turns(player)
    # MED fail-closed fix (class invariant with (a)/(b)/(c) above,
    # 2026-07-20 revision): `decision.projected_payback or 0.0` used to
    # coerce an UNKNOWN payback to 0 -- i.e. treat "we don't know" as the
    # single BEST possible outcome (free) -- exactly the fail-OPEN shape
    # this class of fix exists to close. `choose_upgrade()`'s own contract
    # guarantees a real positive `projected_payback` whenever
    # `decision.recommend` is True (see `evaluate_candidate`'s `pb is
    # None` early-return, ship_upgrade_decision.py), so this branch isn't
    # reachable through today's `choose_upgrade` -- kept as a defensive
    # class-invariant guard (never a caller-trust assumption) against that
    # contract changing underneath this caller, mirroring (a)/(b)/(c).
    if decision.projected_payback is None:
        return None, f"upgrade: {decision.ship.name} payback unknown -- skipped (never treated as free)"
    payback = decision.projected_payback
    total_turns_needed = payback + travel_turns
    if total_turns_needed > productive:
        return None, (
            f"upgrade: {decision.ship.name} payback {payback:.1f}t + {travel_turns}t travel "
            f"(this ship's {snapshot.current_ship.turns_per_warp}/warp) = {total_turns_needed:.1f}t "
            f"> {productive}t productive -- HOLD"
        )

    # HIGH-1 fix (mack poc1/poc5/poc6, triple-proven): the cross-kind EV
    # must be genuine cr/turn, comparable one-for-one against
    # `chain.cr_per_turn`. `holds_per_turn()` is
    # `(holds*margin)/(turns_per_cycle*turns_per_warp)` -- dimensionally
    # cr/turn^2, since `turns_per_cycle` ALREADY bakes in warp time (see
    # `LoopEconomics`'s own docstring: "wall-turns to run one full cycle
    # (warp+trade)") and `holds_per_turn` re-multiplies it. Subtracting
    # two such terms produced a warp-RATIO artifact, not a genuine
    # throughput delta -- poc6 showed the SAME candidate/loop/chain
    # ranked differently based purely on which ship you happened to be
    # flying (3 vs 6 turns/warp), even though the true holds-only benefit
    # never changed. The correct cross-kind EV is the TRUE holds-only
    # delta: extra holds x margin-per-hold, spread over one cycle's wall-
    # turns -- warp-STABLE, independent of either ship's turns_per_warp
    # (that variable only belongs in the TRAVEL feasibility check above,
    # never in this EV). `holds_per_turn` stays exactly as-is for
    # `choose_upgrade()`'s OWN internal same-basis ranking among multiple
    # eligible candidates in the catalog (ship_upgrade_decision.py's
    # concern, correct there) -- this is only about what SELECT compares
    # across kinds.
    #
    # KNOWN LIMITATION (accepted, mack + team-lead, 2026-07-20): this
    # credits the extra-HOLDS benefit only -- it does not also credit a
    # faster hull's cycle-shortening, since `LoopEconomics.turns_per_cycle`
    # isn't decomposed per-ship here. A candidate that's both bigger AND
    # meaningfully faster is therefore conservatively UNDER-counted, never
    # over-counted. A fuller per-ship cycle-time model is a deferred
    # refinement, not built here.
    extra_holds = decision.ship.holds - snapshot.current_ship.holds
    extra_cr_per_turn = extra_holds * snapshot.loop.margin_per_hold / snapshot.loop.turns_per_cycle
    if extra_cr_per_turn <= 0:
        # Defensive only -- `priced_catalog`'s own holds> filter above
        # already guarantees extra_holds > 0 for every candidate
        # `choose_upgrade` could have picked from.
        return None, f"upgrade: {decision.ship.name} no positive holds-only delta vs current ship -- skipped"

    next_sector = None
    if snapshot.stardock_route and len(snapshot.stardock_route) > 1:
        next_sector = snapshot.stardock_route[1]

    return (
        Candidate(
            kind="upgrade",
            ev_per_turn=extra_cr_per_turn,
            rationale=(
                f"detour to StarDock for {decision.ship.name}: payback {payback:.1f}t + "
                f"{travel_turns}t travel <= {productive}t budget; +{extra_cr_per_turn:.1f} cr/turn"
            ),
            next_sector=next_sector,
            upgrade=decision,
        ),
        None,
    )


def _score_explore(snapshot: WorldSnapshot) -> tuple[Optional[Candidate], Optional[str]]:
    if snapshot.explore_next_sector is None:
        return None, "explore: no frontier/route target (exhausted)"
    return (
        Candidate(
            kind="explore",
            ev_per_turn=EXPLORE_BASELINE_EV,
            rationale=(
                f"keep exploring ({snapshot.explore_mode}) toward sector "
                f"{snapshot.explore_next_sector} -- no idle (§11)"
            ),
            next_sector=snapshot.explore_next_sector,
        ),
        None,
    )


def select(snapshot: WorldSnapshot, caps: EconCaps = EconCaps()) -> Decision:
    """SELECT: score every candidate action from scratch and pick the
    highest expected-value one. Stateless -- see module docstring for why
    that's what makes interruption structural rather than a special case;
    `interrupted`/history-tracking is `AutopilotEngine`'s job, not this
    function's."""
    candidates: list[Candidate] = []
    skipped: list[str] = []

    for scorer in (_score_chain, _score_upgrade, _score_explore):
        args = (snapshot, caps) if scorer is not _score_explore else (snapshot,)
        candidate, skip_reason = scorer(*args)
        if candidate is not None:
            candidates.append(candidate)
        elif skip_reason is not None:
            skipped.append(skip_reason)

    if not candidates:
        return Decision(
            ts=time.time(), candidates=(), chosen=None, reason="no_candidates",
            skipped=tuple(skipped), snapshot=snapshot,
        )

    ranked = sorted(candidates, key=lambda c: c.ev_per_turn, reverse=True)
    chosen = ranked[0]
    return Decision(
        ts=time.time(),
        candidates=tuple(candidates),
        chosen=chosen,
        reason=f"highest EV: {chosen.kind} ({chosen.ev_per_turn:.2f} cr/turn)",
        skipped=tuple(skipped),
        snapshot=snapshot,
    )


# The one whitelist of candidate kinds `select()` can ever produce (mirrors
# `AutopilotEngine._execute()`'s own belt-and-braces whitelist) -- used only
# to give `decision_to_trace()`'s `candidates` list a stable, predictable
# ordering (run_chain, upgrade, explore) regardless of which kinds happened
# to score vs. get skipped this tick.
_TRACE_KIND_ORDER = ("run_chain", "upgrade", "explore")


def decision_to_trace(decision: Decision) -> dict:
    """Render a `Decision` into the cross-seat trace schema (2026-07-20
    supplement, the sibling-seat "Decisions-box" viewer contract): ONE
    structured object a remote viewer and a human-readable proof render
    both consume identically -- see this module's tests for the exact
    shape asserted field-by-field. Exact schema:

        {"tick": int,
         "context": {"turns_left": int|None, "cash": int|None, "sector": int|None},
         "candidates": [{"kind": str, "ev_cr_per_turn": float|None,
                         "rationale": str, "gated": bool, "gate_reason": str|None}, ...],
         "chosen": str|None}

    `ev_cr_per_turn` is `None` whenever a candidate's genuine cr/turn is
    unknown (skipped at SELECT-time, or the winning candidate's SEND was
    HELD/unconfirmed) -- NEVER 0 or a guess, the same None-discipline as
    this module's fail-closed fixes. A candidate that was actually SCORED
    (present in `decision.candidates`) is `gated=False`; one that never
    produced a `Candidate` at all (only a `decision.skipped` reason string,
    itself always prefixed `"<kind>: ..."` -- see each `_score_*` function)
    is `gated=True` with that reason. `chosen` is the winning kind, or
    `None` when the tick HOLDs -- which includes BOTH "nothing scored"
    (`decision.chosen is None`) AND "something scored and won, but the
    live send was HELD or came back unconfirmed" (HIGH-2 / the confirmed-
    handling MED fix): in the latter case the winning candidate's own
    trace entry is re-marked `gated=True` with the `send_outcome` as its
    `gate_reason` -- it DID win the score (still shown), it just never
    became a real action this tick."""
    snap = decision.snapshot
    context = {
        "turns_left": snap.turns_left if snap is not None else None,
        "cash": snap.credits if snap is not None else None,
        "sector": snap.sector if snap is not None else None,
    }

    by_kind: dict[str, dict] = {}
    for c in decision.candidates:
        by_kind[c.kind] = {
            "kind": c.kind,
            "ev_cr_per_turn": c.ev_per_turn,
            "rationale": c.rationale,
            "gated": False,
            "gate_reason": None,
        }
    for reason in decision.skipped:
        kind, _, detail = reason.partition(":")
        kind = kind.strip()
        if kind in _TRACE_KIND_ORDER and kind not in by_kind:
            detail = detail.strip() or reason
            by_kind[kind] = {
                "kind": kind,
                "ev_cr_per_turn": None,
                "rationale": detail,
                "gated": True,
                "gate_reason": detail,
            }

    chosen_kind = decision.chosen.kind if decision.chosen is not None else None
    if chosen_kind is not None and decision.send_outcome and (
        decision.send_outcome.startswith("held:") or _is_unconfirmed_outcome(decision.send_outcome)
    ):
        entry = by_kind.get(chosen_kind)
        if entry is not None:
            entry["gated"] = True
            entry["gate_reason"] = decision.send_outcome
        chosen_kind = None

    return {
        "tick": decision.tick,
        "context": context,
        "candidates": [by_kind[k] for k in _TRACE_KIND_ORDER if k in by_kind],
        "chosen": chosen_kind,
    }


class AutopilotEngine:
    """Owns ONE tick's ASSESS -> SELECT -> EXECUTE -> RECORD for one
    session. `profile.autonomous` (captured once, at construction, as
    `self.enabled`) fail-closed-gates `live_tick()`; `dry_run_tick()`
    NEVER sends regardless of `self.enabled` (the pre-enablement proof
    surface).

    Mirrors `skills.replay_skill()`'s own posture: this class does NOT
    touch `control_lock` itself -- exactly like `replay_skill()`, the
    raw per-cycle driver, has no control-lock interaction of its own,
    leaving that to its scheduler (`loop_player.LoopPlayer`, which enters/
    leaves MODE_AUTO_LOOP once for the whole multi-cycle run). Here,
    `AutopilotLoop` is that scheduler -- see its own docstring. A caller
    driving `live_tick()` standalone (outside an `AutopilotLoop`) is
    responsible for holding whatever exclusive slot applies, the same
    trust contract `replay_skill()` already has with ITS callers.

    **HIGH-3 fix (mack poc2, 2026-07-20): interrupt-history is LIVE-tick
    ONLY, and lock-guarded.** `_last_chosen_kind` is the human-facing
    interrupt-proof signal (design decision #5's `[INTERRUPT]` tag) --
    only `live_tick()` ever WRITES it; `dry_run_tick()` READS it (so a
    preview's own `interrupted` flag answers "would this interrupt the
    actual driven history"), but never mutates it. Without this split, a
    no-op preview call (e.g. a status/preview verb showing "what would
    autopilot do right now") could flip `interrupted` on the NEXT real
    live tick even though the real driven kind never changed (a false
    positive), or mask a genuine interrupt (a false negative) -- poc2
    confirmed the false-positive live. `self._lock` additionally guards
    every read/write of `_last_chosen_kind`/`self.decisions`: a
    background `AutopilotLoop` thread calling `live_tick()` and a
    foreground caller calling `dry_run_tick()` (a status/preview verb)
    on the SAME engine instance are a genuine concurrent-access
    possibility this module must not assume away."""

    def __init__(
        self,
        session,
        profile,
        control_lock,
        *,
        ledger=None,
        session_id: Optional[str] = None,
        caps: EconCaps = EconCaps(),
    ):
        self.session = session
        self.profile = profile
        self.control_lock = control_lock
        self.ledger = ledger
        self.session_id = session_id
        self.caps = caps
        # WO-P1 fail-closed gate: captured once here, from the profile
        # handed in at construction -- `live_tick()` consults ONLY this,
        # never re-reads `profile.autonomous` live, so a profile object
        # mutated after construction can't silently flip a live engine's
        # gate out from under a caller already holding a reference to it.
        self.enabled = bool(getattr(profile, "autonomous", False))
        # Bounded ring (mack MED finding) -- see _MAX_DECISIONS_KEPT.
        self.decisions: deque[Decision] = deque(maxlen=_MAX_DECISIONS_KEPT)
        self._last_chosen_kind: Optional[str] = None  # LIVE-tick-only -- see class docstring's HIGH-3 note
        self._lock = threading.Lock()
        # Cross-seat trace supplement (2026-07-20): one monotonic counter,
        # shared by dry-run and live ticks alike, stamped onto each
        # `Decision.tick` under `self._lock` -- so a caller polling
        # `trace_log()`/`decision_to_trace()` over time sees a stable,
        # never-reused sequence even though `self.decisions` itself is a
        # bounded ring that evicts old entries.
        self._tick_counter = 0
        # WO-FA4 (A-M1, the #1 arm-prerequisite): `AutopilotLoop.start()`
        # installs `self._stop.is_set` here so a whole-chain `run_chain`
        # tick can abort BETWEEN sends, not only at the next tick boundary.
        # Deliberately NEVER falls back to `control_lock.is_driver_fenced()`
        # -- that fence is structurally DEAD under MODE_AUTO_LOOP (mack's
        # WO-FA4 finding: it only flips when `take_human()` finds
        # `_driving` True, and `_driving` is only ever set by
        # `acquire_driver()` -- the do/send-family dispatch path, never
        # this engine's own `live_tick()`; `take_human()` refuses outright
        # under MODE_AUTO_LOOP before ever reaching that branch). A caller
        # driving `_execute()` standalone with no loop (so
        # `_abort_requested` stays `None`) gets a permanently-False abort
        # predicate, never a crash.
        self._abort_requested: Optional[Callable[[], bool]] = None
        # WO-FA4: bounded to the single most-recent `run_chain()` result --
        # an introspection convenience only (e.g. a future status verb),
        # never read by `decision_to_trace()`/the trace schema itself.
        self._last_chain_result: Optional[ChainRunResult] = None

    def _fresh_credits(self) -> Optional[int]:
        """WO-FA-SAFE (hub-signed-off design + Rook must-fix #1): the
        STRICT, freshness-gated credits source `assess()`'s now-required
        `credits` kwarg is fed from at BOTH tick sites below -- replaces
        `assess()`'s own former internal `parse_state(rendered_text).
        get("credits")` read (price-pollutable: a port's own price quote
        satisfies it just as well as a real balance). Reads
        `session.credits_snapshot()` (session.py, Rook must-fix #3 -- an
        ATOMIC `(last_credits, last_credits_ts)` pair, never two separate
        unlocked attribute reads) and returns the balance ONLY when it's
        both known and no older than `self.caps.credits_stale_ms` (default
        15s -- see `DEFAULT_CREDITS_STALE_MS`'s own comment for the
        one-macro-cycle exposure this bound accepts); `None` otherwise
        (never observed, or stale). hasattr-guarded like every other
        `credits_snapshot`/`observe_credits` call site -- a session lacking
        the method reads as `(None, None)`, the same fail-closed shape as
        a real session that never captured a balance.

        `_score_upgrade()`'s existing `credits is None` fail-closed skip
        (mack M-b) then applies unchanged -- this function narrows WHAT
        counts as "known", it doesn't change how an unknown balance is
        handled. `_score_chain()` never reads credits at all (Rook
        must-fix #2 -- see that function's own comment) -- a stale/unknown
        reading here does not affect a `run_chain` candidate's score.

        Multiplayer arming-gate (Rook must-fix #6, written, not a
        footnote): this inherits `credits_balance()`'s documented
        FORGED-BALANCE residual (state_parser.py, FA9-class roadmap
        prerequisite) -- a forged in-band "You have N credits" broadcast
        poisons `last_credits` exactly like a real one. SOLO-safe today (no
        other player exists on a crawl_sacrificial game to author such a
        forgery); arming this engine's credits-gated candidates in
        multiplayer REQUIRES WO-FA9 first."""
        if hasattr(self.session, "credits_snapshot"):
            bal, ts = self.session.credits_snapshot()
        else:
            bal, ts = None, None
        age_ms = (time.monotonic() - ts) * 1000 if ts is not None else None
        fresh = bal is not None and age_ms is not None and age_ms <= self.caps.credits_stale_ms
        return bal if fresh else None

    def dry_run_tick(self, **assess_kwargs) -> Decision:
        """The pre-enablement proof surface (design decision #5):
        ASSESS + SELECT + RECORD, ZERO sends -- regardless of
        `self.enabled`. Reads (never writes) the LIVE interrupt history
        -- see class docstring's HIGH-3 note."""
        text = self.session.render_text(self.session.render())
        # WO-FA7a round 5: feed the credits-supervision surface from this
        # tick's own render, the same class of autonomous per-tick screen
        # read replay_skill/play_skill/LoopPlayer were already fixed for.
        # hasattr-guarded, mirroring every other call site (session.py/
        # protocol.py/skills.py/crawl_driver.py/loop_player.py).
        if hasattr(self.session, "observe_credits"):
            self.session.observe_credits(text)
        # WO-FA-SAFE: `assess()`'s `credits` now comes from THIS engine's
        # own strict, freshness-gated read -- see `_fresh_credits()`'s own
        # docstring -- never from `assess()`'s internal screen parse.
        snapshot = assess(text, credits=self._fresh_credits(), **assess_kwargs)
        decision = select(snapshot, self.caps)
        with self._lock:
            interrupted = (
                decision.chosen is not None
                and self._last_chosen_kind is not None
                and decision.chosen.kind != self._last_chosen_kind
            )
            self._tick_counter += 1
            decision = dataclasses.replace(decision, tick=self._tick_counter, interrupted=interrupted)
            self.decisions.append(decision)
        self._record(decision, pre_text=text, input_text="<dry-run:no-send>", post_text=text, dry_run=True)
        return decision

    def live_tick(self, **assess_kwargs) -> Decision:
        """Fail-closed: refuses via `AutopilotGateError` before a single
        byte is assessed for sending unless `self.enabled` is True (i.e.
        `profile.autonomous` was True at construction). Sends at most ONE
        navigation keystroke this tick, gated by HIGH-2's classify check
        -- see module docstring's Scope/HIGH-2 sections. The ONLY path
        that writes `_last_chosen_kind` -- see class docstring's HIGH-3
        note."""
        if not self.enabled:
            raise AutopilotGateError(f"autonomous_disabled:profile={getattr(self.profile, 'name', '?')}")
        pre_text = self.session.render_text(self.session.render())
        # WO-FA7a round 5: same credits-supervision feed as dry_run_tick()
        # above -- see its comment for the full rationale.
        if hasattr(self.session, "observe_credits"):
            self.session.observe_credits(pre_text)
        # WO-FA-SAFE: same strict, freshness-gated source as dry_run_tick()
        # -- see `_fresh_credits()`'s own docstring.
        snapshot = assess(pre_text, credits=self._fresh_credits(), **assess_kwargs)
        decision = select(snapshot, self.caps)

        with self._lock:
            interrupted = (
                decision.chosen is not None
                and self._last_chosen_kind is not None
                and decision.chosen.kind != self._last_chosen_kind
            )
            if decision.chosen is not None:
                self._last_chosen_kind = decision.chosen.kind
        if interrupted:
            decision = dataclasses.replace(decision, interrupted=True)

        post_text = pre_text
        input_text = "<no-send>"
        chosen = decision.chosen
        # WO-FIGHTER-FLOOR-TOLL (folds WO-FIGHTER-AUTO-R): Option? dialogues
        # classify as sector_display and would otherwise HOLD forever on
        # HIGH-2. Resolve A/R THIS tick before any bare sector-number send.
        # Never auto-Pay (P). Haggle / other non-Option? prompts fall through.
        fighter_cleared = self._try_clear_fighter_option(pre_text)
        if fighter_cleared is not None:
            outcome, input_text, post_text = fighter_cleared
            decision = dataclasses.replace(decision, send_outcome=outcome)
        elif chosen is not None and chosen.next_sector is not None:
            # HIGH-2 gate-check TOCTOU fix (cipher re-verify, 2026-07-20):
            # ONE fresh render feeds BOTH the full-text and the prompt-line
            # the gate classifies against -- never reuse tick-start
            # `pre_text` (already stale by the time we reach the gate)
            # alongside a SECOND, later render's prompt line. Matches the
            # repo's own "one render feeds both" convention (see e.g.
            # login.py: `rows = session.render(); text =
            # session.render_text(rows)`). A blank gate render (no rows,
            # or an empty last line -- a screen-clear mid-transition, e.g.
            # a hub-warp) is ITSELF a HOLD: classify.py's own documented
            # last-resort fallback (`if not prompt_line: <gate-scan the
            # WHOLE full_text>`) would otherwise let a STALE main_command
            # string still sitting in `pre_text` green-light a send onto a
            # screen that was never actually confirmed settled at all --
            # cipher's PoC fired a real send this way through the old
            # stale-`pre_text`-plus-fresh-blank-prompt_line combination.
            gate_rows = self.session.render()
            gate_prompt = gate_rows[-1].strip() if gate_rows else ""
            if not gate_prompt:
                decision = dataclasses.replace(decision, send_outcome="held:blank_screen")
            else:
                gate_full = self.session.render_text(gate_rows)
                cls = classify_screen(gate_full, gate_prompt)
                if cls != _MOVEMENT_PROMPT_CLASS:
                    # HIGH-2: the live screen isn't the movement prompt --
                    # HOLD, never send a bare sector number into whatever
                    # blocking prompt (haggle, colonist-qty, fighter-deploy,
                    # ...) is actually live right now.
                    decision = dataclasses.replace(decision, send_outcome=f"held:not_main_command:{cls}")
                elif chosen.kind == "explore" and _explore_target_confirmed_non_adjacent(
                    gate_full, chosen.next_sector
                ):
                    # HIGH backstop -- see _explore_target_confirmed_non_adjacent's
                    # own docstring: never fire a bare warp at a sector the
                    # live screen positively shows isn't one of the current
                    # sector's own warps.
                    decision = dataclasses.replace(decision, send_outcome="held:non_adjacent")
                else:
                    confirmed, outcome_detail = self._execute(chosen, snapshot)
                    post_text = self.session.render_text(self.session.render())
                    # WO-FA7a round 5 (observe-only): the freshest screen
                    # after any send this tick actually fires -- the most
                    # supervision-relevant read of the three sites in this
                    # class (see dry_run_tick()'s comment for the full
                    # rationale).
                    if hasattr(self.session, "observe_credits"):
                        self.session.observe_credits(post_text)
                    # WO-FA4: a `run_chain` candidate's `_execute()` drives
                    # many sends, not just `next_sector` -- record what
                    # actually happened (the chain's own sector path +
                    # realized credits_delta) rather than a misleadingly
                    # narrow single number.
                    if chosen.kind == "run_chain" and chosen.chain is not None:
                        path = "->".join(str(s) for s in chosen.chain.sectors)
                        result = self._last_chain_result
                        if result is not None and result.credits_delta is not None:
                            input_text = f"<run_chain:{path} credits_delta={result.credits_delta:+d}>"
                        else:
                            input_text = f"<run_chain:{path}>"
                    else:
                        input_text = str(chosen.next_sector)
                    decision = dataclasses.replace(
                        decision,
                        send_outcome=outcome_detail if outcome_detail is not None else ("sent" if confirmed else "unconfirmed"),
                    )

        with self._lock:
            self._tick_counter += 1
            decision = dataclasses.replace(decision, tick=self._tick_counter)
            self.decisions.append(decision)

        self._record(decision, pre_text=pre_text, input_text=input_text, post_text=post_text, dry_run=False)
        return decision

    def trace_log(self) -> list[dict]:
        """Cross-seat trace supplement transport (2026-07-20): the bounded
        recent-decision ring (see `_MAX_DECISIONS_KEPT`), each entry
        rendered through `decision_to_trace()` -- the accessor a
        "Decisions-box" viewer (or any other status/preview caller) polls
        for the full recent history, oldest first. Lock-guarded, same as
        every other read/write of `self.decisions` -- see class
        docstring's HIGH-3 note."""
        with self._lock:
            return [decision_to_trace(d) for d in self.decisions]

    def _try_clear_fighter_option(
        self, screen_text: str
    ) -> Optional[tuple[str, str, str]]:
        """WO-FIGHTER-FLOOR-TOLL: if ``screen_text`` is a fighter toll
        ``Option?`` dialogue, send Attack or Retreat and return
        ``(send_outcome, input_text, post_text)``; otherwise ``None`` so
        the normal HIGH-2 / navigation path runs.

        Never sends ``P`` (toll pay). Unparsed Option? → hold outcome
        (still a non-None return so we don't fire a bare sector number).
        """
        rows = screen_text.split("\n")
        prompt = rows[-1].strip() if rows else ""
        fo = decide_from_screen(
            screen_text,
            prompt,
            reserve=self.caps.fighter_reserve,
            max_enemy=self.caps.fighter_auto_attack_max_enemy,
        )
        if not fo.detected:
            return None
        if fo.key is None:
            return (f"held:fighter_option:{fo.reason}", "<no-send>", screen_text)
        _reason, _elapsed, confirmed = send_and_confirm(
            self.session,
            fo.key,
            confirm_prompt=None,
            enter=True,
        )
        post_text = self.session.render_text(self.session.render())
        if hasattr(self.session, "observe_credits"):
            self.session.observe_credits(post_text)
        if confirmed:
            return (f"sent:fighter_option:{fo.key}", fo.key, post_text)
        return (
            f"unconfirmed:fighter_option:{fo.key}:{_reason}:{float(_elapsed):.3f}",
            fo.key,
            post_text,
        )

    def _execute(self, candidate: Candidate, snapshot: Optional[WorldSnapshot] = None) -> tuple[bool, Optional[str]]:
        """Sends whatever `candidate` requires and returns `(confirmed,
        outcome_detail)`.

        `"upgrade"`/`"explore"`: a single bare `candidate.next_sector`
        keystroke via `send_and_confirm`. On `confirmed=True`,
        `outcome_detail=None` (caller falls back to `"sent"`). On
        `confirmed=False`, WO-SETTLE-FALSEPOS: explore may salvage to
        `sent:settle_salvage:<reason>:<elapsed>` when the post-send
        screen is still `main_command` and `parse_state` sector equals
        the intended hop (false-positive idle/stability flake); otherwise
        returns instrumented `unconfirmed:<reason>:<elapsed>` (upgrade
        never salvages). Caller/`AutopilotLoop` treat any
        `unconfirmed…` outcome as a desync halt.

        `"run_chain"` (WO-FA4): routes to `trade_driver.run_chain()` --
        the WHOLE chain (navigate/dock/buy/sell/repeat), synchronously,
        within this ONE call -- rather than the single-keystroke-per-tick
        cadence the other two kinds still use (a deliberate scope change:
        see trade_driver.py's own module docstring for why a multi-send
        macro can't fit the old one-keystroke contract). `is_armed` reads
        `self.enabled` LIVE (never a value captured once at construction
        elsewhere) and `should_abort` reads `self._chain_abort_requested`
        LIVE -- both REQUIRED, fail-closed predicates on `run_chain()`'s
        own signature (A-C1/A-M1). `confirmed` is `result.completed`;
        `outcome_detail` is `f"sent:credits_delta={...}"` on completion
        (surfacing the realized credits delta, never just a bare "sent")
        or `f"held:{result.stop_reason}"` otherwise -- matching this
        module's existing `"held:..."` schema (`decision_to_trace()`
        already treats any `"held:"`-prefixed `send_outcome` as "scored
        but never became a real action", the correct bucket for every
        trade_driver landmine stop). `snapshot` supplies the `world_id`/
        `state_dir`/`turns_left` a chain run needs that a bare `Candidate`
        doesn't carry -- `None`, or a snapshot with no resolvable
        `world_id`/`turns_left` (a caller testing `_execute()` standalone,
        or a live tick before `_autopilot_snapshot_kwargs()`'s trade lane
        is wired) fails closed to a HOLD, never a guess at which world to
        read/write -- `trade_driver.run_chain()` is never even called."""
        # Belt-and-braces: `select()` can only ever produce these three
        # kinds (see module docstring's Hard safety section) -- this
        # dispatch can never actually reach the else branch through
        # `select()`'s own output, but a bare pass-through with no
        # whitelist at all would silently trust ANY future candidate
        # kind, including one this module never intended to authorize.
        if candidate.kind not in ("run_chain", "upgrade", "explore"):
            raise AutopilotGateError(f"refused_unknown_candidate_kind:{candidate.kind}")

        if candidate.kind == "run_chain":
            if (
                candidate.chain is None
                or snapshot is None
                or snapshot.world_id is None
                or snapshot.turns_left is None
            ):
                return False, "held:run_chain_unavailable"
            result = run_chain(
                self.session,
                candidate.chain,
                world_id=snapshot.world_id,
                state_dir=snapshot.state_dir,
                turns_left=snapshot.turns_left,
                caps=self.caps,
                should_abort=self._chain_abort_requested,
                is_armed=lambda: self.enabled,
                config=TradeDriverConfig(min_margin_per_hop=self.caps.min_margin_per_hop),
            )
            self._last_chain_result = result
            if result.completed:
                if result.credits_delta is None:
                    return True, "sent"
                return True, f"sent:credits_delta={result.credits_delta:+d}"
            return False, f"held:{result.stop_reason}"

        # WO-SETTLE-EARLY: navigation warps opt into retry_unstable_idle so
        # a hop that paints during/after the first idle+stability window
        # confirms instead of false-unconfirmed (3034→250 / 4571→2429).
        # Default settle fail-fast stays for skills/login (colonist race).
        reason, elapsed, confirmed = send_and_confirm(
            self.session,
            str(candidate.next_sector),
            confirm_prompt=None,
            enter=True,
            retry_unstable_idle=True,
        )
        if confirmed:
            return True, None

        # WO-SETTLE-FALSEPOS (A): explore-only salvage for the live
        # false-positive class (e.g. 173→119): settle idle+stability flake
        # reports confirmed=False even though the warp landed — post-parse
        # sector == intended hop AND screen still classifies main_command.
        # Upgrade keeps the strict unconfirmed path (no salvage). Never
        # weakens trade_driver / run_chain.
        if candidate.kind == "explore" and candidate.next_sector is not None:
            post_rows = self.session.render()
            post_prompt = post_rows[-1].strip() if post_rows else ""
            post_full = self.session.render_text(post_rows)
            post_cls = classify_screen(post_full, post_prompt) if post_prompt else None
            post_sector = parse_state(post_full).get("sector")
            if post_cls == _MOVEMENT_PROMPT_CLASS and post_sector == candidate.next_sector:
                return True, f"sent:settle_salvage:{reason}:{float(elapsed):.3f}"

        # WO-SETTLE-FALSEPOS (B): instrument settle reason + elapsed so a
        # future deep-dive can tell timeout vs idle-then-bytes without
        # discarding send_and_confirm's first two return values.
        return False, f"unconfirmed:{reason}:{float(elapsed):.3f}"

    def _chain_abort_requested(self) -> bool:
        """A-M1's live abort predicate for a whole-chain `run_chain` tick
        -- `AutopilotLoop.start()` installs `self._abort_requested` as
        `self._stop.is_set`, so `tw autopilot stop` reaches an in-flight
        chain within one send-step (see class docstring's A-M1 note on
        `self._abort_requested`). Permanently False when nothing installed
        it (a caller driving `_execute()`/`live_tick()` standalone, no
        `AutopilotLoop`) -- never an AttributeError/crash."""
        return self._abort_requested is not None and bool(self._abort_requested())

    def _record(self, decision: Decision, *, pre_text: str, input_text: str, post_text: str, dry_run: bool) -> None:
        if self.ledger is None:
            return
        prefix = "DRY-RUN " if dry_run else ""
        if decision.chosen is None:
            intent = f"{prefix}{decision.reason}"
        else:
            tag = " [INTERRUPT]" if decision.interrupted else ""
            outcome = f" [{decision.send_outcome}]" if decision.send_outcome else ""
            intent = f"{prefix}{decision.reason}{tag}{outcome}: {decision.chosen.rationale}"
        settled_class = (
            "autopilot_tick_unconfirmed"
            if _is_unconfirmed_outcome(decision.send_outcome)
            else "autopilot_tick"
        )
        self.ledger.record_do(
            pre_text,
            input_text,
            False,
            post_text,
            settled_class,
            actor=ACTOR,
            session_id=self.session_id,
            intent=intent,
        )

    def _record_crash(self, exc: BaseException) -> None:
        """MED fix (mack poc4): a background `AutopilotLoop` tick that
        raises must not die silently. Ledgers a distinguishable
        `"autopilot_crashed"` entry (actor=trainer) BEFORE the loop's own
        `finally` releases MODE_AUTO_LOOP, so a caller inspecting the
        ledger/session-retro (or the loop's own `last_error`, see
        `AutopilotLoop`) can tell "crashed mid-run" apart from "never got
        a chance to tick yet" -- both of which otherwise look identical
        (`running=False`, `ticks_done` unchanged)."""
        if self.ledger is None:
            return
        try:
            text = self.session.render_text(self.session.render())
        except Exception:
            text = "<render_failed_during_crash_handling>"
        self.ledger.record_do(
            text,
            "<no-send>",
            False,
            text,
            "autopilot_crashed",
            actor=ACTOR,
            session_id=self.session_id,
            intent=f"CRASHED: {type(exc).__name__}: {exc}",
        )


class AutopilotLoop:
    """Background AUTO-LOOP scheduler -- mirrors `loop_player.LoopPlayer`
    exactly (same thread + control-lock discipline, same "entering/
    leaving MODE_AUTO_LOOP is THIS class's job alone, never per-tick"
    rule): `start()` enters MODE_AUTO_LOOP ONCE for the whole run (raises
    `ControlModeConflict` if a human is attached or another AUTO_LOOP
    run is already active); each cycle calls
    `engine.live_tick(**snapshot_provider())`; `stop()`/the run's own
    `finally` leaves MODE_AUTO_LOOP exactly once. `snapshot_provider` is a
    zero-arg callable returning a fresh kwargs dict each tick (wiring
    live game_knowledge/game_data reads into that callable is the
    daemon-integration caller's job -- this class only owns the thread
    lifecycle + control-lock transition, same division of labor
    `LoopPlayer` already has with `replay_skill()`).

    Two MED fixes (mack, 2026-07-20):
    - **Silent thread death (poc4):** a `live_tick()` exception used to
      propagate straight out of the background thread with `finally`
      quietly releasing the control-lock and nothing else -- a crash and
      "never ticked yet" were indistinguishable from the outside. Now
      caught, stashed on `self.last_error`, ledgered via
      `engine._record_crash()`, and the loop stops cleanly.
    - **Honor `send_and_confirm`'s `confirmed`:** a tick whose
      `Decision.send_outcome == "unconfirmed"` means a real desync
      (settle.py: never safe to proceed past) -- the loop halts rather
      than ticking blindly forward past it, and records why via
      `self.last_error`.
    """

    def __init__(
        self,
        engine: AutopilotEngine,
        snapshot_provider: Callable[[], dict],
        *,
        tick_interval_s: float = 1.0,
        max_ticks: int = _MAX_TICKS,
    ):
        self.engine = engine
        self.snapshot_provider = snapshot_provider
        # LOW fixes (cipher): clamp caller input rather than trusting it
        # verbatim -- the hard-cap/no-busy-loop backstops are a class
        # invariant, not merely a documented convention.
        #
        # MED fix (mack re-verify, 2026-07-20): a non-finite tick_interval_s
        # (NaN, or +-inf) used to bypass this floor entirely via `max()`'s
        # own NaN-compare quirk (`max(nan, x)` returns `nan`, not `x`) --
        # the unclamped NaN then reaches `time.sleep(nan)` in `_run()`'s
        # tick loop, OUTSIDE that method's own try/except, so the
        # background thread dies with `self.last_error` left at `None` --
        # the exact silent-death failure mode this revision's MED fix
        # (poc4) exists to close. `math.isfinite()` catches NaN AND +-inf
        # uniformly; either floors to the same `_MIN_TICK_INTERVAL_S` a
        # non-positive interval already floors to.
        interval = float(tick_interval_s)
        self.tick_interval_s = max(interval, _MIN_TICK_INTERVAL_S) if math.isfinite(interval) else _MIN_TICK_INTERVAL_S
        # LOW fix (cipher re-verify, 2026-07-20): a negative/zero max_ticks
        # survives the old `min(int(max_ticks), _MAX_TICKS)` unchanged
        # (`min(-10, 500) == -10`), and `range(-10)` is empty -- a 0-tick,
        # silently-"successful" no-op run that masks whatever caller bug
        # passed a negative value in the first place. Floor to >=1 tick.
        self.max_ticks = max(1, min(int(max_ticks), _MAX_TICKS))
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.ticks_done = 0
        self.last_decision: Optional[Decision] = None
        self.last_error: Optional[str] = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Raises `AutopilotGateError` if the engine isn't gate-enabled,
        `AutopilotLoopError` if already running, `ControlModeConflict` if
        the control-lock refuses (human attached, or -- belt and braces
        -- somehow already in auto_loop)."""
        if not self.engine.enabled:
            raise AutopilotGateError(
                f"autonomous_disabled:profile={getattr(self.engine.profile, 'name', '?')}"
            )
        if self.running:
            raise AutopilotLoopError("already_running")
        self.engine.control_lock.enter_auto_loop()  # raises ControlModeConflict on refusal
        self._stop.clear()
        # A-M1: install the loop-stop kill switch into the engine so a
        # whole-chain `run_chain` tick can abort BETWEEN sends, not only at
        # the next tick boundary below -- see `_chain_abort_requested()`'s
        # own docstring for why this (never `control_lock.is_driver_fenced`)
        # is the real kill switch under MODE_AUTO_LOOP. Cleared in `_run`'s
        # `finally` (even on crash/stop) so a stale callable never survives
        # this loop's own lifetime.
        self.engine._abort_requested = self._stop.is_set
        self.ticks_done = 0
        self.last_decision = None
        self.last_error = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, join_timeout: float = 2.0) -> bool:
        """Signals the loop to exit ASAP and joins up to `join_timeout`
        seconds -- mirrors `LoopPlayer.stop()`'s own contract, including
        why the join matters for a caller relying on "stop() returned =>
        control_lock is back to ai_pilot". Idempotent/safe when nothing
        is running.

        WO-FA4 (A-M1): for a whole-chain `run_chain` tick, this same stop
        event is also the engine's `should_abort` predicate
        (`self.engine._abort_requested`, installed in `start()`) --
        `trade_driver.run_chain()` checks it at every send-step choke
        point, so a mid-chain abort halts within ONE send-step rather than
        only at the next `_run()` tick boundary. A single in-flight
        `send_and_confirm` still has to finish (its own settle timeout)
        before the next check.

        Returns whether the thread had actually stopped by the time this
        returns (LOW fix, cipher: previously undocumented/unsignaled --
        a single in-flight tick outlasting `join_timeout` is a safe,
        best-effort situation, NOT a wedge: `_stop` is still set, and the
        loop's own next tick boundary + `finally` will still release
        MODE_AUTO_LOOP; this return value just lets a caller tell "it's
        already stopped" from "still winding down")."""
        self._stop.set()
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout=join_timeout)
        return not thread.is_alive()

    def snapshot(self) -> dict:
        return {
            "running": self.running,
            "ticks_done": self.ticks_done,
            "last_reason": self.last_decision.reason if self.last_decision else None,
            "last_error": self.last_error,
            # Cross-seat trace supplement (2026-07-20): the status-field
            # transport option -- a caller polling this loop's own
            # snapshot() gets the last tick's structured trace for free,
            # no separate accessor needed for the single-most-recent case
            # (see `AutopilotEngine.trace_log()` for the full recent history).
            "last_trace": decision_to_trace(self.last_decision) if self.last_decision is not None else None,
        }

    def _run(self) -> None:
        try:
            for _ in range(self.max_ticks):
                if self._stop.is_set():
                    break
                try:
                    kwargs = self.snapshot_provider()
                    self.last_decision = self.engine.live_tick(**kwargs)
                except Exception as exc:  # noqa: BLE001 -- MED fix: never die silently, see class docstring
                    self.last_error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
                    with contextlib.suppress(Exception):
                        self.engine._record_crash(exc)
                    break
                self.ticks_done += 1
                # A-M1: after a mid-chain abort the stop event is already
                # set (a `run_chain` tick that HELD with stop_reason
                # "aborted") -- leave immediately rather than sleeping out
                # another full tick_interval_s first.
                if self._stop.is_set():
                    break
                outcome = self.last_decision.send_outcome
                if _is_unconfirmed_outcome(outcome):
                    # MED fix: a real settle desync -- halt rather than
                    # tick blindly past it (settle.py's own contract).
                    # WO-SETTLE-FALSEPOS: instrumented `unconfirmed:reason:elapsed`
                    # still halts; salvaged explore warps never reach here
                    # (they send_outcome as sent:settle_salvage:...).
                    self.last_error = "settle_unconfirmed: halted rather than ticking past a send/settle desync"
                    break
                # FA4 cipher bank (post-land MED): a mid-offer HOLD that
                # left the port's offer prompt on screen
                # (`held:over_budget:` / `held:credits_unknown:`) must
                # stop the loop so MODE_AUTO_LOOP releases promptly --
                # otherwise the next tick can keep driving past a stuck
                # dialogue. Same release seam as unconfirmed above.
                if outcome is not None and (
                    outcome.startswith("held:over_budget:")
                    or outcome.startswith("held:credits_unknown:")
                ):
                    self.last_error = f"chain_held_halt:{outcome}"
                    break
                time.sleep(self.tick_interval_s)
        finally:
            self.engine._abort_requested = None
            with contextlib.suppress(ControlModeConflict):
                self.engine.control_lock.leave_auto_loop()


def maybe_auto_start(
    session,
    profile,
    control_lock,
    snapshot_provider: Callable[[], dict],
    *,
    ledger=None,
    session_id: Optional[str] = None,
    caps: EconCaps = EconCaps(),
    tick_interval_s: float = 1.0,
) -> Optional[AutopilotLoop]:
    """P1-d: the post-login auto-start hook (design doc's
    "Auto-start-on-connect"). Intended call site: right after `run_login`
    (`login.py`) reaches `main_command`, e.g. `protocol.py`'s
    `_dispatch_ensure`, once that (separate, shared-file) integration is
    wired -- this function is deliberately standalone/pure here (no edit
    to `login.py`/`protocol.py`/`daemon.py`, all either explicitly
    out-of-lane for this WO or on the "don't rewrite the engines" list)
    so it's directly callable/testable without that wiring existing yet.

    Returns a STARTED `AutopilotLoop` iff `profile.autonomous` is True
    AND the control-lock will accept entering MODE_AUTO_LOOP right now
    (not already human-attached or already auto-looping); returns `None`
    otherwise -- never raises for the ordinary "not enabled" / "human has
    the keyboard" cases, since a post-login hook declining to start must
    never crash the login success path it's attached to. Never starts
    under MODE_HUMAN (checked twice: once here for a fast/clear early
    exit, and authoritatively inside `AutopilotLoop.start()` ->
    `control_lock.enter_auto_loop()`'s own atomic check -- mirroring
    control_lock.py's own documented "up-front check is never the source
    of truth" pattern, so a race between the two can never leave this
    silently started under a human)."""
    if not bool(getattr(profile, "autonomous", False)):
        return None
    if control_lock.mode == MODE_HUMAN:
        return None
    engine = AutopilotEngine(session, profile, control_lock, ledger=ledger, session_id=session_id, caps=caps)
    loop = AutopilotLoop(engine, snapshot_provider, tick_interval_s=tick_interval_s)
    try:
        loop.start()
    except ControlModeConflict:
        return None
    return loop
