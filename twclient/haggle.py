"""Deterministic auto-haggle -- NO LLM (DESIGN-v2.md §9, C8-lite).

Negotiates the port OFFER sub-dialogue only: the caller has already
navigated quantity/commodity selection (that's the trade-path's job, not
this module's) and is sitting at an active
"We'll buy/sell them for N credits.\\nYour offer [N] ?" prompt.
`run_haggle()` opens with an aggressive-but-plausible counter off the
port's own baseline, concedes toward the port's counter-offer each
round, accepts once the port's price is close enough to fair value (or
the round cap is hit), and safely falls back to the blank-input
accept-default on any desync -- it never guesses or presses on past a
screen it can't positively identify. Every send here goes through
`settle.send_and_confirm` (the DESIGN-v2 §8 send/settle-race fix): a
round only advances on a POSITIVE match of the next expected screen,
never a bare idle timeout.

**Ground truth (2026-07-19 live captures against a real TWGS server,
tests/test_haggle.py reproduces these verbatim):** every observed real
deal converged within 2 rounds no matter how aggressive the opening
counter was -- a port barely concedes off its own stated price:
  - buy (port buys from us, we want a HIGHER price): baseline 2,214 ->
    our ask 2,450 -> port's re-quote 2,216 (a 2cr move) -> accepted.
  - sell (port sells to us, we want a LOWER price): baseline 758 -> our
    ask 700 -> port's re-quote 753 (a 5cr move) -> accepted.
Acceptance phrasing is NOT uniform -- "Done, we'll take the lot.",
"Cheapskate.  Here, take them and leave me alone.", "You insult my
intelligence, but we'll buy them anyway.", "You will put me out of
business, I'll take your offer." were all seen live for the SAME
underlying event (deal closed) -- so resolution is detected
structurally (state_parser.parse_haggle's `current_default` going
absent from the CURRENT prompt line), never by matching a phrase list.
ROUND_CAP is generous headroom for a more stubborn port, not the
expected common case.
"""

from .settle import send_and_confirm
from .state_parser import parse_haggle

_DEFAULT_ROUND_CAP = 4
_DEFAULT_ACCEPT_THRESHOLD_PCT = 5.0
_DEFAULT_OPEN_AGGRESSION_PCT = 15.0
_DEFAULT_STEP_TIMEOUT_S = 8.0

# The settle-gate for every send in this module (DESIGN-v2 §8 fix): a
# round either continues (another "Your offer [...]?" prompt) or
# resolves. A resolved dialogue's next screen isn't uniform -- back to
# the main command prompt, or straight into the NEXT commodity's
# quantity prompt at the same port (both seen live in one capture) -- so
# both are named here. Extend this as live play reveals more shapes
# (same "extend as reality reveals more screens" convention as
# state_parser.py/classify.py).
_CONFIRM_RE = r"Your\s+offer\s*\[|Command\s*\[\s*TL\s*=|[Hh]ow\s+many\s+holds"


class HaggleOutcome:
    ACCEPTED = "accepted"
    ROUND_CAP_FALLBACK = "round_cap_fallback"
    DESYNC_FALLBACK = "desync_fallback"
    NO_ACTIVE_HAGGLE = "no_active_haggle"


def _favorable_sign(direction):
    """"sell" (port sells to us, we're buying) -> our counter is BELOW
    the reference; "buy" (port buys from us, we're selling) -> our
    counter is ABOVE it. Unrecognized/missing direction (shouldn't
    happen once current_default is confirmed present, since both are
    extracted from the same dialogue) defaults to the conservative
    "buy" sign rather than raising."""
    return -1 if direction == "sell" else 1


def _within_threshold(value, reference, threshold_pct):
    if not reference:
        return True
    return abs(value - reference) <= reference * (threshold_pct / 100.0)


def _round_credits(value):
    return int(round(value))


def _result(outcome, rounds, final_price, direction, fair_value):
    return {
        "resolved": outcome == HaggleOutcome.ACCEPTED,
        "outcome": outcome,
        "rounds": rounds,
        "final_price": final_price,
        "direction": direction,
        "fair_value": fair_value,
    }


def _accept_current_default(session, step_timeout):
    """The blank-input-accepts-default trick (DESIGN-v2 §8's own
    live-drive finding, reused deliberately) -- send nothing rather than
    re-typing the number already showing. Returns `confirmed`."""
    _reason, _elapsed, confirmed = send_and_confirm(
        session, "", _CONFIRM_RE, enter=True, timeout_s=step_timeout
    )
    return confirmed


def run_haggle(
    session,
    fair_value=None,
    accept_threshold_pct=_DEFAULT_ACCEPT_THRESHOLD_PCT,
    open_aggression_pct=_DEFAULT_OPEN_AGGRESSION_PCT,
    round_cap=_DEFAULT_ROUND_CAP,
    step_timeout=_DEFAULT_STEP_TIMEOUT_S,
):
    """Run the negotiation to completion against `session` (must already
    be sitting at an active offer prompt). Returns
    `{resolved, outcome, rounds, final_price, direction, fair_value}`.
    Never raises on a desync -- falls back to accepting whatever's
    currently on offer and reports `outcome=desync_fallback` instead."""
    text = session.render_text(session.render())
    haggle = parse_haggle(text)
    if "current_default" not in haggle:
        return _result(HaggleOutcome.NO_ACTIVE_HAGGLE, 0, None, haggle.get("direction"), fair_value)

    direction = haggle.get("direction")
    reference = fair_value if fair_value is not None else haggle.get("baseline", haggle["current_default"])
    sign = _favorable_sign(direction)
    our_ask = _round_credits(reference + sign * reference * (open_aggression_pct / 100.0))

    for round_i in range(1, round_cap + 1):
        _reason, _elapsed, confirmed = send_and_confirm(
            session, str(our_ask), _CONFIRM_RE, enter=True, timeout_s=step_timeout
        )
        if not confirmed:
            _accept_current_default(session, step_timeout)
            return _result(HaggleOutcome.DESYNC_FALLBACK, round_i, None, direction, reference)

        text = session.render_text(session.render())
        haggle = parse_haggle(text)
        if "current_default" not in haggle:
            # The offer prompt is gone -- the port took our ask as-is
            # (no counter-quote round), deal closed at what we sent.
            return _result(HaggleOutcome.ACCEPTED, round_i, our_ask, direction, reference)

        current = haggle["current_default"]
        if _within_threshold(current, reference, accept_threshold_pct):
            if not _accept_current_default(session, step_timeout):
                return _result(HaggleOutcome.DESYNC_FALLBACK, round_i, None, direction, reference)
            return _result(HaggleOutcome.ACCEPTED, round_i, current, direction, reference)

        # Concede a step toward the midpoint of our own ask and the
        # port's counter, and go another round.
        our_ask = _round_credits((our_ask + current) / 2.0)

    # Round cap hit without converging within threshold -- the safe
    # fallback per DESIGN-v2 §9: accept the current default rather than
    # loop further (a real port CAN simply refuse to move, live-confirmed).
    if not _accept_current_default(session, step_timeout):
        return _result(HaggleOutcome.DESYNC_FALLBACK, round_cap, None, direction, reference)
    return _result(HaggleOutcome.ROUND_CAP_FALLBACK, round_cap, haggle.get("current_default"), direction, reference)
