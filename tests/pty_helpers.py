"""Shared Layer-B pty + pyte helpers (WO-P3-HARNESS-REHAB D1 lane 2).

Extracted from the archive/pre-rebirth patterns in ``test_spectate_app.py``
and ``test_interactive_app.py`` so Phase-3 frame WOs can write
``tw2002_aiclient``-only proofs without depending on banked ``twclient``
test modules.

Scope (thin harness only):
  - winsize + openpty spawn/capture
  - ordered mid-run keystroke injection
  - pyte replay → grid / find_text / cell attrs
  - opt-in controlling-tty claim for live-resize / SIGWINCH proofs

Out of scope (deliberate):
  - cockpit chrome product UI
  - ``frame_layout`` geometry port
  - credentials / secrets
  - live ``run/twd.sock`` attachment

Skip-guard for curses-in-pty suites stays in ``tests.conftest.pty_curses_supported``
(functional probe already greenfield). Re-exported here for one-stop imports.

Controlling TTY / SIGWINCH (WO-P3-PTY-CTTY)
-------------------------------------------
Default spawn keeps ``start_new_session=True`` and does **not** claim the
pty slave as the child's controlling terminal. Existing 030/cockpit Layer-B
suites rely on that path and must stay unchanged.

Live-resize tests that need ``SIGWINCH`` when the parent calls
``set_winsize(master_fd, …)`` must opt in::

    capture_pty(..., claim_ctty=True)
    capture_pty_with_keys(..., claim_ctty=True)

That path skips ``start_new_session`` and instead runs ``preexec_fn`` →
``os.setsid()`` + ``ioctl(slave_fd, TIOCSCTTY)`` so the slave becomes the
controlling tty and a later ``set_winsize(master_fd, …)`` delivers
``SIGWINCH``. Custom Layer-B drivers can also call
``_claim_controlling_tty`` from their own ``preexec_fn``.

Terminal environment (WO-AUDIT-PTY-TERM-INHERITANCE)
----------------------------------------------------
A test must control the terminal it is testing, so the child's terminal
type is **assigned, never inherited**. See ``DEFAULT_TERM`` and
``_GEOMETRY_ENV_VARS`` below for the two variables involved and the
measurements behind them; ``term=`` is the one deliberate override
channel, and ``rows=``/``cols=`` is the only size channel.
"""

from __future__ import annotations

import fcntl
import os
import pty
import re
import select
import signal
import struct
import subprocess
import termios
import time
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pyte

# Genuine SGR color-SET (not bare reset / bold alone) — archive
# test_spectate_app._COLOR_SET_SGR_RE. Useful for Layer-B color proofs.
COLOR_SET_SGR_RE = re.compile(rb"\x1b\[[0-9;]*(?:3[0-7]|4[0-7]|9[0-7]|10[0-7])m")

# Default detach for spectate-style loops (``q``). Attach uses Ctrl-] —
# pass ``detach_keys=bytes([29])`` instead.
DEFAULT_DETACH = b"q"

# Terminal type every capture_pty* child gets unless a caller names another
# with ``term=``. It is ASSIGNED, never ``setdefault``-ed: a ``setdefault``
# respects an inherited ``TERM``, so a pty test drove whatever terminal the
# invoking shell happened to export. Measured on this tree, same code, only
# ``TERM`` changed:
#
#     TERM=xterm-256color   cup=True    tests/test_bank_unreadable_pty.py  4 passed
#     TERM=dumb             cup=False   tests/test_bank_unreadable_pty.py  4 FAILED
#     TERM=<unset>          curses.setupterm() fails
#
# Without ``cup`` curses cannot address the cursor, so panel content never
# lands where pyte replays it while line-drawing chrome still emits — the
# symptom is a chrome-only grid and a content assertion failing on the
# terminal rather than on the product.
#
# ``"xterm"`` is not arbitrary: it is what the rest of this suite already
# standardises on — ``tests/conftest.py::pty_curses_supported`` probes with
# ``TERM="xterm"``, and every local ``_drive_pty`` in the cockpit/spectate
# Layer-B modules sets ``env["TERM"] = "xterm"``. Helper-driven and
# locally-driven pty tests therefore prove against one terminal.
DEFAULT_TERM = "xterm"

