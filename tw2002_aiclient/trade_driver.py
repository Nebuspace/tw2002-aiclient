"""Guarded one-pass trade-chain execution.

`autopilot.py`'s own module docstring cut EXECUTE to navigation-only and
explicitly deferred "a fuller haggle-wired trade-loop driver" as a
follow-up. This module is that follow-up: given a `chains.ProfitChain`
already discovered by `trade_adapter.build_trade_hops` +
`chains.longest_profit_chain`, `run_chain()` drives the WHOLE loop --
navigate -> dock -> buy -> navigate -> dock -> sell -> repeat -- end to
end, synchronously, one call. `autopilot.AutopilotEngine._execute_chain()`
routes a chosen `"run_chain"` candidate here instead of a single bare
sector-number send.

**Ground truth, not invention.** Every screen shape this module drives
against is cited from a LIVE-CAPTURED source already in this repo:
  - The port-encounter menu + trade-select + docking cascade:
    `tests/test_world_model_integration.py`'s scroll-off-burst test (a
    real pyte-fed transcript) and `tests/fixtures/port_trade_screen.txt`
    (the "nothing tradeable" case) both show the SAME sequence: at the
    ordinary sector command prompt, `"P"` -> `<A> Attack this Port` /
    `<T> Trade at this Port` / `<Q> Quit, nevermind`, "Enter your choice
    [T] ?" -> `"T"` (never any other letter) -> `<Port>` -> "Docking..."
    -> "One turn deducted, N turns left." -> the commerce report -> back
    to the ordinary "Command [TL=...]" prompt (docked commerce prints
    ABOVE the same sector command prompt, never a distinct prompt shape
    -- `state_parser.is_genuine_port_report()` exists precisely because
    classify.py can't tell "docked" from "just standing here" from the
    prompt alone).
  - The commodity quantity prompt ("How many holds of X [N]?") is cited
    independently by `ledger.py`'s `extract_prompt()` docstring,
    `guardian.py`'s inactivity-timeout rationale, and DESIGN-v2.md's §8
    "phantom-blank-line" incident report.
  - The offer/haggle prompt ("Your offer [N] ?") is `state_parser.
    parse_haggle`'s own live-captured shape, already exercised by
    `haggle.py`/`tests/test_haggle.py`.
  - `tests/fixtures/port_trade_screen.txt` is the live "nothing
    tradeable here" case: the cascade never shows a quantity prompt at
    all when nothing is tradeable -- this module's own depletion
    detection (`_visit_port()`) relies on exactly that observed
    behavior: a commodity absent from the whole cascade means "not
    tradeable right now", never a guessed `[0]` default.

There is no separate "undock" verb anywhere in this game: the docked
Command prompt IS the ordinary sector command prompt, so simply warping
to the next hop's sector IS the undock action -- this module never sends
an explicit undock keystroke.

**PALADIN (no combat/attack/genesis verb reachable from any driver
state).** The only single-letter commands this module can EVER send are
the two hardcoded literals `"P"` (enter the port) and `"T"` (trade,
NEVER `"A"`ttack) -- enforced at TWO layers: `_send_letter()`'s own
allowlist (no call site ever constructs a letter from caller input), and
`_confirmed_send()`'s general shape-assert (belt-and-braces, catches any
FUTURE bad construction from ANY call site, not just letter sends).
Every other send is a bare sector number (nav), a bare non-negative
integer (a quantity), `"0"` (decline a commodity we don't want), or `""`
(accept the port's own current offer -- no countering).

**Auto-haggle OFF.** This module NEVER counters an offer: `_accept_offer()`
always sends a blank line, accepting the port's own current default. If a
particular server variant refuses a bare accept and forces at least one
counter, the resulting screen fails every recognized confirm shape and
`send_and_confirm` reports `confirmed=False` -- this module HOLDs cleanly
(`"unconfirmed_send:..."`) rather than ever implementing counter logic.

**Fresh-render gate before every send (HIGH-2/TOCTOU discipline).** Every
send in this module is preceded by a FRESH `session.render()` call whose
resulting text/prompt-line is what gets checked against the expected
shape for that step -- never a screen captured earlier in the call.
Mirrors `autopilot.py`'s own HIGH-2 fix (same `classify_screen` call,
same "blank render is itself a HOLD" rule) for navigation sends, and
haggle.py's `_resolution_evidence()` convention (check the CURRENT
last-non-blank line, never trust a whole-buffer `confirm_prompt` match by
itself) for the dock/trade-cascade sends.

**Interruptibility (A-M1, the #1 arm-prerequisite).** `run_chain()` takes
a REQUIRED, fail-closed `should_abort: Callable[[], bool]` -- checked at
the same choke point (`_confirmed_send()`) as every other gate, so an
in-flight chain halts within ONE send-step of the caller's stop signal
firing, never only at the next `AutopilotLoop` tick boundary. The
original design considered wiring `control_lock.is_driver_fenced()` (the
WO-CLEANPREEMPT fence `skills.replay_skill()`/`loop_player.LoopPlayer`
both use) -- but that fence is STRUCTURALLY DEAD for the autopilot path:
it only flips when `take_human()` finds `_driving` True, and `_driving`
is set only by `acquire_driver()` (the do/send-family dispatch path);
the autopilot runs under `MODE_AUTO_LOOP` instead, and `take_human()`
REFUSES OUTRIGHT under that mode (`control_lock.py`'s own
`locked_by_auto_loop`) -- the fence can never fire here. `should_abort`
generalizes this into the one predicate that actually matters:
`AutopilotLoop` wires `should_abort=self._stop.is_set`, so `tw autopilot
stop` reaches an in-flight chain within one send-step, and once
`AutopilotLoop._run()`'s own next tick-boundary check observes the same
stop signal and its `finally` releases `MODE_AUTO_LOOP` (the existing,
unchanged mechanism -- see that class's own docstring), `tw attach`
succeeds immediately after.

**Fail-closed arming (A-C1).** `run_chain()` also takes a REQUIRED
`is_armed: Callable[[], bool]` -- checked alongside `should_abort` at the
same choke point. `AutopilotEngine._execute_chain()` supplies
`lambda: self.enabled` (immutable post-construction, so this is never a
live toggle -- see that method's own docstring for why a REQUIRED INPUT,
not an internal re-check, is the correct shape: a bare `self.enabled`
re-check INSIDE this module would be a no-op against a value this module
has no way to read on its own).

**Turns budget.** This server never surfaces a live turn COUNT outside a
post-dock "N turns left." line (`TL=` is an HH:MM:SS countdown here, see
`state_parser.py`'s own module docstring) -- so this module tracks a
LOCAL decrementing budget (1 turn/warp + `config.dock_turn_cost` per
dock, both conservative estimates) and RECONCILES it against the
authoritative post-dock reading every time one is available
(`_reconcile_turns()`), at both port visits of every hop. A hop's
upfront turn-floor check (in `run_chain()`, using the chain's own
discovery-time `hop.turns` estimate) is NOT the only gate: `_visit_port()`
independently re-verifies `turns_budget - config.dock_turn_cost >=
caps.turn_reserve` immediately before EVERY dock (A-M3) -- a hop whose
discovery-time estimate undercounts the live route (the known graph grew
since discovery) still gets caught at the dock boundary, not two sends
past the breach.

**Per-buy precision.** Quantity is computed from the SAME pct-based price
estimate `trade_adapter._commodity_price()` already uses for chain
discovery (never a fresh, diverging pricing model), sized conservatively
under `caps.cash_floor` with `config.qty_safety_margin` headroom, then
RE-VERIFIED against the live TOTAL the qty prompt's own follow-up offer
reports (`state_parser.parse_haggle()`'s `current_default` -- a
TRANSACTION TOTAL for the submitted qty, never a per-unit price) before
ever accepting. A strict balance is re-read immediately before every buy
decision (`_current_strict_credits()`, itself `state_parser.
credits_balance()` off the CURRENT screen when a balance line is visible
there, else `session.credits_snapshot()`'s freshness-gated cache --
NEVER `state_parser.parse_state()`'s loose, price-pollutable `credits`
field) and again immediately after, with a MAGNITUDE sanity check (A-C4)
on the resulting delta -- not merely its direction, so a real overcharge
or mis-parse whose direction still happens to be correct is still caught.

**Cargo never stranded (A-M2).** On the SELL side, a genuine `[0]`
live-max bracket for the commodity we're actually holding is a distinct,
fatal stop (`"cargo_stranded:..."`) -- never a silent "decline and count
the hop complete", which would strand cargo we already paid for while
reporting a profitable round trip that never actually happened.

**UX-parity progress events (A-PROG, not a freeze fix).** `run_chain()`
takes an optional `on_progress` callback, invoked at each hop boundary
(and once more when the chain stops) -- mirrors `loop_player.LoopPlayer.
_broadcast_progress()`'s pattern exactly (a plain event dict, pushed by
the caller through `watch.WatchHub.broadcast_extra()`). `AutopilotLoop`
never freezes the raw spectate viewport during a chain (`WatchHub._loop`
polls session state independently of protocol.py, on its own 50ms
thread); what's missing without this is the hop/step METADATA overlay
(which hop, which step) `LoopPlayer` already has and `AutopilotLoop`
otherwise lacks. This module never imports `watch.py`/`autopilot.py`
itself -- the callback is the caller's job to wire.
"""

