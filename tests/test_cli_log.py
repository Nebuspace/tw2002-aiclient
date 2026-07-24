"""Honest greenfield gap proof: ``tw log`` / ``tw trail`` are not wired.

Live ``cli.build_parser()`` exposes only ``status`` and ``ensure``.
A ledger CLI verb waits on a later WO — do not invent one here.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.session import cli


def test_parser_has_status_and_ensure_only():
    parser = cli.build_parser()
    status = parser.parse_args(["status"])
    ensure = parser.parse_args(["ensure", "--profile", "x"])
    assert status.func is cli.cmd_status
    assert ensure.func is cli.cmd_ensure
    # Subparser choices are exactly the live verb table.
    sub = next(
        a for a in parser._actions if getattr(a, "choices", None) is not None
    )
    assert set(sub.choices) == {"status", "ensure"}


def test_log_verb_is_not_wired():
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["log"])
    assert exc.value.code == 2


def test_trail_alias_is_not_wired():
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["trail"])
    assert exc.value.code == 2
