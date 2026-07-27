"""WO-CONN-CHIP-PTY-PROOF — the CONN chip on a real terminal.

# Why this file exists

The CONN chip was the **only unpinned wire** found by the 2026-07-27
draw-wire sweep (`scripts/wire-sweep.py`): 12 cockpit surfaces swept, and
deleting ``conn_chip=`` from ``screens.py``'s composer call left the entire
suite green at **4917 tests, 0 failures**.

That is not a shortage of tests. ``tests/test_conn_toggle.py`` covers the
chip thoroughly — every state, every focus variant, placement against the
seat label. But every one of those assertions calls
``compose_control_strip_segments`` **directly**, so none of them can observe
whether ``screens.py`` passes the chip at all. The chip could be composed
perfectly and never reach the operator's screen.

The sweep also found *why* the other eleven surfaces were safe: every one of
them has a Layer-B PTY **content** proof. CONN was the only control-strip
chip without one. So this file is not a bespoke "wire test" — it is the
missing member of an existing family, using the harness
``test_cockpit_arm_pty.py`` / ``test_cockpit_liveness_pty.py`` /
``test_cockpit_covermeter_pty.py`` already use for the neighbouring chips on
this very row.

# What is proven here that cannot be proven headlessly

Three states rendered by the real draw path, through real curses, read back
off a pyte grid:

* ``connected: True``   -> ``CONN``
* ``connected: False``  -> ``DISC``
* the field absent      -> ``DISC?``

The third is the load-bearing one for honesty: an unknown connection state
must render its own marker rather than being folded into ``DISC``, because
"I know you are disconnected" and "I do not know" are different claims and
only one of them is true with no daemon.

Proving more than one state matters for a second reason: a wire pinned by a
single state can be satisfied by a hardcoded chip. Three distinct outputs
from three distinct payloads show the value is genuinely flowing.

# Harness duplication is the convention here, deliberately

The pty drive loop below is near-identical to the sibling suites'. Each pty
file in this repo carries its own copy rather than importing a private
helper across test modules. Hoisting it into ``tests/pty_helpers.py`` would
be a real improvement and is **out of scope for this WO** — noted in the
STATUS as a banked follow-on rather than smuggled in beside a wire proof.
"""

from __future__ import annotations

import json
import os
import pty
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.pty_ui


from .pty_helpers import (
    find_text,
    pty_curses_supported,
    pyte_grid,
    set_winsize,
    terminate_session_group,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HANDLE = "Alpha"
FULL_ROWS, FULL_COLS = 40, 160

_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)