# Stripped from every child env. ncurses honours these ABOVE the pty's real
# winsize, so an ambient exported ``COLUMNS`` silently resizes a test's
# terminal. Measured on a 24x80 pty: no vars → ``curses.COLS`` 80;
# ``COLUMNS=200`` → 200; ``LINES=50`` → 50 rows. The child would then paint
# a geometry the ``pyte_grid(captured, rows, cols)`` replay does not read.
# ``rows=``/``cols=`` (→ ``TIOCSWINSZ``) is this harness's only size channel;
# a test that wants a different size says so there.
_GEOMETRY_ENV_VARS = ("LINES", "COLUMNS")


def _child_environment(env: dict[str, str] | None, term: str | None) -> dict[str, str]:
    """Child env with a *decided* terminal — never an ambient one.

    ``term`` is assigned over whatever ``env`` (or ``os.environ``) carries.
    That deliberately outranks a caller-supplied ``env=`` too: the one caller
    in-tree that passes ``env=`` builds it as ``dict(os.environ, …)`` to pin
    an unrelated variable, so its ``TERM`` is still ambient inheritance
    wearing an explicit-looking coat. A caller that genuinely wants another
    terminal — e.g. proving behaviour under a poor one — passes ``term=``,
    which cannot be confused with a leak.

    ``term=None`` removes ``TERM`` entirely: the deliberate "no terminal type
    at all" case, where ``curses.setupterm()`` fails. Every value of ``term``
    yields a known child terminal; none of them inherits one.
    """
    child_env = dict(os.environ if env is None else env)
    if term is None:
        child_env.pop("TERM", None)
    else:
        child_env["TERM"] = term
    for var in _GEOMETRY_ENV_VARS:
        child_env.pop(var, None)
    return child_env


def _claim_controlling_tty(slave_fd: int) -> None:
    """Make ``slave_fd`` this process's controlling terminal (resize opt-in).

    Default ``capture_pty*`` uses ``start_new_session=True`` alone — the child
    is a session leader via Popen but never claims the pty as ctty, so
    ``SIGWINCH`` from a later ``TIOCSWINSZ`` on the master is never delivered.
    Call from ``preexec_fn`` when ``claim_ctty=True`` (do **not** also pass
    ``start_new_session=True`` — this function calls ``setsid`` itself).
    """
    os.setsid()
    # TIOCSCTTY: claim controlling tty (usual Unix form: ioctl arg 0).
    fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)


def set_winsize(fd: int, rows: int, cols: int) -> None:
    """``TIOCSWINSZ`` on a pty fd — size for curses; master resize → SIGWINCH iff ctty."""
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def capture_pty(
    argv: Sequence[str],
    stop_condition: Callable[[bytes], bool],
    *,
    timeout: float = 10.0,
    rows: int = 24,
    cols: int = 80,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    term: str | None = DEFAULT_TERM,
    detach_keys: bytes = DEFAULT_DETACH,
    drain_after_s: float = 5.0,
    claim_ctty: bool = False,
) -> bytes:
    """Spawn ``argv`` in a pty; stream stdout until ``stop_condition`` or timeout.

    Always attempts ``detach_keys`` before teardown (spectate ``q``, attach
    Ctrl-], etc.). Drains the master while waiting so a clean child exit
    isn't wedged on a full pty buffer (archive lesson from confirm-gate
    RECORD_PATH flows).

    ``term`` — the child's ``TERM``, assigned over ``env``/``os.environ``
    (``None`` unsets it). See ``_child_environment``; ``LINES``/``COLUMNS``
    never reach the child, ``rows``/``cols`` set the size.

    ``claim_ctty=False`` (default): ``start_new_session=True`` only — preserves
    existing 030/cockpit Layer-B behavior (no SIGWINCH delivery).

    ``claim_ctty=True``: child ``setsid`` + ``TIOCSCTTY`` so a later
    ``set_winsize(master_fd, …)`` can deliver ``SIGWINCH`` for live-resize
    proofs. Opt in only from resize tests.
    """
    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, rows, cols)
    child_env = _child_environment(env, term)

    popen_kwargs: dict[str, Any] = {
        "stdin": slave_fd,
        "stdout": slave_fd,
        "stderr": slave_fd,
        "cwd": str(cwd) if cwd is not None else None,
        "env": child_env,
    }
    if claim_ctty:
        # Slave must stay open in the child until ioctl; pass fd via closure.
        def _preexec() -> None:
            _claim_controlling_tty(slave_fd)

        popen_kwargs["preexec_fn"] = _preexec
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(list(argv), **popen_kwargs)
    os.close(slave_fd)

    captured = b""
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
            if stop_condition(captured):
                break
    finally:
        try:
            if detach_keys:
                os.write(master_fd, detach_keys)
        except OSError:
            pass
        captured += _drain_until_exit(proc, master_fd, drain_after_s)
        _close_master(master_fd)
    return captured


