"""Deterministic auto-haggle tests (DESIGN-v2.md §9) -- no network, a
scripted fake port session, seeded from real captured haggle exchanges
against twgs.test.example (2026-07-19, see haggle.py's module
docstring for the raw transcripts these numbers come from)."""

from tw2002_aiclient.session.haggle import HaggleOutcome, run_haggle


class FakePortSession:
    """A minimal fake session that plays ONE port's side of a haggle
    dialogue: `.send()` immediately produces the next screen via a
    caller-supplied `respond(sent_text, round_i) -> new_text` callback,
    so haggle.py's reactive ask/counter loop is exercised deterministically
    with no real clock or socket. `round_i` is 1-based and increments on
    every send (including the final blank accept-default send)."""

    def __init__(self, initial_text, respond):
        self._text = initial_text
        self._respond = respond
        self.round_i = 0
        self.sent = []
        self.rx_count = 1
        self.last_rx = 0.0
        self.t = 0.0

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds

    def render(self):
        return self._text.splitlines()

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._text

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))
        self.round_i += 1
        self._text = self._respond(text, self.round_i)
        self.rx_count += 1
        self.last_rx = self.t


def _scripted(responses):
    def respond(_sent, round_i):
        return responses[round_i - 1]

    return respond


class SettlingThenReactiveSession:
    """Like `FakePortSession`, but the very FIRST screen isn't
    immediately stable -- bytes keep arriving on a scripted
    `(arrival_time, text)` timeline (same model as test_settle.py's
    `StagedSession`) before the TRUE settled render appears. Needed to
    prove `run_haggle`'s pre-send freshness gate (TW-01 defect #3)
    actually waits for `settle.wait_until_settled()` rather than reading
    whatever's on screen the instant it's invoked. Once the staged
    arrivals are exhausted, `.send()` behaves exactly like
    `FakePortSession` (a reactive, scripted responder)."""

    def __init__(self, stages, respond):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._stages = sorted(stages)
        self._text = ""
        self._respond = respond
        self.round_i = 0
        self.sent = []
        self._apply_pending()

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        self._apply_pending()

    def _apply_pending(self):
        while self._stages and self._stages[0][0] <= self.t:
            _, text = self._stages.pop(0)
            self._text = text
            self.rx_count += 1
            self.last_rx = self.t

    def render(self):
        return self._text.splitlines()

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._text

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))
        self.round_i += 1
        self._text = self._respond(text, self.round_i)
        self.rx_count += 1
        self.last_rx = self.t


def test_run_haggle_buy_direction_converges_in_two_rounds_like_the_real_capture():
    # Real capture: baseline 2,214 -> our aggressive ask (buy direction
    # means we're SELLING, want MORE) -> port barely concedes to 2,216
    # -> accepted on round 2 via the blank-default-accept trick.
    responses = [
        "We'll buy them for 2,216 credits.\nYour offer [2,216] ? ",
        "Done, we'll take the lot.\n\nYou have 112,940 credits and 50 empty cargo holds.\n\n"
        "Command [TL=00:00:00]:[27584] (?=Help)? : ",
    ]
    session = FakePortSession("We'll buy them for 2,214 credits.\nYour offer [2,214] ? ", _scripted(responses))

    result = run_haggle(session, round_cap=4)

    assert result == {
        "resolved": True,
        "outcome": HaggleOutcome.ACCEPTED,
        # "rounds" counts negotiation ROUNDS (bounded by round_cap), not
        # raw sends -- the ask and the accept it earns share round 1.
        "rounds": 1,
        "final_price": 2216,
        "direction": "buy",
        "fair_value": 2214,
    }
    first_ask = int(session.sent[0][0])
    assert first_ask > 2214  # "buy": aggressive counter is ABOVE baseline
    assert session.sent[1] == ("", True, False)  # the accept-default send, closing round 1


def test_run_haggle_sell_direction_converges_in_two_rounds_like_the_real_capture():
    # Real capture: baseline 758 -> our aggressive ask (sell direction
    # means we're BUYING, want LESS) -> port concedes to 753 -> accepted.
    responses = [
        "We'll sell them for 753 credits.\nYour offer [753] ? ",
        "Cheapskate.  Here, take them and leave me alone.\n\n"
        "You have 112,187 credits and 0 empty cargo holds.\n\n"
        "Command [TL=00:00:00]:[27584] (?=Help)? : ",
    ]
    session = FakePortSession("We'll sell them for 758 credits.\nYour offer [758] ? ", _scripted(responses))

    result = run_haggle(session, round_cap=4)

    assert result["outcome"] == HaggleOutcome.ACCEPTED
    assert result["rounds"] == 1  # the ask and its accept share round 1
    assert result["final_price"] == 753
    assert result["direction"] == "sell"
    first_ask = int(session.sent[0][0])
    assert first_ask < 758  # "sell": aggressive counter is BELOW baseline


