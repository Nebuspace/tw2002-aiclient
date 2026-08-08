"""Coaching engine — canon I2/I3 (`canon/engine/coaching-engine.md`).

Two pure functions:

* ``infer_coach_triggers`` (canon I2) — live game-state → the set of applicable
  strategy-card trigger ids. **Fail-closed**: an input it cannot read simply
  omits that trigger; it never guesses one (canon's rule that an unrecognised
  situation produces *no* advice rather than plausible advice).
* ``compose_decisions_coach`` (canon I3) — triggered cards → human-facing
  callout lines. Renders **only** text authored in ``data/coach/strategies.json``
  and never a keystroke or an armed behavior. No prose originates here; that is
  canon's "no competing source of card text" rule, and it is why this module
  has no string constants beyond the honest empty state.

Ported at the rebirth from pre-rebirth ``twclient/spectate_layout.py`` (deleted
by the ``452d896`` scaffold) per ``WO-COACH-ENGINE-PORT``. Only the coaching
kernel came across -- the surrounding spectate layout did not.
"""

from __future__ import annotations

from typing import Sequence

from tw2002_aiclient.chain_units import chain_hop_count_and_unit

__all__ = [
    "infer_coach_triggers",
    "compose_decisions_coach",
    "compose_decisions_placeholder",
]

# A chain is only worth coaching about once it is an actual loop rather than a
# single leg.
_MIN_CHAIN_HOPS = 2


def infer_coach_triggers(
    *,
    classification: str | None = None,
    prompt: str | None = None,
    fighters_aboard: int | None = None,
    chain=None,
    genesis_count: int = 0,
    dead_end_count: int = 0,
    explore_mode: str | None = None,
    has_port: bool = False,
    loop_depleting: object = False,
) -> list[str]:
    """Map live context to ``StrategyCard.when_trigger`` ids.

    Pure and fail-closed: unknown inputs omit that trigger rather than guessing
    one. Returns unique ids in a stable priority order for
    ``compose_decisions_coach``.

    ``loop_depleting`` is identity-true only (``is True``): a truthy string /
    ``1`` / ``"yes"`` must not fire the card (WO-COACH-LOOP-DEPLETING-TRIGGER).
    """
    found: list[str] = []

    def _add(trigger: str) -> None:
        if trigger not in found:
            found.append(trigger)

    cls = (classification or "").strip()
    prompt_l = (prompt or "").lower()

    if has_port or cls in ("port_trade", "cim_report"):
        _add("docked_at_port")
    # 0 fighters -> holds-first card (when_trigger=at_shipyard); also when the
    # live prompt already looks like a shipyard/StarDock surface.
    if fighters_aboard is not None and int(fighters_aboard) == 0:
        _add("at_shipyard")
    if "stardock" in prompt_l or "shipyard" in prompt_l:
        _add("at_shipyard")
    hop_n, _unit = chain_hop_count_and_unit(chain)
    if hop_n is not None and hop_n >= _MIN_CHAIN_HOPS:
        _add("chain_opportunity")
    # After chain_opportunity: same loop family, depletion advice when the
    # armed loop has already halted for floor / turn budget.
    if loop_depleting is True:
        _add("loop_depleting")
    if int(genesis_count or 0) > 0 or int(dead_end_count or 0) > 0:
        _add("at_dead_end")
    if explore_mode and explore_mode != "off":
        _add("exploring_frontier")
    if "option?" in prompt_l or "fighters to use" in prompt_l:
        _add("toll_or_gate")
    # Status-verb path withholds the live prompt (credential safety), so the
    # Option? substring never reaches this consumer. Classification is the
    # closed substitute that still fires the toll card (WO-WIRE-REROUTE-EV).
    if cls == "fighter_encounter":
        _add("toll_or_gate")
    return found


def compose_decisions_placeholder() -> list[str]:
    """Honest empty state for the DECISIONS pane — no live trace, no triggers."""
    return [
        "—",
        "Exploring…",
    ]


def compose_decisions_coach(
    kb,
    triggers: Sequence[str] | None,
    *,
    width: int = 22,
    max_cards: int = 3,
) -> list[str]:
    """Render coaching callouts for the active triggers.

    ``kb`` is a ``coach_kb.CoachKB`` (or ``None``). Cards carrying
    ``hypothesis_flags`` are suffixed ``(unverified)`` so an unproven number is
    never presented as fact. Card text is never rewritten or invented; an empty
    or non-matching trigger set yields the honest placeholder.
    """
    width = max(8, int(width))
    if kb is None or not triggers:
        return compose_decisions_placeholder()

    cards = []
    seen_ids: set[str] = set()
    for trigger in triggers:
        for card in kb.by_trigger(trigger):
            if card.id in seen_ids:
                continue
            seen_ids.add(card.id)
            cards.append(card)
    if not cards:
        return compose_decisions_placeholder()

    cards.sort(key=lambda c: (c.priority, c.id))
    lines: list[str] = []
    for card in cards[: max(1, int(max_cards))]:
        title = card.title.strip() or card.id
        if card.hypothesis_flags:
            title = f"{title} (unverified)"
        lines.append(title[:width])
        what = (card.what or "").strip()
        if what:
            # Indent body; wrap by hard clip to panel width.
            body = f" {what}"
            lines.append(body[:width])
        if card.steps:
            step0 = str(card.steps[0]).strip()
            if step0:
                lines.append(f" → {step0}"[:width])
    return lines or compose_decisions_placeholder()
