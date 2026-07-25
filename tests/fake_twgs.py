"""A scripted fake TWGS telnet server -- the no-real-game harness
WO-P2-020's Accept rides on (see `test_ensure_from_play.py`).

Speaks PLAIN TEXT, not real telnet IAC: the client side (`session/iac.py`'s
`TelnetHandler`) already answers WILL/WONT/DO/DONT + TTYPE/NAWS entirely on
its own, so a fake server that never sends any IAC bytes at all still
drives the client through a normal connect -- there is nothing here to
negotiate. Every screen is CP437/ASCII-safe plain text, `\\r\\n`-terminated
per line except the CURRENT prompt line (no trailing newline -- that's what
makes it "the thing the server is blocked waiting on", per classify.py's
own gate-anchor docstring).

Four scenario `mode`s (WO-P2-023): `"returning"` (default, described below),
`"new"` (full NEW-registration arc -- char_create -> Y -> password CREATE
(captures whatever the client sends, since the automaton GENERATES it --
never checked against a fixed value -- and verifies the "repeat to verify"
resend is byte-identical) -> trader name (B) -> ship name/confirm -> planet
name -> planet command (Q) -> main_command; captured generated password
exposed as `.generated_password`), `"refused"` (presents char_create then
verifies the connection receives NOT ONE byte afterward -- login.py's
`allow_register=False` guard raises BEFORE any send; result exposed as
`.received_after_char_create`), and `"wrong_password"` (RETURNING pre-login,
then re-presents `Password?` ONCE more after the client's single send --
exercises the RETURNING branch's fail-fast, send-once ceiling, canon:
`login-automaton.md`; the one received attempt recorded in
`.received_passwords`). NEW-arc screen text lifted from the archive's own
proven fixtures (`archive/pre-rebirth-2026-07-23/code/tests/test_login.py`'s
`_new_registration_steps`), same discipline as the RETURNING text below.

`"returning"`-only resume knobs (WO-P2-024, idempotent-resume proof, canon:
`login-automaton.md`'s "Idempotent resume" section): `start_at=<step>`
begins the CONNECTION already presenting a given pre-login screen (one of
`_PRE_LOGIN_STEPS` below) as the very FIRST thing sent, skipping every
earlier step entirely -- simulating a socket a prior partial drive already
carried mid-flow, the shape a fresh `ensure` against an already-mid-flow
session sees. Since the automaton is reactive/screen-keyed rather than
step-counted (`_decide()` dispatches on the CURRENT classification only),
it needs no special-casing to resume from here -- proving that IS the
point. `restale_game_select=True` re-presents a STALE, un-cleared
`"Select a game :"` screen once, right after the real game_select is
answered and the flow has genuinely moved on to module_entry_menu -- a
redraw/scrollback-glitch shape, not a second real door-select -- exercising
`session.game_select_answered`'s no-double-answer refusal in `login.py`'s
`_decide()` (returns `None`, the same "nothing matched" signal any other
unrecognized screen produces, rather than re-sending the letter). Both
raise `ValueError` at construction time if combined with a non-`"returning"`
mode -- neither knob has meaning for the NEW/refused/wrong_password arcs.

Every scripted step's received input is ALSO captured generically on
`.received_inputs` (`dict[label, list[str]]`, append-only, same `label`
strings passed to `_expect_line`/`_expect_key`/`_capture_line`) -- lets a
test assert a given step fired EXACTLY ONCE (or not at all, for a skipped
`start_at` prefix) without needing a dedicated field per step the way
`.received_passwords`/`.generated_password` already are for the
password-specific steps.

State machine (RETURNING flow -- the primary/default path; see above for the
other three `mode`s):

  connect
    -> OUTER_NAME   "Please enter your name (ENTER for none):"
         expects a blank line (classify_screen: login_name, the
         "(ENTER for none)" branch in login.py's _decide -> blank)
    -> GAME_SELECT   "<F> Bob the Builder\\nSelect a game :"
         expects exactly ONE byte, no CRLF (classify_screen: game_select --
         login.py sends menu-style single-key selections with no trailing
         Enter, settle.py's own documented phantom-blank-line hazard)
    -> MODULE_MENU   "T - Play Trade Wars 2002\\nI - Introduction & Help\\n
                       Enter your choice:"
         expects a line (classify_screen: menu, via the dash-style option
         anchor -- login.py's _MODULE_ENTRY_MENU_RE)
    -> LOGIN_NAME    "What is your name?"
         expects a line (classify_screen: login_name, the character-handle
         branch -- profile.handle)
    -> ANSI_PROMPT   "Use ANSI graphics?"
         expects a line (classify_screen: ansi_prompt -- always "Y")
    -> SHOW_LOG      "Show today's log? (Y/N) [N]"
         expects a line (no classify.py gate anchor of its own --
         login.py's _SHOW_LOG_RE matches the whole screen text ahead of
         the ordinary classification dispatch -- always "N")
    -> LOGIN_PASSWORD "Password?"
         expects a line, SECRET (classify_screen: login_password -- the
         profile's saved/env credential)
    -> MAIN_COMMAND  "Hello <handle>, welcome to:\\r\\nCommand [TL=00:00:00]:
                       [24146] (?=Help)? :"
         terminal state -- no further script step. The welcome banner and
         the settled `Command [TL=...]` prompt are sent as ONE write (a
         real TWGS pushes the post-login banner unsolicited, immediately
         followed by the settled prompt); `send_and_confirm`'s idle-only
         confirmation (login.py never supplies a `confirm_prompt`) just
         needs the byte stream to go quiet after this, which one write
         naturally satisfies.

Screen text lifted from the archive's own live-captured RETURNING-branch
fixture (`archive/pre-rebirth-2026-07-23/code/tests/test_login.py::
test_returning_login_uses_saved_password_and_skips_registration`) --
proven-correct against the real automaton, not invented here.
"""

