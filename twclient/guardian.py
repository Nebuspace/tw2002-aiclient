"""SessionGuardian — D9 reconnect + login-replay, and D10 conservative
idle-keepalive (DESIGN-v2.md §3 v2.1 item 4).

Both are "poll session health every few seconds" background concerns, so
they share one thread rather than running two redundant pollers:

- **D9 (the credential-mismatch fix):** if the telnet connection has dropped (server
  kick, network blip) AND a profile was recorded via
  `session.mark_profile()` (set by a prior successful `ensure`), the
  guardian calls `session.reconnect()` then replays the SAME login
  automaton used by `ensure` (B1), using the SAVED credential (never
  regenerating one for an existing character) to land back at
  `main_command` automatically -- without the LLM/CLI needing to notice
  the drop and re-issue anything.
- **D10:** when the session has been idle (no bytes in either direction)
  past `_IDLE_KEEPALIVE_MS`, send a harmless blank keystroke to reset the
  server's inactivity clock -- but ONLY when the current screen
  classifies as `main_command`. This is deliberately the single safest
  screen: never on login_password (would desync a pending credential
  prompt), never on port_trade/computer/sector_display (a stray blank
  Enter could accept an unintended default -- e.g. "How many holds...
  [50]?" defaults to buying 50). The observed live INACTIVITY WARNING
  sequence is "Sixty seconds" -> "Thirty seconds" -> "TEN seconds" ->
  terminated (session logs), so the keepalive threshold is set well
  under the first warning.
"""

import threading
import time

_POLL_INTERVAL_S = 2.0
_IDLE_KEEPALIVE_MS = 45_000  # comfortably under the observed 60s first warning
_RECONNECT_BACKOFF_S = 3.0
_MAX_RECONNECT_ATTEMPTS = 5


class SessionGuardian:
    def __init__(
        self,
        session,
        get_password,
        save_password,
        load_profile=None,
        classify_screen=None,
        poll_interval_s=_POLL_INTERVAL_S,
        idle_keepalive_ms=_IDLE_KEEPALIVE_MS,
        reconnect_backoff_s=_RECONNECT_BACKOFF_S,
        max_reconnect_attempts=_MAX_RECONNECT_ATTEMPTS,
    ):
        self.session = session
        self.get_password = get_password
        self.save_password = save_password
        # Injected (not hard-imported) so tests can supply a fake profile
        # store / classifier without touching disk or twclient.classify's
        # real anchor table — mirrors login.run_login's DI for the same
        # reason. Defaults to the real implementations for live use.
        self._load_profile = load_profile
        self._classify_screen = classify_screen
        self.poll_interval_s = poll_interval_s
        self.idle_keepalive_ms = idle_keepalive_ms
        self.reconnect_backoff_s = reconnect_backoff_s
        self.max_reconnect_attempts = max_reconnect_attempts
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self.last_reconnect_error = None
        self.reconnect_count = 0

    def _resolve_load_profile(self):
        if self._load_profile is not None:
            return self._load_profile
        from .credentials import load_profile

        return load_profile

    def _resolve_classify_screen(self):
        if self._classify_screen is not None:
            return self._classify_screen
        from .classify import classify_screen

        return classify_screen

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            self._stop.wait(self.poll_interval_s)
            if self._stop.is_set():
                return
            try:
                self._tick()
            except Exception as e:  # noqa: BLE001 — a guardian hiccup must never kill the daemon
                self.last_reconnect_error = str(e)

    def _tick(self):
        session = self.session
        if not session.conn.connected:
            self._maybe_reconnect()
            return
        self._maybe_keepalive()

    # -- D9 ----------------------------------------------------------------

    def _maybe_reconnect(self):
        session = self.session
        if not session.auto_login_profile:
            return  # never seen a successful login -- nothing to replay
        from .credentials import CredentialError
        from .login import LoginError, run_login

        load_profile = self._resolve_load_profile()

        for attempt in range(self.max_reconnect_attempts):
            if self._stop.is_set():
                return
            try:
                profile = load_profile(session.auto_login_profile)
                session.reconnect()
                run_login(
                    session,
                    profile,
                    get_password=self.get_password,
                    save_password=self.save_password,
                    target="main_command",
                )
                self.reconnect_count += 1
                self.last_reconnect_error = None
                return
            except (OSError, LoginError, CredentialError) as e:
                self.last_reconnect_error = str(e)
                self._stop.wait(self.reconnect_backoff_s)
        # Exhausted attempts -- give up until the next drop-detection
        # tick naturally retries (still not connected, so _tick() will
        # call back in here on the next poll).

    # -- D10 -----------------------------------------------------------------

    def _maybe_keepalive(self):
        session = self.session
        idle_ms = (time.monotonic() - session.last_rx) * 1000
        if idle_ms < self.idle_keepalive_ms:
            return
        text = session.render_text()
        rows = session.render()
        prompt = rows[-1].strip() if rows else ""
        classify_screen = self._resolve_classify_screen()

        cls = classify_screen(text, prompt)
        if cls != "main_command":
            return  # conservative: only ever nudge the single safest screen
        try:
            session.send("", enter=True, secret=False)
        except OSError:
            pass  # a send failing here just means we're mid-drop -- D9 picks it up next tick
