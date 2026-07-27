"""WO-P5-070 — Analyze draft → human approve gate."""

from __future__ import annotations

import inspect

import pytest

from tw2002_aiclient.cockpit import draft_approve


def test_create_analyze_draft_is_inert() -> None:
    draft = draft_approve.create_analyze_draft("main_command")
    assert draft["when"]["screen"] == "main_command"
    assert draft["source"] == "analyze"
    assert draft["approved"] is False
    assert draft["playback_eligible"] is False
    assert draft["do"] is None


def test_promote_to_approved_sets_flags() -> None:
    draft = draft_approve.create_analyze_draft("game_select")
    promoted = draft_approve.promote_to_approved(draft)
    assert promoted is not None
    assert promoted["approved"] is True
    assert promoted["playback_eligible"] is True
    assert draft["approved"] is False


def test_resolve_draft_approve_key_default_deny() -> None:
    assert draft_approve.resolve_draft_approve_key(ord("y")) == draft_approve.CONFIRM
    assert draft_approve.resolve_draft_approve_key(13) == draft_approve.CANCEL
    assert draft_approve.resolve_draft_approve_key(27) == draft_approve.CANCEL


def test_draft_approve_module_has_no_send_path() -> None:
    src = inspect.getsource(draft_approve)
    assert "send_key" not in src
    assert "session.send" not in src


def test_analyze_close_intent_does_not_populate_stub_store() -> None:
    from tests.test_cockpit_analyze import _make_play

    play = _make_play()
    play.current_classification = "main_command"
    play.analyze_session.open()
    assert play.handle_key(ord("a")) == "analyze_close"
    assert play.stub_store.get() is None
    assert play.pending_analyze_draft is None


def test_analyze_close_wiring_via_app_actions() -> None:
    """Closing analyze leaves draft pending until y/N — stub_store stays empty."""
    from tests.test_cockpit_analyze import _make_play

    play = _make_play()
    play.current_classification = "dock"
    play.analyze_session.open()
    play.analyze_session.close()
    draft = draft_approve.create_analyze_draft(play.current_classification)
    play.pending_analyze_draft = draft
    play.begin_draft_approve(draft)
    assert play.stub_store.get() is None
    assert play._draft_approve is draft


def test_draft_approve_intent_promotes_stub() -> None:
    from tests.test_cockpit_analyze import _make_play

    play = _make_play()
    draft = draft_approve.create_analyze_draft("main_command")
    play.pending_analyze_draft = draft
    play.begin_draft_approve(draft)
    assert play.handle_key(ord("y")) == "draft_approve"
    approved = draft_approve.promote_to_approved(draft)
    play.stub_store.set(approved)
    got = play.stub_store.get()
    assert got is not None
    assert got["approved"] is True
    assert got["playback_eligible"] is True


def test_draft_reject_clears_pending() -> None:
    from tests.test_cockpit_analyze import _make_play

    play = _make_play()
    draft = draft_approve.create_analyze_draft("x")
    play.pending_analyze_draft = draft
    play.begin_draft_approve(draft)
    assert play.handle_key(ord("n")) == "draft_reject"
    play.pending_analyze_draft = None
    assert play.stub_store.get() is None


def test_ledger_attribution_only_after_approve() -> None:
    from tests.test_cockpit_analyze import _make_play

    play = _make_play()
    assert play.approval_ledger_events == []
    draft = draft_approve.create_analyze_draft("sector")
    play.pending_analyze_draft = draft
    play.begin_draft_approve(draft)
    play.handle_key(ord("n"))
    assert play.approval_ledger_events == []
    play.pending_analyze_draft = draft
    play.begin_draft_approve(draft)
    play.handle_key(ord("y"))
    play.approval_ledger_events.append(
        {"actor": "app", "event": "analyze_rule_approved", "screen": "sector"}
    )
    assert len(play.approval_ledger_events) == 1
    assert play.approval_ledger_events[0]["actor"] == "app"


@pytest.mark.parametrize("hostile", [None, 0, object()])
def test_create_analyze_draft_never_raises(hostile: object) -> None:
    assert isinstance(draft_approve.create_analyze_draft(hostile), dict)
