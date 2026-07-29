"""NPC fighter-toll encounter policy — classify, decide, and answer safely.

Canon contract: ``canon/strategy/toll-and-defense.md``.  The decision gates
below are that page's, not this module's invention:

* **§ Schema — the decision parameters** defines ``force_share_auto_attack``
  (≥ 0.90), ``winnable_enemy_band`` (≤ 3 enemies) and the reserve floors.
* **§ Toll-dialogue guard behavior (I5)** fixes the branch order: 0 fighters ⇒
  Retreat; never Pay; counts unreadable ⇒ Retreat at ``Option?``; autonomous
  Attack only when *all* of {both counts present, enemy ≤ band, force_share ≥
  threshold, target is NPC}.
* **§ NPC / PvP boundary (hard)** — a real player on either side means this
  page does not apply and the client STOPS.

Two properties are load-bearing and each has a falsification pin in
``tests/test_fighter_toll_policy.py``:

1. **``force_share`` is a force *share*, not a win probability.**  Canon names
   it that deliberately.  ``0.80`` does not mean "I accept a 20% chance of
   losing" — there is no combat model here, and inventing one is out of scope.
   The name exists so a future reader cannot talk themselves into lowering the
   threshold on a risk budget the number does not represent.
2. **Missing is not zero.**  A count that failed to parse must never reach the
   arithmetic.  ``own / (own + enemy)`` with ``enemy = 0`` returns ``1.0`` —
   maximum confidence — so treating an absent count as zero would make the app
   *most* willing to fight when it knows *least*.  Both counts are proven
   present before any comparison runs.

The quantity prompt is part of the same encounter, not a second classifier.
The archived implementation answered it with ``max_avail`` when counts were
unreadable — committing the entire complement on the least information, at the
one step that cannot be taken back.  Canon now forbids that explicitly, and so
does :func:`decide_quantity`.  Retreat is *not* available there (``A`` has
already been sent), and a bare unanswered STOP is also unsafe: an idle prompt
defaulting to ``[0]`` was observed re-firing Attack forever.  So the STOP
returned here **owns the prompt** — see :class:`EncounterDecision.halt`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# --- canon-cited parameters ------------------------------------------------
# Names mirror `canon/strategy/toll-and-defense.md` § Schema. They are server
# semantics per canon ("not fixed numbers, and belong in configuration"), so
# every entry point takes them as keyword arguments; these are defaults only.

#: canon `reserve_floor` — deploy/sell clamp, not a combat trigger.
DEFAULT_FIGHTER_RESERVE = 5
#: canon schema `winnable_enemy_band` — "single or few"; above this a fight is never
#: *clearly* winnable regardless of ratio, so the ratio gate alone is not enough.
DEFAULT_AUTO_ATTACK_MAX_ENEMY = 3
#: canon `force_share_auto_attack` — Max-ratified 2026-07-28.
DEFAULT_FORCE_SHARE_AUTO_ATTACK = 0.90

# Pay (`P`) is optional on live toll screens, so the prompt is matched with and
# without it. Pay is never auto-selected regardless (canon: "Never Pay").
_OPTION_PROMPT_RE = re.compile(
    r"Option\?\s*\(\s*A\s*,\s*D\s*,\s*I\s*,\s*R\s*(?:,\s*P\s*)?\s*,\s*S\s*,\s*\?\s*\)\s*:\s*\?",
    re.IGNORECASE,
)
_FIGHTER_VS_RE = re.compile(
    r"Your\s+fighters\s*:\s*(\d+)\s+vs\.?\s*theirs\s*:\s*(\d+)",
    re.IGNORECASE,
)
# Corp toll banner, used when the vs-line has scrolled out of the viewport. It
# carries only the enemy side, which is why `yours` stays None on this path.
_TOLL_ENEMY_RE = re.compile(
    r"Fighters\s*:\s*(\d+)\s*\([^)]*\)\s*\[Toll\]",
    re.IGNORECASE,
)
_ATTACK_QTY_RE = re.compile(
    r"How many fighters do you wish to use\s*\(\s*0\s+to\s+(\d+)\s*\)\s*\[(\d+)\]\s*\?",
    re.IGNORECASE,
)
# A player name on a combat frame moves it across canon's hard PvP boundary.
# Detection is deliberately broad: a false PvP positive costs a STOP (safe),
# a false negative runs NPC math against a person (forbidden).
_PVP_MARKER_RE = re.compile(
    r"\b(?:commander|captain|player)\s+\w+\s+(?:is|has)\b|attacked\s+by\s+player\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EncounterState:
    """A parsed ``Option?`` toll frame — or a frame that is not one."""

    detected: bool
    yours: Optional[int] = None
    theirs: Optional[int] = None
    is_pvp: bool = False

    @property
    def counts_present(self) -> bool:
        """Both counts parsed. Distinct from "both counts are zero"."""
        return self.yours is not None and self.theirs is not None


@dataclass(frozen=True)
class EncounterDecision:
    """What the deterministic guard may send, and whether it must halt.

    ``key`` is the keystroke to send, or ``None`` when nothing may be sent.
    ``halt`` marks a STOP that **owns the prompt**: the caller must escalate
    and must not re-enter the encounter flow, which is what stops an idle
    quantity prompt from re-firing Attack in a loop.
    """

    detected: bool
    key: Optional[str]
    reason: str
    yours: Optional[int] = None
    theirs: Optional[int] = None
    halt: bool = False


def force_share(own: int, enemy: int) -> float:
    """``own / (own + enemy)`` — a share of present forces, not a win chance.

    Raises on an empty engagement rather than returning a number: with both
    sides at zero there is no share to speak of, and every fallback value here
    would be a lie in one direction or the other.
    """
    total = own + enemy
    if total <= 0:
        raise ValueError("force_share undefined with no fighters on either side")
    return own / total


def parse_encounter(screen_text: str, prompt_line: str = "") -> EncounterState:
    """Detect the ``Option?`` frame and read whatever counts are on it."""
    blob = f"{screen_text}\n{prompt_line}"
    if not _OPTION_PROMPT_RE.search(blob):
        return EncounterState(detected=False)
    is_pvp = bool(_PVP_MARKER_RE.search(blob))
    m = _FIGHTER_VS_RE.search(blob)
    if m:
        return EncounterState(True, int(m.group(1)), int(m.group(2)), is_pvp)
    toll = _TOLL_ENEMY_RE.search(blob)
    if toll:
        # Enemy side only; `yours` stays None so `counts_present` is False and
        # the caller takes the Retreat exit rather than guessing our own side.
        return EncounterState(True, None, int(toll.group(1)), is_pvp)
    return EncounterState(True, None, None, is_pvp)


def decide_encounter(
    state: EncounterState,
    *,
    force_share_auto_attack: Optional[float] = DEFAULT_FORCE_SHARE_AUTO_ATTACK,
    winnable_enemy_band: int = DEFAULT_AUTO_ATTACK_MAX_ENEMY,
    reserve: int = DEFAULT_FIGHTER_RESERVE,
    allow_pay: bool = False,
) -> EncounterDecision:
    """Attack / Retreat / STOP for a parsed ``Option?`` frame.

    ``allow_pay`` exists so a test can prove Pay is never chosen; it does not
    change behaviour. ``force_share_auto_attack=None`` means the threshold is
    unratified — the guard then never attacks (fail closed).
    """
    del allow_pay, reserve  # documented, never behavioural — see canon § I5.

    if not state.detected:
        return EncounterDecision(False, None, "not_encounter")

    # PvP is decided before any math: canon's boundary is that the math does
    # not run to a decision at all, not that it runs and is then discarded.
    if state.is_pvp:
        return EncounterDecision(
            True, None, "pvp_hard_stop", state.yours, state.theirs, halt=True
        )

    if not state.counts_present:
        # Canon's safe exit at `Option?`: never a blind engage, never Pay.
        return EncounterDecision(
            True, "R", "unparsed_counts_retreat", state.yours, state.theirs
        )

    yours, theirs = state.yours, state.theirs
    assert yours is not None and theirs is not None  # counts_present
    if yours < 0 or theirs < 0:
        return EncounterDecision(
            True, None, "invalid_counts_stop", yours, theirs, halt=True
        )
    if yours == 0:
        return EncounterDecision(True, "R", "no_fighters_retreat", yours, theirs)
    if theirs == 0:
        # A present zero: there is nothing to engage, so take the non-engaging
        # exit rather than sending Attack at an empty band.
        return EncounterDecision(True, "R", "no_enemy_retreat", yours, theirs)
    if force_share_auto_attack is None:
        return EncounterDecision(
            True, "R", "threshold_unset_retreat", yours, theirs
        )
    if theirs > winnable_enemy_band:
        return EncounterDecision(
            True,
            "R",
            f"enemy_band_exceeded:theirs={theirs}:band={winnable_enemy_band}",
            yours,
            theirs,
        )
    share = force_share(yours, theirs)
    if share < force_share_auto_attack:
        return EncounterDecision(
            True,
            "R",
            f"force_share_below_gate:share={share:.4f}:gate={force_share_auto_attack}",
            yours,
            theirs,
        )
    return EncounterDecision(
        True,
        "A",
        f"attack_npc:share={share:.4f}:gate={force_share_auto_attack}"
        f":theirs={theirs}:band={winnable_enemy_band}",
        yours,
        theirs,
    )


def parse_quantity_prompt(
    screen_text: str, prompt_line: str = ""
) -> Optional[tuple[int, int]]:
    """``(max_available, prompt_default)`` for the post-Attack quantity ask."""
    m = _ATTACK_QTY_RE.search(f"{screen_text}\n{prompt_line}")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def decide_quantity(
    screen_text: str,
    prompt_line: str = "",
    *,
    winnable_enemy_band: int = DEFAULT_AUTO_ATTACK_MAX_ENEMY,
) -> EncounterDecision:
    """Answer ``How many fighters…`` — or halt, but never spend everything.

    The archived implementation returned ``max_avail`` when neither count could
    be read. That is the single most dangerous branch in this flow and canon
    now forbids it by name, so the unreadable path here returns a halting STOP
    instead. See the module docstring.
    """
    qty = parse_quantity_prompt(screen_text, prompt_line)
    if qty is None:
        return EncounterDecision(False, None, "not_quantity_prompt")
    max_avail, _default = qty
    blob = f"{screen_text}\n{prompt_line}"
    if _PVP_MARKER_RE.search(blob):
        return EncounterDecision(True, None, "pvp_hard_stop", halt=True)

    m = _FIGHTER_VS_RE.search(blob)
    if m is None:
        # Counts unreadable on *this* frame — qty screens routinely omit the
        # `Option?` line, so presence at the previous step proves nothing here.
        return EncounterDecision(
            True, None, "qty_counts_unreadable_stop", halt=True
        )
    yours, theirs = int(m.group(1)), int(m.group(2))
    if max_avail < 1 or theirs < 1:
        return EncounterDecision(
            True, None, "qty_unavailable_stop", yours, theirs, halt=True
        )
    if theirs > winnable_enemy_band:
        return EncounterDecision(
            True, None, "qty_band_exceeded_stop", yours, theirs, halt=True
        )
    commit = min(max(theirs, 1), max_avail)
    return EncounterDecision(
        True, str(commit), f"qty_commit:{commit}:max={max_avail}", yours, theirs
    )


def next_encounter_input(
    screen_text: str,
    prompt_line: str = "",
    *,
    force_share_auto_attack: Optional[float] = DEFAULT_FORCE_SHARE_AUTO_ATTACK,
    winnable_enemy_band: int = DEFAULT_AUTO_ATTACK_MAX_ENEMY,
) -> EncounterDecision:
    """One flow for the whole encounter, quantity prompt first.

    The quantity ask is checked ahead of ``Option?`` because both can be on
    screen at once; answering the older ``Option?`` in that state is what
    re-sends Attack against a live quantity prompt.
    """
    qty = decide_quantity(
        screen_text, prompt_line, winnable_enemy_band=winnable_enemy_band
    )
    if qty.detected:
        return qty
    return decide_encounter(
        parse_encounter(screen_text, prompt_line),
        force_share_auto_attack=force_share_auto_attack,
        winnable_enemy_band=winnable_enemy_band,
    )
