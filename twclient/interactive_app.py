"""`tw attach` — the interactive live console.

`tw spectate` (spectate_app.py) stays the read-only dashboard; this is
the driving seat. The operator's keystrokes are forwarded, one at a time and
unbuffered (TW2002 reads most menu commands a single keystroke at a
time -- batching would break the real-BBS feel), to the daemon's single
game connection, and the live screen streams back in real color. Reuses
spectate_app.py's color-rendering primitives (_ColorPairs,
_draw_main_pane) and SpectateClient wholesale rather than reinventing
them -- the only new machinery here is the INPUT side and the
full-screen (no sidebar/ticker) layout that suits actual play better
than the passive dashboard does.

Two connections, opened before curses ever touches the terminal:
  - `output_client` (SpectateClient, unmodified) -- the existing
    read-only `subscribe` stream, exactly what `tw spectate` uses.
  - `input_conn` (AttachInputConn) -- a persistent `attach` connection
    dedicated to forwarding keystrokes. Opening it is what takes the
    daemon's control-lock (control_lock.py); closing it (clean detach,
    Ctrl-C, or a crash) is what releases it -- see daemon.py's
    CommandHandler._handle_attach for the server-side half of that
    contract.

Ctrl-] (ASCII 29 -- the classic telnet-client escape character) detaches
and hands control back to the AI. It's deliberately NOT 'q'/Ctrl-C like
spectate's detach key: those are live TW2002 menu commands (e.g. 'Q' to
quit), so reusing them here would eat real game input.
"""

import curses
import json
import signal
import socket
import threading

from .spectate_app import MIN_COLS, MIN_LINES, SpectateClient, _ColorPairs, _draw_main_pane
from .spectate_layout import DEFAULT_EVENT

DETACH_KEY = 29  # Ctrl-] -- release control, hand back to the AI

_resize_pending = threading.Event()


def _on_sigwinch(signum, frame):
    _resize_pending.set()


class AttachInputConn:
    """Persistent socket dedicated to sending the operator's raw keystrokes to the
    daemon's `attach` verb -- the WRITE half of `tw attach`'s
    two-connection design (SpectateClient, reused unmodified, is the
    READ half). One JSON line out ({"key": ...}), one JSON line back
    ({"ok": ...}) per keystroke -- a unix-domain round trip is
    sub-millisecond locally, so this stays perfectly responsive without
    needing its own background thread."""

    def __init__(self, sock_path):
        self.sock_path = str(sock_path)
        self._sock = None
        self._file = None
        self.error = None

    def connect(self):
        """Sends the initial {"verb": "attach"} request and waits for
        the daemon's ack -- this is the moment the control-lock is taken
        (or rejected, e.g. another human session is already attached),
        so a rejection is caught HERE, before curses ever takes over the
        terminal."""
        try:
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.connect(self.sock_path)
            self._file = self._sock.makefile("rwb")
            self._file.write((json.dumps({"verb": "attach", "args": {}}) + "\n").encode("utf-8"))
            self._file.flush()
            line = self._file.readline()
        except OSError as e:
            self.error = str(e)
            return False
        if not line:
            self.error = "no_response"
            return False
        try:
            resp = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as e:
            self.error = f"bad_response:{e}"
            return False
        if not resp.get("ok"):
            self.error = resp.get("error", "attach_rejected")
            return False
        return True

    def send_key(self, data: bytes):
        """Forward one keystroke's raw bytes. Best-effort: a failed send
        just drops that one keystroke rather than killing the whole
        interactive session -- a dropped key is far less bad than the
        TUI dying mid-play. `data` is decoded latin-1 (an exact 1:1
        byte<->codepoint mapping for the 0-255 range every terminal
        keystroke produces) so it round-trips through JSON untouched."""
        if self._file is None:
            return False
        try:
            self._file.write((json.dumps({"key": data.decode("latin-1")}) + "\n").encode("utf-8"))
            self._file.flush()
            line = self._file.readline()
            if not line:
                return False
            return bool(json.loads(line.decode("utf-8")).get("ok"))
        except (OSError, json.JSONDecodeError):
            return False

    def close(self):
        """Both the makefile() wrapper and the raw socket must be closed
        -- makefile() holds its own reference to the underlying fd, so
        closing only self._sock leaves it open and the daemon's
        readline() never sees EOF (the control-lock would never
        release). shutdown() first for an immediate, unambiguous FIN
        regardless of refcounting."""
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass


def _encode_key(ch):
    """Translate one curses getch() result into the exact raw bytes to
    forward to the game. No local line-editing/buffering -- every
    keystroke goes straight out. Returns None for anything that isn't a
    forwardable keystroke (curses.KEY_RESIZE, -1 = no key this tick, or
    any other unmapped curses macro >= 256)."""
    if ch in (curses.KEY_ENTER, 10, 13):
        return b"\r\n"
    if ch in (curses.KEY_BACKSPACE, 127, 8):
        return b"\x08"
    if ch == curses.KEY_UP:
        return b"\x1b[A"
    if ch == curses.KEY_DOWN:
        return b"\x1b[B"
    if ch == curses.KEY_RIGHT:
        return b"\x1b[C"
    if ch == curses.KEY_LEFT:
        return b"\x1b[D"
    if 0 <= ch < 256:
        return bytes([ch])
    return None