from __future__ import annotations

import contextlib
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional

from .chains import ProfitChain, TradeHop
from .explore import known_graph, path_to_sector
from .session.classify import classify_screen, is_avoid_danger_warp
from .session.settle import send_and_confirm
from .session.state_parser import (
    OUTCOME_READ,
    read_credits_balance,
    read_current_sector,
    read_port_commodities_from_report,
    read_turns_left_from_screen,
    read_warps_from_sector_status,
)
from .trade_adapter import DEFAULT_CEILING_MULTIPLIER, DEFAULT_FLOOR_PRICES, _commodity_price

# The one live classification a bare sector-number nav send is safe
# against -- mirrors autopilot.py's own `_MOVEMENT_PROMPT_CLASS` (same
# value, kept as an independent constant so this module has no
# import-time dependency on autopilot.py -- see module docstring's
# PALADIN section for why this module never depends upward on the engine
# that calls it).
_MOVEMENT_PROMPT_CLASS = "main_command"

# -- ground-truth screen-shape patterns (see module docstring's citations
# for each) -- case-SENSITIVE, matching `settle.send_and_confirm`'s own
# no-re.IGNORECASE convention (it hands `wait_prompt` straight to
# `re.compile()` with no flags) wherever a pattern is used as a
# confirm_prompt. Extraction-only patterns (never a confirm_prompt) stay
# `re.I` for robustness, same split state_parser.py/haggle.py already use.
_PORT_MENU_CONFIRM_PATTERN = r"Enter\s+your\s+choice\s*\[\s*T\s*\]\s*\?"
_PORT_MENU_PROMPT_RE = re.compile(_PORT_MENU_CONFIRM_PATTERN)
_QTY_PROMPT_PATTERN = r"How\s+many\s+holds\s+of\s+[A-Za-z ]+\s*\[\s*\d[\d,]*\s*\]\s*\?"
_QTY_PROMPT_RE = re.compile(r"how\s+many\s+holds\s+of\s+([A-Za-z ]+?)\s*\[\s*(\d[\d,]*)\s*\]\s*\?", re.I)
_COMMAND_PROMPT_PATTERN = r"Command\s*\[\s*TL\s*="
_COMMAND_PROMPT_RE = re.compile(_COMMAND_PROMPT_PATTERN)
_OFFER_PROMPT_PATTERN = r"Your\s+offer\s*\[\s*\d[\d,]*\s*\]\s*\?"
_OFFER_PROMPT_RE = re.compile(
    r"Your\s+offer\s*\[\s*(\d[\d,]*)\s*\]\s*\?\s*$", re.I
)
_CARGO_HOLDS_EMPTY_RE = re.compile(r"(\d[\d,]*)\s+empty\s+cargo\s+holds", re.I)

