"""Settle-detection timing tests with a fake clock — no real sleeping."""

from tw2002_aiclient.session.settle import send_and_confirm, wait_for_settle, wait_until_settled


class ScriptedSession:
    """A fake session whose simulated clock only advances via .sleep(),
    and which can be scripted to "receive" bytes at specific simulated
    times — letting us test settle timing deterministically and fast.
    """

    def __init__(self, byte_arrival_times=(), text="", text_changes_at=None):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._pending_arrivals = sorted(byte_arrival_times)
        self._text = text
        self._text_changes_at = text_changes_at  # (time, new_text) or None

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        self._apply_pending()

    def _apply_pending(self):
        while self._pending_arrivals and self._pending_arrivals[0] <= self.t:
            self._pending_arrivals.pop(0)
            self.rx_count += 1
            self.last_rx = self.t
        if self._text_changes_at and self.t >= self._text_changes_at[0]:
            self._text = self._text_changes_at[1]

    def render_text(self):
        return self._text


def test_no_bytes_at_all_hits_timeout():
    s = ScriptedSession()
    reason, elapsed = wait_for_settle(s, timeout_s=1.0, poll_interval_s=0.05)
    assert reason == "timeout"
    assert elapsed >= 1.0


def test_idle_settle_after_debounce_following_a_byte():
    # One byte arrives shortly after send; nothing else follows.
    s = ScriptedSession(byte_arrival_times=[0.1])
    reason, elapsed = wait_for_settle(s, debounce_ms=350, timeout_s=8.0, poll_interval_s=0.04)
    assert reason == "idle"
    # settle should land at ~0.1 + 0.35 = 0.45s, well before the 8s timeout
    assert 0.4 <= elapsed <= 0.6


def test_never_settles_idle_without_any_new_bytes():
    """Idle can only fire once >=1 byte has arrived since the send —
    otherwise a dead connection with zero traffic would look 'settled'.
    """
    s = ScriptedSession()  # no arrivals scheduled
    reason, elapsed = wait_for_settle(s, debounce_ms=50, timeout_s=0.5, poll_interval_s=0.05)
    assert reason == "timeout"


def test_prompt_match_wins_immediately_even_before_any_sleep():
    s = ScriptedSession(text="Command [TL=0100] (?=Help)? :")
    reason, elapsed = wait_for_settle(s, wait_prompt=r"Command \[TL=", timeout_s=8.0)
    assert reason == "prompt"
    assert elapsed == 0.0


def test_wait_prompt_case_mismatch_times_out_never_matches():
    """Canon invariant: wait_prompt is case-sensitive (no IGNORECASE).
    A pattern that differs only in letter case must fall through to
    timeout — never silently match the wrong screen.
    """
    s = ScriptedSession(text="Command [TL=0100] (?=Help)? :")
    reason, elapsed = wait_for_settle(
        s, wait_prompt=r"command \[tl=", timeout_s=0.5, poll_interval_s=0.05
    )
    assert reason == "timeout"
    assert elapsed >= 0.5


def test_prompt_match_arriving_later_beats_idle_and_timeout():
    s = ScriptedSession(
        byte_arrival_times=[0.1, 0.2],
        text="",
        text_changes_at=(0.2, "Password:"),
    )
    reason, elapsed = wait_for_settle(
        s, wait_prompt="Password:", debounce_ms=350, timeout_s=8.0, poll_interval_s=0.04
    )
    assert reason == "prompt"
    assert elapsed < 1.0  # found well before the idle debounce or timeout would fire


def test_timeout_fires_even_with_traffic_if_no_prompt_and_never_idle():
    # Bytes keep arriving faster than the debounce window, so idle never fires.
    s = ScriptedSession(byte_arrival_times=[0.05 * i for i in range(1, 50)])
    reason, elapsed = wait_for_settle(s, debounce_ms=100, timeout_s=1.0, poll_interval_s=0.02)
    assert reason == "timeout"
    assert elapsed >= 1.0


# -- wait_until_settled: the pre-send freshness gate (TW-01 defect #3) --
# Unlike wait_for_settle (which can only detect idleness that occurs
# DURING its own call window -- it requires rx_count to increase past
# the value captured at call-start), wait_until_settled must recognize a
# screen that was ALREADY fully settled before it was ever invoked --
# exactly haggle.py's pre-send use case: the caller is handed a session
# already sitting at a prompt, with no send of its own to wait on.


