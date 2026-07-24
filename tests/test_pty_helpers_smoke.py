"""WO-P3-HARNESS-REHAB D1 lane-3 — smallest Accept proof for pty helpers.

Proves ``tests/pty_helpers.py`` + ``tests/fake_client.py`` collect/import
green against ``tw2002_aiclient`` only (no ``twclient``). Does NOT drive
spectate TUI.
"""

from __future__ import annotations

import ast
import os
import pty
from pathlib import Path

from tw2002_aiclient.session.terminal import TerminalScreen, init_locale

from .fake_client import FakeClient
from .pty_helpers import (
    find_text,
    pty_curses_supported,
    pyte_grid,
    set_winsize,
)

_HELPERS = Path(__file__).resolve().parent / "pty_helpers.py"
_FAKE = Path(__file__).resolve().parent / "fake_client.py"
_SMOKE = Path(__file__).resolve()


def _assert_no_twclient(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("twclient"), path
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not mod.startswith("twclient"), path


def test_harness_modules_import_tw2002_aiclient_only():
    for path in (_HELPERS, _FAKE, _SMOKE):
        _assert_no_twclient(path)


def test_fake_client_scripted_events():
    client = FakeClient([{"kind": "tick"}, {"kind": "done"}], gap_s=0.0)
    assert client.next_event() == {"kind": "tick"}
    assert client.next_event() == {"kind": "done"}
    assert client.next_event(timeout=0.01) is None
    client.close()


def test_set_winsize_on_openpty():
    master_fd, slave_fd = pty.openpty()
    try:
        set_winsize(slave_fd, 24, 80)
    finally:
        os.close(slave_fd)
        os.close(master_fd)


def test_pyte_grid_finds_painted_text():
    # Home + plain text — enough to prove pyte replay without curses/TUI.
    captured = b"\x1b[HCREDITS\r\n"
    grid = pyte_grid(captured, 24, 80)
    loc = find_text(grid, "CREDITS")
    assert loc is not None
    assert loc[0] == 0


def test_tw2002_aiclient_terminal_feeds_cp437():
    init_locale()
    screen = TerminalScreen(columns=80, lines=25)
    screen.feed(b"hello")
    assert "hello" in "".join(screen.raw_display())


def test_pty_curses_probe_is_bool():
    assert isinstance(pty_curses_supported(), bool)