def capture_pty_with_keys(
    argv: Sequence[str],
    steps: Sequence[tuple[bytes, bytes] | None],
    stop_condition: Callable[[bytes], bool],
    *,
    timeout: float = 10.0,
    rows: int = 24,
    cols: int = 80,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    term: str | None = DEFAULT_TERM,
    detach_keys: bytes = DEFAULT_DETACH,
    drain_after_s: float = 5.0,
    claim_ctty: bool = False,
) -> bytes:
    """Like ``capture_pty``, plus ordered mid-run keystroke injection.

    Each step is ``(marker_bytes, keys_bytes)``: once ``marker_bytes`` first
    appears in the captured stream, write ``keys_bytes`` once. Steps fire
    strictly in order (step N never before step N-1). ``None`` entries are
    skipped. Mirrors archive ``_run_fake_spectate_and_type_in_pty`` /
    ``test_control_panel._drive_pty``.

    ``term`` / ``claim_ctty`` — same contract as ``capture_pty``.
    """
    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, rows, cols)
    child_env = _child_environment(env, term)

    popen_kwargs: dict[str, Any] = {
        "stdin": slave_fd,
        "stdout": slave_fd,
        "stderr": slave_fd,
        "cwd": str(cwd) if cwd is not None else None,
        "env": child_env,
    }
    if claim_ctty:
        def _preexec() -> None:
            _claim_controlling_tty(slave_fd)

        popen_kwargs["preexec_fn"] = _preexec
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(list(argv), **popen_kwargs)
    os.close(slave_fd)

    pending = [s for s in steps if s is not None]
    fired = [False] * len(pending)
    captured = b""
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
            for i, (marker, keys) in enumerate(pending):
                if fired[i]:
                    continue
                if i > 0 and not fired[i - 1]:
                    break
                if marker in captured:
                    try:
                        os.write(master_fd, keys)
                    except OSError:
                        pass
                    fired[i] = True
            if stop_condition(captured):
                break
    finally:
        try:
            if detach_keys:
                os.write(master_fd, detach_keys)
        except OSError:
            pass
        captured += _drain_until_exit(proc, master_fd, drain_after_s)
        _close_master(master_fd)
    return captured


def pyte_screen(captured: bytes, rows: int, cols: int) -> pyte.Screen:
    """Replay raw pty bytes through pyte into a ``rows``×``cols`` screen.

    Returns the live ``pyte.Screen`` — use ``.display`` for text,
    ``.buffer[r][c].fg`` / ``.reverse`` / ``.bold`` for cell attrs,
    ``.cursor.y/x`` for caret proofs. UTF-8 with replacement (curses
    chrome under a UTF-8 locale).
    """
    screen = pyte.Screen(cols, rows)
    stream = pyte.Stream(screen)
    stream.feed(captured.decode("utf-8", errors="replace"))
    return screen


def pyte_grid(captured: bytes, rows: int, cols: int) -> list[str]:
    """Plain-text rows from ``pyte_screen(...).display``."""
    return list(pyte_screen(captured, rows, cols).display)


def find_text(grid: Sequence[str], needle: str) -> tuple[int, int] | None:
    """``(row, col)`` of the first ``needle`` in a pyte grid, or ``None``."""
    for r, row_text in enumerate(grid):
        c = row_text.find(needle)
        if c != -1:
            return r, c
    return None


