"""Deterministic, guarded resolver for one port OFFER dialogue.

The caller must already have navigated to a live ``Your offer [N]?`` prompt.
This module only negotiates that prompt; it never chooses a commodity or
starts a trade path.  Every send is confirmed against a fresh render, and
anything that cannot be positively identified is a desync, never a guessed
money-path success.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from .settle import send_and_confirm, wait_until_settled
from .state_parser import OUTCOME_READ, read_credits_balance

_DEFAULT_ROUND_CAP = 4
_DEFAULT_ACCEPT_THRESHOLD_PCT = 5.0
_DEFAULT_OPEN_AGGRESSION_PCT = 15.0
_DEFAULT_STEP_TIMEOUT_S = 8.0
_DEFAULT_FRESH_RENDER_DEBOUNCE_MS = 350
_DEFAULT_FRESH_RENDER_TIMEOUT_S = 2.0

_OFFER_RE = re.compile(
    r"We'll[ \t]+(?P<direction>buy|sell)[ \t]+them[ \t]+for[ \t]+"
    r"(?P<baseline>\d[\d,]*)[ \t]+credits\.",
    re.IGNORECASE,
)
_CURRENT_OFFER_RE = re.compile(
    r"Your[ \t]+offer[ \t]*\[[ \t]*(?P<default>\d[\d,]*)[ \t]*\][ \t]*\?",
    re.IGNORECASE,
)
_CONTINUE_RE = r"Your\s+offer\s*\["
_RESOLUTION_RE = r"Command\s*\[\s*TL\s*=|[Hh]ow\s+many\s+holds"
_CONFIRM_RE = f"{_CONTINUE_RE}|{_RESOLUTION_RE}"
_RESOLUTION_LINE_RE = re.compile(_RESOLUTION_RE)
_RESOLUTION_UNAMBIGUOUS_RE = re.compile(r"[Hh]ow\s+many\s+holds")
_ACCEPTANCE_CONTEXT_RE = re.compile(
    r"you have\s+[\d,]+\s+credits|we'll take|take them|i'll take|"
    r"we'll buy them anyway|out of business|cheapskate|done,",
    re.IGNORECASE,
)


class HaggleOutcome:
    """Closed outcome vocabulary for :func:`run_haggle`."""

    ACCEPTED = "accepted"
    ROUND_CAP_FALLBACK = "round_cap_fallback"
    DESYNC_FALLBACK = "desync_fallback"
    NO_ACTIVE_HAGGLE = "no_active_haggle"


def _last_nonblank_line(text: str) -> str:
    return next((line.strip() for line in reversed(text.splitlines()) if line.strip()), "")


def _parse_haggle(text: str) -> dict[str, Any]:
    """Read an OFFER only when its default is on the current prompt line."""
    current = _CURRENT_OFFER_RE.search(_last_nonblank_line(text))
    if current is None:
        return {}

    offers = list(_OFFER_RE.finditer(text))
    if not offers:
        return {}
    offer = offers[-1]
    return {
        "direction": offer.group("direction").lower(),
        "baseline": int(offer.group("baseline").replace(",", "")),
        "current_default": int(current.group("default").replace(",", "")),
    }


def _credits_balance(text: str) -> Optional[int]:
    credits = read_credits_balance(text)
    return credits.balance if credits.outcome == OUTCOME_READ else None


def _favorable_sign(direction: Optional[str]) -> int:
    return -1 if direction == "sell" else 1


def _within_threshold(value: int, reference: int, threshold_pct: float) -> bool:
    return abs(value - reference) <= reference * (threshold_pct / 100.0)


def _result(
    outcome: str,
    rounds: int,
    final_price: Optional[int],
    direction: Optional[str],
    fair_value: Optional[int],
) -> dict[str, Any]:
    return {
        "resolved": outcome == HaggleOutcome.ACCEPTED,
        "outcome": outcome,
        "rounds": rounds,
        "final_price": final_price,
        "direction": direction,
        "fair_value": fair_value,
    }


def _resolution_evidence(text: str) -> bool:
    """Require a live resolution line, not a stale whole-screen match."""
    last = _last_nonblank_line(text)
    if not _RESOLUTION_LINE_RE.search(last):
        return False
    if _RESOLUTION_UNAMBIGUOUS_RE.search(last):
        return True
    return bool(_ACCEPTANCE_CONTEXT_RE.search(text))


def _credit_delta_price(
    before_credits: Optional[int], after_credits: Optional[int], direction: Optional[str]
) -> Optional[int]:
    if before_credits is None or after_credits is None:
        return None
    delta = after_credits - before_credits
    if direction == "sell":
        return -delta if delta < 0 else None
    return delta if delta > 0 else None


def _evidence_backed_price(
    text: str,
    before_credits: Optional[int],
    direction: Optional[str],
    candidate_price: int,
) -> Optional[int]:
    delta_price = _credit_delta_price(before_credits, _credits_balance(text), direction)
    if delta_price is not None:
        return delta_price
    return candidate_price if _resolution_evidence(text) else None


def _accept_current_default_and_confirm(session: Any, step_timeout: float) -> Optional[str]:
    """Accept a proven current default by blank Enter and confirm the result."""
    _reason, _elapsed, confirmed = send_and_confirm(
        session, "", _CONFIRM_RE, enter=True, timeout_s=step_timeout
    )
    if not confirmed:
        return None
    return session.render_text(session.render())


def run_haggle(
    session: Any,
    fair_value: Optional[int] = None,
    accept_threshold_pct: float = _DEFAULT_ACCEPT_THRESHOLD_PCT,
    open_aggression_pct: float = _DEFAULT_OPEN_AGGRESSION_PCT,
    round_cap: int = _DEFAULT_ROUND_CAP,
    step_timeout: float = _DEFAULT_STEP_TIMEOUT_S,
    fresh_render_debounce_ms: int = _DEFAULT_FRESH_RENDER_DEBOUNCE_MS,
    fresh_render_timeout_s: float = _DEFAULT_FRESH_RENDER_TIMEOUT_S,
) -> dict[str, Any]:
    """Resolve a live OFFER, returning a positive-evidence-backed outcome.

    A missing or unsettled OFFER produces no send.  Once a counter has been
    sent, every next render must be a fresh OFFER or a positively evidenced
    resolution; otherwise the result is ``desync_fallback``.
    """
    gate_reason, _elapsed = wait_until_settled(
        session, debounce_ms=fresh_render_debounce_ms, timeout_s=fresh_render_timeout_s
    )
    if gate_reason != "idle":
        return _result(HaggleOutcome.DESYNC_FALLBACK, 0, None, None, fair_value)

    text = session.render_text(session.render())
    haggle = _parse_haggle(text)
    if "current_default" not in haggle:
        return _result(HaggleOutcome.NO_ACTIVE_HAGGLE, 0, None, None, fair_value)

    direction = haggle["direction"]
    reference = fair_value if fair_value is not None else haggle["baseline"]
    our_ask = round(reference + _favorable_sign(direction) * reference * open_aggression_pct / 100.0)
    before_credits = _credits_balance(text)

    for round_i in range(1, round_cap + 1):
        _reason, _elapsed, confirmed = send_and_confirm(
            session, str(our_ask), _CONFIRM_RE, enter=True, timeout_s=step_timeout
        )
        if not confirmed:
            _accept_current_default_and_confirm(session, step_timeout)
            return _result(HaggleOutcome.DESYNC_FALLBACK, round_i, None, direction, reference)

        text = session.render_text(session.render())
        haggle = _parse_haggle(text)
        if "current_default" not in haggle:
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

        our_ask = round((our_ask + current) / 2.0)

    accepted_text = _accept_current_default_and_confirm(session, step_timeout)
    if accepted_text is None:
        return _result(HaggleOutcome.DESYNC_FALLBACK, round_cap, None, direction, reference)
    price = _evidence_backed_price(
        accepted_text, before_credits, direction, haggle["current_default"]
    )
    if price is None:
        return _result(HaggleOutcome.DESYNC_FALLBACK, round_cap, None, direction, reference)
    return _result(HaggleOutcome.ROUND_CAP_FALLBACK, round_cap, price, direction, reference)