# Whatever the trade cascade can legitimately land on after a dock-select
# or a decline: another commodity's quantity prompt, or the cascade
# ending back at the ordinary command prompt.
_CASCADE_ENTRY_PATTERN = f"{_QTY_PROMPT_PATTERN}|{_COMMAND_PROMPT_PATTERN}"
# After submitting a quantity: the haggle/offer prompt for THIS
# commodity, or (a port that skips the offer step entirely) straight to
# the next cascade entry.
_OFFER_OR_CASCADE_PATTERN = f"{_OFFER_PROMPT_PATTERN}|{_CASCADE_ENTRY_PATTERN}"

# The ONLY single-letter commands this module may ever send -- see module
# docstring's PALADIN section. "A" (Attack) and "Q" (Quit, nevermind) are
# both real options on the port-encounter menu and MUST never be reachable
# from any code path here.
_ALLOWED_LETTER_SENDS = frozenset({"P", "T", "Y", "N"})
# "Y"/"N" are WO-WARP-CONFIRM-Y only (avoid-list warp confirm after an
# intentional hop this module just sent -- N on the avoid-DANGER body,
# Y on an ordinary confirm; see `_navigate`). Still never Attack/Quit/Pay
# — those stay out.

DEFAULT_MAX_STEPS = 200
DEFAULT_QTY_SAFETY_MARGIN = 0.9
DEFAULT_STEP_TIMEOUT_S = 8.0
DEFAULT_DOCK_TURN_COST = 1
DEFAULT_MIN_MARGIN_PER_HOP = 0
# A-C4: no known live rounding source between the live TOTAL a haggle
# accept confirms and the actual observed credits delta -- an exact
# match is expected. Kept as a named, config-driven constant (never
# hardcoded inline) in case a future server variant needs slack.
DEFAULT_CREDIT_DELTA_EPSILON = 0
# bounded: 3 known commodities + 1 margin -- see _visit_port()'s own
# per-commodity cascade loop.
_MAX_COMMODITY_PROMPTS = 4


class PaladinViolation(Exception):
    """Belt-and-braces (mirrors `autopilot.AutopilotGateError`'s own
    kind-whitelist role): raised if a caller ever calls `_send_letter()`
    with anything outside `_ALLOWED_LETTER_SENDS`, or if `_confirmed_send()`
    is ever asked to send a shape outside "" / digits-only / an allowed
    letter (A-C2). Unreachable through this module's own code today --
    every call site already only constructs one of those shapes -- kept
    as a defensive class-invariant guard, not a caller-trust assumption."""


class ChainHold(Exception):
    """Internal control-flow signal: `run_chain()`'s one and only place
    that turns a stop condition into a `ChainRunResult` -- every helper
    below raises this the instant it detects ANY stop condition (an
    abort/arm-gate refusal, the turn floor, max steps, an unexpected
    screen, a settle desync, a depleted/unaffordable/stranded leg, a
    below-floor realized margin, ...) rather than returning a sentinel a
    caller could accidentally ignore."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class TradeDriverConfig:
    """Every knob this driver owns that ISN'T already an `EconCaps` field
    (reserve/cash-floor stay on the caller's `EconCaps` -- never
    duplicated here, see `run_chain()`'s own `caps` parameter) --
    config-not-hardcoded per WO-FA4's explicit requirement."""

    max_steps: int = DEFAULT_MAX_STEPS
    qty_safety_margin: float = DEFAULT_QTY_SAFETY_MARGIN
    step_timeout_s: float = DEFAULT_STEP_TIMEOUT_S
    dock_turn_cost: int = DEFAULT_DOCK_TURN_COST
    min_margin_per_hop: int = DEFAULT_MIN_MARGIN_PER_HOP
    credit_delta_epsilon: int = DEFAULT_CREDIT_DELTA_EPSILON
    price_floor_prices: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_FLOOR_PRICES))
    price_ceiling_multiplier: float = DEFAULT_CEILING_MULTIPLIER