def test_wait_until_settled_reports_idle_immediately_if_already_quiet_before_the_call():
    s = ScriptedSession(byte_arrival_times=[0.0])
    s.sleep(0.01)  # process the t=0 arrival -- last_rx lands at ~0.01
    s.t = 1.0  # jump the clock directly (bypassing sleep()'s own coarse
    # last_rx-restamping) -- simulates real time having already passed
    # well beyond the debounce window before the gate is ever called
    reason, elapsed = wait_until_settled(s, debounce_ms=350, timeout_s=8.0, poll_interval_s=0.04)
    assert reason == "idle"
    assert elapsed < 0.1  # found on the very first check -- no extra waiting needed


def test_wait_until_settled_keeps_waiting_while_new_bytes_keep_arriving():
    # A burst of arrivals all under the debounce window apart -- must
    # settle debounce_ms after the LAST one, not the first.
    s = ScriptedSession(byte_arrival_times=[0.1, 0.2, 0.3])
    reason, elapsed = wait_until_settled(s, debounce_ms=350, timeout_s=8.0, poll_interval_s=0.04)
    assert reason == "idle"
    assert elapsed >= 0.65


def test_wait_until_settled_times_out_if_traffic_never_goes_quiet():
    s = ScriptedSession(byte_arrival_times=[0.05 * i for i in range(1, 50)])
    reason, elapsed = wait_until_settled(s, debounce_ms=100, timeout_s=1.0, poll_interval_s=0.02)
    assert reason == "timeout"
    assert elapsed >= 1.0


def test_wait_until_settled_never_reports_idle_with_zero_bytes_ever_received():
    # Same guard as wait_for_settle's own idle path -- a connection that
    # has never produced any traffic isn't "settled", it never started.
    s = ScriptedSession()  # no arrivals scheduled at all
    reason, elapsed = wait_until_settled(s, debounce_ms=50, timeout_s=0.3, poll_interval_s=0.05)
    assert reason == "timeout"


# -- send_and_confirm: the send/settle race fix (DESIGN-v2 §8, ELEVATED) --


class StagedSession:
    """A fake session with a scripted (arrival_time, new_text) timeline
    -- unlike ScriptedSession's single `text_changes_at`, this supports
    several successive screen states, needed to script a transitional
    "flickers then changes again" screen for the stability-recheck test.
    Also records every `.send()` call so a test can assert exactly what
    was sent, with what `enter`/`secret`."""

    def __init__(self, stages=(), initial_text=""):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._stages = sorted(stages)
        self._text = initial_text
        self.sent = []

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

    def render_text(self):
        return self._text

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))


def test_send_and_confirm_happy_path_matches_and_stays_stable():
    s = StagedSession(stages=[(0.05, "Your offer [158] ?")])
    reason, elapsed, confirmed = send_and_confirm(s, "158", r"Your\s+offer\s*\[", enter=True, timeout_s=2.0)
    assert reason == "prompt"
    assert confirmed is True
    assert s.sent == [("158", True, False)]


def test_send_and_confirm_passes_enter_false_and_secret_through_to_send():
    # A menu-style selection that must NOT get an auto-appended CRLF --
    # exactly the live phantom-blank-line hazard's fix (DESIGN-v2 §8):
    # the caller controls `enter` per send, no blanket default.
    s = StagedSession(stages=[(0.05, "Command [TL=00753:0/0/0/850] (?=Help)? :")])
    reason, elapsed, confirmed = send_and_confirm(
        s, "A", r"Command\s*\[\s*TL\s*=", enter=False, secret=False, timeout_s=2.0
    )
    assert confirmed is True
    assert s.sent == [("A", False, False)]


def test_send_and_confirm_rejects_a_transient_flicker_not_yet_settled():
    # Regression (DESIGN-v2 §8 -- the hub-warp-animation finding): the
    # confirm_prompt can match on ONE frame of a still-transitioning
    # multi-stage screen and be gone a beat later. Not confirmed unless
    # it's STILL there after one more quiet moment.
    s = StagedSession(stages=[(0.05, "Your offer [158] ?"), (0.12, "Docking...")])
    reason, elapsed, confirmed = send_and_confirm(
        s, "158", r"Your\s+offer\s*\[", enter=True, timeout_s=2.0, stability_pause_s=0.15
    )
    assert reason == "prompt"  # it DID match, transiently
    assert confirmed is False  # ...but wasn't still there on the re-check


