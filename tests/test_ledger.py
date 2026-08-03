"""PWO-094 / PWO-025 residual — LedgerWriter schema + actor tagging."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tw2002_aiclient.ledger import (
    REDACTED,
    LedgerWriter,
    compute_reward,
    extract_prompt,
    read_entries,
    render_trail_line,
)
from tw2002_aiclient.session.session import VALID_SENDERS

PRE = (
    "You have 1,000 credits.\n"
    "Turns left: 50\n"
    "50 empty cargo holds\n"
    "Your offer [158]?"
)
POST = (
    "You have 1,230 credits.\n"
    "Turns left: 49\n"
    "49 empty cargo holds\n"
    "Command [TL=49]:"
)


def test_record_do_app_actor_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path=path)
    entry = writer.record_do(
        PRE,
        "158",
        secret=False,
        post_text=POST,
        settled_class="port_trade",
        actor="app",
        session_id="sess-app-1",
        intent="selling organics",
    )
    assert entry["actor"] == "app"
    assert entry["session_id"] == "sess-app-1"
    assert entry["input"] == "158"
    assert entry["prompt"] == "Your offer [158]?"
    assert entry["reward"]["d_credits"] == 230
    assert entry["reward"]["d_turns"] == -1
    assert entry["reward"]["d_cargo"] == -1
    assert "ts" in entry

    rows = read_entries(path)
    assert len(rows) == 1
    assert rows[0]["actor"] == "app"
    assert rows[0]["session_id"] == "sess-app-1"
    # JSONL round-trip
    raw = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(raw) == 1
    assert json.loads(raw[0])["actor"] == "app"


def test_record_do_human_actor_tag(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path=path)
    entry = writer.record_do(
        "Command [TL=40]:",
        "d",
        secret=False,
        post_text="Sector 12\nCommand [TL=39]:",
        settled_class="main_command",
        actor="human",
        session_id="sess-human-1",
    )
    assert entry["actor"] == "human"
    assert entry["actor"] in VALID_SENDERS
    rows = read_entries(path)
    assert rows[0]["actor"] == "human"


def test_secret_send_redacts_input_and_prompt(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path=path)
    entry = writer.record_do(
        "Please enter your password:",
        "s3cret-value",
        secret=True,
        post_text="Password accepted.\nCommand [TL=50]:",
        settled_class="main_command",
        actor="human",
        session_id="sess-secret",
    )
    assert entry["input"] == REDACTED
    assert entry["prompt"] == REDACTED
    blob = path.read_text(encoding="utf-8")
    assert "s3cret-value" not in blob
    assert entry["input"] == REDACTED


def test_password_shaped_prompt_redacted_even_without_secret_flag() -> None:
    assert extract_prompt("Enter password now:") == REDACTED
    assert extract_prompt("Your offer [10]?") == "Your offer [10]?"


def test_refuse_ai_actor(tmp_path: Path) -> None:
    writer = LedgerWriter(path=tmp_path / "ledger.jsonl")
    with pytest.raises(ValueError, match="VALID_SENDERS|ai"):
        writer.record_do(
            PRE,
            "x",
            secret=False,
            post_text=POST,
            settled_class="unknown",
            actor="ai",
            session_id="sess-bad",
        )


def test_require_session_id(tmp_path: Path) -> None:
    writer = LedgerWriter(path=tmp_path / "ledger.jsonl")
    with pytest.raises(ValueError, match="session_id"):
        writer.record_do(
            PRE,
            "x",
            secret=False,
            post_text=POST,
            settled_class="unknown",
            actor="app",
            session_id="",
        )


def test_reward_omits_unknown_fields() -> None:
    assert compute_reward({"credits": 1}, {"credits": 2}) == {"d_credits": 1}
    assert compute_reward({}, {"credits": 2}) == {}


def test_trail_render_keeps_redaction() -> None:
    line = render_trail_line(
        {
            "ts": "2026-08-03T05:00:00Z",
            "settled_class": "login_password",
            "prompt": REDACTED,
            "input": REDACTED,
            "reward": {},
            "screen_delta_summary": "unchanged",
        }
    )
    assert REDACTED in line
    assert "s3cret" not in line
