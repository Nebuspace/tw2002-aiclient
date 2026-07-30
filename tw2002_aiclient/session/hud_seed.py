"""Cold-join HUD seed via one safe, bounded ship-info probe.

The probe is deliberately narrow: only a positively classified
``main_command`` screen may send ``I``. Every other screen defers, including
fighter ``Option?`` dialogues where ``I`` has dialogue-local meaning.
Confirmation looks for the ship-info ``Credits :`` line (always present),
not ``Turns left``, so unlimited-turn variants that omit turns still seed.
Seed completeness is credits + empty cargo holds; turns stay sticky when
stated and honestly absent otherwise. Failures are diagnostic return values
and never break a successful ensure.
"""

from __future__ import annotations

from .settle import send_and_confirm
from .state_parser import OUTCOME_READ

_PROBE_TIMEOUT_S = 8.0
_STALE_S = 20.0
# Confirm the ship-info screen itself, not a turns line. Unlimited-turn
# variants omit ``Turns left`` while still printing Credits / holds.
_SHIP_INFO_CONFIRM = r"(?im)^[ \t]*Credits[ \t]*:[ \t]*\d"


def _render(session) -> tuple[str, str]:
    rows = session.render()
    text = session.render_text(rows)
    prompt = rows[-1].strip() if rows else ""
    return text, prompt


def _observe(session, text: str, prompt: str) -> None:
    session.observe_credits(text)
    session.observe_turns(text, prompt)
    session.observe_cargo(text)
    session.observe_sector(prompt)


def _values(session) -> tuple[object, object, object]:
    return (
        session.credits_snapshot(),
        session.turns_snapshot(),
        session.cargo_snapshot(),
    )


def _seed_complete(credits, cargo) -> bool:
    """Credits + empty holds are enough; turns may be honestly absent."""
    return credits.outcome == OUTCOME_READ and cargo.outcome == OUTCOME_READ


def seed_hud_after_join(session, *, force: bool = False) -> dict:
    """Observe once, then issue at most one ``I`` if a tracked seed is absent."""
    required = (
        "render",
        "render_text",
        "classify",
        "send",
        "observe_credits",
        "credits_snapshot",
        "observe_turns",
        "turns_snapshot",
        "observe_cargo",
        "cargo_snapshot",
        "observe_sector",
    )
    if not all(callable(getattr(session, name, None)) for name in required):
        return {"hud_seed_probed": False, "hud_seed_reason": "unsupported_session"}

    try:
        text, prompt = _render(session)
        _observe(session, text, prompt)
        credits, turns, cargo = _values(session)
        complete = _seed_complete(credits, cargo)
        stale = any(
            snapshot.outcome == OUTCOME_READ
            and snapshot.age_s is not None
            and snapshot.age_s >= _STALE_S
            for snapshot in (credits, turns, cargo)
        )
        if complete and not (force and stale):
            return {"hud_seed_probed": False, "hud_seed_reason": "already_seeded"}

        if session.classify() != "main_command":
            return {"hud_seed_probed": False, "hud_seed_reason": "unsafe_screen"}

        _reason, _elapsed, confirmed = send_and_confirm(
            session,
            "I",
            confirm_prompt=_SHIP_INFO_CONFIRM,
            enter=True,
            secret=False,
            timeout_s=_PROBE_TIMEOUT_S,
        )
        if not confirmed:
            return {"hud_seed_probed": True, "hud_seed_reason": "probe_unconfirmed"}

        text, prompt = _render(session)
        _observe(session, text, prompt)
        credits, turns, cargo = _values(session)
        if not _seed_complete(credits, cargo):
            return {
                "hud_seed_probed": True,
                "hud_seed_reason": "probe_incomplete",
                "credits": credits.balance if credits.outcome == OUTCOME_READ else None,
                "turns_left": turns.turns if turns.outcome == OUTCOME_READ else None,
                "cargo": cargo.cargo if cargo.outcome == OUTCOME_READ else None,
            }
        return {
            "hud_seed_probed": True,
            "hud_seed_reason": "seeded",
            "credits": credits.balance,
            "turns_left": turns.turns if turns.outcome == OUTCOME_READ else None,
            "cargo": cargo.cargo,
        }
    except Exception as exc:  # noqa: BLE001 — ensure success must survive seed failure
        return {
            "hud_seed_probed": False,
            "hud_seed_reason": "probe_error",
            "hud_seed_error": type(exc).__name__,
        }