@dataclass(frozen=True)
class ChainRunResult:
    """`run_chain()`'s one falsifiable output. `stop_reason` is
    `"completed"` iff every hop finished (buy+sell) and the ship is back
    at the chain's start sector; every other value names exactly which
    stop condition ended it (see each raise site below) -- the caller
    (`autopilot.AutopilotEngine.live_tick()`) prefixes it `"held:"` to
    match that module's existing `decision.send_outcome` schema; kept
    bare here since this module has no dependency on autopilot.py's
    trace conventions."""

    completed: bool
    hops_completed: int
    steps: int
    credits_delta: Optional[int]
    stop_reason: str
    trace: tuple[str, ...] = field(default_factory=tuple)


class _StepCtx:
    """Bundles the mutable per-call state every step helper below needs,
    so `run_chain()`'s own body stays a plain, readable hop loop. Not a
    public type -- constructed once per `run_chain()` call."""

    def __init__(
        self,
        session,
        config: TradeDriverConfig,
        should_abort: Callable[[], bool],
        is_armed: Callable[[], bool],
    ):
        self.session = session
        self.config = config
        self._should_abort = should_abort
        self._is_armed = is_armed
        self.steps = 0
        self.trace: list[str] = []

    def aborted(self) -> bool:
        """A-M1: the REQUIRED abort predicate -- see module docstring."""
        return bool(self._should_abort())

    def armed(self) -> bool:
        """A-C1: the REQUIRED fail-closed arm gate -- see module docstring."""
        return bool(self._is_armed())

    def fresh(self) -> tuple[str, str]:
        """ONE fresh render -> `(full_text, prompt_line)` -- the single
        source every gate check below reads, never a memoized/stale
        earlier render (HIGH-2/TOCTOU discipline, see module docstring)."""
        rows = self.session.render()
        prompt_line = rows[-1].strip() if rows else ""
        full_text = self.session.render_text(rows)
        return full_text, prompt_line


def _confirmed_send(ctx: _StepCtx, text: str, confirm_prompt: Optional[str], *, enter: bool) -> None:
    """The one place every actual send in this module funnels through:
    the fail-closed arm gate (A-C1), the abort predicate (A-M1), the
    step budget, a shape-assert (A-C2), then `settle.send_and_confirm` --
    and a clean `ChainHold` the instant any of those refuse."""
    if not ctx.armed():
        raise ChainHold("armed_off")
    if ctx.aborted():
        raise ChainHold("aborted")
    if ctx.steps >= ctx.config.max_steps:
        raise ChainHold("max_steps_exceeded")
    # A-C2: belt-and-braces PALADIN shape-assert at the TRUE choke
    # point -- every call site above this one already only ever
    # constructs "" / a bare non-negative integer / an allowed letter;
    # this catches a FUTURE bad construction from ANY call site, not
    # just `_send_letter()`'s own narrower allowlist.
    if text != "" and not text.isdigit() and text not in _ALLOWED_LETTER_SENDS:
        raise PaladinViolation(f"refused_disallowed_send_shape:{text!r}")
    _reason, _elapsed, confirmed = send_and_confirm(
        ctx.session, text, confirm_prompt, enter=enter, timeout_s=ctx.config.step_timeout_s
    )
    ctx.steps += 1
    if not confirmed:
        raise ChainHold(f"unconfirmed_send:{text!r}")


def _send_letter(ctx: _StepCtx, letter: str, confirm_prompt: str) -> None:
    """PALADIN allowlist gate -- see module docstring. `letter` is always
    a hardcoded caller literal (`"P"`/`"T"`); this assertion is defensive,
    never a caller-trust assumption."""
    if letter not in _ALLOWED_LETTER_SENDS:
        raise PaladinViolation(f"refused_disallowed_letter_send:{letter!r}")
    _confirmed_send(ctx, letter, confirm_prompt, enter=True)


