"""Settle detection — the reliability core (DESIGN.md §6).

After a send, the screen is "settled" on the FIRST of:
  (a) prompt  — --wait-prompt regex matches the rendered screen
  (b) idle    — no new bytes for debounce_ms, AND >=1 byte arrived since
                the send (so we never call a screen "settled" before the
                server has said anything at all)
  (c) timeout — the overall timeout elapsed

This is deliberately decoupled from real sockets/threads/wall-clock so it
can be unit-tested with a fake clock: `session` just needs to expose
`.rx_count`, `.last_rx`, `.clock()`, `.sleep(seconds)`, `.render_text()`
(plus `.send(text, enter, secret)` for `send_and_confirm` below).

**Send/settle race (DESIGN-v2.md §8, ELEVATED -- bitten live 3x, incl. a
-75-alignment auto-taken-colonist prompt and auto-given-away cargo):** a
bare `session.send(...)` + idle-only `wait_for_settle()` pair only proves
the screen went QUIET -- never that it's quiet on the SPECIFIC prompt the
caller thinks it is. Two related live failure shapes:
  1. A menu-style single-key selection sent WITH its usual trailing CRLF
     (`A\\r\\n`) can have that trailing Enter consumed by the server as
     an immediate blank/default-accept on the very NEXT prompt, before
     the caller's real follow-up answer is ever sent -- the caller has
     no way to un-send bytes already on the wire, so eliminating this at
     the SOURCE means not appending a CRLF the target prompt doesn't
     need in the first place (the live-proven workaround: send the
     selection with no trailing Enter).
  2. A multi-stage screen transition (an animation, a slow multi-part
     redraw) can go quiet just long enough to satisfy the debounce
     window mid-transition, then keep changing -- an idle-only settle
     can hand the caller a screen that LOOKS done but isn't (the
     already-known hub-warp-animation finding, same §8).
`send_and_confirm()` closes both: the caller supplies `enter` explicitly
per send (no blanket default-Enter) and a `confirm_prompt` the settled
screen must POSITIVELY match (never idle-only) -- a wrong/transitional
screen fails the match outright instead of masquerading as "settled" --
plus one extra quiet beat re-check after the match to reject a
transient flicker. A caller that never proceeds past `confirmed=False`
structurally cannot answer a prompt it hasn't verified it's looking at.
"""

import re

# The stability re-check pause after an initial confirm_prompt match --
# short enough to stay unnoticeable in a real 8s+ step budget, long
# enough to catch a screen still mid-transition (the hub-warp-animation
# shape: text changes again a beat after a first quiet moment).
_CONFIRM_STABILITY_PAUSE_S = 0.15


def wait_for_settle(session, wait_prompt=None, debounce_ms=350, timeout_s=8.0, poll_interval_s=0.04):
    start = session.clock()
    start_rx_count = session.rx_count
    debounce_s = debounce_ms / 1000.0
    prompt_re = re.compile(wait_prompt) if wait_prompt else None

    while True:
        now = session.clock()
        elapsed = now - start

        if prompt_re is not None and prompt_re.search(session.render_text()):
            return "prompt", elapsed

        if elapsed >= timeout_s:
            return "timeout", elapsed

        got_new_bytes = session.rx_count > start_rx_count
        idle_for = now - session.last_rx
        if got_new_bytes and idle_for >= debounce_s:
            return "idle", elapsed

        session.sleep(poll_interval_s)


def wait_until_settled(session, debounce_ms=350, timeout_s=8.0, poll_interval_s=0.04):
    """Block until the session's rx activity has been quiet for at least
    `debounce_ms` **as measured right now** -- a pre-send freshness gate
    for a caller about to READ the current render and act on it, distinct
    from `wait_for_settle()`'s "wait for a change, then settle" contract.

    `wait_for_settle()` can only detect idleness that occurs DURING its
    own call window: it requires `session.rx_count` to increase past the
    value captured at call-start before "idle" can ever fire (see its
    `test_never_settles_idle_without_any_new_bytes` case) -- so it
    structurally cannot confirm a screen that was ALREADY fully settled
    before the call began, which is exactly the case at the TOP of
    `haggle.run_haggle()`: the caller is handed a session already sitting
    at an offer prompt, with no send of its own to wait on. Reading
    `session.render()` at that point with no freshness check at all
    risks parsing a screen still mid-transition from whatever action the
    CALLER took to get there (DESIGN-v2 §8's send/settle-race philosophy,
    applied to the read side instead of the send side).

    Same `>=1 byte ever received` guard as `wait_for_settle()`'s own idle
    path (a connection that has NEVER produced any traffic isn't
    "settled", it's simply never having started) -- times out instead of
    reporting idle. Returns `("idle", elapsed)` or `("timeout", elapsed)`.
    """
    start = session.clock()
    debounce_s = debounce_ms / 1000.0

    while True:
        now = session.clock()
        elapsed = now - start

        if session.rx_count > 0 and (now - session.last_rx) >= debounce_s:
            return "idle", elapsed

        if elapsed >= timeout_s:
            return "timeout", elapsed

        session.sleep(poll_interval_s)


def send_and_confirm(
    session,
    text,
    confirm_prompt,
    enter=True,
    secret=False,
    timeout_s=8.0,
    debounce_ms=350,
    poll_interval_s=0.04,
    stability_pause_s=_CONFIRM_STABILITY_PAUSE_S,
):
    """Send `text` (with EXPLICIT `enter` -- the caller decides per
    prompt-shape, not a blanket default) then require the settled screen
    to POSITIVELY match `confirm_prompt` -- never idle-only. Returns
    `(reason, elapsed, confirmed)`. `confirmed=False` (target prompt
    never matched within `timeout_s`, or matched only transiently and
    was gone on the stability re-check) means a desync the caller MUST
    treat as unsafe to proceed past -- never guess/answer a prompt it
    can't positively identify (see module docstring)."""
    session.send(text, enter=enter, secret=secret)
    reason, elapsed = wait_for_settle(
        session, wait_prompt=confirm_prompt, debounce_ms=debounce_ms, timeout_s=timeout_s, poll_interval_s=poll_interval_s
    )
    if reason != "prompt":
        return reason, elapsed, False

    # Stability re-check: a transitional screen can flash confirm_prompt
    # in one frame and be gone a beat later -- confirmed only if it's
    # STILL there after one more quiet moment.
    session.sleep(stability_pause_s)
    if not re.search(confirm_prompt, session.render_text()):
        return "prompt", elapsed, False
    return "prompt", elapsed, True
