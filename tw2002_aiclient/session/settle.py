"""Settle detection — the reliability core (canon: architecture/settle-detection.md).

After a send, the screen is "settled" on the FIRST of:
  (a) prompt  — --wait-prompt regex matches the rendered screen
                (optionally ALSO requiring >=1 byte since the wait began,
                via `prompt_requires_new_bytes` — see below)
  (b) idle    — no new bytes for debounce_ms, AND >=1 byte arrived since
                the send (so we never call a screen "settled" before the
                server has said anything at all)
  (c) timeout — the overall timeout elapsed

This is deliberately decoupled from real sockets/threads/wall-clock so it
can be unit-tested with a fake clock: `session` just needs to expose
`.rx_count`, `.last_rx`, `.clock()`, `.sleep(seconds)`, `.render_text()`
(plus `.send(text, enter, secret)` for `send_and_confirm` below).

**Send/settle race (ELEVATED -- bitten live 3x, incl. a
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
     already-known hub-warp-animation finding).
`send_and_confirm()` closes both: the caller supplies `enter` explicitly
per send (no blanket default-Enter) and a `confirm_prompt` the settled
screen must POSITIVELY match (never idle-only) -- a wrong/transitional
screen fails the match outright instead of masquerading as "settled" --
plus one extra quiet beat re-check after the match to reject a
transient flicker. A caller that never proceeds past `confirmed=False`
structurally cannot answer a prompt it hasn't verified it's looking at.

**Replay/login callers without a nameable target:** these callers often
don't have a single known target regex the way a small closed set of
dialogue shapes does -- a recorded skill step or login sub-step
frequently has no explicit `wait_prompt` at all. `send_and_confirm(
confirm_prompt=None)` covers this: it confirms via a genuinely settled
idle instead of a regex match, still applying the same stability re-check
(no MORE bytes arrive during one more quiet beat) so a mid-transition
screen can't masquerade as settled just because it happened to go quiet
for one debounce window. Separately, when a `confirm_prompt` IS given, a
bare debounce-satisfying "idle" with no match is no longer treated as
a stop condition on its own -- it's discarded and re-polled against the
remaining timeout budget, since a slow multi-stage transition (the
hub-warp-animation shape) can go quiet just long enough to satisfy
`debounce_ms` mid-transition, well before the true target text ever
arrives.

**Stale-line match (`match_scope`, WO-SETTLE-PROMPT-LINE):** a third
window, independent of both of the above and closed by neither.
TradeWars is a scrolling BBS door -- it does not clear the screen between
screens -- so a prompt shape the caller is waiting for is routinely still
sitting PLAINLY VISIBLE up the 80x25 grid, several rows above the screen
that is actually current. (A property of the visible grid, not a
scrollback leak: `terminal.py` uses `pyte.Screen`, which keeps no history
buffer at all.) Searching `session.render_text()` -- the WHOLE rendered
grid -- therefore lets a `wait_prompt` match a line the PREVIOUS screen
left behind. Demonstrated end-to-end against a real `Session` and a real
captured screen in `tests/test_settle_real_screen.py`: a wait for
`Command \\[TL=` issued from the port menu returns `("prompt", 0.0)`
against a `Command [TL=` that scrolled up two screens ago, while the
current prompt line still reads `Enter your choice [T] ?`.

`send_and_confirm`'s stale-pre-send guard below does NOT cover this: that
guard asks only whether `rx_count` moved since the send, and a single
echoed keystroke byte satisfies it -- after which the whole-screen search
confirms against the stale row anyway, and the stability re-check (also a
whole-screen search) re-confirms that same stale row a beat later.

`match_scope` is the seam. `"screen"` (the default) is the whole-grid
search this system has always done and the one canon states literally
(`canon/architecture/settle-detection.md`: "matches the rendered screen
text"). `"prompt_line"` narrows the search to
`session.current_prompt_line()` -- the same single-line gate anchor
`classify.classify_screen` evaluates against, and the layer whose own
canon states the general rule this defect breaks: "text-matching a
screen's own shape is never a sufficient trust signal; provenance
(exclusivity, adjacency to a genuine current prompt) is"
(`canon/engine/screen-understanding.md`).

The default is deliberately NOT flipped here. Canon's mechanism sentence
prescribes the whole-screen search, so changing it silently would be a
canon deviation rather than a fix; and the narrowing has a real cost --
a `wait_prompt` written to span rows (`--wait-prompt` is
operator-supplied and free-form) matches under `"screen"` and can only
ever time out under `"prompt_line"`, turning a false settle into a hang.
Both halves are pinned as tests. Opt-in until canon rules -- which is
also what canon itself now says: research/tw2002-screen-patterns.md
P-SETTLE-LINE parks "which canon doc governs default `match_scope`" as an
open question and rules "until ruled, do not flip defaults in a drive-by
tip; pin prompt-line scope where a WO explicitly Accepts it."

One caller has taken that opt-in: `protocol.dispatch`'s `do` verb
(WO-DO-PROMPT-LINE-PIN), the one settle in the protocol that follows a
send of its own. `read` reaches this module through the SAME
`Session.wait_settle` door and deliberately keeps `"screen"` -- it sends
nothing, so "is this shape anywhere on the screen I'm looking at?" is its
honest question, and it is the only caller that can still express a
cross-row `wait_prompt`. Two callers, one door, opposite values: that is
why this is pinned per-call-site and a default could not serve it.

**Stale pre-send prompt match (`prompt_requires_new_bytes`,
WO-DO-SETTLE-RX-GUARD):** a FOURTH window, orthogonal to the three above
and to `match_scope` in particular.

The prompt branch below has always been allowed to win at its own t=0,
with no freshness clause at all -- while the idle branch immediately
under it has carried one since this module was written (`got_new_bytes`:
">=1 byte arrived since the wait began, so we never call a screen
'settled' before the server has said anything"). For a caller that only
ASKS about the current screen (the `read` verb, which sends nothing at
all) that asymmetry is correct and load-bearing: "is this prompt there?"
is answered instantly and truthfully by a prompt that is there. For a
caller that SENT something first (`do`) it is a false settle, because
the awaited prompt is routinely the SAME shape as the pre-send prompt --
`Command [TL=` → `Command [TL=`, which is canon's own worked `tw do`
example (`canon/architecture/session-engine.md`) and the single most
common `do` this product issues. That call returned `("prompt", 0.0)`
before the game had responded at all, handing the App
`settled_reason: prompt` -- documented as the STRONGEST confirmation
available, "quiet on a specific, named shape" -- over a screen that had
not changed.

`match_scope` cannot close this one. The stale-line defect above is
about WHERE the regex is searched; here the awaited shape genuinely IS
on the current prompt line, so it matches immediately under BOTH scopes.
Only a freshness clause rejects it. Conversely this guard does not close
the stale-line defect either (see the residual note below) -- the two are
independent and each needs its own fix.

`prompt_requires_new_bytes=True` gives the prompt branch the SAME
`got_new_bytes` predicate the idle branch already applies, reusing the
identical `start_rx_count` captured at wait entry rather than a second,
separately-captured count that could disagree with it. Entry-capture is
also the most faithful point available: `do` calls this immediately after
`session.send()` returns, so the floor is "bytes on the wire after ours
went out" -- bytes that arrived during `send()`'s own pre-write
anti-hammer pause (a previous command still painting) are correctly
counted as OLD, which a floor captured before the send would have
mistaken for a response.

It stays OPT-IN, and `False` remains the default, because the
match-at-t0 contract is CORRECT for every current caller except `do`:
`read` asks a read-only question about the screen as it stands;
`send_and_confirm` applies a guard of its own one layer up (see its
docstring's "Stale pre-send match guard") and relies on the inner wait
returning the match so it can adjudicate -- SIMILAR but measurably not
equivalent, since it floors on `rx_count` as of before its `send()`
rather than as of wait entry (measured head-to-head in
`tests/test_settle_send_confirm_freshness.py`); `login`'s bare settles
supply no `wait_prompt` at all. Flipping the default would break `read`'s
contract to fix `do`'s.

Two costs, stated rather than discovered later:
  1. A `do` whose game legitimately produces NO output now spends its
     whole budget and returns `timeout` where it used to return `prompt`
     instantly. That is the point -- `timeout` is canon's bounded "could
     not confirm", and a `prompt` asserted over zero bytes of evidence is
     a lie -- but it is a real latency change on that path, including
     the degenerate zero-byte send (`input=""` with `enter=False`).
  2. `rx_count` is a BYTE counter, so a single echoed keystroke satisfies
     the guard while proving nothing about the screen. This is exactly
     the residual `send_and_confirm`'s own guard has always carried, and
     it is deliberately matched rather than "improved" with a bigger byte
     threshold. (A "the render changed" predicate was considered and
     rejected: a legitimate identical repaint would then never settle,
     converting a false settle into a genuine hang.)

     What remains after that one echoed byte splits in two, and
     `match_scope` answers only ONE half -- stated here because an
     earlier revision of this paragraph said flatly that the residual's
     "fix is `match_scope`", which is half wrong and misleading exactly
     where it matters most, on the verb that now sets both:
       - **stale ROW** (awaited text sitting somewhere up the grid):
         `match_scope="prompt_line"` does close it -- not by waiting for
         the real prompt, but by withholding the `prompt` claim so the
         settle resolves as `idle` instead. `do` pins this scope
         (WO-DO-PROMPT-LINE-PIN).
       - **equal prompt** (awaited text IS the pre-send prompt line):
         `match_scope` does NOT close it and cannot. The echo lands ON
         the very line being searched (`Command [TL=...]: P`), so the
         window stays open identically under BOTH scopes -- measured, not
         reasoned, in `tests/test_do_settle_rx_guard.py::test_prompt_line_
         scope_does_not_close_the_equal_prompt_residual`.
     So `do` carries both narrowings and is still not airtight; the
     guard's own claim stays the narrow one it can actually keep -- a
     settle is never asserted when the game has said NOTHING at all.
"""

