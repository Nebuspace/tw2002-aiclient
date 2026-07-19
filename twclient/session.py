"""Session — the live telnet+pyte state a daemon process owns.

Implements the settle-detection protocol (`.rx_count`, `.last_rx`,
`.clock()`, `.sleep()`, `.render_text()`) directly, so `settle.wait_for_settle`
can be handed `self`.
"""

import threading
import time

from .connection import TelnetConnection
from .iac import TelnetHandler
from .logging_util import TranscriptLogger
from .settle import wait_for_settle
from .terminal import TerminalScreen

MIN_SEND_GAP_S = 0.15  # guardrail: no hammering the server


class Session:
    def __init__(self, host, port, name, log_dir):
        self.host = host
        self.port = port
        self.name = name

        self.terminal = TerminalScreen()
        self.negotiator = TelnetHandler()
        self.logger = TranscriptLogger(log_dir)
        self.conn = TelnetConnection(self.host, self.port, self.terminal, self.negotiator, logger=self.logger)

        self.lock = self.conn.lock
        self.send_lock = threading.Lock()
        self._last_send_time = 0.0

        # TX channel (TUI-POLISH-PLAN.md "Core transparency"): the most
        # recent thing sent to the game, threaded through
        # protocol.build_response() so every watch event -- AI-pilot,
        # auto-loop, or attach alike -- can show it, from ONE chokepoint
        # (send()/send_raw() below), the same way build_response() is
        # the single chokepoint on the receive side. `None` until the
        # first send; a `secret=True` send stores the SAME "<redacted>"
        # placeholder protocol.py's history/ledger already use -- never
        # the real password text.
        self.last_sent = None
        self.last_sent_ts = None

        self.history = []  # ring buffer of recent do/read events
        self._history_cap = 200

        # D9 reconnect + login-replay: set once `ensure` succeeds against
        # a profile, so a later drop can be auto-recovered without the
        # caller re-specifying which credential to replay.
        self.auto_login_profile = None

    def start(self, timeout=10):
        self.conn.connect(timeout=timeout)

    def mark_profile(self, profile_name):
        """Record which profile last successfully logged this session in
        -- the SessionGuardian (D9) replays login against this profile
        after an auto-reconnect."""
        self.auto_login_profile = profile_name

    def reconnect(self, timeout=10):
        """D9: tear down a dead telnet connection and establish a fresh
        one to the same host/port. A fresh TerminalScreen + TelnetHandler
        are used (a new TCP connection means the server expects fresh IAC
        negotiation and starts drawing from its own login entry point --
        reusing the old pyte screen would show stale frozen content under
        newly-arriving bytes). The logger and history are preserved so
        the transcript/recent-events stay continuous across the drop."""
        try:
            self.conn.close()
        except Exception:
            pass
        self.terminal = TerminalScreen()
        self.negotiator = TelnetHandler()
        self.conn = TelnetConnection(self.host, self.port, self.terminal, self.negotiator, logger=self.logger)
        self.lock = self.conn.lock
        self.conn.connect(timeout=timeout)

    # -- rendering ---------------------------------------------------

    def render(self):
        with self.lock:
            return self.terminal.render_cropped()

    def render_with_color(self):
        """(rows, color_map) captured under ONE lock acquisition (D13) —
        calling render() and terminal.color_map() as two separate calls
        risks a byte arriving in between, shifting the bounding box and
        producing a color map that no longer lines up with the text."""
        with self.lock:
            return self.terminal.render_cropped(), self.terminal.color_map()

    def render_raw(self):
        with self.lock:
            return self.terminal.raw_display()

    def render_text(self, rows=None):
        return "\n".join(rows if rows is not None else self.render())

    def cursor_pos(self):
        """Thread-safe read of the pyte cursor's {"x","y"} -- the caret
        position `tw attach`'s MANUAL-mode keypress echo draws at. Same
        locking discipline as render()/render_with_color(): the reader
        thread mutates the pyte screen (cursor included) under `self.lock`,
        so any other thread reading it must take the same lock."""
        with self.lock:
            return self.terminal.cursor()

    # -- settle-detection protocol (see settle.wait_for_settle) ------

    @property
    def rx_count(self):
        return self.conn.rx_count

    @property
    def last_rx(self):
        return self.conn.last_rx

    def clock(self):
        return time.monotonic()

    def sleep(self, seconds):
        time.sleep(seconds)

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350):
        return wait_for_settle(self, wait_prompt=wait_prompt, timeout_s=timeout, debounce_ms=debounce_ms)

    # -- sending -------------------------------------------------------

    def send(self, text, enter=True, secret=False):
        with self.send_lock:
            now = time.monotonic()
            delta = now - self._last_send_time
            if delta < MIN_SEND_GAP_S:
                time.sleep(MIN_SEND_GAP_S - delta)
            self.conn.send_text(text, enter=enter, secret=secret)
            self._last_send_time = time.monotonic()
            self.last_sent = "<redacted>" if secret else text
            self.last_sent_ts = self._last_send_time

    def send_raw(self, data: bytes):
        """Exact-byte pass-through for interactive `tw attach` keystrokes
        -- no text encoding, no auto-appended \\r\\n (unlike send()); the
        caller (daemon.py's CommandHandler._handle_attach) has already
        decided the exact wire bytes for this keystroke. Still goes
        through the same send_lock + MIN_SEND_GAP_S anti-hammer
        guardrail as send() -- a human mashing keys deserves the same
        courtesy to the server as a scripted `do`.

        `last_sent` gets the LATIN-1-decoded text (a raw keystroke has no
        `secret` flag of its own -- see interactive_app.py's known
        unredacted-attach-logging limitation; this doesn't newly regress
        anything, just surfaces the same already-unredacted bytes)."""
        with self.send_lock:
            now = time.monotonic()
            delta = now - self._last_send_time
            if delta < MIN_SEND_GAP_S:
                time.sleep(MIN_SEND_GAP_S - delta)
            self.conn.send_bytes(data)
            self._last_send_time = time.monotonic()
            self.last_sent = data.decode("latin-1", errors="replace")
            self.last_sent_ts = self._last_send_time

    # -- history ---------------------------------------------------------

    def record_history(self, verb, args, prompt, classification, settled_reason):
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "verb": verb,
            "args": args,
            "prompt": prompt,
            "classification": classification,
            "settled_reason": settled_reason,
        }
        self.history.append(entry)
        if len(self.history) > self._history_cap:
            self.history.pop(0)

    def close(self):
        self.conn.close()
        self.logger.close()