# Underscore aliases — drop-in for archive-local ``_set_winsize`` / ``_pyte_*``.
_set_winsize = set_winsize
_capture_pty = capture_pty
_pyte_screen = pyte_screen
_pyte_grid = pyte_grid
_find_text = find_text


def terminate_session_group(
    proc: subprocess.Popen, *, wait_timeout: float = 5.0, grace_s: float = 0.0
) -> None:
    """Attempt to kill ``proc``'s session/process group; degrade honestly on EPERM.

    Every pty spawn in this suite uses ``start_new_session=True`` (or the
    ``claim_ctty=True`` preexec's own ``os.setsid()`` in
    ``_claim_controlling_tty`` above) so the child can never steal the
    runner's controlling terminal (WO-P3-PTY-CTTY) -- deliberate and
    correct. The same isolation means a bare ``proc.kill()`` (``SIGKILL``
    to the direct child PID only) never reaches anything THAT child itself
    spawned, and a signal to *pytest's own* process group never reaches
    this session at all -- the mechanism behind the 2026-07-26 incident's
    11 orphaned ``curses.wrapper(_run)`` processes (WO-TUI-DEAD-TERMINAL-
    SPIN Defect 2): a full-suite run that gets SIGTERM'd skips every
    ``finally`` in the killing process, so this cleanup never even runs,
    and the isolated child is simply reparented to init. ``os.killpg``
    is the *preferred* ordinary-path sweep for the whole GROUP -- but it
    is **not** an unconditional guarantee: this suite's curses-in-pty
    harness under ``start_new_session=True`` reliably raises
    ``PermissionError`` on Darwin (WO-TUI-KILLPG-EPERM-CURSES-PTY;
    sleep controls and minimal curses+setsid alone do not). On
    EPERM this helper warns loudly and falls back to a direct-child kill
    only -- grandchildren in that group are **not** reaped by this call.

    ``grace_s`` (default 0 -- no change from prior behaviour): wait up to
    this long for the DIRECT child to exit on its own before signalling
    anything, mirroring the graceful-exit window some callers had before
    they were swapped onto this helper (e.g. ``tests/
    attach_terminal_harness.py``, which gave a real ``tw attach`` process 5
    real seconds to unwind before any kill). This is a courtesy to the
    direct child only -- the preferred path still *attempts* a group
    sweep below whether or not the grace period was needed, because Defect 2
    is precisely the case where the direct child DID exit cleanly (on its
    own, inside or outside any grace window) while something it spawned did
    not. (EPERM carve-out may still reduce that attempt to a direct kill.)

    The group signal below is unconditional -- **not** gated on
    ``proc.poll()``. The prior ``if proc.poll() is None: killpg()`` guard
    was itself Defect 2's bug: it skipped the whole-group signal exactly
    when the direct child had ALREADY exited (the common, clean-exit case),
    which is exactly when a grandchild it spawned earlier is most likely to
    be the only thing left alive. A process group is a kernel object that
    persists as long as any member is alive, independent of whether its
    original leader has already exited and been reaped -- so ``killpg``
    still reaches a surviving grandchild even after the direct child (the
    group leader) is gone.

    Every call site's ``proc`` is documented (and expected) to have been
    spawned with ``start_new_session=True`` or the ``claim_ctty`` preexec's
    own ``setsid()`` -- both make the child its own session AND process
    group leader, so ``pgid == proc.pid``. That invariant is CHECKED, not
    assumed, on every call (see ``_is_group_leader`` below) -- a docstring
    claim that "every site setsid's" is exactly the kind of enumeration
    claim that has been wrong before, so a call whose child did NOT setsid
    degrades to a direct-child-only kill instead of blindly trusting it.

    A naive ``os.getpgid(proc.pid) == proc.pid`` check at CLEANUP time (as
    opposed to spawn time) has its own trap once the child has already
    exited and been reaped (the common, clean-exit case this fix exists
    for): ``os.getpgid`` on a reaped pid raises ``ProcessLookupError``
    (measured) -- there is no live pid left to query. Treating that as
    "not a leader, skip the signal" would skip the signal in exactly the
    case that matters most (a live grandchild in a now-leaderless group).
    Treating it as "assume it WAS a leader" is the safe direction instead:
    if it really did setsid, any surviving members are still reachable via
    ``killpg(proc.pid, ...)``; if it never setsid'd and is now reaped,
    ``proc.pid`` is not a real pgid for anything and ``killpg`` on it is a
    harmless ``ProcessLookupError`` no-op -- never our own group, because a
    NON-setsid'd child's pgid is OUR OWN pgid, not its own pid, so the only
    way ``killpg(proc.pid, ...)`` could hit our own group is the
    astronomically unlikely coincidence of ``proc.pid`` itself matching
    our pgid number.

    Never raises: ``os.killpg`` racing an already-fully-reaped group (no
    member left alive at all) is swallowed exactly like ``Popen.kill()``
    already swallows "already dead" for the direct-PID form this replaces.
    """
    if grace_s > 0:
        try:
            proc.wait(timeout=grace_s)
        except subprocess.TimeoutExpired:
            pass

    def _is_group_leader() -> bool:
        """True iff ``proc`` really did setsid (pgid == its own pid).

        Checked while the child is STILL ALIVE where possible -- a
        post-reap re-check (`os.getpgid(proc.pid)` at cleanup time,
        gated on `proc.poll()`) was tried and rejected: once the pid is
        reaped, `os.getpgid` raises `ProcessLookupError` regardless of
        whether it really was a leader, so that check degrades to "not a
        leader" in exactly the exit-0-with-live-grandchild case this fix
        exists for. `ProcessLookupError` here instead means "can no
        longer verify, but a real leader's group -- if any -- is still
        reachable via killpg(proc.pid, ...); a non-leader's would never
        have been proc.pid to begin with" -- so it degrades to True
        (assume leader), the safe direction for THIS check specifically.
        """
        try:
            return os.getpgid(proc.pid) == proc.pid
        except ProcessLookupError:
            return True

    def _signal_group() -> None:
        if not _is_group_leader():
            # This child's own pgid is OUR pgid (it never setsid'd) --
            # killpg(proc.pid, ...) here would target proc.pid as if it
            # were a group id, which is not our own group (that group IS
            # reachable as os.getpgid(0), a different number from
            # proc.pid) and essentially never resolves to anything real,
            # but it is also not a signal this helper is entitled to send
            # on this child's behalf. Direct-kill only.
            proc.kill()
            return
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Known suite-harness carve-out (WO-TUI-KILLPG-EPERM-CURSES-PTY):
            # this suite's curses-in-pty teardown reliably EPERM on Darwin;
            # plain sleep and minimal curses+setsid alone do not (CC 18:42Z).
            # Further harness ingredient unidentified — see
            # audit/killpg-eperm-curses-pty-20260726.md. Keep LOUD: a
            # silent direct-child-only fallback looks identical to a
            # healthy killpg run and hides the orphan-latent path.
            warnings.warn(
                f"terminate_session_group: os.killpg({proc.pid}, SIGKILL) "
                "raised PermissionError -- falling back to a direct-child "
                "kill only; anything else in this process group is NOT "
                "reaped by this call",
                RuntimeWarning,
                stacklevel=2,
            )
            try:
                proc.kill()
            except ProcessLookupError:
                pass

    _signal_group()
    try:
        proc.wait(timeout=wait_timeout)
    except subprocess.TimeoutExpired:
        _signal_group()
        try:
            proc.wait(timeout=wait_timeout)
        except subprocess.TimeoutExpired:
            pass


