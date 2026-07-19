"""pty regression test for `tw attach`'s interactive keystroke-routing +
control-lock handoff -- the TUI-pty-proof rule: a socket-only test never
exercises the curses/input path (getch(), keypad translation, the resize
guard), so proving a keystroke the operator actually types reaches the game
requires a REAL pty + real curses, exactly like test_spectate_app.py's
existing pattern for `tw spectate`.

Runs entirely against the ISOLATED FakeAttachSession daemon from
conftest.py, on its own temp socket -- never run/twd.sock, never the
live game server. A second attach against the real daemon mid-session
would inject real keystrokes into the actual live game; this test proves
the mechanism without ever touching it.
"""

import fcntl
import os
import pty
import select
import struct
import subprocess
import termios
import time
from pathlib import Path

import pyte

from twclient.control_lock import MODE_HUMAN

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python3"

# Well above interactive_app.MIN_LINES/MIN_COLS so the "terminal too
# small" message never applies here.
PTY_ROWS, PTY_COLS = 24, 80

DETACH_BYTE = bytes([29])  # Ctrl-] -- interactive_app.DETACH_KEY

# A standalone bootstrap script (not `tw attach`, which hardcodes the
# project's real run/twd.sock) that drives run_interactive_attach()
# directly against whatever temp sock/pid path this test hands it.
_BOOTSTRAP_TEMPLATE = """\
import sys
sys.path.insert(0, {project_root!r})
from twclient.interactive_app import run_interactive_attach
sys.exit(run_interactive_attach({sock_path!r}, {pid_path!r}))
"""


def _set_winsize(fd, rows, cols):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _run_attach_in_pty(tmp_path, sock_path, pid_path, send_bytes=b"", stop_condition=lambda buf: False, timeout=10.0):
    """Spawn the real `run_interactive_attach` curses loop inside a pty
    against the fake daemon at sock_path. Once the status bar's first
    paint proves the attach handshake completed, optionally type
    send_bytes into the pty, then run until stop_condition(captured) or
    timeout, and ALWAYS detach with Ctrl-] (the app's own release key)
    before returning."""
    bootstrap = tmp_path / "attach_bootstrap.py"
    bootstrap.write_text(
        _BOOTSTRAP_TEMPLATE.format(project_root=str(PROJECT_ROOT), sock_path=str(sock_path), pid_path=str(pid_path))
    )

    master_fd, slave_fd = pty.openpty()
    _set_winsize(slave_fd, PTY_ROWS, PTY_COLS)
    env = dict(os.environ)
    env["TERM"] = "xterm"

    proc = subprocess.Popen(
        [str(VENV_PYTHON), str(bootstrap)],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=str(PROJECT_ROOT),
        env=env,
        start_new_session=True,  # own session -- pty slave becomes its controlling terminal
    )
    os.close(slave_fd)  # only the child needs the slave end

    captured = b""
    sent = False
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master_fd], [], [], 0.5)
            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                captured += chunk
            if send_bytes and not sent and b"ATTACHED" in captured:
                os.write(master_fd, send_bytes)
                sent = True
            if stop_condition(captured):
                break
    finally:
        try:
            os.write(master_fd, DETACH_BYTE)
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        try:
            os.close(master_fd)
        except OSError:
            pass
    return captured


def test_attach_forwards_a_real_keystroke_through_a_pty(fake_daemon, tmp_path):
    pid_path = tmp_path / "fake.pid"
    pid_path.write_text("0")

    captured = _run_attach_in_pty(
        tmp_path,
        fake_daemon.sock_path,
        pid_path,
        send_bytes=b"d",
        stop_condition=lambda buf: bool(fake_daemon.session.raw_sent),
    )

    assert b"ATTACHED" in captured, f"status bar never rendered; captured:\n{captured!r}"
    assert fake_daemon.session.raw_sent == [b"d"], (
        "the 'd' typed into the pty never reached the fake session through the real "
        f"curses -> socket -> daemon -> session.send_raw() path; raw_sent="
        f"{fake_daemon.session.raw_sent!r}"
    )