def test_run_haggle_accepts_immediately_if_the_port_takes_the_opening_ask_outright():
    # No counter-quote round at all -- the offer prompt is simply gone
    # after round 1, meaning the port took our ask as-is.
    responses = ["You will put me out of business, I'll take your offer.\n\nCommand [TL=00:00:00]:[1] (?=Help)? : "]
    session = FakePortSession("We'll buy them for 1,000 credits.\nYour offer [1,000] ? ", _scripted(responses))

    result = run_haggle(session, round_cap=4)

    assert result["outcome"] == HaggleOutcome.ACCEPTED
    assert result["rounds"] == 1
    assert result["final_price"] == int(session.sent[0][0])


def test_run_haggle_concedes_toward_midpoint_when_not_yet_within_threshold():
    # Round 1's aggressive ask (2000 * 1.15 = 2300) draws a port counter
    # (2250) still outside the default 5% threshold of the 2000
    # baseline -- round 2 must concede to the MIDPOINT of our own ask
    # and the port's counter (round((2300+2250)/2) = 2275), not just
    # resend 2300. The port's round-2 counter (2010) IS within
    # threshold, so round 3 accepts it via blank.
    responses = [
        "We'll buy them for 2,250 credits.\nYour offer [2,250] ? ",
        "We'll buy them for 2,010 credits.\nYour offer [2,010] ? ",
        "Done, we'll take the lot.\n\nCommand [TL=00:00:00]:[1] (?=Help)? : ",
    ]
    session = FakePortSession("We'll buy them for 2,000 credits.\nYour offer [2,000] ? ", _scripted(responses))

    result = run_haggle(session, round_cap=4, accept_threshold_pct=5.0, open_aggression_pct=15.0)

    assert session.sent[0] == ("2300", True, False)
    assert session.sent[1] == ("2275", True, False)
    assert session.sent[2] == ("", True, False)
    assert result["outcome"] == HaggleOutcome.ACCEPTED
    assert result["rounds"] == 2  # round 1 (2300, rejected) + round 2 (2275, accepted)
    assert result["final_price"] == 2010


def test_run_haggle_round_cap_fallback_when_the_port_never_converges():
    # A synthetic stubborn port (ports CAN simply refuse, DESIGN-v2 §9)
    # that never re-quotes anywhere near baseline -- the round cap is
    # hit and the safe fallback (accept the current default) fires
    # rather than negotiating forever.
    def respond(_sent, round_i):
        if round_i <= 4:
            return "We'll buy them for 5,000 credits.\nYour offer [5,000] ? "
        return "Done, we'll take the lot.\n\nCommand [TL=00:00:00]:[1] (?=Help)? : "

    session = FakePortSession("We'll buy them for 2,000 credits.\nYour offer [2,000] ? ", respond)

    result = run_haggle(session, round_cap=4, accept_threshold_pct=5.0)

    assert result["outcome"] == HaggleOutcome.ROUND_CAP_FALLBACK
    assert result["resolved"] is False
    assert result["rounds"] == 4
    assert result["final_price"] == 5000
    assert session.sent[-1] == ("", True, False)  # the fallback accept-default send


def test_run_haggle_desync_fallback_when_the_screen_goes_unrecognized():
    # The target confirm_prompt never matches at all (an unmodeled
    # interstitial, e.g. a random event) -- a safe fallback, not a
    # blind guess at an unrecognized screen.
    def respond(_sent, _round_i):
        return "A klaxon sounds. Intruder alert!\n"

    session = FakePortSession("We'll buy them for 2,000 credits.\nYour offer [2,000] ? ", respond)

    result = run_haggle(session, round_cap=4, step_timeout=0.05)

    assert result["outcome"] == HaggleOutcome.DESYNC_FALLBACK
    assert result["resolved"] is False
    assert result["final_price"] is None


def test_run_haggle_no_active_haggle_when_dispatched_off_context():
    session = FakePortSession("Command [TL=00753:0/0/0/850] (?=Help)? : ", lambda _s, _r: "")

    result = run_haggle(session)

    assert result["outcome"] == HaggleOutcome.NO_ACTIVE_HAGGLE
    assert result["resolved"] is False
    assert session.sent == []  # never sends anything with nothing to negotiate


def test_run_haggle_honors_an_explicit_fair_value_override():
    # An explicit fair_value (e.g. a caller's learned running average)
    # takes priority over the port's own stated baseline as the
    # reference the opening ask and acceptance threshold are anchored to.
    responses = [
        "We'll buy them for 3,010 credits.\nYour offer [3,010] ? ",
        "Done, we'll take the lot.\n\nCommand [TL=00:00:00]:[1] (?=Help)? : ",
    ]
    session = FakePortSession("We'll buy them for 2,000 credits.\nYour offer [2,000] ? ", _scripted(responses))

    result = run_haggle(session, fair_value=3000, round_cap=4, accept_threshold_pct=5.0, open_aggression_pct=0.0)

    # open_aggression_pct=0.0 -> round 1's ask is the fair_value itself, not the port's baseline.
    assert session.sent[0] == ("3000", True, False)
    assert result["fair_value"] == 3000
    assert result["outcome"] == HaggleOutcome.ACCEPTED


