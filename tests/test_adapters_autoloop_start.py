"""`adapters.autoloop_start` -- the money path's transport (WO-PLAY-AUTOLOOP-START).

All daemon I/O is mocked via monkeypatch on ``_cli.send_request``; no live
socket, mirroring ``tests/test_adapters_autoloop.py``.

Two properties carry the weight here, and neither is about the happy path:

* **A blank name never reaches the wire.** The refusal has to be reachable
  with no daemon at all, because "there is no loop to name" and "there is no
  daemon" are the same moment for a cold cockpit. A version that round-trips
  to learn `missing_name` would arm nothing but would also look, to a caller,
  like a transport failure it might retry.
* **`force` is not a parameter.** The daemon refuses it; a keyword that
  exists only to be refused invites a confirm prompt promising a waiver
  the socket cannot grant. ``cycles`` *is* a parameter (WO-AUTOLOOP-CYCLES)
  and is clamped on the daemon.
"""

from __future__ import annotations

import inspect

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


def _never_called(sink):
    def spy(verb, args, run_dir=None):
        sink.append((verb, args, run_dir))
        raise AssertionError(f"reached the wire with {verb} {args}")
    return spy


def test_sends_the_autoloop_start_verb_with_the_name(monkeypatch, tmp_path):
    sink: list = []
    monkeypatch.setattr(_cli, "send_request", _spy({"ok": True, "started": True}, sink))
    result = adapters.autoloop_start("grind-alpha", run_dir=tmp_path)
    assert result.ok is True
    assert sink[0][0] == "autoloop_start"
    assert sink[0][1] == {"name": "grind-alpha"}


def test_floor_is_omitted_when_not_supplied(monkeypatch, tmp_path):
    """`None` -> omit, so the daemon applies its own policy. Mirrors
    `explore_start`'s discipline; an explicit `"floor": None` on the wire
    would be a different request than "no opinion"."""
    sink: list = []
    monkeypatch.setattr(_cli, "send_request", _spy({"ok": True}, sink))
    adapters.autoloop_start("grind-alpha", run_dir=tmp_path)
    assert "floor" not in sink[0][1]


def test_floor_is_sent_when_supplied(monkeypatch, tmp_path):
    sink: list = []
    monkeypatch.setattr(_cli, "send_request", _spy({"ok": True}, sink))
    adapters.autoloop_start("grind-alpha", floor=500, run_dir=tmp_path)
    assert sink[0][1] == {"name": "grind-alpha", "floor": 500}


def test_a_bad_floor_is_the_daemon_s_refusal_not_a_local_one(monkeypatch, tmp_path):
    """The adapter does NOT re-validate `floor`; it forwards and lets the
    named `invalid_floor` come back. Pins the single-owner decision: if
    someone later adds a local copy of the rule, this goes red and they have
    to decide deliberately rather than by accident."""
    sink: list = []
    monkeypatch.setattr(
        _cli, "send_request", _spy({"ok": False, "error": "invalid_floor"}, sink)
    )
    result = adapters.autoloop_start("grind-alpha", floor=True, run_dir=tmp_path)
    assert sink[0][1]["floor"] is True      # forwarded, not swallowed
    assert result.ok is False
    assert result.reason == "invalid_floor"


def test_blank_name_fails_closed_without_touching_the_wire(monkeypatch, tmp_path):
    sink: list = []
    monkeypatch.setattr(_cli, "send_request", _never_called(sink))
    for blank in ("", "   ", "\t\n"):
        result = adapters.autoloop_start(blank, run_dir=tmp_path)
        assert result.ok is False
        assert result.reason == "missing_name"
    assert sink == []


def test_non_string_name_fails_closed_without_touching_the_wire(monkeypatch, tmp_path):
    sink: list = []
    monkeypatch.setattr(_cli, "send_request", _never_called(sink))
    for bogus in (None, 0, 1, True, [], {}, object()):
        result = adapters.autoloop_start(bogus, run_dir=tmp_path)
        assert result.ok is False, f"{bogus!r} armed something"
        assert result.reason == "missing_name"
    assert sink == []


def test_daemon_refusal_survives_as_a_typed_reason(monkeypatch, tmp_path):
    """Every refusal the daemon can produce stays machine-readable rather
    than being smoothed into a generic failure."""
    for code in (
        "autoloop_unavailable",
        "missing_name",
        "invalid_floor",
        "invalid_cycles",
        "unsupported_arg:force",
        "floor_unsupported",
        "invalid_turn_budget",
        "turn_budget_unsupported",
        "locked_by_active_driver",
    ):
        monkeypatch.setattr(_cli, "send_request", _spy({"ok": False, "error": code}))
        result = adapters.autoloop_start("grind-alpha", run_dir=tmp_path)
        assert result.ok is False
        assert result.reason == code


def test_transport_failure_never_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(_cli, "send_request", _spy(OSError("socket gone")))
    result = adapters.autoloop_start("grind-alpha", run_dir=tmp_path)
    assert result.ok is False
    assert result.reason == "unknown"
    assert "OSError" in (result.detail or "")


def test_the_run_report_survives_in_raw(monkeypatch, tmp_path):
    wire = {"ok": True, "started": True, "name": "grind-alpha", "steps": 12}
    monkeypatch.setattr(_cli, "send_request", _spy(wire))
    result = adapters.autoloop_start("grind-alpha", run_dir=tmp_path)
    assert result.raw["steps"] == 12


def test_cycles_is_a_parameter_force_is_not():
    """``cycles`` unlocked in WO-AUTOLOOP-CYCLES; ``force`` stays absent."""
    params = set(inspect.signature(adapters.autoloop_start).parameters)
    assert "cycles" in params
    assert "force" not in params


def test_cycles_reaches_the_wire(monkeypatch, tmp_path):
    sink = []
    monkeypatch.setattr(_cli, "send_request", _spy({"ok": True, "started": True}, sink))
    result = adapters.autoloop_start("grind-alpha", cycles=7, run_dir=tmp_path)
    assert result.ok is True
    assert sink[0][0] == "autoloop_start"
    assert sink[0][1]["cycles"] == 7


def test_a_missing_ok_key_is_not_read_as_success(monkeypatch, tmp_path):
    """A malformed response must not arm-by-omission. `resp.get("ok")` is
    falsy for a dict that never mentions it."""
    monkeypatch.setattr(_cli, "send_request", _spy({"started": True}))
    result = adapters.autoloop_start("grind-alpha", run_dir=tmp_path)
    assert result.ok is False
