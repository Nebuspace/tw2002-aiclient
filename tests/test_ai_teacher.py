"""WO-BUILD-AI-TEACHER-ANALYZE-CLI -- the on-demand retrospective AI teacher.

Canon: ``canon/engine/ai-teacher.md``. Pins:

1. ``gather_escalation_context`` bundles frame + last-N ledger rows.
2. ``analyze_escalation`` with a valid backend draft writes through the real
   ``write_draft`` -- resulting file is ``approved: False`` and is not armed
   without a separate ``promote_draft``/``tw rule approve`` call.
3. A PvP-initiating draft is declined -- and no draft file is written
   (negative control: the drafts dir stays empty).
4. ``no_backend_configured`` always raises ``AITeacherBackendNotConfigured``.
5. A malformed backend response propagates ``RuleDocumentError`` from the
   kernel's strict parser, unswallowed.
6. Structural no-live-send-path pin over ``ai_teacher.py`` / ``teach_cli.py``,
   mirroring ``test_cockpit_analyze.py`` -- adapted because this module
   legitimately calls ``write_draft`` (a filesystem write, not a live send),
   so the grep targets the live-send primitive itself rather than the bare
   substring ``"write"``.
"""

from __future__ import annotations

import inspect
import json

import pytest

from tw2002_aiclient import ai_teacher, teach_cli
from tw2002_aiclient.rules.store import drafts_dir
from tw2002_aiclient.rules.writer import RuleWriteError

VALID_DRAFT = {
    "rule_id": "warp-confirm-yes",
    "when": "warp_confirm",
    "do": "send-y",
    "priority": 10,
}

PVP_DRAFT = {
    "rule_id": "attack-the-player",
    "when": "player_attack",
    "do": "attack-player",
    "priority": 10,
}

MALFORMED_DRAFT = {
    "rule_id": "bad-scope-rule",
    "when": "command_prompt",
    "do": "dock",
    "priority": 10,
    "scope": "not-a-real-scope",
}


def _fake_backend(draft: dict):
    def backend(context: dict) -> dict:
        return dict(draft)

    return backend


# ---------------------------------------------------------------------------
# 1 -- gather_escalation_context windowing
# ---------------------------------------------------------------------------


def test_gather_escalation_context_bundles_frame_and_ledger():
    frame = {"screen": "command_prompt", "credits": 100}
    entries = [{"n": i} for i in range(3)]
    context = ai_teacher.gather_escalation_context(frame, entries, window=10)
    assert context["frame"] == frame
    assert context["recent_ledger"] == entries


def test_gather_escalation_context_keeps_only_last_window():
    frame = {"screen": "command_prompt"}
    entries = [{"n": i} for i in range(25)]
    context = ai_teacher.gather_escalation_context(frame, entries, window=5)
    assert context["recent_ledger"] == entries[-5:]
    assert len(context["recent_ledger"]) == 5


def test_gather_escalation_context_none_ledger_is_empty_list():
    context = ai_teacher.gather_escalation_context({"screen": "x"}, None)
    assert context["recent_ledger"] == []


# ---------------------------------------------------------------------------
# 2 -- valid draft writes through the real write_draft, stays inert
# ---------------------------------------------------------------------------


def test_analyze_escalation_writes_inert_draft(tmp_path):
    result = ai_teacher.analyze_escalation(
        {"frame": {}, "recent_ledger": []},
        _fake_backend(VALID_DRAFT),
        state_dir=tmp_path,
    )
    assert result["declined"] is False
    path = result["draft"]
    on_disk = json.loads((tmp_path).joinpath("rules", "_drafts", "warp-confirm-yes.json").read_text())
    assert on_disk["approved"] is False
    assert on_disk["rule_id"] == "warp-confirm-yes"
    assert str(path).endswith("warp-confirm-yes.json")


