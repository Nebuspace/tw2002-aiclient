"""Unit tests for explore adapter functions (WO-PLAY-EXPLORE-ADAPTER).

All daemon I/O is mocked via monkeypatch on ``_cli.send_request``; no live
daemon is required.  Covers:
- payload mapping for explore_start (world_id always sent; min_sectors /
  turn_budget included only when not None — mirrors cmd_explore_start discipline)
- explore_status / explore_stop send matching verbs with empty payloads
- explore_start_for_profile derives world_id via world_identity
- transport failures → ExploreResult(ok=False) never bare exceptions
- daemon ok=False → ExploreResult(ok=False, reason=..., detail=...)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient import adapters
from tw2002_aiclient.adapters import ExploreResult
from tw2002_aiclient.session import cli as _cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _DuckProfile:
    """Duck-typed profile exposing host / game_letter / handle."""

    def __init__(self, host="tw.example.com", game_letter="A", handle="Trader"):
        self.host = host
        self.game_letter = game_letter
        self.handle = handle


def _make_send_request_spy(return_value: dict):
    """Return (spy_fn, calls_list) where spy_fn records (verb, payload, run_dir)."""
    calls: list[tuple] = []

    def _spy(verb: str, payload: dict, *, run_dir: Path | None = None) -> dict:
        calls.append((verb, dict(payload), run_dir))
        return return_value

    return _spy, calls


# ---------------------------------------------------------------------------
# explore_start — payload mapping (Accept criterion 1)
# ---------------------------------------------------------------------------


def test_explore_start_sends_world_id(monkeypatch, tmp_path):
    spy, calls = _make_send_request_spy({"ok": True})
    monkeypatch.setattr(_cli, "send_request", spy)

    result = adapters.explore_start("tw_example_com__A__Trader", run_dir=tmp_path)

    assert result.ok is True
    assert len(calls) == 1
    verb, payload, _ = calls[0]
    assert verb == "explore_start"
    assert payload["world_id"] == "tw_example_com__A__Trader"


def test_explore_start_omits_min_sectors_when_not_supplied(monkeypatch, tmp_path):
    spy, calls = _make_send_request_spy({"ok": True})
    monkeypatch.setattr(_cli, "send_request", spy)

    adapters.explore_start("slug", run_dir=tmp_path)

    _, payload, _ = calls[0]
    assert "min_sectors" not in payload
    assert "turn_budget" not in payload


def test_explore_start_includes_min_sectors_when_supplied(monkeypatch, tmp_path):
    """Accept criterion 1: explore_start("slug", min_sectors=5) → payload has min_sectors=5."""
    spy, calls = _make_send_request_spy({"ok": True})
    monkeypatch.setattr(_cli, "send_request", spy)

    adapters.explore_start("slug", min_sectors=5, run_dir=tmp_path)

    _, payload, _ = calls[0]
    assert payload["min_sectors"] == 5
    assert "turn_budget" not in payload


def test_explore_start_includes_turn_budget_when_supplied(monkeypatch, tmp_path):
    spy, calls = _make_send_request_spy({"ok": True})
    monkeypatch.setattr(_cli, "send_request", spy)

    adapters.explore_start("slug", turn_budget=100, run_dir=tmp_path)

    _, payload, _ = calls[0]
    assert payload["turn_budget"] == 100
    assert "min_sectors" not in payload


def test_explore_start_includes_both_when_supplied(monkeypatch, tmp_path):
    spy, calls = _make_send_request_spy({"ok": True})
    monkeypatch.setattr(_cli, "send_request", spy)

    adapters.explore_start("slug", min_sectors=10, turn_budget=200, run_dir=tmp_path)

    _, payload, _ = calls[0]
    assert payload == {"world_id": "slug", "min_sectors": 10, "turn_budget": 200}


def test_explore_start_raw_is_wire_dict(monkeypatch, tmp_path):
    wire = {"ok": True, "distinct_sectors": 42, "outcome": "running"}
    spy, _ = _make_send_request_spy(wire)
    monkeypatch.setattr(_cli, "send_request", spy)

    result = adapters.explore_start("slug", run_dir=tmp_path)

    assert result.ok is True
    assert result.raw == wire


# ---------------------------------------------------------------------------
# explore_status (Accept criterion 2)
# ---------------------------------------------------------------------------


def test_explore_status_sends_correct_verb(monkeypatch, tmp_path):
    spy, calls = _make_send_request_spy({"ok": True})
    monkeypatch.setattr(_cli, "send_request", spy)

    result = adapters.explore_status(run_dir=tmp_path)

    assert result.ok is True
    assert calls[0][0] == "explore_status"
    assert calls[0][1] == {}  # empty payload


# ---------------------------------------------------------------------------
# explore_stop (Accept criterion 2)
# ---------------------------------------------------------------------------


def test_explore_stop_sends_correct_verb(monkeypatch, tmp_path):
    spy, calls = _make_send_request_spy({"ok": True})
    monkeypatch.setattr(_cli, "send_request", spy)

    result = adapters.explore_stop(run_dir=tmp_path)

    assert result.ok is True
    assert calls[0][0] == "explore_stop"
    assert calls[0][1] == {}  # empty payload


# ---------------------------------------------------------------------------
# explore_start_for_profile (Accept criterion 3)
# ---------------------------------------------------------------------------


def test_explore_start_for_profile_derives_world_id(monkeypatch, tmp_path):
    """Accept criterion 3: explore_start_for_profile uses world_identity under the hood."""
    spy, calls = _make_send_request_spy({"ok": True})
    monkeypatch.setattr(_cli, "send_request", spy)

    profile = _DuckProfile(host="tw.example.com", game_letter="A", handle="Trader")
    result = adapters.explore_start_for_profile(profile, run_dir=tmp_path)

    assert result.ok is True
    _, payload, _ = calls[0]
    # world_id_from_profile: host lowercased+sanitized, game_letter, handle
    assert payload["world_id"] == "tw_example_com__A__Trader"


def test_explore_start_for_profile_passes_min_sectors(monkeypatch, tmp_path):
    spy, calls = _make_send_request_spy({"ok": True})
    monkeypatch.setattr(_cli, "send_request", spy)

    profile = _DuckProfile(host="h", game_letter="Z", handle="Zapper")
    adapters.explore_start_for_profile(profile, min_sectors=3, run_dir=tmp_path)

    _, payload, _ = calls[0]
    assert payload["min_sectors"] == 3
    assert "turn_budget" not in payload


def test_explore_start_for_profile_bad_profile_raises(tmp_path):
    """Bad profile (missing handle) → WorldIdentityError, not swallowed."""
    from tw2002_aiclient.world_identity import WorldIdentityError

    class _BadProfile:
        host = "h"
        game_letter = "A"
        handle = None  # missing

    with pytest.raises(WorldIdentityError):
        adapters.explore_start_for_profile(_BadProfile(), run_dir=tmp_path)


# ---------------------------------------------------------------------------
# Transport failures → ok=False, never raises (Accept criterion 4)
# ---------------------------------------------------------------------------


def test_explore_start_transport_exception_returns_ok_false(monkeypatch, tmp_path):
    def _boom(*a, **kw):
        raise OSError("connection refused")

    monkeypatch.setattr(_cli, "send_request", _boom)

    result = adapters.explore_start("slug", run_dir=tmp_path)

    assert isinstance(result, ExploreResult)
    assert result.ok is False
    assert result.reason == "unknown"
    assert "OSError" in (result.detail or "")


def test_explore_stop_transport_exception_returns_ok_false(monkeypatch, tmp_path):
    def _boom(*a, **kw):
        raise RuntimeError("socket timeout")

    monkeypatch.setattr(_cli, "send_request", _boom)

    result = adapters.explore_stop(run_dir=tmp_path)

    assert result.ok is False
    assert result.reason == "unknown"


def test_explore_status_transport_exception_returns_ok_false(monkeypatch, tmp_path):
    def _boom(*a, **kw):
        raise ConnectionError("daemon gone")

    monkeypatch.setattr(_cli, "send_request", _boom)

    result = adapters.explore_status(run_dir=tmp_path)

    assert result.ok is False
    assert result.reason == "unknown"


# ---------------------------------------------------------------------------
# Daemon ok=False → ExploreResult(ok=False) with reason + detail
# ---------------------------------------------------------------------------


def test_explore_start_daemon_failure_maps_to_ok_false(monkeypatch, tmp_path):
    spy, _ = _make_send_request_spy({"ok": False, "error": "explore_already_running"})
    monkeypatch.setattr(_cli, "send_request", spy)

    result = adapters.explore_start("slug", run_dir=tmp_path)

    assert result.ok is False
    assert result.reason == "explore_already_running"
    assert result.detail == "explore_already_running"


def test_explore_start_daemon_failure_with_detail(monkeypatch, tmp_path):
    wire = {"ok": False, "error": "world_not_found", "detail": "no world slug 'bad'"}
    spy, _ = _make_send_request_spy(wire)
    monkeypatch.setattr(_cli, "send_request", spy)

    result = adapters.explore_start("bad", run_dir=tmp_path)

    assert result.ok is False
    assert result.reason == "world_not_found"
    assert "no world slug" in (result.detail or "")
    assert result.raw == wire


def test_explore_stop_daemon_failure_maps_to_ok_false(monkeypatch, tmp_path):
    spy, _ = _make_send_request_spy({"ok": False, "error": "explore_not_running"})
    monkeypatch.setattr(_cli, "send_request", spy)

    result = adapters.explore_stop(run_dir=tmp_path)

    assert result.ok is False
    assert result.reason == "explore_not_running"


def test_explore_status_daemon_failure_maps_to_ok_false(monkeypatch, tmp_path):
    spy, _ = _make_send_request_spy({"ok": False, "error": "daemon_not_running"})
    monkeypatch.setattr(_cli, "send_request", spy)

    result = adapters.explore_status(run_dir=tmp_path)

    assert result.ok is False
    assert result.reason == "daemon_not_running"


# ---------------------------------------------------------------------------
# ExploreResult is a frozen dataclass
# ---------------------------------------------------------------------------


def test_explore_result_is_frozen():
    r = ExploreResult(ok=True)
    with pytest.raises((AttributeError, TypeError)):
        r.ok = False  # type: ignore[misc]


def test_explore_result_defaults():
    r = ExploreResult(ok=False)
    assert r.reason is None
    assert r.detail is None
    assert r.raw is None
