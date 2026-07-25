"""WO-AUDIT-PLAYER-BANK-STORE-HONESTY — Layer-B proof at the operator's screen.

Accept #1 is a claim about what a human *sees*, not about a return value, so
it is proven where they see it: real curses in a real pty, driving the real
``app._run_bank`` loop against a real bank file on disk, replayed through pyte.

Three scenarios, three different screens:

* a genuinely absent bank        -> the column header and ``(bank empty …)``
* a bank the process may not read -> ``bank could not be read``, cause ``denied``
* a bank whose bytes are garbage  -> ``bank could not be read``, cause ``corrupt``

Before this WO all three painted the *same* screen -- the empty one -- because
``player_bank._load_bank_raw`` answered ``{"version": 1, "players": []}`` to
every one of them. The grid assertions below are two-sided on purpose: the
failure screens must not merely gain a warning, they must LOSE the column
header and the ``(bank empty …)`` line, because a header above no rows is a
table of zero rows and zero is a count nobody was entitled to report.

Layer-A coverage for the classification itself lives in
``tests/test_player_bank.py``; this file only proves the ``app.py`` catch and
the ``screens.py`` render around it. Isolation: ``player_bank.BANK_PATH`` and
``credentials.list_profile_summaries`` are both redirected inside the spawned
process, so neither the real ``state/`` nor the real ``config/`` tree is read.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from tw2002_aiclient.screens import (
    BANK_EMPTY_LINE,
    BANK_UNREADABLE_HEAD,
    BANK_UNREADABLE_HINT,
)

from .pty_helpers import capture_pty, pty_curses_supported, pyte_grid

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)
_ROOT_SKIP = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses file permissions — the denial can't be provoked",
)

# Wide enough that a tmp-dir bank path in the reason line is not clipped by
# _safe_addstr, so an assertion about the reason is about the reason and not
# about the terminal width.
ROWS, COLS = 30, 160

# The column header BankViewScreen paints above a real listing. Its ABSENCE is
# half the proof on a failure screen.
HEADER_TOKEN = "last_played"

_BOOTSTRAP = r"""
import os
import sys

os.environ.pop("TW2002_LAUNCHER_SMOKE", None)
os.environ.pop("TW2002_HANDOFF_SMOKE", None)
os.environ.pop("TW2002_BANK_SMOKE", None)
os.environ.pop("TW2002_LAUNCHER_DEMO", None)

sys.path.insert(0, {project_root!r})

from pathlib import Path

from tw2002_aiclient.session import credentials, player_bank

# Real file on disk, real conditions -- only WHICH file is redirected.
player_bank.BANK_PATH = Path({bank_path!r})
# No profiles, so every row on screen (or its absence) is about the bank.
credentials.list_profile_summaries = lambda: []

import curses

from tw2002_aiclient import app

curses.wrapper(app._run_bank)
"""


def _drive_bank_pty(bank_path: Path, timeout: float = 12.0) -> list[str]:
    """Spawn the real bank view in a pty and return the pyte grid.

    ``capture_pty`` sends its default ``q`` during teardown, which is exactly
    what ``BankViewScreen.handle_key`` answers ``"quit"`` to, so ``_run_bank``
    returns and ``curses.wrapper`` tears the screen down cleanly rather than
    being killed mid-frame.
    """
    script = _BOOTSTRAP.format(project_root=str(PROJECT_ROOT), bank_path=str(bank_path))
    captured = capture_pty(
        [sys.executable, "-c", script],
        # The footer is the last thing painted before refresh(), so once it is
        # on the wire the whole frame has been queued.
        lambda buf: b"launcher" in buf,
        timeout=timeout,
        rows=ROWS,
        cols=COLS,
    )
    return pyte_grid(captured, ROWS, COLS)


def _joined(grid: list[str]) -> str:
    return "\n".join(grid)


@_PTY_SKIP
def test_absent_bank_paints_the_empty_listing(tmp_path):
    """The control. A real negative keeps the table and the empty line."""
    grid = _joined(_drive_bank_pty(tmp_path / "player_bank.json"))
    assert BANK_EMPTY_LINE in grid
    assert HEADER_TOKEN in grid
    assert BANK_UNREADABLE_HEAD not in grid


@_PTY_SKIP
@_ROOT_SKIP
def test_unreadable_bank_paints_a_failure_not_an_empty_listing(tmp_path):
    bank_path = tmp_path / "player_bank.json"
    bank_path.write_text(
        json.dumps({"version": 1, "players": [{"name": "ghost"}]}), encoding="utf-8"
    )
    os.chmod(bank_path, 0o000)
    try:
        grid = _joined(_drive_bank_pty(bank_path))
    finally:
        os.chmod(bank_path, 0o600)

    assert BANK_UNREADABLE_HEAD in grid
    assert BANK_UNREADABLE_HINT in grid
    assert "denied: Permission denied" in grid
    # The two-sided half: the operator is not told a negative that was never
    # established. No empty-line claim, and no zero-row table implying one.
    assert BANK_EMPTY_LINE not in grid
    assert HEADER_TOKEN not in grid
    # A bank row existed and went unread -- it must not have leaked onto the
    # screen either, since nothing was successfully read.
    assert "ghost" not in grid


@_PTY_SKIP
def test_corrupt_bank_paints_a_different_failure_than_a_denied_one(tmp_path):
    """Accept #2 at the surface: the two causes do not render alike.

    "I was not allowed to look" and "I looked and it was garbage" call for
    different actions, so the operator can tell which one happened without
    leaving the screen.
    """
    bank_path = tmp_path / "player_bank.json"
    bank_path.write_text("{not json at all,,,", encoding="utf-8")
    grid = _joined(_drive_bank_pty(bank_path))

    assert BANK_UNREADABLE_HEAD in grid
    assert "corrupt: invalid JSON" in grid
    assert "denied" not in grid
    assert BANK_EMPTY_LINE not in grid
    assert HEADER_TOKEN not in grid


@_PTY_SKIP
def test_non_utf8_bank_reaches_the_screen_instead_of_killing_the_view(tmp_path):
    """The condition that used to escape as an unhandled UnicodeDecodeError.

    Pre-WO this raised straight out of ``list_players()`` through
    ``_run_bank`` and ``curses.wrapper``, so the bank view did not render a
    wrong answer -- it rendered nothing at all and took the process with it.
    A drawn frame carrying the reason is the proof it is now handled.
    """
    bank_path = tmp_path / "player_bank.json"
    bank_path.write_bytes(b'{"version": 1, "players": [{"name": "\xff\xfe"}]}')
    grid = _joined(_drive_bank_pty(bank_path))

    assert BANK_UNREADABLE_HEAD in grid
    assert "corrupt: not valid UTF-8" in grid
    assert BANK_EMPTY_LINE not in grid
    assert HEADER_TOKEN not in grid
