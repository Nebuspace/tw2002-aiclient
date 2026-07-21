"""Before/after state-signature comparison → confidence delta.

Pure: no I/O, no daemon.
"""

_EXPLORE_DELTA = 0.1
_MATCH_DELTA = 0.2
_MISMATCH_DELTA = -0.15


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def compare_transition(
    before_signature: str,
    after_signature: str,
    *,
    expected_transition: str | None = None,
    prior_confidence: float = 0.0,
) -> dict:
    """Compare a tried action's before/after signatures.

    Returns
    ``{"matched", "observed_transition", "confidence_delta", "new_confidence", "reason"}``.
    """
    prior = _clamp01(float(prior_confidence))
    observed = after_signature

    if expected_transition is None:
        # Exploratory observe: any real transition is a modest positive.
        if after_signature == before_signature:
            delta = 0.0
            matched = False
            reason = "no transition (same screen)"
        else:
            delta = _EXPLORE_DELTA
            matched = True
            reason = "exploratory transition observed"
        return {
            "matched": matched,
            "observed_transition": observed,
            "confidence_delta": delta,
            "new_confidence": _clamp01(prior + delta),
            "reason": reason,
        }

    if after_signature == expected_transition:
        delta = _MATCH_DELTA
        return {
            "matched": True,
            "observed_transition": observed,
            "confidence_delta": delta,
            "new_confidence": _clamp01(prior + delta),
            "reason": "expected transition matched",
        }

    # Mismatch — including same-screen when something else was expected.
    delta = _MISMATCH_DELTA
    reason = (
        "no transition (same screen); expected different"
        if after_signature == before_signature
        else "transition mismatched expectation"
    )
    return {
        "matched": False,
        "observed_transition": observed,
        "confidence_delta": delta,
        "new_confidence": _clamp01(prior + delta),
        "reason": reason,
    }
