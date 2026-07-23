"""Cold-join HUD seed — probe ship-info once when credits/turns unknown.

WO-HUD-CREDITS-TURNS-JOIN: explore screens often omit both a "You have N
credits" line and a turn count, so FA7a + parse_state leave the spectate
HUD at `-` forever unless something asks for ship info. At main_command,
`<I>` is ship-info — this module sends that one keystroke when either
sticky value is still missing after login/ensure. On a fighter
``Option?`` dialogue, ``I`` is Info (not ship-info) and must NOT be
probed — deferred so Attack/Retreat can clear first.
"""

from __future__ import annotations

from .settle import send_and_confirm

_PROBE_TIMEOUT_S = 8.0


def _observe(session, text: str) -> None:
    if hasattr(session, "observe_credits"):
        session.observe_credits(text)
    if hasattr(session, "observe_turns"):
        session.observe_turns(text)
    if hasattr(session, "observe_fighters"):
        session.observe_fighters(text)


def _snapshots(session):
    bal = ts_c = turns = ts_t = None
    if hasattr(session, "credits_snapshot"):
        bal, ts_c = session.credits_snapshot()
    if hasattr(session, "turns_snapshot"):
        turns, ts_t = session.turns_snapshot()
    return bal, turns


def seed_hud_after_join(session) -> dict:
    """Observe current screen; if credits or turns still unknown, send `I`.

    Returns a small dict for ensure/status extras: probed bool + values.
    Never raises — a failed probe must not break ensure's success path.

    Skips the I-probe while a fighter ``Option?`` dialogue is on screen:
    ``I`` is Info on that menu (not ship-info), and the probe can scroll
    the ``Your fighters: N vs. theirs: M`` line off pyte's 25-line
    viewport so ensure cannot Attack/Retreat.
    """
    try:
        text = session.render_text(session.render())
        _observe(session, text)
        bal, turns = _snapshots(session)
        if bal is not None and turns is not None:
            return {"hud_seed_probed": False, "credits": bal, "turns_left": turns}

        from .fighter_toll_policy import parse_fighter_option

        rows = text.split("\n")
        prompt = rows[-1].strip() if rows else ""
        if parse_fighter_option(text, prompt).detected:
            return {
                "hud_seed_probed": False,
                "hud_seed_deferred": "fighter_option",
                "credits": bal,
                "turns_left": turns,
            }

        # Single-key ship-info — no trailing assumptions about leaving the
        # current dialogue; settle whatever screen I produces.
        send_and_confirm(
            session, "I", enter=True, secret=False, timeout_s=_PROBE_TIMEOUT_S,
        )
        text = session.render_text(session.render())
        _observe(session, text)
        bal, turns = _snapshots(session)
        return {"hud_seed_probed": True, "credits": bal, "turns_left": turns}
    except Exception as exc:  # noqa: BLE001 — ensure success must not fail here
        return {"hud_seed_probed": False, "hud_seed_error": str(exc)}
