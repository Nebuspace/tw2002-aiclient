"""SessionGuardian — D9 reconnect + login-replay, and D10 conservative
idle-keepalive (WO-P2-027 + WO-P2-028).

Canon: `canon/architecture/resilience-and-reconnect.md` (Drop Detection &
Reconnect, Login-Replay & Resume Verification, Conservative Idle-Keepalive).

A single daemon thread polls session health every few seconds:

- **D9:** if the telnet connection has dropped (`conn.connected is False`)
  AND a profile was recorded via `session.mark_profile()` (set by a prior
  successful `ensure`), the guardian calls `session.reconnect()` then
  replays the SAME login automaton used by `ensure`, using the SAVED
  credential (never regenerating one for an existing character) to land
  back at a *verified* `main_command` — without the driving surface
  needing to notice the drop. Exhaustion / unverified screens fail loud
  (`last_reconnect_error`); never report resume success on an unknown
  screen. After ``max_reconnect_attempts`` fails, a sticky
  ``reconnect_exhausted`` flag suppresses further auto-retry until a
  successful reconnect (or ``clear_reconnect_exhausted``) — the status
  verb surfaces typed reason ``reconnect_exhausted`` for the STOP banner.
  No auto-MODE_HUMAN from this path (keyboard escalate stays manual).

- **D10:** when the session has been idle past `idle_keepalive_ms` (default
  45s, under the observed first inactivity warning), send a harmless blank
  Enter — but ONLY when the current screen classifies as `main_command`.
  Never on password / trade / confirm / combat / unknown (a stray Enter
  could accept a default purchase or desync a credential prompt). Actor-
  tagged `app`, with a Trace-Ledger row when a `ledger` is injected
  (WO-GUARDIAN-KEEPALIVE-LEDGER). ≤ one send per idle window (send resets
  the idle anchor).
  Disconnected / reconnect-in-flight ticks never nudge (`_tick` routes
  drops to D9; `_reconnect_in_flight` + connected guard block D10 mid-burst).
"""

from __future__ import annotations

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
        ledger=None,
    ):
        self.session = session
        self.get_password = get_password
        self.save_password = save_password
        # Optional Trace-Ledger (daemon passes LedgerWriter). Keepalive
        # bypasses protocol.dispatch, so rows are written here directly.
        self.ledger = ledger
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
        # Sticky after a full reconnect burst fails (WO-FIX-SESSIONGUARDIAN-
        # EXHAUSTED-RECONNECT-SILENT). Suppresses silent forever-retry while
        # disconnected; cleared on successful reconnect / explicit clear /
        # observing connected again (manual ensure).
        self.reconnect_exhausted = False
        # Set for the whole reconnect+replay burst so D10 cannot nudge
        # while connected has flipped True mid-login (password screen, etc.).
        self._reconnect_in_flight = False
        # Idle-window anchor for D10: after a keepalive send, suppress
        # further nudges until idle rebuilds from this mono stamp (RX echo
        # may also advance last_rx; we take the later of the two).
        self._last_keepalive_mono = None

    def clear_reconnect_exhausted(self) -> None:
        """Allow another auto-reconnect burst (operator / ensure cleared)."""
        self.reconnect_exhausted = False

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
        if session.conn.connected:
            # Manual ensure/reconnect may restore the socket outside D9 —
            # drop the sticky escalate so status stops claiming exhaustion.
            if self.reconnect_exhausted:
                self.clear_reconnect_exhausted()
            self._maybe_keepalive()
            return
        self._maybe_reconnect()

    # -- D9 ----------------------------------------------------------------

    def _maybe_reconnect(self):
        session = self.session
        if not session.auto_login_profile:
            return  # never seen a successful login -- nothing to replay
        if self.reconnect_exhausted:
            return  # sticky: no silent forever-retry (status surfaces it)
        from .login import LoginError, run_login

        load_profile = self._resolve_load_profile()
        self._reconnect_in_flight = True
        try:
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
                    self.reconnect_exhausted = False
                    return
                except (OSError, LoginError) as e:
                    self.last_reconnect_error = str(e)
                    self._stop.wait(self.reconnect_backoff_s)
            # Exhausted attempts — sticky fail-loud (not silent poll-retry).
            # status["intervention"] carries code reconnect_exhausted; no
            # auto-MODE_HUMAN (keyboard escalate stays operator-driven).
            self.reconnect_exhausted = True
        finally:
            self._reconnect_in_flight = False

    # -- D10 (WO-P2-028) ---------------------------------------------------


    def _record_keepalive_ledger(self, pre_text: str) -> None:
        """Append one Trace-Ledger row for a D10 keepalive send. Never raises."""
        ledger = self.ledger
        if ledger is None:
            return
        session = self.session
        try:
            from types import SimpleNamespace

            from .protocol import _record_ledger

            post_text = session.render_text(session.render())
            rows = session.render()
            prompt = rows[-1].strip() if rows else ""
            classify_screen = self._resolve_classify_screen()
            settled = classify_screen(post_text, prompt)
            resp = {
                "screen": post_text.splitlines(),
                "classification": settled if isinstance(settled, str) else "unknown",
            }
            server = SimpleNamespace(ledger=ledger, control_lock=None)
            _record_ledger(
                server,
                session,
                pre_text,
                "",
                secret=False,
                resp=resp,
                actor="app",
            )
        except Exception:  # noqa: BLE001 -- ledger must never kill the guardian tick
            return

    def _maybe_keepalive(self):
        session = self.session
        # Drop path owns the poll: never nudge while disconnected or while
        # reconnect+replay is mid-burst (connected may be True after
        # reconnect() but before verified main_command).
        if not session.conn.connected or self._reconnect_in_flight:
            return
        # Idle clock: later of last RX and last keepalive send so a fire
        # resets the window even before the server echo updates last_rx.
        idle_anchor = session.last_rx
        if self._last_keepalive_mono is not None:
            idle_anchor = max(idle_anchor, self._last_keepalive_mono)
        idle_ms = (time.monotonic() - idle_anchor) * 1000
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
            # WO-GUARDIAN-KEEPALIVE-LEDGER: pre-send screen for Trace-Ledger
            # (keepalive never enters protocol.dispatch / _record_ledger).
            pre_text = text
            session.send("", enter=True, secret=False, sender="app")
            self._last_keepalive_mono = time.monotonic()
            self._record_keepalive_ledger(pre_text)
        except OSError:
            pass  # mid-drop — D9 picks it up next tick; do not stamp
