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


# --------------------------------------------------------------------------
# WO-AUTOLOOP-PAUSE-RESUME — pause / relaunch adapters
# --------------------------------------------------------------------------

def test_pause_sends_the_pause_verb(monkeypatch, tmp_path):
    sink: list = []
    monkeypatch.setattr(_cli, "send_request", _spy({"ok": True, "paused": True}, sink))
    assert adapters.autoloop_pause(run_dir=tmp_path).ok is True
    assert sink[0][0] == "autoloop_pause"


def test_relaunch_sends_the_relaunch_verb_not_resume(monkeypatch, tmp_path):
    """The rename has to reach the wire. If this adapter still said
    `autoloop_resume` the daemon would answer `unknown_verb` and the
    operator would see a broken button instead of a working one."""
    sink: list = []
    monkeypatch.setattr(_cli, "send_request", _spy({"ok": True, "relaunched": True}, sink))
    assert adapters.autoloop_relaunch(run_dir=tmp_path).ok is True
    assert sink[0][0] == "autoloop_relaunch"
    assert sink[0][0] != "autoloop_resume"


def test_relaunch_carries_the_disclosure_fields_through_raw(monkeypatch, tmp_path):
    """The money-path contract. A caller cannot render the confirm gate
    honestly unless BOTH fields survive the adapter."""
    wire = {"ok": True, "relaunched": True,
            "replays_from_start": True, "sends_already_issued": 3}
    monkeypatch.setattr(_cli, "send_request", _spy(wire))
    raw = adapters.autoloop_relaunch(run_dir=tmp_path).raw
    assert raw["replays_from_start"] is True
    assert raw["sends_already_issued"] == 3


def test_unknown_send_count_stays_none_not_zero(monkeypatch, tmp_path):
    """`None` means the player never gave a count. Rendering it as "0 sends
    already issued" would be an affirmative claim that nothing reached the
    wire -- the same honest-`?` rule the coverage meter follows."""
    wire = {"ok": True, "relaunched": True,
            "replays_from_start": True, "sends_already_issued": None}
    monkeypatch.setattr(_cli, "send_request", _spy(wire))
    assert adapters.autoloop_relaunch(run_dir=tmp_path).raw["sends_already_issued"] is None


@pytest.mark.parametrize("verb_fn,reason", [
    (lambda **k: adapters.autoloop_pause(**k), "autoloop_unavailable"),
    (lambda **k: adapters.autoloop_relaunch(**k), "not_paused"),
])
def test_daemon_refusals_surface_as_reasons(monkeypatch, tmp_path, verb_fn, reason):
    monkeypatch.setattr(_cli, "send_request", _spy({"ok": False, "error": reason}))
    result = verb_fn(run_dir=tmp_path)
    assert result.ok is False and result.reason == reason


@pytest.mark.parametrize("fn", ["autoloop_pause", "autoloop_relaunch"])
def test_transport_failure_never_raises(monkeypatch, tmp_path, fn):
    monkeypatch.setattr(_cli, "send_request", _spy(OSError("socket gone")))
    result = getattr(adapters, fn)(run_dir=tmp_path)
    assert result.ok is False and result.reason == "unknown"


def test_there_is_no_autoloop_resume_adapter():
    """Structural companion to the daemon-side refusal: the word must not
    be reachable from the client either."""
    assert not hasattr(adapters, "autoloop_resume")
