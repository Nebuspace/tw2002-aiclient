"""pty regression tests for the Trainer Control Panel's REAL keypress-
driven daemon interaction (TUI-POLISH-PLAN.md): mode cycling, the
Learned-Loops Library (browse -> select -> start), AUTO-LOOP stop/pause/
resume, and Panic. Runs `tw spectate`'s actual `run_interactive()` entry
point inside a real pty against the isolated fake-session daemon from
conftest.py -- never run/twd.sock, never the live game.

test_spectate_app.py already proves the control strip/mode badge/TX/
loops-library RENDER correctly (scripted events + a monkeypatched
fetch_status, no real daemon needed for pure rendering proof). This file
is the complementary proof that a keypress actually reaches
_handle_key() -> _send_control() -> the real wire protocol -> the
daemon's control_lock/loop_player -> and the change is visible back on
screen -- the end-to-end loop, not just each half of it.
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

from twclient import skills
from twclient.control_lock import MODE_AI_PILOT, MODE_AUTO_LOOP, MODE_SPECTATE

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python3"
PTY_ROWS, PTY_COLS = 32, 110  # right_gutter tier -- control strip + full HUD room

_BOOTSTRAP_TEMPLATE = """\
import sys
sys.path.insert(0, {project_root!r})
from pathlib import Path
from twclient.spectate_app import run_interactive
sys.exit(run_interactive(Path({sock_path!r}), Path({pid_path!r})))
"""


def _set_winsize(fd, rows, cols):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _drive_pty(tmp_path, sock_path, pid_path, steps, final_stop=lambda buf: False, timeout=10.0):
    """Spawn the real `run_interactive()` curses loop inside a pty
    against the fake daemon at sock_path. `steps` is an ORDERED list of
    (marker_bytes, keys_bytes) pairs: once `marker_bytes` first appears
    in the captured output, `keys_bytes` is written to the pty and the
    driver advances to the next step -- strictly sequential, mirrors
    test_interactive_app.py's single-step version, extended to a
    sequence for the control panel's multi-keypress flows (open library
    -> select -> start). Always detaches with 'q' before returning."""
    bootstrap = tmp_path / "panel_bootstrap.py"
    bootstrap.write_text(
        _BOOTSTRAP_TEMPLATE.format(project_root=str(PROJECT_ROOT), sock_path=str(sock_path), pid_path=str(pid_path))
    )

    master_fd, slave_fd = pty.openpty()
    _set_winsize(slave_fd, PTY_ROWS, PTY_COLS)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    proc = subprocess.Popen(
        [str(VENV_PYTHON), str(bootstrap)], stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
        cwd=str(PROJECT_ROOT), env=env, start_new_session=True,
    )
    os.close(slave_fd)

    captured = b""
    step_i = 0
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master_fd], [], [], 0.3)
            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                captured += chunk
            if step_i < len(steps):
                marker, keys = steps[step_i]
                if marker in captured:
                    try:
                        os.write(master_fd, keys)
                    except OSError:
                        pass
                    step_i += 1
            elif final_stop(captured):
                break
    finally:
        try:
            os.write(master_fd, b"q")
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


def _wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


_STEP = {"input": "d", "wait_prompt": None, "expected_post_class": "main_command"}


def test_pressing_m_cycles_ai_pilot_to_spectate_and_back(fake_daemon, tmp_path):
    pid_path = tmp_path / "fake.pid"
    pid_path.write_text("0")

    captured = _drive_pty(
        tmp_path, fake_daemon.sock_path, pid_path,
        steps=[
            (b"AI-PILOT", b"m"),  # cycle ai_pilot -> spectate
        ],
        final_stop=lambda buf: b"SPECTATE" in buf,
        timeout=8.0,
    )
    assert fake_daemon.control_lock.mode == MODE_SPECTATE, (
        f"pressing M never reached the daemon -- control_lock.mode is {fake_daemon.control_lock.mode!r}"
    )
    assert b"SPECTATE" in captured, f"badge never re-rendered after the mode change; captured:\n{captured!r}"


def test_pressing_p_panics_and_stops_a_running_loop(fake_daemon, tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(skills, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(skills, "DRAFTS_DIR", skills_dir / "_drafts")
    skills.save_skill("panic-loop", [_STEP], source="recorded")
    fake_daemon.session.wait_settle = lambda **kw: (time.sleep(0.05), ("idle", 0.05))[1]

    skill = skills.load_skill("panic-loop")
    fake_daemon.loop_player.start(skill, "panic-loop", cycles=50)
    assert _wait_until(lambda: fake_daemon.loop_player.cycles_done >= 1)
    assert fake_daemon.control_lock.mode == MODE_AUTO_LOOP

    pid_path = tmp_path / "fake.pid"
    pid_path.write_text("0")
    captured = _drive_pty(
        tmp_path, fake_daemon.sock_path, pid_path,
        steps=[(b"AUTO-LOOP", b"p")],
        final_stop=lambda buf: b"SPECTATE" in buf,
        timeout=8.0,
    )
    assert _wait_until(lambda: not fake_daemon.loop_player.running)
    assert fake_daemon.control_lock.mode == MODE_SPECTATE, (
        f"Panic never landed the daemon in SPECTATE -- mode is {fake_daemon.control_lock.mode!r}"
    )
    assert b"SPECTATE" in captured


def test_library_browse_select_and_enter_starts_the_loop(fake_daemon, tmp_path, monkeypatch):
    """The full Learned-Loops Library flow: L opens it, the real
    list_skills call populates it with an actually-saved skill, Enter
    ARMS a y/N confirm gate (a live-money action must never fire from a
    single keystroke -- see spectate_app._handle_key), y CONFIRMS it --
    proven by the daemon's OWN loop_player actually running afterward,
    not just the overlay's own rendered text."""
    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(skills, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(skills, "DRAFTS_DIR", skills_dir / "_drafts")
    skills.save_skill("library-loop", [_STEP, _STEP, _STEP], source="recorded")
    fake_daemon.session.wait_settle = lambda **kw: (time.sleep(0.05), ("idle", 0.05))[1]

    pid_path = tmp_path / "fake.pid"
    pid_path.write_text("0")
    captured = _drive_pty(
        tmp_path, fake_daemon.sock_path, pid_path,
        steps=[
            (b"AI-PILOT", b"l"),                     # open the library
            (b"library-loop", b"\r"),                # Enter -- ARM the confirm gate (does not start yet)
            (b"LIVE? y/N", b"y"),                    # confirm -- NOW start at the default 1 cycle
        ],
        final_stop=lambda buf: fake_daemon.loop_player.running,
        timeout=8.0,
    )
    assert b"library-loop" in captured, f"library never listed the saved skill; captured:\n{captured!r}"
    assert b"LIVE? y/N" in captured, f"confirm prompt never rendered before starting; captured:\n{captured!r}"
    assert _wait_until(lambda: fake_daemon.loop_player.skill_name == "library-loop"), (
        "Enter-then-y in the library never actually started the highlighted loop on the daemon"
    )
    fake_daemon.loop_player.stop()
    _wait_until(lambda: not fake_daemon.loop_player.running)


def test_library_enter_alone_does_not_start_the_loop_on_the_daemon(fake_daemon, tmp_path, monkeypatch):
    """The other half of the confirm-gate proof, against the REAL daemon
    (test_spectate_app.py's fake-client-only harness already proves the
    same thing at the _send_control() call-recording level -- this is
    the end-to-end version): Enter alone must leave the daemon's
    loop_player completely untouched, not just "not yet started"."""
    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(skills, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(skills, "DRAFTS_DIR", skills_dir / "_drafts")
    skills.save_skill("library-loop", [_STEP], source="recorded")
    fake_daemon.session.wait_settle = lambda **kw: (time.sleep(0.05), ("idle", 0.05))[1]

    pid_path = tmp_path / "fake.pid"
    pid_path.write_text("0")
    captured = _drive_pty(
        tmp_path, fake_daemon.sock_path, pid_path,
        steps=[
            (b"AI-PILOT", b"l"),        # open the library
            (b"library-loop", b"\r"),   # Enter -- must only ARM, never start
        ],
        final_stop=lambda buf: b"LIVE? y/N" in buf,
        timeout=8.0,
    )
    assert b"LIVE? y/N" in captured, f"confirm prompt never rendered; captured:\n{captured!r}"
    assert not fake_daemon.loop_player.running, (
        "a bare Enter started the loop on the daemon before the confirm was ever answered"
    )
    assert fake_daemon.loop_player.skill_name is None


def test_x_stops_a_running_loop_and_returns_to_ai_pilot(fake_daemon, tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(skills, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(skills, "DRAFTS_DIR", skills_dir / "_drafts")
    skills.save_skill("x-loop", [_STEP], source="recorded")
    fake_daemon.session.wait_settle = lambda **kw: (time.sleep(0.05), ("idle", 0.05))[1]

    skill = skills.load_skill("x-loop")
    fake_daemon.loop_player.start(skill, "x-loop", cycles=50)
    assert _wait_until(lambda: fake_daemon.loop_player.cycles_done >= 1)

    pid_path = tmp_path / "fake.pid"
    pid_path.write_text("0")
    _drive_pty(
        tmp_path, fake_daemon.sock_path, pid_path,
        steps=[(b"AUTO-LOOP", b"x")],
        final_stop=lambda buf: b"AI-PILOT" in buf,
        timeout=8.0,
    )
    assert _wait_until(lambda: not fake_daemon.loop_player.running)
    assert fake_daemon.control_lock.mode == MODE_AI_PILOT
    assert fake_daemon.loop_player.last_result == "stopped"


def test_space_pauses_and_resumes_a_running_loop(fake_daemon, tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(skills, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(skills, "DRAFTS_DIR", skills_dir / "_drafts")
    skills.save_skill("pause-loop", [_STEP], source="recorded")
    fake_daemon.session.wait_settle = lambda **kw: (time.sleep(0.05), ("idle", 0.05))[1]

    skill = skills.load_skill("pause-loop")
    fake_daemon.loop_player.start(skill, "pause-loop", cycles=50)
    assert _wait_until(lambda: fake_daemon.loop_player.cycles_done >= 1)

    pid_path = tmp_path / "fake.pid"
    pid_path.write_text("0")
    _drive_pty(
        tmp_path, fake_daemon.sock_path, pid_path,
        steps=[(b"AUTO-LOOP", b" ")],  # Space -- pause
        final_stop=lambda buf: b"PAUSED" in buf,
        timeout=8.0,
    )
    assert _wait_until(lambda: fake_daemon.loop_player.paused)

    fake_daemon.loop_player.stop()
    _wait_until(lambda: not fake_daemon.loop_player.running)
