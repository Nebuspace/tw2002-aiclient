"""Smoke proofs for Layer-B shared harness helpers (WO-P3-HARNESS-REHAB D1 lane 2).

Network-free, twclient-free, no cockpit chrome. Proves the helpers import
and behave well enough for later frame WOs to build on.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.fake_client import FakeClient
from tests.pty_helpers import (
    COLOR_SET_SGR_RE,
    find_text,
    pyte_grid,
    pyte_screen,
    set_winsize,
)


HELPERS = (
    Path(__file__).resolve().parent / "fake_client.py",
    Path(__file__).resolve().parent / "pty_helpers.py",
)


def test_helpers_do_not_import_twclient():
    """Layer-B consumers must stay on tw2002_aiclient / stdlib / pyte only."""
    for path in HELPERS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("twclient"), path
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith("twclient"), path


def test_fake_client_yields_events_then_none():
    client = FakeClient([{"screen": ["hi"]}, {"screen": ["bye"]}], gap_s=0.0)
    assert client.remaining == 2
    assert client.next_event() == {"screen": ["hi"]}
    assert client.next_event() == {"screen": ["bye"]}
    assert client.exhausted
    assert client.next_event(timeout=0.0) is None
    client.close()  # no-op, must not raise


def test_pyte_helpers_locate_text_and_color_attrs():
    # Minimal ANSI: clear, cyan "CREDITS" at home, then plain "SECTOR".
    captured = b"\x1b[2J\x1b[H\x1b[36mCREDITS\x1b[0m SECTOR"
    rows, cols = 5, 40
    screen = pyte_screen(captured, rows, cols)
    grid = pyte_grid(captured, rows, cols)
    pos = find_text(grid, "CREDITS")
    assert pos == (0, 0)
    cell = screen.buffer[0][0]
    assert cell.data == "C"
    assert cell.fg == "cyan"
    assert find_text(grid, "SECTOR") == (0, 8)
    assert COLOR_SET_SGR_RE.search(captured) is not None


def test_set_winsize_callable():
    # Smoke: symbol exists and is callable (real ioctl needs a pty fd —
    # capture_pty exercises that path when a Layer-B suite lands).
    assert callable(set_winsize)


def test_claim_ctty_opt_in_is_documented_kwarg():
    """Resize tests opt in via claim_ctty=True; default stays off (no SIGWINCH)."""
    import inspect

    from tests.pty_helpers import _claim_controlling_tty, capture_pty, capture_pty_with_keys

    assert callable(_claim_controlling_tty)
    for fn in (capture_pty, capture_pty_with_keys):
        params = inspect.signature(fn).parameters
        assert "claim_ctty" in params
        assert params["claim_ctty"].default is False
