"""WO-TUI-HELP-ARGV: ``--help`` / ``-h`` must not enter curses."""

from __future__ import annotations

import curses
import subprocess
import sys
from pathlib import Path

import pytest

from tw2002_aiclient import app

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_prints_usage_and_skips_curses_wrapper(monkeypatch, flag, capsys):
    called: list[bool] = []

    def _boom(*_a, **_k):
        called.append(True)
        raise AssertionError("curses.wrapper must not run for --help")

    monkeypatch.setattr(curses, "wrapper", _boom)
    assert app.main([flag]) == 0
    assert called == []
    out = capsys.readouterr().out
    assert "usage: tw2002-aiclient" in out
    assert "--help" in out


def test_unknown_argv_exits_2_without_curses(monkeypatch, capsys):
    def _boom(*_a, **_k):
        raise AssertionError("curses.wrapper must not run for bad argv")

    monkeypatch.setattr(curses, "wrapper", _boom)
    assert app.main(["--nope"]) == 2
    err = capsys.readouterr().err
    assert "unexpected argument" in err


def test_module_help_subprocess_exits_0():
    """CI has no checkout ``.venv``; exercise the same entry as ``python -m``."""
    proc = subprocess.run(
        [sys.executable, "-m", "tw2002_aiclient", "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "usage: tw2002-aiclient" in proc.stdout