def test_attach_status_bar_echoes_the_tx_of_the_last_key_sent(fake_daemon, tmp_path):
    """Core transparency's TX readout in MANUAL mode -- tracked LOCALLY
    by interactive_app.py itself (the client already knows exactly what
    it just sent the instant it sends it), not round-tripped through the
    daemon's watch stream, so this doesn't depend on a settle-edge ever
    firing for a keystroke that doesn't change the (fake) screen."""
    pid_path = tmp_path / "fake.pid"
    pid_path.write_text("0")

    captured = _run_attach_in_pty(
        tmp_path,
        fake_daemon.sock_path,
        pid_path,
        send_bytes=b"d",
        stop_condition=lambda buf: b"\xe2\x86\x92 d" in buf,  # UTF-8 for "→ d"
    )
    text = captured.decode("utf-8", errors="replace")
    assert "→ d" in text, f"TX readout never showed the sent key; captured:\n{text}"


def test_attach_caret_tracks_the_reported_cursor_position(fake_daemon, tmp_path):
    """motion F2: a visible caret at the game's own cursor position, not
    the hidden cursor spectate uses -- sourced from the daemon's
    build_response() "cursor" field (session.cursor_pos()), carried on
    the subscribe stream's very first seeded event."""
    fake_daemon.session._cursor = {"x": 5, "y": 2}
    pid_path = tmp_path / "fake.pid"
    pid_path.write_text("0")

    captured = _run_attach_in_pty(
        tmp_path,
        fake_daemon.sock_path,
        pid_path,
        stop_condition=lambda buf: b"ATTACHED" in buf,
        timeout=8.0,
    )
    assert b"ATTACHED" in captured, f"attach never rendered; captured:\n{captured!r}"

    screen = pyte.Screen(PTY_COLS, PTY_ROWS)
    stream = pyte.Stream(screen)
    stream.feed(captured.decode("utf-8", errors="replace"))
    assert (screen.cursor.y, screen.cursor.x) == (2, 5), (
        f"caret did not land at the reported cursor position (2,5) -- "
        f"actual terminal cursor ended at ({screen.cursor.y},{screen.cursor.x})"
    )


def test_ctrl_bracket_detaches_and_releases_the_control_lock(fake_daemon, tmp_path):
    pid_path = tmp_path / "fake.pid"
    pid_path.write_text("0")

    _run_attach_in_pty(
        tmp_path,
        fake_daemon.sock_path,
        pid_path,
        stop_condition=lambda buf: b"ATTACHED" in buf,
        timeout=8.0,
    )
    # _run_attach_in_pty's own `finally` already sent Ctrl-] and waited
    # for the subprocess to exit -- the connection is closed by now, but
    # give the daemon's handler thread a beat to run its own `finally:
    # lock.release_human()`.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and fake_daemon.control_lock.mode == MODE_HUMAN:
        time.sleep(0.02)

    assert fake_daemon.control_lock.mode != MODE_HUMAN, "control-lock still held by human after Ctrl-] detach"


def test_second_attach_is_rejected_while_pty_session_is_active(fake_daemon, tmp_path):
    """Proves the rejection surfaces BEFORE curses ever takes over the
    terminal (interactive_app.run_interactive_attach's connect-both-first
    ordering) -- a second concurrent `tw attach` prints a plain-text
    error and exits, rather than silently stealing/racing the lock."""
    from twclient.interactive_app import AttachInputConn

    holder = AttachInputConn(fake_daemon.sock_path)
    assert holder.connect() is True
    try:
        pid_path = tmp_path / "fake.pid"
        pid_path.write_text("0")
        captured = _run_attach_in_pty(
            tmp_path,
            fake_daemon.sock_path,
            pid_path,
            stop_condition=lambda buf: b"ERROR" in buf,
            timeout=6.0,
        )
        assert b"already_attached" in captured, f"expected a rejection message; captured:\n{captured!r}"
        assert b"ATTACHED" not in captured, "second session must never reach the curses TUI while locked out"
    finally:
        holder.close()