_BOOTSTRAP = r"""
import json
import os
import sys

os.environ["TW2002_LAUNCHER_DEMO"] = "1"
os.environ.pop("TW2002_HANDOFF_SMOKE", None)
os.environ.pop("TW2002_LAUNCHER_SMOKE", None)
os.environ.pop("TW2002_BANK_SMOKE", None)

sys.path.insert(0, __PROJECT_ROOT__)

from tw2002_aiclient import adapters
from tw2002_aiclient.adapters import EnsureResult


def _fake_ensure(profile, **kwargs):
    return EnsureResult(ok=True, classification="main_command")


adapters.ensure_session = _fake_ensure

_STATUS_JSON = __STATUS_JSON__
if _STATUS_JSON:
    from tw2002_aiclient.session import cli as session_cli

    _payload = json.loads(_STATUS_JSON)

    def _fake_send_request(verb, args=None, **kwargs):
        if verb == "status":
            return _payload
        return {"ok": False, "error": "not_stubbed"}

    session_cli.send_request = _fake_send_request

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""


def _settle(master_fd: int, captured: bytes, seconds: float) -> bytes:
    """Keep draining for ``seconds``. One ``refresh()`` of a 40x160 frame
    spans several OS-level pty chunks and the control strip is drawn LAST,
    so a one-shot read can snapshot mid-flush and miss exactly the row this
    file is about."""
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


def _drive(tmp_path: Path, status: dict | None, *, timeout: float = 20.0) -> bytes:
    """Spawn ``app._run`` in a 40x160 pty, Enter through the launcher, and
    capture the settled cockpit frame. ``status`` is the payload the stubbed
    poll returns, or ``None`` to leave the real no-daemon path in place."""
    bootstrap = tmp_path / "conn_pty_bootstrap.py"
    bootstrap.write_text(
        _BOOTSTRAP
        .replace("__PROJECT_ROOT__", repr(str(PROJECT_ROOT)))
        .replace("__STATUS_JSON__", repr(json.dumps(status) if status else "")),
        encoding="utf-8",
    )
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir(exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, FULL_ROWS, FULL_COLS)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW_RUN_DIR"] = str(isolated_run_dir)
    for stray in ("TW2002_ASCII", "TW2002_HANDOFF_SMOKE",
                  "TW2002_LAUNCHER_SMOKE", "TW2002_BANK_SMOKE"):
        env.pop(stray, None)

    proc = subprocess.Popen(
        [sys.executable, str(bootstrap)],
        stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
        cwd=str(PROJECT_ROOT), env=env, start_new_session=True,
    )
    os.close(slave_fd)

    captured = b""
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

            grid = pyte_grid(captured, FULL_ROWS, FULL_COLS)
            if phase == "wait_launcher":
                if find_text(grid, "SELECT PROFILE") and find_text(grid, HANDLE):
                    os.write(master_fd, b"\r")
                    phase = "wait_frame"
            elif phase == "wait_frame":
                if find_text(grid, "PLAY SHELL"):
                    captured = _settle(master_fd, captured, 1.6)
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
        terminate_session_group(proc, grace_s=5.0)
        try:
            os.close(master_fd)
        except OSError:
            pass

    assert phase == "done", (
        f"pty CONN drive stalled in phase={phase!r}; last grid:\n"
        + "\n".join(pyte_grid(captured, FULL_ROWS, FULL_COLS))
    )
    return captured


# --------------------------------------------------------------------------
# The wire proof: three payloads, three distinct chips, on a real terminal
# --------------------------------------------------------------------------

@_PTY_SKIP
def test_connected_renders_conn_on_a_real_terminal(tmp_path) -> None:
    """THE pin this file exists for. Goes red if ``screens.py`` stops passing
    ``conn_chip`` — the deletion that previously left the whole suite green."""
    grid = pyte_grid(_drive(tmp_path, {"ok": True, "connected": True}),
                     FULL_ROWS, FULL_COLS)
    assert find_text(grid, "CONN"), (
        "CONN chip not visible on the settled cockpit; grid:\n" + "\n".join(grid)
    )


@_PTY_SKIP
def test_disconnected_renders_disc_on_a_real_terminal(tmp_path) -> None:
    """Second distinct output from a second distinct payload.

    Two states rather than one on purpose: a wire pinned by a single state
    can be satisfied by a hardcoded chip, which would not be a wire at all.
    """
    grid = pyte_grid(_drive(tmp_path, {"ok": True, "connected": False}),
                     FULL_ROWS, FULL_COLS)
    assert find_text(grid, "DISC"), (
        "DISC chip not visible when the daemon reports disconnected; grid:\n"
        + "\n".join(grid)
    )


@_PTY_SKIP
def test_unknown_connection_renders_its_own_marker_not_disc(tmp_path) -> None:
    """Honesty pin: absent ``connected`` must render ``DISC?``, not ``DISC``.

    "I know you are disconnected" and "I do not know" are different claims,
    and with an unusable payload only the second is true. Asserting the
    marker is present is not enough — a chip that rendered plain ``DISC``
    would satisfy that, since ``DISC`` is a prefix of ``DISC?``. So this
    also asserts the ``?`` is on the row.
    """
    grid = pyte_grid(_drive(tmp_path, {"ok": True}), FULL_ROWS, FULL_COLS)
    assert find_text(grid, "DISC?"), (
        "unknown connection state did not render `DISC?`; grid:\n" + "\n".join(grid)
    )
