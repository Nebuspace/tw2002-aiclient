"""`adapters.autoloop_stop` -- the panic path's transport (WO-P5-071).

All daemon I/O is mocked via monkeypatch on ``_cli.send_request``; no live
socket, mirroring ``tests/test_adapters_explore.py``.

The pins that matter here are about *honesty on failure*. An operator who
hit panic is entitled to know whether the halt reached a runner, so a
daemon refusal must survive as a distinguishable non-ok result rather than
being smoothed into a success or collapsed into a generic error.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient import adapters
from tw2002_aiclient.session import cli as _cli


def _spy(response, sink=None):
    def spy(verb, args, run_dir=None):
        if sink is not None:
            sink.append((verb, args, run_dir))
        if isinstance(response, Exception):
            raise response
        return response
    return spy


def test_sends_the_autoloop_stop_verb(monkeypatch, tmp_path):
    sink: list = []
    monkeypatch.setattr(_cli, "send_request", _spy({"ok": True, "stopping": True}, sink))
    result = adapters.autoloop_stop(run_dir=tmp_path)
    assert result.ok is True
    assert sink[0][0] == "autoloop_stop"
    assert sink[0][1] == {}


def test_carries_the_run_report_through_raw(monkeypatch, tmp_path):
    """`raw` keeps the wire dict so a caller can report the outcome; the
    daemon returns `stopping` plus the run report."""
    wire = {"ok": True, "stopping": True, "outcome": "operator_stop", "sends_issued": 7}
    monkeypatch.setattr(_cli, "send_request", _spy(wire))
    result = adapters.autoloop_stop(run_dir=tmp_path)
    assert result.raw["outcome"] == "operator_stop"
    assert result.raw["sends_issued"] == 7


def test_autoloop_unavailable_surfaces_as_a_reason_not_a_success(monkeypatch, tmp_path):
    """The one refusal the daemon itself produces (no player attached).

    Reported, not smoothed: a panic that reached no runner is a different
    fact from a panic that halted a run, and the operator needs to be able
    to tell them apart.
    """
    monkeypatch.setattr(_cli, "send_request", _spy({"ok": False, "error": "autoloop_unavailable"}))
    result = adapters.autoloop_stop(run_dir=tmp_path)
    assert result.ok is False
    assert result.reason == "autoloop_unavailable"


@pytest.mark.parametrize("boom", [OSError("socket gone"), ValueError("bad json"), RuntimeError()])
def test_transport_failure_never_raises(monkeypatch, tmp_path, boom):
    """Panic must not crash the cockpit when the daemon is unreachable --
    that is precisely when someone is pressing it."""
    monkeypatch.setattr(_cli, "send_request", _spy(boom))
    result = adapters.autoloop_stop(run_dir=tmp_path)
    assert result.ok is False
    assert result.reason == "unknown"
    assert type(boom).__name__ in result.detail


def test_missing_ok_key_is_treated_as_failure(monkeypatch, tmp_path):
    """A malformed reply is not evidence the run stopped. Absence of `ok`
    reads as failure, not as success-by-default."""
    monkeypatch.setattr(_cli, "send_request", _spy({"stopping": True}))
    assert adapters.autoloop_stop(run_dir=tmp_path).ok is False


def test_result_type_is_distinct_from_explore(monkeypatch, tmp_path):
    """Separate type by design -- a shared result would let an explore
    outcome be handed to a panic consumer with nothing catching it."""
    monkeypatch.setattr(_cli, "send_request", _spy({"ok": True}))
    result = adapters.autoloop_stop(run_dir=tmp_path)
    assert isinstance(result, adapters.AutoLoopResult)
    assert not isinstance(result, adapters.ExploreResult)


def test_stop_is_idempotent_from_the_callers_view(monkeypatch, tmp_path):
    """The verb is idempotent daemon-side (`_dispatch_autoloop_stop`: "never
    refuses"), so a double-press must not produce a second, different
    answer the cockpit has to reconcile."""
    monkeypatch.setattr(_cli, "send_request", _spy({"ok": True, "stopping": True}))
    first = adapters.autoloop_stop(run_dir=tmp_path)
    second = adapters.autoloop_stop(run_dir=tmp_path)
    assert first.ok is second.ok is True
