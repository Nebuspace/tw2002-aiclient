"""WO-FIGHTER-FLOOR-TOLL — fighter reserve + Option? dialogue policy.

Pure client-side logic (impl-tw2002-logic). No daemon I/O.

Folds / supersedes the parked **WO-FIGHTER-AUTO-R** ticket: when the
live screen is a corp-fighter toll `Option? (A,D,I,R[,P],S,?):?` dialogue
(Pay is omitted on some live tolls — regex treats ``P`` as optional),
autopilot resolves it THIS tick (Attack when clearly winnable, else
Retreat) instead of holding forever on `sector_display` and burning
unlock→R→re-arm thrash.

Safety:
- **Never auto-Pay (`P`)** — toll pay requires an explicit hub GO.
- Reserve floor applies to deploy/sell quantity clamps (keep ≥N aboard).
- Combat Attack uses whatever fighters are aboard; 0 fighters ⇒ Retreat.
- After ``A``, answer ``How many fighters… [0]?`` with a non-zero
  commit (empty Enter = 0 fighters = live ensure stick).

Defaults (configurable via callers / `EconCaps`):
- ``DEFAULT_FIGHTER_RESERVE = 5`` — small early-game floor so a lone
  toll fighter can still be Attacked after deploy/sell, without needing
  the upgrade-path's larger ``keep_min_defense_fighters`` (20).
- ``DEFAULT_AUTO_ATTACK_MAX_ENEMY = 3`` — "single or few"; above that,
  Retreat (multi / not clearly winnable).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Small reserve: enough to clear a 1-fighter toll after routine deploy
# without going to 0; deliberately below upgrade defense floor (20).
DEFAULT_FIGHTER_RESERVE = 5
# Auto-Attack only when enemy count is in this band (single/few).
DEFAULT_AUTO_ATTACK_MAX_ENEMY = 3

# Pay (P) is optional — live TWGS toll screens often show
# ``Option? (A,D,I,R,S,?):?`` without a Pay key (see hud_seed / Ona cold-start).
_OPTION_PROMPT_RE = re.compile(
    r"Option\?\s*\(\s*A\s*,\s*D\s*,\s*I\s*,\s*R\s*(?:,\s*P\s*)?\s*,\s*S\s*,\s*\?\s*\)\s*:\s*\?",
    re.IGNORECASE,
)
_FIGHTER_VS_RE = re.compile(
    r"Your\s+fighters\s*:\s*(\d+)\s+vs\.?\s*theirs\s*:\s*(\d+)",
    re.IGNORECASE,
)
# Corp toll banner when the vs-line has scrolled off pyte's viewport.
_TOLL_ENEMY_RE = re.compile(
    r"Fighters\s*:\s*(\d+)\s*\([^)]*\)\s*\[Toll\]",
    re.IGNORECASE,
)
# After Attack, TWGS asks for a commit count (default [0] — empty Enter
# spends 0 fighters and returns to Option?, which is the live Ona stick).
_ATTACK_QTY_RE = re.compile(
    r"How many fighters do you wish to use\s*\(\s*0\s+to\s+(\d+)\s*\)\s*\[(\d+)\]\s*\?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FighterOptionState:
    """Parsed live Option? toll/combat dialogue (or not-detected)."""

    detected: bool
    yours: Optional[int] = None
    theirs: Optional[int] = None


@dataclass(frozen=True)
class FighterOptionDecision:
    """What autopilot should send (or hold) for a detected Option?."""

    detected: bool
    key: Optional[str]  # "A" | "R" | None (hold / not detected)
    reason: str
    yours: Optional[int] = None
    theirs: Optional[int] = None


def parse_fighter_option(screen_text: str, prompt_line: str = "") -> FighterOptionState:
    """Detect Option? dialogue + parse `Your fighters: N vs. theirs: M`.

    Falls back to the corp ``Fighters: N (…)[Toll]`` banner for *theirs*
    when the vs-line has left the viewport (live ensure stuck on Option?
    with only the prompt still visible).

    Detection anchors to ``prompt_line`` when provided (non-empty): the
    Option? prompt must be the LIVE interactive prompt, not stale
    scrollback left over from a dialogue we already cleared.  When no
    ``prompt_line`` is given (caller-side default ``""``) the whole blob
    is searched, preserving backward-compatibility for direct callers that
    pass only ``screen_text``.  The vs-line / toll-banner search always
    uses the full blob regardless.
    """
    blob = f"{screen_text}\n{prompt_line}"
    detect_in = prompt_line if prompt_line else blob
    if not _OPTION_PROMPT_RE.search(detect_in):
        return FighterOptionState(detected=False)
    m = _FIGHTER_VS_RE.search(blob)
    if m:
        return FighterOptionState(
            detected=True,
            yours=int(m.group(1)),
            theirs=int(m.group(2)),
        )
    toll = _TOLL_ENEMY_RE.search(blob)
    if toll:
        return FighterOptionState(
            detected=True,
            yours=None,
            theirs=int(toll.group(1)),
        )
    return FighterOptionState(detected=True, yours=None, theirs=None)


def max_deployable(
    current_fighters: int,
    *,
    reserve: int = DEFAULT_FIGHTER_RESERVE,
) -> int:
    """How many fighters may be sold/deployed while keeping ≥ ``reserve``."""
    if current_fighters < 0:
        current_fighters = 0
    if reserve < 0:
        reserve = 0
    return max(0, current_fighters - reserve)


def clamp_deploy_or_sell_qty(
    wanted: int,
    current_fighters: int,
    *,
    reserve: int = DEFAULT_FIGHTER_RESERVE,
) -> int:
    """Clamp a deploy/sell quantity so aboard fighters never drop below reserve."""
    if wanted < 0:
        wanted = 0
    return min(wanted, max_deployable(current_fighters, reserve=reserve))


def decide_fighter_option(
    state: FighterOptionState,
    *,
    reserve: int = DEFAULT_FIGHTER_RESERVE,
    max_enemy: int = DEFAULT_AUTO_ATTACK_MAX_ENEMY,
    allow_pay: bool = False,
) -> FighterOptionDecision:
    """Pick Attack / Retreat / hold for a parsed Option? state.

    ``allow_pay`` is always False in production (hub GO required for ``P``);
    accepted only so tests can prove Pay is never selected by default.
    ``reserve`` documents the deploy floor; Attack itself requires
    ``yours >= 1`` and a clearly winnable enemy count (not ``yours > reserve``),
    so a ship that dipped to 3 can still clear a lone toll.
    """
    del allow_pay  # Pay is never auto-selected; parameter documents the hard ban.
    if not state.detected:
        return FighterOptionDecision(
            detected=False, key=None, reason="not_fighter_option"
        )
    if state.yours is None or state.theirs is None:
        # Holding forever wedges ensure/autopilot on live Option? when the
        # vs-line scrolled off. Cannot prove Attack → Retreat (never Pay).
        return FighterOptionDecision(
            detected=True,
            key="R",
            reason="unparsed_retreat_safe",
            yours=state.yours,
            theirs=state.theirs,
        )
    yours, theirs = state.yours, state.theirs
    if theirs < 0 or yours < 0:
        return FighterOptionDecision(
            detected=True,
            key=None,
            reason="invalid_fighter_counts",
            yours=yours,
            theirs=theirs,
        )

    # Clearly winnable: few enemies + we have at least as many fighters.
    if theirs <= max_enemy and yours >= max(theirs, 1):
        return FighterOptionDecision(
            detected=True,
            key="A",
            reason=(
                f"attack_winnable:yours={yours}:theirs={theirs}"
                f":reserve={reserve}:max_enemy={max_enemy}"
            ),
            yours=yours,
            theirs=theirs,
        )

    # Hopeless (0 fighters) or multi / not clearly winnable → Retreat.
    # This is the folded WO-FIGHTER-AUTO-R path (never Pay).
    return FighterOptionDecision(
        detected=True,
        key="R",
        reason=(
            f"retreat:yours={yours}:theirs={theirs}"
            f":reserve={reserve}:max_enemy={max_enemy}"
        ),
        yours=yours,
        theirs=theirs,
    )


def decide_from_screen(
    screen_text: str,
    prompt_line: str = "",
    *,
    reserve: int = DEFAULT_FIGHTER_RESERVE,
    max_enemy: int = DEFAULT_AUTO_ATTACK_MAX_ENEMY,
) -> FighterOptionDecision:
    """Parse + decide in one call (autopilot convenience)."""
    return decide_fighter_option(
        parse_fighter_option(screen_text, prompt_line),
        reserve=reserve,
        max_enemy=max_enemy,
    )


def parse_attack_qty_prompt(
    screen_text: str, prompt_line: str = ""
) -> Optional[tuple[int, int]]:
    """Return ``(max_avail, default)`` for the Attack quantity sub-prompt.

    Anchors detection to ``prompt_line`` when provided (same rationale as
    ``parse_fighter_option``): the qty prompt must be the LIVE interactive
    prompt, not scrollback from an already-answered Attack round.
    """
    blob = f"{screen_text}\n{prompt_line}"
    detect_in = prompt_line if prompt_line else blob
    m = _ATTACK_QTY_RE.search(detect_in)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def attack_fighters_to_commit(
    *,
    yours: Optional[int],
    theirs: Optional[int],
    max_avail: int,
) -> int:
    """Fighters to commit on the qty prompt. Never returns 0 when max≥1."""
    if max_avail < 1:
        return 0
    if theirs is not None and theirs >= 1:
        return min(max(theirs, 1), max_avail)
    if yours is not None and yours >= 1:
        return min(yours, max_avail)
    return max_avail


def _vs_counts(screen_text: str, prompt_line: str = "") -> tuple[Optional[int], Optional[int]]:
    """Parse yours/theirs from the vs-line or Toll banner (no Option? required)."""
    blob = f"{screen_text}\n{prompt_line}"
    m = _FIGHTER_VS_RE.search(blob)
    if m:
        return int(m.group(1)), int(m.group(2))
    toll = _TOLL_ENEMY_RE.search(blob)
    if toll:
        return None, int(toll.group(1))
    return None, None


def next_fighter_option_input(
    screen_text: str,
    prompt_line: str = "",
    *,
    reserve: int = DEFAULT_FIGHTER_RESERVE,
    max_enemy: int = DEFAULT_AUTO_ATTACK_MAX_ENEMY,
) -> FighterOptionDecision:
    """Prefer Attack qty sub-prompt over Option? when both are on screen.

    Live Ona stick: ``A`` was sent, qty prompt appeared with default
    ``[0]``, settle treated idle as done, and the next tick re-fired
    ``A`` forever. Answering the qty prompt clears the fight.

    Qty screens often omit the ``Option?`` line — still read the vs-line
    so we commit ``theirs`` (not max_avail) when visible.
    """
    qty = parse_attack_qty_prompt(screen_text, prompt_line)
    if qty is not None:
        max_avail, _default = qty
        yours, theirs = _vs_counts(screen_text, prompt_line)
        n = attack_fighters_to_commit(
            yours=yours, theirs=theirs, max_avail=max_avail
        )
        if n < 1:
            return FighterOptionDecision(
                detected=True,
                key=None,
                reason="attack_qty_unavailable",
                yours=yours,
                theirs=theirs,
            )
        return FighterOptionDecision(
            detected=True,
            key=str(n),
            reason=f"attack_qty:{n}:max={max_avail}",
            yours=yours,
            theirs=theirs,
        )
    return decide_from_screen(
        screen_text,
        prompt_line,
        reserve=reserve,
        max_enemy=max_enemy,
    )