def _current_strict_credits(session, caps, current_text: str) -> Optional[int]:
    """The strict credits source, per-buy precision: the freshest
    possible reading first -- `state_parser.credits_balance()` off the
    screen we're already holding (the docked commerce report genuinely
    prints "You have N credits..." on the SAME screen, see
    `tests/fixtures/port_trade_screen.txt`) -- falling back to `session.
    credits_snapshot()`'s freshness-gated cache (mirrors `autopilot.
    AutopilotEngine._fresh_credits()`/`loop_player.py`'s own identical
    inline copy of this exact check -- an independent, duplicated
    implementation is this codebase's own established convention for
    this specific cross-module concern) when the current screen carries
    no balance line of its own. NEVER `state_parser.parse_state()`'s
    loose `credits` field (a port's own price quote satisfies it just as
    well as a real balance)."""
    on_screen = read_credits_balance(current_text)
    if on_screen.outcome == OUTCOME_READ:
        return on_screen.balance
    if hasattr(session, "credits_snapshot"):
        snapshot = session.credits_snapshot()
    else:
        snapshot = None
    if snapshot is None:
        return None
    # Current Session contract: a validated snapshot carrying an age. Keep
    # tuple support only for the archived hermetic driver fixtures.
    if hasattr(snapshot, "outcome"):
        if snapshot.outcome != OUTCOME_READ:
            return None
        age_s = getattr(snapshot, "age_s", None)
        balance = getattr(snapshot, "balance", None)
        if age_s is None or balance is None:
            return None
        return balance if age_s * 1000 <= caps.credits_stale_ms else None
    try:
        balance, timestamp = snapshot
    except (TypeError, ValueError):
        return None
    if balance is None or timestamp is None:
        return None
    age_ms = (time.monotonic() - timestamp) * 1000
    return balance if age_ms <= caps.credits_stale_ms else None


def _free_holds(text: str) -> Optional[int]:
    m = _CARGO_HOLDS_EMPTY_RE.search(text)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def _reconcile_turns(text: str, turns_budget: int) -> int:
    """The authoritative post-dock "N turns left." reading (`state_parser.
    parse_state()`'s own `_TURNS_LEFT_PLAIN_RE` path) OVERWRITES the local
    estimate whenever one is available on THIS screen; otherwise the
    local decrementing budget (already conservative -- see module
    docstring) stands unchanged."""
    live = read_turns_left_from_screen(text)
    return live.turns if live.outcome == OUTCOME_READ else turns_budget


def _find_commodity_row(text: str, commodity: str) -> Optional[dict]:
    report = read_port_commodities_from_report(text)
    if not report.observed:
        return None
    for row in report.commodities:
        if str(row.get("name", "")).casefold() == commodity.casefold():
            return row
    return None


