"""AUDIT-WIRE-ACTION-SAFETY-COVERAGE-STARTUP-ASSERT — boot wire pins."""

from __future__ import annotations

import inspect

from tw2002_aiclient import app as app_mod
from tw2002_aiclient.action_safety import assert_coverage_map_intact


def test_app_main_wires_assert_coverage_map_intact() -> None:
    src = inspect.getsource(app_mod.main)
    assert "assert_coverage_map_intact" in src
    assert "action_safety" in src


def test_help_path_does_not_require_coverage_assert(capsys) -> None:
    """--help must stay TTY-free and must not depend on coverage I/O."""
    assert app_mod.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert out.strip()


def test_assert_coverage_map_intact_still_green() -> None:
    assert_coverage_map_intact()