from __future__ import annotations

import errno
import socket
import threading
import time

# Teardown races under pytest-xdist: stop() closes sockets while the accept
# thread is mid-send/recv. Those OSErrors are not script failures — treat as
# ordinary peer-closed, never append to `.errors` (which many tests assert empty).
_TEARDOWN_ERRNOS = frozenset(
    {
        errno.EBADF,
        errno.ECONNRESET,
        errno.ENOTCONN,
        errno.EPIPE,
        getattr(errno, "ECONNABORTED", -1),
        getattr(errno, "ESHUTDOWN", -1),
    }
)


def _is_teardown_oserror(exc: BaseException) -> bool:
    if isinstance(exc, ConnectionError):
        return True
    if not isinstance(exc, OSError):
        return False
    return exc.errno in _TEARDOWN_ERRNOS or exc.errno is None


class ScriptMismatch(Exception):
    """A scripted step received input that didn't match what the login
    automaton is documented to send at that step -- recorded on
    `FakeTWGS.errors` rather than raised in the server thread (an
    exception there would just vanish silently), so the test can assert
    the harness itself stayed in sync."""


class _Reader:
    """Small buffered reader over one client socket -- supports both
    line-terminated reads (`\\r\\n`, every scripted step except
    game_select) and exact-byte reads (game_select's single, un-terminated
    key), off the SAME buffer, since both shapes can occur on the same
    connection."""

    def __init__(self, sock: socket.socket):
        self._sock = sock
        self._buf = bytearray()

    def _fill(self):
        try:
            chunk = self._sock.recv(4096)
        except OSError as e:
            if _is_teardown_oserror(e):
                raise ConnectionError("peer closed") from e
            raise
        if not chunk:
            raise ConnectionError("peer closed")
        self._buf.extend(chunk)

    def read_line(self) -> bytes:
        while b"\r\n" not in self._buf:
            self._fill()
        line, _, rest = bytes(self._buf).partition(b"\r\n")
        self._buf = bytearray(rest)
        return line

    def read_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            self._fill()
        data = bytes(self._buf[:n])
        self._buf = self._buf[n:]
        return data