def _offer_total(text: str) -> Optional[int]:
    """The current prompt's standing transaction total, never a body quote."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    match = _OFFER_PROMPT_RE.search(lines[-1])
    if match is None:
        return None
    return int(match.group(1).replace(",", ""))


def _dock(ctx: _StepCtx, hop_index: int) -> None:
    """`"P"` (enter the port) then `"T"` (trade -- PALADIN: never
    `"A"`ttack) -- the live-captured menu cascade, see module docstring.
    Gated on the CURRENT screen genuinely being the ordinary sector
    command prompt before ever sending "P" (HIGH-2 discipline, same
    classification autopilot.py's own nav gate uses)."""
    full_text, prompt_line = ctx.fresh()
    if not prompt_line or classify_screen(full_text, prompt_line) != _MOVEMENT_PROMPT_CLASS:
        raise ChainHold(f"unexpected_screen:predock:{hop_index}")
    _send_letter(ctx, "P", _PORT_MENU_CONFIRM_PATTERN)

    # Re-derive the CURRENT line independently rather than trusting the
    # settle-layer match alone (haggle.py's `_resolution_evidence()`
    # convention -- see module docstring's fresh-render-gate section).
    _full_text, prompt_line = ctx.fresh()
    if not _PORT_MENU_PROMPT_RE.search(prompt_line):
        raise ChainHold(f"unexpected_screen:dock_menu:{hop_index}")
    _send_letter(ctx, "T", _CASCADE_ENTRY_PATTERN)


def _decline(ctx: _StepCtx) -> None:
    _confirmed_send(ctx, "0", _CASCADE_ENTRY_PATTERN, enter=True)


def _send_qty(ctx: _StepCtx, qty: int) -> None:
    _confirmed_send(ctx, str(qty), _OFFER_OR_CASCADE_PATTERN, enter=True)


def _accept_offer(ctx: _StepCtx) -> None:
    """Fixed-price ACCEPT path only: a blank line always accepts
    whatever the port's own current default is, never a counter-offer.
    If a server variant refuses a bare accept, the resulting screen
    fails to confirm and `_confirmed_send` raises `ChainHold
    ("unconfirmed_send:...")` -- the bounded-HOLD backstop, never
    counter logic (see module docstring)."""
    _confirmed_send(ctx, "", _CASCADE_ENTRY_PATTERN, enter=True)


def _sanity_check_delta(
    direction: str, before: Optional[int], after: Optional[int], total: Optional[int], epsilon: int
) -> bool:
    """A-C4: validates MAGNITUDE, not just direction. The original check
    accepted ANY drop in the right direction (buy: `after<=before`;
    sell: `after>=before`) -- which would miss a real overcharge/
    mis-parse whose direction still happened to be correct. `None` on
    `before`/`after`/`total` means "can't verify" -- never spuriously
    blocks a trade whose credits (or live total) simply weren't
    observable at one of the checkpoints."""
    if before is None or after is None or total is None:
        return True
    actual_delta = (before - after) if direction == "buy" else (after - before)
    return abs(actual_delta - total) <= epsilon


def _trade_target(
    ctx: _StepCtx,
    hop: TradeHop,
    direction: str,
    live_max: int,
    held_qty: int,
    port_row: Optional[dict],
    free_holds: Optional[int],
    caps,
    config: TradeDriverConfig,
    hop_index: int,
) -> tuple[int, Optional[int]]:
    """Size, submit, and (if it clears every gate) accept ONE commodity
    trade at the quantity prompt we're already sitting at. Returns the
    actual traded quantity and live transaction total. Raises
    `ChainHold` on any stop condition -- never silently trades an unsafe
    quantity."""
    if direction == "sell":
        qty = max(0, min(live_max, held_qty))
    else:
        price = _commodity_price(port_row, config.price_floor_prices, config.price_ceiling_multiplier) if port_row else None
        strict_credits = _current_strict_credits(ctx.session, caps, ctx.fresh()[0])
        if strict_credits is None:
            _decline(ctx)
            raise ChainHold(f"credits_unknown:{hop_index}:{direction}")
        if price is None or price <= 0:
            _decline(ctx)
            raise ChainHold(f"price_unknown:{hop_index}:{direction}:{hop.commodity}")
        budget = strict_credits - caps.cash_floor
        affordable = int(budget / price * config.qty_safety_margin) if budget > 0 else 0
        qty = max(0, min(live_max, affordable))
        if free_holds is not None:
            qty = min(qty, free_holds)

    if qty <= 0:
        # A-M2 (CRITICAL): a genuine `[0]` live-max bracket on the SELL
        # side, with cargo we actually hold, must never be silently
        # "declined" and let the caller count this hop as completed --
        # that strands cargo we already paid for while reporting a
        # profitable round trip that never happened. Distinct from the
        # generic "not tradeable at all" / "can't afford any" cases
        # below, which are honest, non-stranding stops.
        if direction == "sell" and held_qty > 0 and live_max == 0:
            _decline(ctx)
            raise ChainHold(f"cargo_stranded:{hop_index}:{direction}:{hop.commodity}")
        _decline(ctx)
        if live_max > 0:
            # The port genuinely has stock, we simply can't afford/carry
            # any -- a distinct, honest stop from "not tradeable at all".
            raise ChainHold(f"unaffordable:{hop_index}:{direction}:{hop.commodity}")
        return 0, None

    before_text = ctx.fresh()[0]
    before_credits = _current_strict_credits(ctx.session, caps, before_text)
    _send_qty(ctx, qty)

    text = ctx.fresh()[0]
    total = _offer_total(text)
    if total is None:
        # The dialogue skipped straight past the offer step -- never
        # silently trusted (haggle.py's own "the offer prompt is gone
        # alone is never proof of a deal" discipline, applied here too).
        raise ChainHold(f"unexpected_screen:offer:{hop_index}:{direction}")

    # `current_default`/`baseline` are TRANSACTION TOTALS for the qty we
    # just submitted, never a per-unit price -- re-confirm the STRICT
    # balance against this live TOTAL before ever accepting.
    cur_credits = _current_strict_credits(ctx.session, caps, text)
    if direction == "buy":
        if cur_credits is None:
            raise ChainHold(f"credits_unknown:{hop_index}:{direction}")
        if cur_credits - total < caps.cash_floor:
            # Bounded-HOLD backstop: never counter, never accept over
            # budget -- just stop here.
            raise ChainHold(f"over_budget:{hop_index}:{direction}:{hop.commodity}")

    _accept_offer(ctx)
    after_text = ctx.fresh()[0]
    after_credits = _current_strict_credits(ctx.session, caps, after_text)
    if not _sanity_check_delta(
        direction,
        cur_credits if cur_credits is not None else before_credits,
        after_credits,
        total,
        config.credit_delta_epsilon,
    ):
        raise ChainHold(f"credit_delta_anomaly:{hop_index}:{direction}:{hop.commodity}")

    ctx.trace.append(f"hop{hop_index} {direction} {qty}x {hop.commodity} @ ~{total}cr total")
    return qty, total


def _visit_port(
    ctx: _StepCtx,
    hop: TradeHop,
    direction: str,
    held_qty: int,
    caps,
    config: TradeDriverConfig,
    turns_budget: int,
    hop_index: int,
) -> tuple[int, Optional[int], int]:
    """Dock, drive the commodity cascade (trade OUR target commodity,
    decline every other one), and reconcile the turns budget. Returns
    `(traded_qty, transaction_total, new_turns_budget)`. Raises
    `ChainHold(f"depleted:...")` if the cascade never shows our target
    commodity at all (the port has nothing to trade for it right now --
    see module docstring's `port_trade_screen.txt` citation)."""
    if ctx.aborted():
        raise ChainHold("aborted")
    # A-M3 (HIGH): re-verify the turn floor immediately before THIS
    # dock, not just via run_chain()'s own upfront per-hop estimate. A
    # hop whose discovery-time `hop.turns` undercounts the live route
    # (the known graph grew since discovery) passes that upfront check,
    # `_navigate()` then consumes the real (larger) turn cost, and this
    # dock would otherwise fire unconditionally past the reserve.
    if turns_budget - config.dock_turn_cost < caps.turn_reserve:
        raise ChainHold(f"turn_floor:{hop_index}:predock")
    _dock(ctx, hop_index)
    text = ctx.fresh()[0]
    turns_budget = _reconcile_turns(text, turns_budget - config.dock_turn_cost)
    port_row = _find_commodity_row(text, hop.commodity)
    free_holds = _free_holds(text) if direction == "buy" else None

    traded_qty = 0
    transaction_total = None
    seen_target = False
    for _ in range(_MAX_COMMODITY_PROMPTS):
        if ctx.aborted():
            raise ChainHold("aborted")
        full_text, prompt_line = ctx.fresh()
        m = _QTY_PROMPT_RE.search(prompt_line)
        if m:
            name, live_max_s = m.group(1).strip(), m.group(2)
            live_max = int(live_max_s.replace(",", ""))
            if not seen_target and name.casefold() == hop.commodity.casefold():
                seen_target = True
                traded_qty, transaction_total = _trade_target(
                    ctx, hop, direction, live_max, held_qty, port_row, free_holds, caps, config, hop_index
                )
            else:
                _decline(ctx)
            continue
        if _COMMAND_PROMPT_RE.search(prompt_line):
            break
        raise ChainHold(f"unexpected_screen:cascade:{hop_index}")
    else:
        raise ChainHold(f"max_commodity_prompts_exceeded:{hop_index}")

    if not seen_target:
        raise ChainHold(f"depleted:{hop_index}:{direction}:{hop.commodity}")
    return traded_qty, transaction_total, turns_budget


def _navigate(
    ctx: _StepCtx,
    graph: Mapping[int, tuple],
    frm: int,
    to: int,
    turns_budget: int,
    caps,
    hop_index: int,
) -> int:
    """One warp at a time along the known-graph shortest path from `frm`
    to `to`, each gated fresh (HIGH-2 classify check + a non-adjacent
    backstop mirroring `autopilot.py`'s own HIGH fix) -- never the
    chain's own far-side sector fired blind."""
    if frm == to:
        return turns_budget
    path = path_to_sector(graph, frm, to)
    if path is None or len(path) < 2:
        raise ChainHold(f"route_unknown:{hop_index}")

    for next_sector in path[1:]:
        if ctx.aborted():
            raise ChainHold("aborted")
        if turns_budget - 1 < caps.turn_reserve:
            raise ChainHold(f"turn_floor:{hop_index}")
        full_text, prompt_line = ctx.fresh()
        if not prompt_line:
            raise ChainHold(f"unexpected_screen:nav_blank:{hop_index}")
        cls = classify_screen(full_text, prompt_line)
        if cls != _MOVEMENT_PROMPT_CLASS:
            raise ChainHold(f"unexpected_screen:nav_not_main_command:{hop_index}:{cls}")
        live_warps = read_warps_from_sector_status(full_text)
        if live_warps is not None and next_sector not in live_warps:
            raise ChainHold(f"non_adjacent_nav:{hop_index}:{next_sector}")
        _confirmed_send(ctx, str(next_sector), None, enter=True)
        turns_budget -= 1
        # WO-WARP-CONFIRM-Y (REVISE, hub reject of always-Y): TWGS avoid-list
        # mid-warp Y/N after *this* hop. Intentional by construction (we just
        # sent the sector). Other unexpected screens still HOLD at the next
        # hop's entry gate. Avoid-DANGER body -> decline (N) and HOLD this
        # hop rather than loop back into the same avoided sector -- the
        # chain's route was computed against the known graph, not against
        # TWGS's separate avoid-list, so this is the one place that can
        # discover a route step is avoided, and refusing beats guessing a
        # detour. Ordinary confirm (no DANGER body) -> Y, as before.
        full_text, prompt_line = ctx.fresh()
        if classify_screen(full_text, prompt_line) == "warp_confirm":
            if is_avoid_danger_warp(full_text):
                _confirmed_send(ctx, "N", None, enter=False)
                raise ChainHold(f"avoid_declined:{hop_index}:{next_sector}")
            _confirmed_send(ctx, "Y", None, enter=False)
    return turns_budget


def _emit_progress(
    on_progress: Optional[Callable[[dict], None]],
    *,
    hop_index: int,
    hops_total: int,
    steps: int,
    done: bool,
    stop_reason: Optional[str] = None,
) -> None:
    """A-PROG: UX parity for the spectate witness, NOT a freeze fix (see
    module docstring) -- a plain event dict, mirroring `loop_player.
    LoopPlayer._broadcast_progress()`'s own shape. Availability-only:
    an exception from a caller's own callback must never abort the
    chain over a pure telemetry concern."""
    if on_progress is None:
        return
    event = {
        "kind": "chain_progress",
        "hop_index": hop_index,
        "hops_total": hops_total,
        "steps": steps,
        "done": done,
        "stop_reason": stop_reason,
    }
    with contextlib.suppress(Exception):
        on_progress(event)


def run_chain(
    session,
    chain: ProfitChain,
    *,
    world_id: Optional[str],
    turns_left: Optional[int],
    caps,
    should_abort: Callable[[], bool],
    is_armed: Callable[[], bool],
    state_dir=None,
    config: Optional[TradeDriverConfig] = None,
    on_progress: Optional[Callable[[dict], None]] = None,
) -> ChainRunResult:
    """Drive `chain` to completion: for every hop, buy `hop.commodity` at
    `hop.frm` (assumed to be the CURRENT sector for hop 0 -- the same
    precondition `autopilot._score_chain()` already requires before ever
    choosing a `run_chain` candidate -- and, for every later hop, the
    previous hop's own `to`, since `chains.py`'s cycle-hop chaining
    invariant guarantees `hops[i].to == hops[i+1].frm`), navigate to
    `hop.to`, sell there, and move on -- until every hop is done (ship
    back at the chain's start sector) or a stop condition ends it early.

    `world_id`/`turns_left` are REQUIRED keyword-only params (no
    default) that may still legitimately be `None` -- meaning "unknown"
    -- in which case this function HOLDs immediately rather than crash
    or guess (the same required-but-nullable shape `autopilot.assess()`'s
    `credits` kwarg already established). `caps` is the caller's
    `autopilot.EconCaps` instance (duck-typed here --
    `.cash_floor`/`.turn_reserve`/`.credits_stale_ms` -- so this module
    has no import-time dependency on autopilot.py, see module
    docstring's PALADIN section for why layering stays one-directional).

    `should_abort`/`is_armed` (A-M1/A-C1): REQUIRED, fail-closed
    predicates -- see module docstring. `on_progress` (A-PROG): optional,
    availability-only telemetry -- see `_emit_progress()`.

    Never raises out to the caller -- every stop condition is caught here
    and turned into a `ChainRunResult`."""
    config = config if config is not None else TradeDriverConfig()
    if world_id is None:
        return ChainRunResult(
            completed=False, hops_completed=0, steps=0, credits_delta=None,
            stop_reason="world_id_unknown", trace=(),
        )
    if turns_left is None:
        return ChainRunResult(
            completed=False, hops_completed=0, steps=0, credits_delta=None,
            stop_reason="turns_left_unknown", trace=(),
        )

    ctx = _StepCtx(session, config, should_abort, is_armed)
    graph = known_graph(world_id, state_dir=state_dir)

    start_text, start_prompt = ctx.fresh()
    start_sector = read_current_sector(start_prompt)
    if start_sector.outcome != OUTCOME_READ:
        return ChainRunResult(
            completed=False,
            hops_completed=0,
            steps=0,
            credits_delta=None,
            stop_reason="start_anchor_unknown",
            trace=(),
        )
    if not chain.sectors or start_sector.sector != chain.sectors[0]:
        return ChainRunResult(
            completed=False,
            hops_completed=0,
            steps=0,
            credits_delta=None,
            stop_reason=(
                f"start_anchor_mismatch:{start_sector.sector}:"
                f"{chain.sectors[0] if chain.sectors else 'missing'}"
            ),
            trace=(),
        )
    start_credits = _current_strict_credits(session, caps, start_text)
    turns_budget = turns_left
    hops_completed = 0
    stop_reason = "completed"

    try:
        for hop_index, hop in enumerate(chain.hops):
            if ctx.aborted():
                raise ChainHold("aborted")
            # Pre-hop turn-floor check: the WARP cost (`hop.turns`,
            # `trade_adapter`'s own path-length figure) plus a
            # conservative TWO-dock estimate (frm + to) -- the
            # authoritative post-dock reading reconciles this every hop
            # boundary regardless (`_reconcile_turns`), and `_visit_port`
            # independently re-checks it at each actual dock (A-M3) --
            # this is only the upfront "would even ATTEMPTING this hop
            # strand us" check.
            if turns_budget - (hop.turns + 2 * config.dock_turn_cost) < caps.turn_reserve:
                raise ChainHold(f"turn_floor:{hop_index}")

            bought_qty, buy_total, turns_budget = _visit_port(
                ctx, hop, "buy", 0, caps, config, turns_budget, hop_index
            )
            turns_budget = _navigate(ctx, graph, hop.frm, hop.to, turns_budget, caps, hop_index)
            _sold_qty, sell_total, turns_budget = _visit_port(
                ctx, hop, "sell", bought_qty, caps, config, turns_budget, hop_index
            )
            hops_completed += 1
            if buy_total is None or sell_total is None:
                raise ChainHold(f"realized_margin_unknown:{hop_index}")
            realized_margin = sell_total - buy_total
            if realized_margin <= 0 or realized_margin < config.min_margin_per_hop:
                ctx.trace.append(
                    f"hop{hop_index} realized-loss: bought {buy_total}cr, "
                    f"sold {sell_total}cr, margin {realized_margin:+d}cr -> chain aborted"
                )
                raise ChainHold(f"realized_margin_below_floor:{hop_index}:{realized_margin}")
            _emit_progress(on_progress, hop_index=hop_index, hops_total=len(chain.hops), steps=ctx.steps, done=False)
    except ChainHold as hold:
        stop_reason = hold.reason

    end_text = ctx.fresh()[0]
    end_credits = _current_strict_credits(session, caps, end_text)
    credits_delta = end_credits - start_credits if start_credits is not None and end_credits is not None else None

    _emit_progress(
        on_progress, hop_index=hops_completed, hops_total=len(chain.hops), steps=ctx.steps,
        done=True, stop_reason=stop_reason,
    )
    return ChainRunResult(
        completed=(stop_reason == "completed"),
        hops_completed=hops_completed,
        steps=ctx.steps,
        credits_delta=credits_delta,
        stop_reason=stop_reason,
        trace=tuple(ctx.trace),
    )
