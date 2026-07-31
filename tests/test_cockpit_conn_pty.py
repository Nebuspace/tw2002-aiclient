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

# Harness: shared ``drive_play_shell_pty`` (WO-PTY-DRIVE-HOIST). Assertions
# stay suite-local; only the Layer-B drive loop is shared.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.pty_ui


from .pty_helpers import (
    drive_play_shell_pty,
    find_text,
    pty_curses_supported,
    pyte_grid,
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
    capture1, _ = drive_play_shell_pty(
        bootstrap,
        project_root=PROJECT_ROOT,
        rows=FULL_ROWS,
        cols=FULL_COLS,
        handle=HANDLE,
        timeout=timeout,
    )
    return capture1


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
def test_connected_conn_rides_the_top_strip_only(tmp_path) -> None:
    """Accept #3 (WO-PLAY-STRIP-TRAINER-CHROME / DECISION
    `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 3): CONN moved onto
    the row-1 profile strip and must be ABSENT from the bottom control
    strip it used to render on. ``find_text`` alone (the pin above) cannot
    see this — it is satisfied by CONN appearing anywhere at all, including
    a stray second copy left behind on the old row. This test additionally
    pins WHERE the chip is (near the top, under the outer frame's own
    title row) and that it never appears a second time anywhere else on
    the settled frame."""
    grid = pyte_grid(_drive(tmp_path, {"ok": True, "connected": True}),
                     FULL_ROWS, FULL_COLS)
    hit = find_text(grid, "CONN")
    assert hit, "CONN chip not visible on the settled cockpit; grid:\n" + "\n".join(grid)
    row, _col = hit
    assert row <= 3, (
        f"CONN chip found at row {row}, expected on the top profile strip "
        "(row 1, just under the outer frame's title row); grid:\n"
        + "\n".join(grid)
    )
    other_rows = [r for r, line in enumerate(grid) if "CONN" in line and r != row]
    assert not other_rows, (
        f"CONN also appears at row(s) {other_rows} -- expected exactly once, "
        "on the top strip, and absent from the bottom control strip; "
        "grid:\n" + "\n".join(grid)
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