# Deliberately compact -- a plain 80-col terminal (TW2002's own native
# width) is a real target, not just a wide dev terminal, and the TX
# segment (Core transparency) needs guaranteed room; a longer wording
# here silently truncated it off-screen (caught by the pty proof).
_STATUS_TEMPLATE = "ATTACHED -- Ctrl-] detach | sent:{n} → {last}"


def _repr_key(data: bytes) -> str:
    """Human-readable echo of one forwarded keystroke for the status
    bar's TX readout ("Core transparency", TUI-POLISH-PLAN.md) -- a
    printable single byte shows as itself, Enter/Backspace/arrows show
    their name (their raw bytes are control sequences, not something
    worth echoing literally), anything else falls back to its repr()."""
    if data == b"\r\n":
        return "<Enter>"
    if data == b"\x08":
        return "<Backspace>"
    names = {b"\x1b[A": "<Up>", b"\x1b[B": "<Down>", b"\x1b[C": "<Right>", b"\x1b[D": "<Left>"}
    if data in names:
        return names[data]
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        return repr(data)
    return text if text.isprintable() else repr(data)


def _run(stdscr, output_client, input_conn):
    # Visible (not hidden like spectate's curs_set(0)) -- this IS the
    # driving seat, so the caret tracks the game's own cursor position
    # (motion F2's "keypress echo + caret") the way a real BBS terminal
    # would, distinct from spectate's read-only dashboard.
    curses.curs_set(1)
    stdscr.nodelay(True)
    stdscr.timeout(100)
    prev_handler = signal.signal(signal.SIGWINCH, _on_sigwinch)
    _resize_pending.clear()
    palette = _ColorPairs()
    palette.init()

    last_event = dict(DEFAULT_EVENT)
    keys_sent = 0
    last_key_text = "-"

    try:
        while True:
            ch = stdscr.getch()
            if ch == DETACH_KEY:
                return
            if ch == curses.KEY_RESIZE or _resize_pending.is_set():
                curses.update_lines_cols()
                _resize_pending.clear()
            elif ch != -1:
                data = _encode_key(ch)
                if data is not None:
                    input_conn.send_key(data)
                    keys_sent += 1
                    last_key_text = _repr_key(data)

            event = output_client.next_event(timeout=0.05)
            if event is not None:
                last_event = event

            lines, cols = stdscr.getmaxyx()
            if lines < MIN_LINES or cols < MIN_COLS:
                stdscr.erase()
                msg = (
                    f"Terminal too small ({cols}x{lines}) — need at least "
                    f"{MIN_COLS}x{MIN_LINES}. Resize to continue."
                )
                try:
                    stdscr.addnstr(0, 0, msg, cols - 1)
                except curses.error:
                    pass
                stdscr.refresh()
                continue

            _render(stdscr, last_event, keys_sent, last_key_text, lines, cols, palette)
    finally:
        signal.signal(signal.SIGWINCH, prev_handler)


def _render(stdscr, event, keys_sent, last_key_text, lines, cols, palette):
    """Full-screen MAIN pane (no sidebar/ticker split -- unlike
    spectate's dashboard, attach wants every column for the authentic
    game screen) plus a one-line reverse-video status/hotkey-hint bar
    with the live TX readout, plus a visible caret at the game's own
    cursor position (motion F2)."""
    body_h = max(1, lines - 1)

    stdscr.erase()
    status = _STATUS_TEMPLATE.format(n=keys_sent, last=last_key_text)
    try:
        stdscr.addnstr(lines - 1, 0, status, cols - 1, curses.A_REVERSE)
    except curses.error:
        pass
    stdscr.noutrefresh()

    main_win = curses.newwin(body_h, cols, 0, 0)
    _draw_main_pane(main_win, event.get("screen") or [], event.get("color") or [], body_h, cols, palette)

    cursor = event.get("cursor") or {"x": 0, "y": 0}
    cy = max(0, min(body_h - 1, cursor.get("y", 0)))
    cx = max(0, min(cols - 1, cursor.get("x", 0)))
    try:
        main_win.move(cy, cx)
        main_win.noutrefresh()  # a second, cheap no-content refresh just to push the moved cursor
    except curses.error:
        pass

    curses.doupdate()


def run_interactive_attach(sock_path, pid_path):
    """Entry point for `tw attach`'s real curses TUI. Opens BOTH
    connections before touching curses at all: a rejection (e.g. another
    human session is already attached) is reported in plain text, not
    buried inside the TUI."""
    output_client = SpectateClient(sock_path)
    if not output_client.connect():
        print(f"ERROR: could not connect to daemon at {sock_path}: {output_client.connect_error}")
        print("Is the daemon running? (`tw status`)")
        return 1

    input_conn = AttachInputConn(sock_path)
    if not input_conn.connect():
        output_client.close()
        print(f"ERROR: could not attach: {input_conn.error}")
        return 1

    try:
        curses.wrapper(_run, output_client, input_conn)
    except KeyboardInterrupt:
        pass
    finally:
        input_conn.close()
        output_client.close()
    return 0