import re

# The stability re-check pause after an initial confirm_prompt match --
# short enough to stay unnoticeable in a real 8s+ step budget, long
# enough to catch a screen still mid-transition (the hub-warp-animation
# shape: text changes again a beat after a first quiet moment).
_CONFIRM_STABILITY_PAUSE_S = 0.15

# WHERE a `wait_prompt`/`confirm_prompt` regex is searched (see the module
# docstring's "Stale-line match" section for why this is a choice at all,
# rather than always the whole screen).
#
#   "screen"      -- the whole rendered grid (`session.render_text()`).
#                    The historical behavior and canon's literal wording;
#                    the ONLY scope under which a cross-row pattern can
#                    match. Can also match a line a previous screen left
#                    behind.
#   "prompt_line" -- the current prompt line only
#                    (`session.current_prompt_line()`). Cannot match a
#                    stale row -- and cannot match across rows either.
MATCH_SCOPE_SCREEN = "screen"
MATCH_SCOPE_PROMPT_LINE = "prompt_line"
MATCH_SCOPES = (MATCH_SCOPE_SCREEN, MATCH_SCOPE_PROMPT_LINE)


def _match_source(session, match_scope):
    """Resolve `match_scope` to the zero-arg callable whose return value a
    prompt regex is searched against.

    Resolved ONCE at wait entry, never per poll, for two reasons that are
    both about failing in the right place: an unknown scope (a typo) and
    a session that cannot serve the requested scope are both caller bugs
    that must surface before the wait begins -- not on some later poll,
    and in `send_and_confirm`'s case not after a keystroke has already
    reached the wire, which cannot be un-sent.

    Neither failure degrades to the permissive whole-screen search. A
    silent fallback would reinstate the stale-line match at precisely the
    one call site that asked not to have it, and would do it invisibly --
    the worst possible shape for a safety predicate. `"prompt_line"`
    imposes `current_prompt_line()` as an ADDITIONAL requirement on this
    module's otherwise-`render_text()`-only session protocol (see the
    module docstring's protocol list), so a session that cannot serve it
    is refused rather than quietly widened.
    """
    if match_scope == MATCH_SCOPE_SCREEN:
        return session.render_text
    if match_scope == MATCH_SCOPE_PROMPT_LINE:
        source = getattr(session, "current_prompt_line", None)
        if source is None:
            raise TypeError(
                f"match_scope={MATCH_SCOPE_PROMPT_LINE!r} requires session."
                f"current_prompt_line(); {type(session).__name__} does not provide it"
            )
        return source
    raise ValueError(f"match_scope must be one of {MATCH_SCOPES}, got {match_scope!r}")


