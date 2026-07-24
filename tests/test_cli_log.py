"""Honest greenfield gap proof: ``tw log`` / ``tw trail`` are not wired.

Live ``cli.build_parser()`` exposes the shipped ops verb table (see README Verb
reference / ``WO-P2-OPS-VERB-SURFACE``). A ledger CLI verb waits on a later WO —
do not invent one here.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.session import cli

# Keep in sync with README Verb reference (shipped) + cli.build_parser().
_SHIPPED_VERBS = frozenset(
    {"status", "ensure", "screen", "stop", "do", "send", "read", "history", "watch"}
)


def test_parser_shipped_verb_allowlist():
    parser = cli.build_parser()
    status = parser.parse_args(["status"])
    ensure = parser.parse_args(["ensure", "--profile", "x"])
    screen = parser.parse_args(["screen"])
    stop = parser.parse_args(["stop"])
    do = parser.parse_args(["do", "d"])
    send = parser.parse_args(["send", "x"])
    read = parser.parse_args(["read"])
    history = parser.parse_args(["history"])
    watch = parser.parse_args(["watch"])
    assert status.func is cli.cmd_status
    assert ensure.func is cli.cmd_ensure
    assert screen.func is cli.cmd_screen
    assert stop.func is cli.cmd_stop
    assert do.func is cli.cmd_do
    assert send.func is cli.cmd_send
    assert read.func is cli.cmd_read
    assert history.func is cli.cmd_history
    assert watch.func is cli.cmd_watch
    # Subparser choices are exactly the live verb table.
    sub = next(
        a for a in parser._actions if getattr(a, "choices", None) is not None
    )
    assert set(sub.choices) == set(_SHIPPED_VERBS)


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