def _drain_until_exit(proc: subprocess.Popen, master_fd: int, drain_after_s: float) -> bytes:
    """Drain master while waiting for child exit; kill its whole session if still alive."""
    extra = b""
    drain_deadline = time.monotonic() + drain_after_s
    while time.monotonic() < drain_deadline and proc.poll() is None:
        ready, _, _ = select.select([master_fd], [], [], 0.2)
        if master_fd in ready:
            try:
                chunk = os.read(master_fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            extra += chunk
    terminate_session_group(proc)
    return extra


def _close_master(master_fd: int) -> None:
    try:
        os.close(master_fd)
    except OSError:
        pass


# Re-export skip-guard without importing conftest at module load (conftest
# pulls heavier session fixtures). Lazy so ``import tests.pty_helpers`` stays
# light and twclient-free.
def pty_curses_supported() -> bool:
    """Functional curses-in-pty probe — delegates to ``tests.conftest``."""
    from tests.conftest import pty_curses_supported as _probe

    return bool(_probe())


# ---------------------------------------------------------------------------
# Cockpit Layer-B play-shell drive (WO-PTY-DRIVE-HOIST)
# ---------------------------------------------------------------------------

_DEFAULT_SMOKE_POPS = (
    "TW2002_ASCII",
    "TW2002_HANDOFF_SMOKE",
    "TW2002_LAUNCHER_SMOKE",
    "TW2002_BANK_SMOKE",
)


def settle_pty(master_fd: int, captured: bytes, seconds: float) -> bytes:
    """Drain the pty master for ``seconds``, appending onto ``captured``.

    One-shot post-sleep reads miss mid-flush frames (control strip is drawn
    last). Shared by the five cockpit chip PTY suites.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        ready, _, _ = select.select([master_fd], [], [], 0.2)
        if master_fd in ready:
            try:
                chunk = os.read(master_fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            captured += chunk
    return captured


def drive_play_shell_pty(
    bootstrap: Path,
    *,
    project_root: Path | str,
    rows: int,
    cols: int,
    handle: str,
    timeout: float = 20.0,
    env_extra: dict[str, str] | None = None,
    env_pops: Sequence[str] = _DEFAULT_SMOKE_POPS,
    settle_s: float = 1.6,
    grace_s: float = 5.0,
    after_first_frame: Callable[[int, bytes], tuple[bytes, bool]] | None = None,
) -> tuple[bytes, bytes | None]:
    """Spawn a bootstrap that runs ``app._run``: Enter launcher → settle play shell → quit.

    Returns ``(capture1, capture2)``. ``capture2`` is set only when
    ``after_first_frame`` returns ``(captured, True)`` (want a second settle
    before quit) — used by the liveness two-capture clock path.

    ``after_first_frame(master_fd, captured) -> (captured, want_second)``.
    Default: settle already applied; quit after first frame.
    """
    import sys

    isolated = Path(bootstrap).parent / "isolated_run"
    isolated.mkdir(exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, rows, cols)
    env = dict(os.environ)
    env["TERM"] = DEFAULT_TERM
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW_RUN_DIR"] = str(isolated)
    if env_extra:
        env.update(env_extra)
    for stray in env_pops:
        env.pop(stray, None)

    proc = subprocess.Popen(
        [sys.executable, str(bootstrap)],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=str(project_root),
        env=env,
        start_new_session=True,
    )
    os.close(slave_fd)

    captured = b""
    capture1: bytes | None = None
    capture2: bytes | None = None
    phase = "wait_launcher"
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master_fd], [], [], 0.2)
            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                captured += chunk

            grid = pyte_grid(captured, rows, cols)
            if phase == "wait_launcher":
                if find_text(grid, "SELECT PROFILE") and find_text(grid, handle):
                    os.write(master_fd, b"\r")
                    phase = "wait_frame"
            elif phase == "wait_frame":
                if find_text(grid, "PLAY SHELL"):
                    captured = settle_pty(master_fd, captured, settle_s)
                    capture1 = captured
                    want_second = False
                    if after_first_frame is not None:
                        captured, want_second = after_first_frame(master_fd, captured)
                        capture1 = captured
                    if want_second:
                        phase = "wait_second"
                    else:
                        os.write(master_fd, b"q")
                        phase = "done"
                        break
            elif phase == "wait_second":
                captured = settle_pty(master_fd, captured, settle_s)
                capture2 = captured
                os.write(master_fd, b"q")
                phase = "done"
                break
        if phase != "done":
            try:
                os.write(master_fd, b"q")
            except OSError:
                pass
    finally:
        drain_deadline = time.monotonic() + 5.0
        while time.monotonic() < drain_deadline and proc.poll() is None:
            ready, _, _ = select.select([master_fd], [], [], 0.2)
            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                captured += chunk
        terminate_session_group(proc, grace_s=grace_s)
        _close_master(master_fd)

    assert phase == "done" and capture1 is not None, (
        f"pty play-shell drive stalled in phase={phase!r}; last grid:\n"
        + "\n".join(pyte_grid(captured, rows, cols))
    )
    return capture1, capture2