def test_analyze_escalation_draft_not_in_blessed_store(tmp_path):
    ai_teacher.analyze_escalation(
        {"frame": {}, "recent_ledger": []},
        _fake_backend(VALID_DRAFT),
        state_dir=tmp_path,
    )
    blessed = tmp_path / "rules"
    blessed_rules = [p for p in blessed.glob("*.json")]
    assert blessed_rules == [], "draft must not appear in the blessed (armed) store"


# ---------------------------------------------------------------------------
# 3 -- ethos-bound decline, negative control: nothing written
# ---------------------------------------------------------------------------


def test_analyze_escalation_declines_pvp_draft(tmp_path):
    result = ai_teacher.analyze_escalation(
        {"frame": {}, "recent_ledger": []},
        _fake_backend(PVP_DRAFT),
        state_dir=tmp_path,
    )
    assert result["declined"] is True
    assert "reason" in result and result["reason"]


def test_analyze_escalation_pvp_decline_writes_nothing(tmp_path):
    ai_teacher.analyze_escalation(
        {"frame": {}, "recent_ledger": []},
        _fake_backend(PVP_DRAFT),
        state_dir=tmp_path,
    )
    drafts = drafts_dir(state_dir=tmp_path)
    written = list(drafts.glob("*.json")) if drafts.exists() else []
    assert written == [], "a declined proposal must leave the drafts dir empty"


# ---------------------------------------------------------------------------
# 4 -- no backend configured
# ---------------------------------------------------------------------------


def test_no_backend_configured_raises():
    with pytest.raises(ai_teacher.AITeacherBackendNotConfigured):
        ai_teacher.analyze_escalation({"frame": {}, "recent_ledger": []}, ai_teacher.no_backend_configured)


# ---------------------------------------------------------------------------
# 5 -- malformed backend output is not swallowed
# ---------------------------------------------------------------------------


def test_malformed_backend_output_propagates_rule_document_error(tmp_path):
    """``write_draft`` re-raises the kernel's strict-parse failure as
    ``RuleWriteError`` (its own type, wrapping the parser's message) --
    ``ai_teacher`` must not swallow it into a soft decline or a silent no-op.
    """
    with pytest.raises(RuleWriteError, match="scope"):
        ai_teacher.analyze_escalation(
            {"frame": {}, "recent_ledger": []},
            _fake_backend(MALFORMED_DRAFT),
            state_dir=tmp_path,
        )


# ---------------------------------------------------------------------------
# 6 -- structural no-live-send-path pin
# ---------------------------------------------------------------------------

_LIVE_SEND_TOKENS = ("session.send", ".send_raw(", "socket.socket", "subprocess", "os.system")


def test_ai_teacher_module_has_no_live_send_path():
    src = inspect.getsource(ai_teacher)
    for forbidden in _LIVE_SEND_TOKENS:
        assert forbidden not in src, (
            f"ai_teacher references {forbidden!r} -- no live-send path allowed; "
            "the AI teacher never live-drives (canon/engine/ai-teacher.md)"
        )


def test_teach_cli_module_has_no_live_send_path():
    src = inspect.getsource(teach_cli)
    for forbidden in _LIVE_SEND_TOKENS:
        assert forbidden not in src, (
            f"teach_cli references {forbidden!r} -- no live-send path allowed; "
            "the AI teacher never live-drives (canon/engine/ai-teacher.md)"
        )


def test_ai_teacher_only_write_path_is_write_draft():
    """Every disk-write in this module is the one sanctioned writer call.

    Mutation-resistant companion to the token pin above: rather than banning
    the substring ``"write"`` outright (``ai_teacher`` legitimately calls
    ``write_draft``, a filesystem draft write, not a live send), assert the
    module imports exactly the one writer symbol and never opens a file
    itself.
    """
    src = inspect.getsource(ai_teacher)
    assert "from .rules.writer import write_draft" in src
    for forbidden in ("open(", "os.open", "Path(", ".write_text(", ".write_bytes("):
        assert forbidden not in src, (
            f"ai_teacher references {forbidden!r} -- all persistence must route "
            "through write_draft, not a second write path"
        )
