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

State machine (RETURNING flow only -- the primary path the WO cares about;
NEW-registration is out of scope for this harness):

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

import socket
import threading


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
        chunk = self._sock.recv(4096)
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

    def __init__(self, *, handle: str, game_letter: str, password: str, host: str = "127.0.0.1"):
        self.handle = handle
        self.game_letter = game_letter
        self.password = password
        self.host = host
        self.errors: list[str] = []

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
        for sock in (self._listener, self._client_conn):
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

    # -- server loop -------------------------------------------------------

    def _accept_loop(self):
        try:
            conn, _addr = self._listener.accept()
        except OSError:
            return  # listener closed under us (stop() during teardown)
        self._client_conn = conn
        try:
            self._run_script(conn)
        except ConnectionError:
            pass  # ordinary peer-closed teardown -- not a script failure
        except Exception as e:  # noqa: BLE001 -- a script bug must surface
            # via .errors, never crash this daemon thread silently.
            self.errors.append(f"{type(e).__name__}: {e}")

    def _run_script(self, conn: socket.socket):
        reader = _Reader(conn)

        self._send(conn, "Please enter your name (ENTER for none):")
        self._expect_line(reader, expected="", label="outer_name")

        self._send(conn, f"<{self.game_letter}> Bob the Builder\r\nSelect a game :")
        self._expect_key(reader, expected=self.game_letter, label="game_select")

        self._send(conn, "T - Play Trade Wars 2002\r\nI - Introduction & Help\r\nEnter your choice:")
        self._expect_line(reader, expected="T", label="module_entry_menu")

        self._send(conn, "What is your name?")
        self._expect_line(reader, expected=self.handle, label="login_name")

        self._send(conn, "Use ANSI graphics?")
        self._expect_line(reader, expected="Y", label="ansi_prompt")

        self._send(conn, "Show today's log? (Y/N) [N]")
        self._expect_line(reader, expected="N", label="show_log")

        self._send(conn, "Password?")
        # The password is checked for exact match (correctness proof, not
        # just presence) but NEVER logged/printed/stored anywhere beyond
        # this local comparison -- see module docstring's redaction note.
        self._expect_line(reader, expected=self.password, label="login_password")

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
        conn.sendall(("\x1b[2J\x1b[H" + text).encode("cp437", errors="replace"))

    def _expect_line(self, reader: _Reader, *, expected: str, label: str):
        got = reader.read_line().decode("cp437", errors="replace")
        if got != expected:
            self.errors.append(f"{label}: expected {expected!r}, got {got!r}")

    def _expect_key(self, reader: _Reader, *, expected: str, label: str):
        got = reader.read_exact(len(expected.encode("cp437"))).decode("cp437", errors="replace")
        if got != expected:
            self.errors.append(f"{label}: expected {expected!r}, got {got!r}")
