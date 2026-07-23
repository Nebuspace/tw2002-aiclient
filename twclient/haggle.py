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
underlying event (deal closed).

**Money-path hardening (TW-01, 2026-07-19) -- three real live-loss
defects fixed:**
  1. The settle-layer confirm regex (below) necessarily matches a bare
     "Command [TL=" ANYWHERE in the (possibly stale) cropped screen --
     `send_and_confirm`/`wait_for_settle` do a plain whole-string
     `re.search`, with no concept of "current line only". A screen can
     hold a Command[TL=...] left over from BEFORE the haggle dialogue
     was ever entered (the exact stale-scrollback trap
     state_parser.py's own module docstring warns about for
     credits/sector) while the TRUE current/bottom line is still
     something else entirely unresolved -- a "misfire" that used to be
     misread as a legitimate confirmation.
  2. `run_haggle` used to treat "the offer prompt is gone" alone as
     proof of "ACCEPTED at whatever we last sent", with zero trade
     evidence -- a bare main-command prompt (or a stray bit of leftover
     input) reaching that same "prompt is gone" state was
     indistinguishable from a genuine deal closing.
  3. The opening read (before round 1's ask is even computed) had no
     freshness gate at all -- a caller invoking `run_haggle()` a moment
     before the screen truly settled could have its very first
     counter-offer computed off a stale/transitional render.

Fixed via `_resolution_evidence()` (anchors the settle-confirmed shape
to the CURRENT line only, the same "gate anchor" convention
`state_parser.parse_haggle`'s own `current_default` check uses) plus an
optional, honestly-computed credits-delta cross-check
(`state_parser.credits_balance`), and a `settle.wait_until_settled()`
pre-send freshness gate. `resolved`/`final_price` are NEVER reported
without one of these two independent positive signals -- anything else
(a bare confirm-shape match with no evidence behind it) is
`DESYNC_FALLBACK`, `resolved=False`, `final_price=None`. ROUND_CAP is
generous headroom for a more stubborn port, not the expected common
case.
"""

import re

from .settle import send_and_confirm, wait_until_settled
from .state_parser import credits_balance, last_nonblank_line, parse_haggle

_DEFAULT_ROUND_CAP = 4
_DEFAULT_ACCEPT_THRESHOLD_PCT = 5.0
_DEFAULT_OPEN_AGGRESSION_PCT = 15.0
_DEFAULT_STEP_TIMEOUT_S = 8.0
_DEFAULT_FRESH_RENDER_DEBOUNCE_MS = 350
_DEFAULT_FRESH_RENDER_TIMEOUT_S = 2.0

# Round-continuation shape: a fresh "Your offer [...]?" prompt means the
# port countered and the dialogue is still live.
_CONTINUE_RE = r"Your\s+offer\s*\["

# Shapes the dialogue can land on once it's DONE (accepted outright, or
# straight into the next commodity's quantity prompt at the same port --
# both seen live in one capture). `send_and_confirm` is handed the
# UNION of both (`_CONFIRM_RE` below) so it doesn't spuriously time out
# on a legitimately-resolved screen -- but matching this union only
# proves the SETTLE layer recognizes the shape *somewhere* on screen,
# never by itself proof the CURRENT line is what it thinks (see
# `_resolution_evidence()`, which closes that gap). Real capitalization
# from live screens -- settle.py's wait_prompt regexes match
# case-sensitively (no re.IGNORECASE), so this stays case-matched too.
_RESOLUTION_RE = r"Command\s*\[\s*TL\s*=|[Hh]ow\s+many\s+holds"
_CONFIRM_RE = f"{_CONTINUE_RE}|{_RESOLUTION_RE}"

_RESOLUTION_LINE_RE = re.compile(_RESOLUTION_RE)
# Matches the unambiguous subset of _RESOLUTION_LINE_RE that is valid
# evidence on its own, without requiring additional screen context.
# "How many holds?" at a multi-commodity port is never a bare-prompt
# ambiguity; Command[TL= IS ambiguous when it's the sole content.
_RESOLUTION_UNAMBIGUOUS_RE = re.compile(r"[Hh]ow\s+many\s+holds")
# Live-captured acceptance phrases (module docstring) + the credits
# balance line. Required alongside a trailing Command[TL= so a sector
# header / other scrollback remnant cannot count as "acceptance context".
_ACCEPTANCE_CONTEXT_RE = re.compile(
    r"you have\s+[\d,]+\s+credits"
    r"|we'll take"
    r"|take them"
    r"|i'll take"
    r"|we'll buy them anyway"
    r"|out of business"
    r"|cheapskate"
    r"|done,",
    re.IGNORECASE,
)


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


def _resolution_evidence(text):
    """True iff the CURRENT (last non-blank) line of `text` is ITSELF a
    recognized post-haggle shape -- not merely present somewhere in the
    (possibly stale) cropped screen. Anchoring to the true current line
    is what a bare whole-string `re.search` (necessarily used by
    `send_and_confirm`'s generic confirm_prompt contract) can't do; this
    is the check that turns a settle-layer "confirmed" into an honest
    "this is actually what's showing right now", the same "gate anchor"
    convention `state_parser.parse_haggle`'s own `current_default` check
    already uses (checked against the last non-blank line only).

    For the Command[TL= variant specifically, a bare Command[TL= as the
    SOLE non-blank content has no acceptance context and is
    DESYNC_FALLBACK, not a resolved deal. Additional non-blank content
    alone is NOT enough (a sector-status remnant + Command is still the
    4187-misfire class) -- require a live-captured acceptance phrase or
    a credits-balance line somewhere on the screen
    ("bare Command[TL= -> DESYNC_FALLBACK" hardening, TW-01)."""
    last = last_nonblank_line(text)
    if not _RESOLUTION_LINE_RE.search(last):
        return False
    if _RESOLUTION_UNAMBIGUOUS_RE.search(last):
        return True
    # Command[TL= on the current line: need real acceptance context, not
    # just "some other non-blank line exists" (scrollback / sector header).
    if sum(1 for line in text.splitlines() if line.strip()) <= 1:
        return False
    return bool(_ACCEPTANCE_CONTEXT_RE.search(text))


def _credit_delta_price(before_credits, after_credits, direction):
    """A verified credits delta consistent with a completed trade at
    SOME price -- honest evidence of the actual transacted amount, not
    a guess. "buy" (we're selling) -> credits must have INCREASED;
    "sell" (we're buying) -> credits must have DECREASED. Returns the
    implied price, or `None` if either side is unknown or the delta
    moved the wrong way (not this trade -- or not a trade at all)."""
    if before_credits is None or after_credits is None:
        return None
    delta = after_credits - before_credits
    if direction == "sell":
        return -delta if delta < 0 else None
    return delta if delta > 0 else None


def _evidence_backed_price(text, before_credits, direction, candidate_price):
    """The offer prompt is gone -- before declaring a deal ACCEPTED,
    require real evidence: (c) a verified credits delta consistent with
    the trade (the strongest signal, when a `before_credits` baseline is
    available -- reports the DELTA as the honest final_price, not
    `candidate_price`), or (b) the current line is a positively
    identified resolution shape (`candidate_price` is what we'd report
    here -- there's no counter-quote to have priced it differently).
    Returns the price to report, or `None` if NEITHER check passes -- the
    caller MUST treat `None` as an unverified desync, never a guess."""
    after_credits = credits_balance(text)
    delta_price = _credit_delta_price(before_credits, after_credits, direction)
    if delta_price is not None:
        return delta_price
    if _resolution_evidence(text):
        return candidate_price
    return None


def _accept_current_default_and_confirm(session, step_timeout):
    """The blank-input-accepts-default trick (DESIGN-v2 §8's own
    live-drive finding, reused deliberately) -- send nothing rather than
    re-typing the number already showing. Returns the settled render
    text if `send_and_confirm` positively matched a recognized
    post-accept shape, else `None` -- a caller-visible desync (the
    settle-layer match itself is still just a SHAPE match; the caller
    must run its own evidence check on the returned text before trusting
    it as a genuine accept, same as every other resolution path here)."""
    _reason, _elapsed, confirmed = send_and_confirm(
        session, "", _CONFIRM_RE, enter=True, timeout_s=step_timeout
    )
    if not confirmed:
        return None
    return session.render_text(session.render())


def run_haggle(
    session,
    fair_value=None,
    accept_threshold_pct=_DEFAULT_ACCEPT_THRESHOLD_PCT,
    open_aggression_pct=_DEFAULT_OPEN_AGGRESSION_PCT,
    round_cap=_DEFAULT_ROUND_CAP,
    step_timeout=_DEFAULT_STEP_TIMEOUT_S,
    fresh_render_debounce_ms=_DEFAULT_FRESH_RENDER_DEBOUNCE_MS,
    fresh_render_timeout_s=_DEFAULT_FRESH_RENDER_TIMEOUT_S,
):
    """Run the negotiation to completion against `session` (must already
    be sitting at an active offer prompt). Returns
    `{resolved, outcome, rounds, final_price, direction, fair_value}`.
    Never raises on a desync -- falls back to accepting whatever's
    currently on offer and reports `outcome=desync_fallback` instead,
    and NEVER reports `resolved=True`/a `final_price` that isn't backed
    by positive evidence (see `_evidence_backed_price`)."""
    gate_reason, _elapsed = wait_until_settled(
        session, debounce_ms=fresh_render_debounce_ms, timeout_s=fresh_render_timeout_s
    )
    if gate_reason != "idle":
        # The screen never settled enough to safely read -- refuse to
        # parse/act on a possibly-transitional render rather than
        # gambling with it (defect #3: the pre-send freshness gate).
        return _result(HaggleOutcome.DESYNC_FALLBACK, 0, None, None, fair_value)

    text = session.render_text(session.render())
    haggle = parse_haggle(text)
    if "current_default" not in haggle:
        return _result(HaggleOutcome.NO_ACTIVE_HAGGLE, 0, None, haggle.get("direction"), fair_value)

    direction = haggle.get("direction")
    reference = fair_value if fair_value is not None else haggle.get("baseline", haggle["current_default"])
    sign = _favorable_sign(direction)
    our_ask = _round_credits(reference + sign * reference * (open_aggression_pct / 100.0))
    before_credits = credits_balance(text)

    for round_i in range(1, round_cap + 1):
        _reason, _elapsed, confirmed = send_and_confirm(
            session, str(our_ask), _CONFIRM_RE, enter=True, timeout_s=step_timeout
        )
        if not confirmed:
            _accept_current_default_and_confirm(session, step_timeout)
            return _result(HaggleOutcome.DESYNC_FALLBACK, round_i, None, direction, reference)

        text = session.render_text(session.render())
        haggle = parse_haggle(text)
        if "current_default" not in haggle:
            # The offer prompt is gone -- the settle layer matched SOME
            # recognized shape, but that alone is never proof of a deal
            # (defect #2). Require positive evidence before reporting
            # ACCEPTED at our_ask.
            price = _evidence_backed_price(text, before_credits, direction, our_ask)
            if price is None:
                return _result(HaggleOutcome.DESYNC_FALLBACK, round_i, None, direction, reference)
            return _result(HaggleOutcome.ACCEPTED, round_i, price, direction, reference)

        current = haggle["current_default"]
        if _within_threshold(current, reference, accept_threshold_pct):
            accepted_text = _accept_current_default_and_confirm(session, step_timeout)
            if accepted_text is None:
                return _result(HaggleOutcome.DESYNC_FALLBACK, round_i, None, direction, reference)
            price = _evidence_backed_price(accepted_text, before_credits, direction, current)
            if price is None:
                return _result(HaggleOutcome.DESYNC_FALLBACK, round_i, None, direction, reference)
            return _result(HaggleOutcome.ACCEPTED, round_i, price, direction, reference)

        # Concede a step toward the midpoint of our own ask and the
        # port's counter, and go another round.
        our_ask = _round_credits((our_ask + current) / 2.0)

    # Round cap hit without converging within threshold -- the safe
    # fallback per DESIGN-v2 §9: accept the current default rather than
    # loop further (a real port CAN simply refuse to move, live-confirmed).
    accepted_text = _accept_current_default_and_confirm(session, step_timeout)
    if accepted_text is None:
        return _result(HaggleOutcome.DESYNC_FALLBACK, round_cap, None, direction, reference)
    price = _evidence_backed_price(accepted_text, before_credits, direction, haggle.get("current_default"))
    if price is None:
        return _result(HaggleOutcome.DESYNC_FALLBACK, round_cap, None, direction, reference)
    return _result(HaggleOutcome.ROUND_CAP_FALLBACK, round_cap, price, direction, reference)