# -- TW-01 money-path hardening regressions (2026-07-19) --------------------
#
# Three real-loss-causing defects: (1) the settle-layer confirm regex
# necessarily matches "Command [TL=" anywhere in the (possibly stale)
# screen, not just the current line; (2) "offer prompt gone" alone used
# to mean ACCEPTED, with zero trade evidence; (3) no freshness gate on
# the very first read, before round 1's ask is even computed. Every test
# below would have failed under the pre-fix code (each traced by hand
# against the old "current_default not in haggle -> ACCEPTED at our_ask"
# / no-gate logic before being written).


def test_run_haggle_stale_command_prompt_elsewhere_on_screen_does_not_confirm_a_deal():
    # The "misfire at 4187" class: our counter-offer send lands on a
    # screen where a Command[TL=...] prompt is still visible near the
    # TOP as stale scrollback left over from BEFORE the haggle dialogue
    # was ever entered, while the TRUE current (bottom) line is
    # something else entirely, unresolved. send_and_confirm's
    # confirm_prompt does a plain whole-string re.search, so it DOES
    # match (the settle layer can't tell stale from current) -- but the
    # offer prompt being gone must never be read as "the port took our
    # ask" without evidence anchored to the REAL current line.
    responses = [
        "Command [TL=00:00:00]:[999] (?=Help)? : \n"
        "A meteor shower forces you to divert course.\n"
        "Recalculating approach vector...\n"
    ]
    session = FakePortSession(
        "We'll buy them for 4,187 credits.\nYour offer [4,187] ? ", _scripted(responses)
    )

    result = run_haggle(session, fair_value=4187, open_aggression_pct=0.0, round_cap=4)

    assert result["outcome"] == HaggleOutcome.DESYNC_FALLBACK
    assert result["resolved"] is False
    assert result["final_price"] is None


def test_run_haggle_stray_content_after_the_accept_default_send_does_not_confirm_a_deal():
    # The "post-accept stray input" class: after we send the blank
    # accept-default (having converged within threshold), a stray bit
    # of leftover/garbled content lands us on a screen where
    # Command[TL=...] is still visible (again satisfying the settle
    # layer's whole-string search) but the TRUE current line is an
    # error/echo, not a genuine resolution.
    responses = [
        "We'll buy them for 2,010 credits.\nYour offer [2,010] ? ",
        "Command [TL=00:00:00]:[1] (?=Help)? : A\n\nUnknown command. Please try again.\n",
    ]
    session = FakePortSession(
        "We'll buy them for 2,000 credits.\nYour offer [2,000] ? ", _scripted(responses)
    )

    result = run_haggle(session, round_cap=4, accept_threshold_pct=5.0, open_aggression_pct=15.0)

    assert session.sent[1] == ("", True, False)  # the accept-default send still went out
    assert result["outcome"] == HaggleOutcome.DESYNC_FALLBACK
    assert result["resolved"] is False
    assert result["final_price"] is None


def test_run_haggle_reports_the_verified_credits_delta_as_final_price_over_a_guessed_ask():
    # When a credits-balance baseline IS available (some port screens DO
    # show it), the verified DELTA is the honest final_price -- never
    # just "whatever we last asked for", even when the two differ (a
    # real trade can close at a slightly different net amount than the
    # raw ask, e.g. a fee folded in) -- final_price must be EVIDENCED,
    # never guessed.
    initial = (
        "You have 100,000 credits and 10 empty cargo holds.\n\n"
        "We'll buy them for 2,000 credits.\nYour offer [2,000] ? "
    )
    responses = [
        "Done, we'll take the lot.\n\n"
        "You have 102,300 credits and 10 empty cargo holds.\n\n"
        "Command [TL=00:00:00]:[1] (?=Help)? : "
    ]
    session = FakePortSession(initial, _scripted(responses))

    result = run_haggle(session, fair_value=2000, open_aggression_pct=0.0, round_cap=4)

    assert session.sent[0][0] == "2000"  # what we actually asked for
    assert result["outcome"] == HaggleOutcome.ACCEPTED
    assert result["final_price"] == 2300  # the VERIFIED delta, not the raw ask