def wait_for_settle(
    session,
    wait_prompt=None,
    debounce_ms=350,
    timeout_s=8.0,
    poll_interval_s=0.04,
    match_scope=MATCH_SCOPE_SCREEN,
    prompt_requires_new_bytes=False,
):
    """`prompt_requires_new_bytes` gates the prompt branch on the same
    ">=1 byte since this wait began" predicate the idle branch already
    applies -- see the module docstring's "Stale pre-send prompt match"
    section for why it exists, why it is opt-in, and what it does NOT
    cover. Set it on a wait that FOLLOWS a send of your own; leave it off
    for a read-only "is this prompt there?" question."""
    start = session.clock()
    start_rx_count = session.rx_count
    debounce_s = debounce_ms / 1000.0
    # HARD RULE (canon: settle-detection.md "Invariant: wait_prompt Is
    # Case-Sensitive") -- compiled WITHOUT re.IGNORECASE. A case-mismatched
    # wait_prompt must silently time out, never silently match the wrong
    # screen. Do not "helpfully" add IGNORECASE here. This is a property
    # of the COMPILE and is therefore identical under every `match_scope`
    # -- narrowing WHERE we search never widens WHAT matches.
    prompt_re = re.compile(wait_prompt) if wait_prompt else None
    # Resolved once, here, so a bad scope fails before the wait rather
    # than mid-poll (see `_match_source`). Only consulted when there is a
    # regex to place: with no `wait_prompt` there is nothing to search
    # and `match_scope` is meaningless, so it is not read at all.
    match_source = _match_source(session, match_scope) if prompt_re is not None else None

    while True:
        now = session.clock()
        elapsed = now - start
        # ONE freshness reading per poll, shared by both branches below --
        # so the prompt branch's guard and the idle branch's own clause can
        # never be satisfied by different notions of "new".
        #
        # Hoisting it above the prompt branch (it used to be read after
        # the match attempt) is behaviour-neutral for the idle branch, not
        # merely "close enough": a byte landing DURING `match_source()`'s
        # locked render would be seen by a later read, but it also pushes
        # `session.last_rx` past the `now` captured at the top of this
        # poll, making `idle_for` negative -- so it could never have
        # satisfied the debounce window in that same poll either way.
        #
        # The PROMPT branch is a different story and the scoping above is
        # deliberate: with the guard ON, a byte landing during that same
        # render WAS counted under the old ordering and is NOT counted
        # now, so the prompt cannot win this poll and wins the next one
        # instead. That is not neutral -- it is strictly MORE conservative
        # on the guarded path, bounded by one poll tick, and it errs
        # toward never asserting a settle on less evidence. Stated rather
        # than left to be inferred from the idle-branch proof, because a
        # reader who assumes "neutral" applies to both branches would be
        # assuming exactly the half that changed.
        got_new_bytes = session.rx_count > start_rx_count

        # Ordered rx-check-first deliberately: when the guard is on and
        # nothing has arrived yet, this skips `match_source()` entirely,
        # so a wait that is going to reject the match anyway never pays
        # for a locked render it cannot use.
        if (
            prompt_re is not None
            and (got_new_bytes or not prompt_requires_new_bytes)
            and prompt_re.search(match_source())
        ):
            return "prompt", elapsed

        # Checked AFTER the prompt branch and BEFORE the idle one, exactly
        # as before: the guard changes WHEN a prompt may win, never
        # whether the budget still bounds the wait. A guarded wait whose
        # bytes never arrive falls through to here and returns
        # `timeout` -- canon's bounded "could not confirm" -- rather than
        # waiting past it.
        if elapsed >= timeout_s:
            return "timeout", elapsed

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
    value captured at call-start before "idle" can ever fire -- so it
    structurally cannot confirm a screen that was ALREADY fully settled
    before the call began, which is exactly the case when a caller is
    handed a session already sitting at an offer prompt, with no send of
    its own to wait on. Reading `session.render()` at that point with no
    freshness check at all risks parsing a screen still mid-transition
    from whatever action the CALLER took to get there (the send/settle-
    race philosophy, applied to the read side instead of the send side).

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
    confirm_prompt=None,
    enter=True,
    secret=False,
    timeout_s=8.0,
    debounce_ms=350,
    poll_interval_s=0.04,
    stability_pause_s=_CONFIRM_STABILITY_PAUSE_S,
    retry_unstable_idle=False,
    match_scope=MATCH_SCOPE_SCREEN,
):
    """Send `text` (with EXPLICIT `enter` -- the caller decides per
    prompt-shape, not a blanket default) then require the settle to be
    POSITIVELY confirmed -- never idle-only. Returns `(reason, elapsed,
    confirmed)`. `confirmed=False` means a desync the caller MUST treat
    as unsafe to proceed past -- never guess/answer a prompt it can't
    positively identify (see module docstring).

    Two confirmation modes, chosen by whether the caller has a specific
    target shape in hand:

    - `confirm_prompt` given (a small closed set of known next-screen
      shapes) -- the settled screen must POSITIVELY match it. A bare
      debounce-satisfying "idle" with NO match is **not** treated as
      proof nothing more is coming: a slow multi-stage transition (the
      hub-warp-animation shape) can go quiet just long enough to satisfy
      `debounce_ms` mid-transition, well before the true target text ever
      arrives -- so an unmatched "idle" is discarded and re-polled against
      the remaining `timeout_s` budget instead of failing fast. Only a
      genuine `confirm_prompt` match, or the whole budget running out,
      ends the wait. Once matched, one more `stability_pause_s` beat
      re-checks it's STILL there (a transitional screen can flash the
      match in one frame and be gone the next).

      **Stale pre-send match guard:** `wait_for_settle`'s own
      match-wins-immediately-at-t0 contract (deliberate and correct for
      a caller-driven `--wait-prompt` poll) means a `confirm_prompt`
      that already matches whatever was on screen BEFORE this call's
      `send()` -- e.g. a repeating offer-prompt shape still showing the
      PREVIOUS round's prompt -- would otherwise be accepted instantly,
      well before the real response to THIS send ever arrives.
      `send_and_confirm` closes this itself (rather than touching
      `wait_for_settle`'s contract): a "prompt" match is only accepted
      once `session.rx_count` has increased past the count captured
      immediately BEFORE `send()` -- i.e. bytes have landed since this
      send was begun -- echoing, but NOT equal to, the idle path's own
      `got_new_bytes` discipline one layer up, which takes its floor at
      wait entry instead. See the `rx_at_send` comment below for what
      the difference between those two floors actually costs, and
      `tests/test_settle_send_confirm_freshness.py` for the head-to-head
      measurement of it. A match against unchanged, pre-send
      content is discarded exactly like a premature idle: one poll tick
      is advanced (since a wait_for_settle call that matches at its own
      t=0 never sleeps internally) and the wait resumes against the
      remaining budget.
    - `confirm_prompt=None` (a recorded step or login sub-step with no
      caller-supplied target regex to confirm against) -- confirms via a
      genuinely settled idle instead: `wait_for_settle`'s own "idle"
      reason, followed by the SAME stability re-check applied to byte
      arrivals rather than a regex match (no MORE bytes arrive during
      one more `stability_pause_s` beat). This is a strictly weaker
      guarantee than a positive shape match (it can't tell WHICH screen
      arrived, only that one did and stayed put) -- callers that can
      name a target shape should always prefer passing `confirm_prompt`.

    **`retry_unstable_idle`:** default `False` keeps the fail-fast on
    bytes-during-stability (colonist-default race / skills with
    `wait_prompt=None`). When `True` (autopilot explore/upgrade warps),
    an unstable idle is NOT an immediate desync: keep re-polling for a
    *stable* idle against the remaining `timeout_s` budget via
    `wait_until_settled` (already-quiet OK -- the bytes that broke
    stability may have been the hop's final paint, so requiring *new*
    bytes would hang). Still bounded: if the screen never goes quiet,
    returns `timeout`/`confirmed=False`.

    **`match_scope`:** applies to `confirm_prompt` only (with
    `confirm_prompt=None` there is no regex to place, so it is not read
    at all) -- see the module docstring. It governs BOTH the match and
    the stability re-check, deliberately: a re-check that fell back to a
    whole-screen search would let a prompt that flashed and moved on find
    its own text still sitting up the grid and re-confirm itself, which
    is the same stale-line hole re-opened one line lower down. The scope
    is resolved BEFORE `send()`, so a caller bug is refused with no byte
    on the wire."""
    # Resolved before send(): an unknown scope, or a session that cannot
    # serve the requested one, is a caller bug that must NOT cost a
    # keystroke -- bytes already on the wire cannot be un-sent (this
    # module's founding scar).
    match_source = _match_source(session, match_scope) if confirm_prompt is not None else None
    # Captured BEFORE send(), not after -- a DIFFERENT floor from the one
    # `wait_for_settle(prompt_requires_new_bytes=True)` takes at wait
    # entry, and NOT interchangeable with it. The two look like copies of
    # one idea and are not; the difference is measured head-to-head in
    # `tests/test_settle_send_confirm_freshness.py` (WO-SEND-CONFIRM-RX-
    # DEDUP), which also pins today's behaviour so a future "dedupe" has
    # to be a decision rather than a tidy-up.
    #
    # Why before: some fake-session test doubles (the historical
    # synchronous-bump convention -- `tests/test_haggle.py` and siblings)
    # bump rx_count SYNCHRONOUSLY inside send() itself and never again, so
    # a floor taken after send() returns swallows the entire response and
    # can never be cleared at all.
    #
    # What that costs, stated rather than discovered later: send() is not
    # instantaneous -- it may sleep up to MIN_SEND_GAP_S for the
    # anti-hammer guardrail, then write the socket and the transcript log,
    # all while the reader thread keeps moving rx_count. A byte landing in
    # THAT window belongs to whatever was already painting, but this floor
    # counts it as new, so a `confirm_prompt` that already matches the
    # PRE-send screen is accepted at elapsed 0.0. The module docstring's
    # `prompt_requires_new_bytes` section argues the wait-entry floor is
    # the faithful one for precisely this reason. Both claims are true of
    # their own caller; which floor THIS one should use is a canon
    # question, deliberately left open here rather than settled silently.
    rx_at_send = session.rx_count
    session.send(text, enter=enter, secret=secret)
    start = session.clock()

    if confirm_prompt is not None:
        while True:
            remaining = timeout_s - (session.clock() - start)
            if remaining <= 0:
                return "timeout", session.clock() - start, False
            reason, _elapsed = wait_for_settle(
                session,
                wait_prompt=confirm_prompt,
                debounce_ms=debounce_ms,
                timeout_s=remaining,
                poll_interval_s=poll_interval_s,
                match_scope=match_scope,
            )
            if reason == "prompt":
                if session.rx_count > rx_at_send:
                    break
                # Matched, but against content that was ALREADY on
                # screen before this send -- no evidence it's a
                # response to what we just sent (see module docstring's
                # "stale pre-send match guard"). wait_for_settle can
                # return "prompt" at its own t=0 with no sleep at all,
                # so advance one poll tick ourselves before re-checking,
                # else this would spin forever without the clock (or the
                # remaining budget) ever moving.
                session.sleep(poll_interval_s)
                continue
            if reason == "timeout":
                return "timeout", session.clock() - start, False
            # reason == "idle" with no confirm_prompt match yet -- a lull,
            # not proof of a genuine stop; keep polling against what's
            # left of the budget rather than failing fast.
        elapsed = session.clock() - start

        # Stability re-check: a transitional screen can flash confirm_prompt
        # in one frame and be gone a beat later -- confirmed only if it's
        # STILL there after one more quiet moment. Re-checked through the
        # SAME `match_source` the match came through (never a bare
        # render_text()): a whole-screen re-check under a prompt_line
        # match would find the flashed prompt still sitting up the grid
        # and re-confirm it, defeating the narrowing at the last step.
        session.sleep(stability_pause_s)
        if not re.search(confirm_prompt, match_source()):
            return "prompt", elapsed, False
        return "prompt", elapsed, True

    # No specific target shape known -- confirm via a genuinely stable
    # idle settle instead: reason must be "idle" (never a bare "prompt",
    # since none was given), then re-verify no MORE bytes arrive during
    # one more stability pause (the same hub-warp-animation fix, applied
    # to byte arrivals instead of a regex match).
    #
    # First pass uses wait_for_settle (requires >=1 new byte since send).
    # Retries after an unstable idle use wait_until_settled so a hop
    # whose final paint already landed during the stability window can
    # still confirm without demanding yet more bytes.
    awaiting_first_byte = True
    first_idle_elapsed = None
    while True:
        remaining = timeout_s - (session.clock() - start)
        if remaining <= 0:
            return "timeout", session.clock() - start, False
        if awaiting_first_byte:
            reason, elapsed = wait_for_settle(
                session,
                wait_prompt=None,
                debounce_ms=debounce_ms,
                timeout_s=remaining,
                poll_interval_s=poll_interval_s,
            )
            awaiting_first_byte = False
        else:
            reason, elapsed = wait_until_settled(
                session,
                debounce_ms=debounce_ms,
                timeout_s=remaining,
                poll_interval_s=poll_interval_s,
            )
            elapsed = session.clock() - start
        if reason != "idle":
            return reason, elapsed if first_idle_elapsed is None else session.clock() - start, False
        if first_idle_elapsed is None:
            first_idle_elapsed = elapsed
        rx_at_settle = session.rx_count
        session.sleep(stability_pause_s)
        if session.rx_count == rx_at_settle:
            return "idle", first_idle_elapsed if not retry_unstable_idle else session.clock() - start, True
        if not retry_unstable_idle:
            # Default: bytes during stability = fail-fast desync
            # (colonist-default / mid-transition race). Do NOT keep
            # waiting for eventual quiescence.
            return "idle", first_idle_elapsed, False
        # retry_unstable_idle: keep polling for a stable quiet within budget.
