"""SessionGuardian — D9 reconnect + login-replay (WO-P2-027).

Canon: `canon/architecture/resilience-and-reconnect.md` (Drop Detection &
Reconnect, Login-Replay & Resume Verification).

A single daemon thread polls session health every few seconds:

- **D9:** if the telnet connection has dropped (`conn.connected is False`)
  AND a profile was recorded via `session.mark_profile()` (set by a prior
  successful `ensure`), the guardian calls `session.reconnect()` then
  replays the SAME login automaton used by `ensure`, using the SAVED
  credential (never regenerating one for an existing character) to land
  back at a *verified* `main_command` — without the driving surface
  needing to notice the drop. Exhaustion / unverified screens fail loud
  (`last_reconnect_error`); never report resume success on an unknown
  screen. Escalate-to-Human keyboard handoff is a follow-up (canon Code
  Divergence); this module records the error and stops the burst.

- **D10 idle-keepalive:** intentionally stubbed here. WO-P2-028 owns the
  `main_command`-only blank Enter nudge. Constructor accepts
  `idle_keepalive_ms` / `classify_screen` for archive API parity so 028
  can fill `_maybe_keepalive` without a signature break; calling it is a
  no-op until then.
"""

from __future__ import annotations

import threading

_POLL_INTERVAL_S = 2.0
_IDLE_KEEPALIVE_MS = 45_000  # reserved for WO-P2-028; unused while stubbed
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
        # store / classifier without touching disk — mirrors login.run_login's
        # DI. Defaults resolve lazily for live daemon use.
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
        # Live credentials.py has no load_profile (WO-P0-005 read-side only).
        # Reuse protocol's ensure-path loader; raise LoginError on failure so
        # _maybe_reconnect's fail-loud catch records it (no CredentialError
        # in the greenfield credentials module — do not invent one here).
        from .login import LoginError
        from .protocol import _load_profile as protocol_load_profile

        def load_profile(name):
            profile, err = protocol_load_profile(name)
            if err is not None:
                raise LoginError(err)
            return profile

        return load_profile

    def _resolve_classify_screen(self):
        # Kept for archive API parity; WO-P2-028 will use this from
        # _maybe_keepalive. Unused while keepalive is stubbed.
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
                # Cipher: type-name only. Unexpected exceptions must not
                # stash str(e) into last_reconnect_error (could embed a
                # secret-bearing payload). Typed reconnect failures below
                # record LoginError/OSError codes only — never passwords.
                self.last_reconnect_error = f"guardian_tick_error:{type(e).__name__}"

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
        from .login import LoginError, run_login

        load_profile = self._resolve_load_profile()

        for attempt in range(self.max_reconnect_attempts):
            if self._stop.is_set():
                return
            try:
                profile = load_profile(session.auto_login_profile)
                session.reconnect()
                # run_login succeeds only when classification == target
                # (verified main_command); otherwise raises LoginError —
                # no false success / blind keystrokes.
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
            except (OSError, LoginError) as e:
                self.last_reconnect_error = str(e)
                self._stop.wait(self.reconnect_backoff_s)
        # Exhausted attempts -- give up until the next drop-detection
        # tick naturally retries (still not connected, so _tick() will
        # call back in here on the next poll). Fail-loud via
        # last_reconnect_error; STOP+Human escalate wiring is follow-up.

    # -- D10 (WO-P2-028) ---------------------------------------------------

    def _maybe_keepalive(self):
        """Stub — idle keepalive is owned by WO-P2-028.

        Connected ticks reach here so the poll loop shape matches the
        archive twin; no keystroke is sent until 028 fills this in.
        `idle_keepalive_ms` / `_resolve_classify_screen` are reserved.
        """
        return