def test_run_haggle_waits_for_a_fresh_settled_render_before_reading_the_opening_prompt():
    # Defect #3: the screen is STILL mid-transition (an intervening
    # "docking" screen, no haggle prompt at all) at the moment
    # run_haggle is invoked; the REAL settled offer-prompt only appears
    # a beat later. Without the pre-send freshness gate, run_haggle
    # would read the transitional text immediately and misreport
    # "no active haggle" even though a genuine dialogue is one beat away.
    stages = [
        (0.0, "Docking with starbase Alpha...\n"),
        (0.2, "We'll buy them for 800 credits.\nYour offer [800] ? "),
    ]
    responses = ["Done, we'll take the lot.\n\nCommand [TL=00:00:00]:[1] (?=Help)? : "]
    session = SettlingThenReactiveSession(stages, _scripted(responses))

    result = run_haggle(session, round_cap=4)

    assert result["outcome"] == HaggleOutcome.ACCEPTED
    first_ask = int(session.sent[0][0])
    assert first_ask > 800  # negotiated off the REAL settled baseline, not the transitional screen


def test_run_haggle_bare_command_prompt_only_after_ask_is_desync_fallback():
    # "4187-misfire" exact shape: after sending our ask, the screen lands
    # on ONLY a bare Command[TL= main-menu prompt with no preceding
    # acceptance phrase or credits line. send_and_confirm's confirm_prompt
    # still fires (whole-string re.search hits Command[TL=), and the offer
    # prompt is gone -- but _resolution_evidence() must require MORE than
    # just the bare prompt as the sole content. Pre-fix: the bare
    # Command[TL= was the last non-blank line, _RESOLUTION_LINE_RE matched,
    # _resolution_evidence() returned True, and final_price was set to
    # our_ask -- a silent false ACCEPTED.
    responses = [
        "Command [TL=00:00:00]:[4187] (?=Help)? : ",
    ]
    session = FakePortSession(
        "We'll buy them for 4,187 credits.\nYour offer [4,187] ? ", _scripted(responses)
    )

    result = run_haggle(session, fair_value=4187, open_aggression_pct=0.0, round_cap=4)

    assert result["outcome"] == HaggleOutcome.DESYNC_FALLBACK
    assert result["resolved"] is False
    assert result["final_price"] is None


def test_run_haggle_bare_command_prompt_only_after_accept_default_is_desync_fallback():
    # Post-accept-stray bare-prompt shape: we've converged within threshold
    # and sent the blank accept-default, but the response is ONLY a bare
    # Command[TL= prompt -- no acceptance phrase, no credits line. The
    # settle layer fires (Command[TL= is in _CONFIRM_RE), the offer prompt
    # is gone -- pre-fix _resolution_evidence() returned True and reported
    # ACCEPTED at current. No acceptance context means DESYNC_FALLBACK.
    responses = [
        "We'll buy them for 2,010 credits.\nYour offer [2,010] ? ",
        "Command [TL=00:00:00]:[1] (?=Help)? : ",
    ]
    session = FakePortSession(
        "We'll buy them for 2,000 credits.\nYour offer [2,000] ? ", _scripted(responses)
    )

    result = run_haggle(session, round_cap=4, accept_threshold_pct=5.0, open_aggression_pct=15.0)

    assert session.sent[1] == ("", True, False)  # the accept-default was still sent
    assert result["outcome"] == HaggleOutcome.DESYNC_FALLBACK
    assert result["resolved"] is False
    assert result["final_price"] is None


def test_run_haggle_sector_header_plus_command_is_desync_fallback():
    # Residual after sole-content fix: any second non-blank line (e.g. a
    # sector status remnant left in the crop) + trailing Command[TL= used
    # to satisfy sum(non_blank)>1 and false-ACCEPT at our_ask. Acceptance
    # context must be a real deal phrase / credits line.
    responses = [
        "Sector  4187 has a port.\nCommand [TL=00:00:00]:[4187] (?=Help)? : ",
    ]
    session = FakePortSession(
        "We'll buy them for 4,187 credits.\nYour offer [4,187] ? ", _scripted(responses)
    )

    result = run_haggle(session, fair_value=4187, open_aggression_pct=0.0, round_cap=4)

    assert result["outcome"] == HaggleOutcome.DESYNC_FALLBACK
    assert result["resolved"] is False
    assert result["final_price"] is None


def test_run_haggle_desync_fallback_when_the_screen_never_settles_before_the_first_read():
    # The screen never stops changing at all (a sustained animation/
    # redraw) -- the freshness gate must time out and refuse to read/act
    # on it, rather than parsing whatever happens to be on screen.
    stages = [(0.05 * i, f"Redrawing frame {i}...\n") for i in range(1, 200)]
    session = SettlingThenReactiveSession(stages, lambda _s, _r: "unreachable")

    result = run_haggle(session, fresh_render_timeout_s=0.5)

    assert result["outcome"] == HaggleOutcome.DESYNC_FALLBACK
    assert result["resolved"] is False
    assert result["final_price"] is None
    assert session.sent == []  # never sends anything against an unsettled render