class FakeTWGS:
    """A scripted, single-connection fake TWGS server. Context-manager
    preferred (`with FakeTWGS(...) as fake:`); `start()`/`stop()` also
    usable directly for a fixture that needs finer-grained lifetime
    control. Reusable across tests -- construct a fresh instance per test,
    never share one live server between tests."""

    # The 6 pre-login screens, in their natural (cold-start) order -- see
    # `_run_pre_login`'s `start_at` handling and the module docstring's
    # resume-knobs paragraph.
    _PRE_LOGIN_STEPS = (
        "outer_name",
        "game_select",
        "module_entry_menu",
        "login_name",
        "ansi_prompt",
        "show_log",
    )

    def __init__(
        self,
        *,
        handle: str,
        game_letter: str,
        password: str,
        host: str = "127.0.0.1",
        mode: str = "returning",
        ship_name: str | None = None,
        planet_name: str | None = None,
        post_password_delay_s: float = 0.0,
        start_at: str | None = None,
        restale_game_select: bool = False,
    ):
        self.handle = handle
        self.game_letter = game_letter
        self.password = password
        self.host = host
        self.mode = mode
        self.ship_name = ship_name or f"{handle}Ship"
        self.planet_name = planet_name or f"{handle}World"
        # "returning" mode only (WO-P2-023 fail-fast fix, Mack HIGH):
        # models a slow/two-stage post-password server response -- an
        # early ack byte that still renders as the SAME `login_password`
        # gate, held for this many seconds before the real next screen
        # (welcome + main_command) arrives. 0.0 (default) is the
        # already-proven instant-response shape every other test uses.
        self.post_password_delay_s = post_password_delay_s
        # "returning" mode only (WO-P2-024 resume knobs -- see module
        # docstring): fail loud at construction time rather than silently
        # ignoring a knob that has no meaning for the other 3 arcs.
        if (start_at is not None or restale_game_select) and mode != "returning":
            raise ValueError("start_at/restale_game_select are only meaningful for mode='returning'")
        if start_at is not None and start_at not in self._PRE_LOGIN_STEPS:
            raise ValueError(f"unknown start_at step: {start_at!r} (expected one of {self._PRE_LOGIN_STEPS!r})")
        self.start_at = start_at
        self.restale_game_select = restale_game_select
        self.errors: list[str] = []

        # -- mode-specific outcomes, populated by the matching _run_* method
        # (see module docstring) -- left at their default until that mode's
        # script actually runs.
        self.generated_password: str | None = None  # "new"
        self.received_after_char_create: bool | None = None  # "refused"
        self.received_passwords: list[str] = []  # "wrong_password"
        # Generic per-label capture, additive alongside the two fields
        # above -- see module docstring's resume-knobs paragraph.
        self.received_inputs: dict[str, list[str]] = {}

        self._listener: socket.socket | None = None
        self._port: int | None = None
        self._accept_thread: threading.Thread | None = None
        self._client_conn: socket.socket | None = None
        self._stop = threading.Event()

    @property
    def port(self) -> int:
        if self._port is None:
            raise RuntimeError("FakeTWGS not started")
        return self._port

    def __enter__(self) -> "FakeTWGS":
        self.start()
        return self

    def __exit__(self, *exc_info):
        self.stop()

    def start(self):
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind((self.host, 0))
        self._listener.listen(1)
        self._port = self._listener.getsockname()[1]
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()

    def stop(self):
        self._stop.set()
        # Close client first so a blocked recv/send wakes; then the listener
        # so a blocked accept returns. Join after both closes.
        for sock in (self._client_conn, self._listener):
            if sock is None:
                continue
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=5.0)
        self._accept_thread = None
        self._listener = None
        self._client_conn = None

    # -- server loop -------------------------------------------------------

    def _accept_loop(self):
        listener = self._listener
        if listener is None:
            return
        try:
            conn, _addr = listener.accept()
        except OSError:
            return  # listener closed under us (stop() during teardown)
        self._client_conn = conn
        try:
            self._run_script(conn)
        except ConnectionError:
            pass  # ordinary peer-closed teardown -- not a script failure
        except OSError as e:
            if _is_teardown_oserror(e) or self._stop.is_set():
                return
            self.errors.append(f"{type(e).__name__}: {e}")
        except Exception as e:  # noqa: BLE001 -- a script bug must surface
            # via .errors, never crash this daemon thread silently.
            if self._stop.is_set() and _is_teardown_oserror(e):
                return
            self.errors.append(f"{type(e).__name__}: {e}")

    def _run_script(self, conn: socket.socket):
        reader = _Reader(conn)
        runner = {
            "returning": self._run_returning,
            "new": self._run_new,
            "refused": self._run_refused,
            "wrong_password": self._run_wrong_password,
        }.get(self.mode)
        if runner is None:
            raise ValueError(f"unknown FakeTWGS mode: {self.mode!r}")
        runner(conn, reader)

    def _run_pre_login(self, conn: socket.socket, reader: "_Reader"):
        """The 6 screens common to every mode -- outer name through
        show-log -- identical regardless of which branch (RETURNING vs
        NEW vs refused) comes next.

        `self.start_at` (returning-only, see module docstring) skips every
        step BEFORE it entirely -- the connection's very first bytes are
        the resumed screen, never the cold-start prefix -- proving the
        automaton needs no special-casing to pick up mid-flow.

        `self.restale_game_select` (returning-only) re-presents a STALE,
        un-cleared "Select a game :" screen once, right after the real
        game_select has been answered and module_entry_menu's own reply
        ("T") has been read -- i.e. the flow has genuinely LEFT
        game_select already (the precondition `session.game_select_
        answered` itself requires). No `_expect_*` read follows the stale
        send: `login.py`'s `_decide()` refuses it (returns `None`), so the
        client sends nothing back at all -- the server just holds long
        enough for the automaton's own idle-settle grace to observe the
        stale screen as genuinely settled (and for send_and_confirm's
        confirm of the PRECEDING "T" send to resolve against it) before
        moving on to the real next screen, `login_name`. The sleep here
        is real wall-clock margin around `settle.py`'s 350ms debounce +
        150ms stability-pause (send_and_confirm) so the stale screen is
        never overwritten before either confirm can observe it settled.
        """
        steps = self._PRE_LOGIN_STEPS
        if self.start_at is not None:
            steps = steps[steps.index(self.start_at) :]

        if "outer_name" in steps:
            self._send(conn, "Please enter your name (ENTER for none):")
            self._expect_line(reader, expected="", label="outer_name")

        if "game_select" in steps:
            self._send(conn, f"<{self.game_letter}> Bob the Builder\r\nSelect a game :")
            self._expect_key(reader, expected=self.game_letter, label="game_select")

        if "module_entry_menu" in steps:
            self._send(conn, "T - Play Trade Wars 2002\r\nI - Introduction & Help\r\nEnter your choice:")
            self._expect_line(reader, expected="T", label="module_entry_menu")

            if self.restale_game_select:
                self._send(conn, f"<{self.game_letter}> Bob the Builder\r\nSelect a game :")
                time.sleep(1.0)

        if "login_name" in steps:
            self._send(conn, "What is your name?")
            self._expect_line(reader, expected=self.handle, label="login_name")

        if "ansi_prompt" in steps:
            self._send(conn, "Use ANSI graphics?")
            self._expect_line(reader, expected="Y", label="ansi_prompt")

        if "show_log" in steps:
            self._send(conn, "Show today's log? (Y/N) [N]")
            self._expect_line(reader, expected="N", label="show_log")

    def _run_returning(self, conn: socket.socket, reader: "_Reader"):
        self._run_pre_login(conn, reader)

        self._send(conn, "Password?")
        # The password is checked for exact match (correctness proof, not
        # just presence) but NEVER logged/printed/stored anywhere beyond
        # this local comparison -- see module docstring's redaction note.
        self._expect_line(reader, expected=self.password, label="login_password")
        # Also recorded on `.received_passwords` (shared with wrong_password
        # mode) so a test can assert "sent exactly once" against a concrete
        # value rather than only the equality check above.
        self.received_passwords.append(self.password)

        if self.post_password_delay_s > 0:
            # Slow/two-stage post-password response (WO-P2-023 fail-fast
            # fix, Mack HIGH): an early ack that re-presents the SAME
            # `login_password` gate -- the identical transient signal a
            # genuine rejection produces -- held for `post_password_delay_s`
            # before the REAL next screen arrives. Proves login.py's
            # stagnation-grace resolves this correctly instead of
            # false-rejecting a legitimate, merely-slow login.
            self._send(conn, "Password?")
            time.sleep(self.post_password_delay_s)

        self._send_welcome_and_hold(conn)

    def _run_new(self, conn: socket.socket, reader: "_Reader"):
        """Full NEW-registration arc -- see module docstring. The password
        CREATE/repeat screens ACCEPT/CAPTURE whatever the client sends
        (the automaton GENERATES it, so a fixed-value check would always
        fail) rather than comparing against `self.password`."""
        self._run_pre_login(conn, reader)

        self._send(
            conn,
            "You were not found in the player database.\r\n"
            "Would you like to start a new character in this game?  (Type Y or N)",
        )
        self._expect_line(reader, expected="Y", label="char_create")

        self._send(conn, "Please enter a password for this game account.\r\nPassword?")
        self.generated_password = self._capture_line(reader, label="password_create")

        self._send(conn, "Repeat password to verify.\r\nPassword?")
        repeat = self._capture_line(reader, label="password_repeat")
        if repeat != self.generated_password:
            self.errors.append(
                f"password_repeat: expected identical resend {self.generated_password!r}, got {repeat!r}"
            )

        self._send(
            conn,
            "Do you wish to make up a new Alias for your Trader Name,\r\n"
            f"or would you rather use your BBS name of {self.handle}?\r\n"
            "Use (N)ew Name or (B)BS Name [B] ?",
        )
        self._expect_line(reader, expected="B", label="trader_name_choice")

        self._send(conn, "What do you want to name your ship? (30 letters)")
        self._expect_line(reader, expected=self.ship_name, label="ship_name")

        self._send(conn, f"{self.ship_name} is what you want?")
        self._expect_line(reader, expected="Y", label="ship_confirm")

        self._send(
            conn,
            "What do you want to name your home planet? (Class K-BE, Desert wasteland)\r\n"
            "[---------------------------------------]",
        )
        self._expect_line(reader, expected=self.planet_name, label="planet_name")

        self._send(conn, "Planet command (?=help) [D]")
        self._expect_line(reader, expected="Q", label="planet_command")

        self._send_welcome_and_hold(conn)

    def _run_refused(self, conn: socket.socket, reader: "_Reader"):
        """`allow_register=False`: char_create's hard-gate must raise
        BEFORE sending a single byte -- proven by verifying the connection
        receives NOTHING after this screen is presented (see module
        docstring; `.received_after_char_create`)."""
        self._run_pre_login(conn, reader)

        self._send(
            conn,
            "You were not found in the player database.\r\n"
            "Would you like to start a new character in this game?  (Type Y or N)",
        )
        self._expect_silence(conn, reader, wait_s=3.0, label="char_create_refused")

        while not self._stop.is_set():
            try:
                chunk = conn.recv(4096)
            except OSError:
                return
            if not chunk:
                return

    def _run_wrong_password(self, conn: socket.socket, reader: "_Reader"):
        """RETURNING pre-login, then re-presents `Password?` ONCE more
        after the client's single send -- exercising the RETURNING
        branch's fail-fast, send-once ceiling (canon:
        `login-automaton.md`): the automaton must treat this reappearance
        as a rejection and raise immediately, never re-sending the
        already-known-bad saved value. `.received_passwords` is populated
        with exactly the one attempt for a correctly-behaving automaton --
        a second entry would mean it re-sent instead of failing loud."""
        self._run_pre_login(conn, reader)

        self._send(conn, "Password?")
        try:
            line = reader.read_line().decode("cp437", errors="replace")
        except ConnectionError:
            return
        self.received_passwords.append(line)
        self._record("login_password", line)

        # Re-present the SAME gate -- the rejection signal the RETURNING
        # branch's fail-fast ceiling reacts to. If the automaton instead
        # re-sends (a regression), that 2nd send lands here uncounted --
        # left unread, since the client is expected to have already
        # raised and closed by the time anything more could arrive.
        self._send(conn, "Password?")

        while not self._stop.is_set():
            try:
                chunk = conn.recv(4096)
            except OSError:
                return
            if not chunk:
                return

    def _send_welcome_and_hold(self, conn: socket.socket):
        # Terminal state: unsolicited welcome banner immediately followed
        # by the settled main_command prompt, ONE write -- see module
        # docstring. No trailing "\r\n" after the prompt: it's the
        # currently-active blocking prompt, not a completed line.
        self._send(conn, f"Hello {self.handle}, welcome to:\r\nCommand [TL=00:00:00]:[24146] (?=Help)? :")

        # Stay connected and quiet past login -- a 2nd `ensure` (the
        # idempotency Accept criterion) re-classifies the already-settled
        # screen without sending anything new, and a daemon `stop`'s
        # best-effort graceful QUIT ("Q"/"Y") is harmless to leave unread
        # on the wire when the test tears down via SIGTERM instead.
        while not self._stop.is_set():
            try:
                chunk = conn.recv(4096)
            except OSError:
                return
            if not chunk:
                return

    # -- scripted step helpers ---------------------------------------------

    def _send(self, conn: socket.socket, text: str):
        # Leading ANSI clear-screen + cursor-home (`ESC[2J ESC[H`): a real
        # TWGS door clears/redraws between major screens (or at minimum
        # echoes the client's own Enter, advancing off the prior prompt's
        # line) -- this fake never echoes client input at all, so without
        # an explicit clear two live bugs both showed up:
        #   1. the next screen's text landed glued onto the tail of the
        #      PREVIOUS unanswered (deliberately newline-less -- see
        #      module docstring) prompt's own row -- caught live: "What
        #      is your name?" + "Use ANSI graphics?" concatenated onto
        #      ONE row re-matched classify.py's `login_name` anchor (a
        #      prefix match) and made the automaton resend the handle
        #      instead of "Y".
        #   2. even after separating rows, login.py's `_SHOW_LOG_RE` /
        #      `_BEEN_ON_TODAY_RE` / `_CLEAR_AVOIDS_RE` nuisance checks
        #      (login.py's own module docstring: matched against the
        #      CURRENT prompt line OR, for `_SHOW_LOG_RE`, the WHOLE
        #      screen text) kept re-matching a STALE "Show today's log?"
        #      line that never scrolled off pyte's un-cleared buffer --
        #      caught live: the automaton re-answered "N" to the
        #      Password prompt instead of sending the credential, since
        #      the show-log text was still sitting in scrollback above it.
        # A real terminal session doesn't accumulate every screen forever
        # either; the clear keeps this fake's pyte buffer shaped the way
        # a real TWGS door's redraw discipline already keeps it.
        payload = ("\x1b[2J\x1b[H" + text).encode("cp437", errors="replace")
        try:
            conn.sendall(payload)
        except OSError as e:
            if self._stop.is_set() or _is_teardown_oserror(e):
                raise ConnectionError("peer closed") from e
            raise

    def _record(self, label: str, value: str):
        """Generic per-label capture -- see module docstring's resume-knobs
        paragraph. Additive alongside the mode-specific fields
        (`.received_passwords`/`.generated_password`) already populated by
        their own call sites; this fires on EVERY labeled read, across all
        4 modes, so a test can assert "this step fired exactly once (or
        zero times)" without a dedicated field per step."""
        self.received_inputs.setdefault(label, []).append(value)

    def _expect_line(self, reader: _Reader, *, expected: str, label: str):
        got = reader.read_line().decode("cp437", errors="replace")
        self._record(label, got)
        if got != expected:
            self.errors.append(f"{label}: expected {expected!r}, got {got!r}")

    def _expect_key(self, reader: _Reader, *, expected: str, label: str):
        got = reader.read_exact(len(expected.encode("cp437"))).decode("cp437", errors="replace")
        self._record(label, got)
        if got != expected:
            self.errors.append(f"{label}: expected {expected!r}, got {got!r}")

    def _capture_line(self, reader: _Reader, *, label: str) -> str:
        """Like `_expect_line`, but ACCEPTS whatever value arrives instead
        of comparing against a fixed expectation -- used for the NEW-arc
        CSPRNG-generated password, whose value this fake can't know ahead
        of time (see module docstring)."""
        got = reader.read_line().decode("cp437", errors="replace")
        self._record(label, got)
        if not got:
            self.errors.append(f"{label}: expected a non-empty password, got {got!r}")
        return got

    def _expect_silence(self, conn: socket.socket, reader: _Reader, *, wait_s: float, label: str):
        """Verify NOT ONE byte arrives -- the `refused` mode's proof that
        login.py's `allow_register=False` guard raises before any send.
        Checks the reader's already-buffered bytes first (a pipelined
        burst the client fired before this call even started waiting),
        then blocks with a bounded socket timeout for anything arriving
        during the wait window. Result recorded on
        `.received_after_char_create` for the test to assert against, in
        addition to the usual `.errors` entry on violation."""
        if reader._buf:
            self.errors.append(f"{label}: received unexpected bytes {bytes(reader._buf)!r} (expected none)")
            self.received_after_char_create = True
            return
        conn.settimeout(wait_s)
        try:
            chunk = conn.recv(1)
        except socket.timeout:
            chunk = b""
        finally:
            conn.settimeout(None)
        if chunk:
            self.errors.append(f"{label}: received unexpected byte {chunk!r} (expected none)")
            self.received_after_char_create = True
        else:
            self.received_after_char_create = False
