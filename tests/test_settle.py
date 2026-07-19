"""Settle-detection timing tests with a fake clock — no real sleeping."""

from twclient.settle import send_and_confirm, wait_for_settle, wait_until_settled


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