def test_send_and_confirm_true_when_prompt_stays_stable_past_the_recheck():
    # Same shape as above, but the next stage arrives well AFTER the
    # stability re-check window -- a genuinely-settled prompt.
    s = StagedSession(stages=[(0.05, "Your offer [158] ?"), (5.0, "Docking...")])
    reason, elapsed, confirmed = send_and_confirm(
        s, "158", r"Your\s+offer\s*\[", enter=True, timeout_s=2.0, stability_pause_s=0.15
    )
    assert confirmed is True


def test_send_and_confirm_never_matching_is_a_safe_desync_not_a_guess():
    # The target prompt never shows up at all (screen moved somewhere
    # unrecognized) -- times out, confirmed=False, NOT a silent
    # idle-settle that hands the caller a screen it never verified.
    s = StagedSession(stages=[(0.05, "some unrelated random event text")])
    reason, elapsed, confirmed = send_and_confirm(s, "158", r"Your\s+offer\s*\[", enter=True, timeout_s=0.3)
    assert reason == "timeout"
    assert confirmed is False
    assert elapsed >= 0.3


# -- TW-02: confirm_prompt=None fallback (replay/play/login's common case,
# no caller-supplied target regex) + the premature-idle fix for the
# confirm_prompt-given path (the hub-warp-animation shape) ------------------


def test_send_and_confirm_none_confirms_via_a_stable_idle_settle():
    s = StagedSession(stages=[(0.05, "Sector : 100")])
    reason, elapsed, confirmed = send_and_confirm(s, "M", confirm_prompt=None, enter=True, timeout_s=2.0)
    assert reason == "idle"
    assert confirmed is True
    assert s.sent == [("M", True, False)]


def test_send_and_confirm_none_rejects_when_more_bytes_arrive_during_the_recheck():
    # The hub-warp-animation shape without a caller-supplied target
    # regex: a debounce-satisfying quiet moment fires "idle", but the
    # screen keeps changing a beat later -- must not be confirmed.
    s = StagedSession(stages=[(0.05, "Docking sequence initiated..."), (0.5, "Docking sequence continues...")])
    reason, elapsed, confirmed = send_and_confirm(s, "M", confirm_prompt=None, enter=True, timeout_s=2.0)
    assert reason == "idle"
    assert confirmed is False


def test_send_and_confirm_retry_unstable_idle_confirms_after_late_paint():
    """WO-SETTLE-EARLY: live 3034→250 / 4571→2429 class — first idle
    fires, hop paint arrives during stability_pause_s (~150ms), then
    screen goes quiet. Default None-mode fail-fast would return
    confirmed=False at ~0.5–0.8s; retry_unstable_idle must confirm
    via wait_until_settled (already-quiet OK) within timeout_s."""
    s = StagedSession(
        stages=[
            (0.05, "Sector  : 3034 in uncharted space.\nCommand [TL=00:00:00]:[3034] (?=Help)? :"),
            (0.50, "Sector  : 250 in uncharted space.\nCommand [TL=00:00:00]:[250] (?=Help)? :"),
        ]
    )
    reason, elapsed, confirmed = send_and_confirm(
        s,
        "250",
        confirm_prompt=None,
        enter=True,
        timeout_s=2.0,
        debounce_ms=350,
        stability_pause_s=0.15,
        retry_unstable_idle=True,
    )
    assert reason == "idle"
    assert confirmed is True
    assert elapsed > 0.5  # past the premature first-idle window
    assert "250" in s.render_text()


def test_send_and_confirm_retry_unstable_idle_still_times_out_when_never_quiet():
    """WO-SETTLE-EARLY Accept: bounded wait — continuous traffic never
    confirms even with retry_unstable_idle."""
    # Bytes every 50ms forever past debounce — never a quiet window.
    stages = [(0.05 * i, f"frame {i}") for i in range(1, 80)]
    s = StagedSession(stages=stages)
    reason, elapsed, confirmed = send_and_confirm(
        s,
        "250",
        confirm_prompt=None,
        enter=True,
        timeout_s=1.0,
        debounce_ms=350,
        stability_pause_s=0.15,
        retry_unstable_idle=True,
    )
    assert confirmed is False
    assert reason in ("timeout", "idle")
    assert elapsed >= 1.0


def test_send_and_confirm_loops_past_a_premature_idle_to_find_the_real_match():
    # The hub-warp-animation shape WITH a caller-supplied target regex:
    # an early, non-matching frame goes quiet long enough to satisfy the
    # debounce window well before the true target text arrives. A bare
    # "idle" with no match must not be treated as a stop condition --
    # the wait keeps going (against the remaining timeout_s budget)
    # until the real confirm_prompt evidence lands, however late.
    s = StagedSession(stages=[(0.05, "Warping..."), (0.9, "Docking complete.")])
    reason, elapsed, confirmed = send_and_confirm(s, "M", r"Docking\s+complete", enter=True, timeout_s=2.0)
    assert reason == "prompt"
    assert confirmed is True


def test_send_and_confirm_prompt_given_still_times_out_when_never_matched():
    # Companion to the above: looping past a premature idle must still
    # be BOUNDED by timeout_s, not an unbounded wait, when the target
    # genuinely never arrives.
    s = StagedSession(stages=[(0.05, "Warping..."), (0.9, "Still warping...")])
    reason, elapsed, confirmed = send_and_confirm(s, "M", r"Docking\s+complete", enter=True, timeout_s=1.0)
    assert reason == "timeout"
    assert confirmed is False
    assert elapsed >= 1.0


# -- P0 finding 1: stale pre-send confirm_prompt match ----------------------
#
# wait_for_settle's own match-wins-immediately-at-t0 contract is correct
# and deliberate for a caller-driven --wait-prompt poll (test above) --
# but send_and_confirm must NEVER let a confirm_prompt match against
# content that was already on screen BEFORE this call's own send() count
# as confirmation. The realistic failure shape: haggle's repeating
# "Your offer [N] ?" prompt is still showing the PREVIOUS round's value
# when the NEXT round's send_and_confirm is invoked -- the real server's
# response hasn't arrived yet, but the regex already matches.


def test_send_and_confirm_rejects_a_stale_confirm_prompt_match_predating_this_send():
    s = StagedSession(
        initial_text="We'll buy them for 2,214 credits.\nYour offer [2,214] ? ",
        stages=[(0.5, "We'll buy them for 2,216 credits.\nYour offer [2,216] ? ")],
    )
    reason, elapsed, confirmed = send_and_confirm(s, "2450", r"Your\s+offer\s*\[", enter=True, timeout_s=8.0)
    assert reason == "prompt"
    assert confirmed is True
    assert s.sent == [("2450", True, False)]
    # Confirmed only once the genuinely NEW response landed (t=0.5) --
    # never against the stale pre-send content sitting there at t=0.
    assert elapsed >= 0.5


def test_send_and_confirm_never_confirms_on_pre_send_content_with_nothing_new_arriving():
    # Companion: if truly NOTHING new ever arrives after the send (the
    # stale content just sits there unchanged forever), the stale-match
    # guard must not spin the wait forever either -- still bounded by
    # timeout_s like every other desync case.
    s = StagedSession(initial_text="Your offer [2,214] ? ")
    reason, elapsed, confirmed = send_and_confirm(s, "2450", r"Your\s+offer\s*\[", enter=True, timeout_s=0.3)
    assert reason == "timeout"
    assert confirmed is False
    assert elapsed >= 0.3


def test_send_and_confirm_none_mode_never_idle_confirms_with_zero_bytes_since_send():
    # Companion check for the confirm_prompt=None fallback path: it
    # already requires session.rx_count to increase past the count
    # captured at THIS call's own start (wait_for_settle's own guard,
    # called immediately after send() with no intervening sleep) --
    # verified explicitly here since it was previously only exercised
    # via wait_for_settle directly, never through send_and_confirm's own
    # call site.
    s = StagedSession(initial_text="Sector : 100")
    reason, elapsed, confirmed = send_and_confirm(s, "M", confirm_prompt=None, enter=True, timeout_s=0.3)
    assert reason == "timeout"
    assert confirmed is False
