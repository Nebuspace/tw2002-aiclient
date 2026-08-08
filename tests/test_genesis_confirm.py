"""PWO-106 Option A — Genesis confirm seam pins (no adapter)."""

from __future__ import annotations

import ast
from pathlib import Path

from tw2002_aiclient.cockpit.armconfirm import CANCEL, CONFIRM
from tw2002_aiclient.genesis_confirm import (
    REFUSED,
    SENT,
    compose_genesis_confirm_line,
    genesis_send_if_confirmed,
    resolve_genesis_confirm_key,
)


def test_compose_line_reuses_armconfirm_yN_and_live_marker():
    line = compose_genesis_confirm_line(42)
    assert "Genesis @ 42" in line
    assert "LIVE?" in line
    assert "y/N" in line


def test_resolve_only_y_confirms_default_deny():
    assert resolve_genesis_confirm_key(ord("y")) == CONFIRM
    assert resolve_genesis_confirm_key(ord("Y")) == CONFIRM
    for bad in (ord("n"), ord("N"), 10, 27, None, "y", True, 3.14):
        assert resolve_genesis_confirm_key(bad) == CANCEL


def test_skipped_confirm_never_reaches_send():
    calls: list[str] = []

    def _send(text: str) -> None:
        calls.append(text)

    for disposition in (CANCEL, None, "Confirm", True, "y", "nope", 1):
        assert (
            genesis_send_if_confirmed(
                disposition=disposition,
                send=_send,
                payload="G",
            )
            == REFUSED
        ), disposition
    assert calls == []


def test_confirm_with_callable_send_delivers_once():
    calls: list[str] = []

    def _send(text: str) -> None:
        calls.append(text)

    assert (
        genesis_send_if_confirmed(
            disposition=CONFIRM,
            send=_send,
            payload="G",
        )
        == SENT
    )
    assert calls == ["G"]


def test_confirm_without_send_or_payload_refuses():
    calls: list[str] = []

    def _send(text: str) -> None:
        calls.append(text)

    assert genesis_send_if_confirmed(disposition=CONFIRM, send=None, payload="G") == REFUSED
    assert (
        genesis_send_if_confirmed(disposition=CONFIRM, send=_send, payload="") == REFUSED
    )
    assert (
        genesis_send_if_confirmed(disposition=CONFIRM, send=_send, payload=None) == REFUSED
    )
    assert calls == []


def test_no_production_caller_of_genesis_send_if_confirmed():
    """WO-WIRE-GENESIS-CONFIRM-UI: product choke-point lives in app.py only.

    Screens raise/resolve the gate; app.py alone may invoke send-if-confirmed.
    """
    root = Path(__file__).resolve().parents[1] / "tw2002_aiclient"
    callers: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "genesis_confirm.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            func = getattr(node, "func", None)
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if isinstance(node, ast.Call) and name == "genesis_send_if_confirmed":
                callers.append(path.name)
    assert callers == ["app.py"], f"unexpected production callers: {callers}"


def test_screens_compose_and_resolve_are_wired():
    """Accept: compose/resolve appear in screens.py (gate UI), not only tests."""
    text = (
        Path(__file__).resolve().parents[1]
        / "tw2002_aiclient"
        / "screens.py"
    ).read_text(encoding="utf-8")
    assert "compose_genesis_confirm_line" in text
    assert "resolve_genesis_confirm_key" in text
    assert "begin_genesis_confirm" in text


def test_play_shell_genesis_confirm_gate_default_deny():
    """screens.py: begin + resolve — cancel never becomes genesis_confirm."""
    from tw2002_aiclient.screens import PlayShellScreen

    play = object.__new__(PlayShellScreen)
    play._arm_confirm = None
    play._genesis_confirm = None
    play._draft_approve = None
    play._rule_identity = None
    play.analyze_session = None
    play.begin_genesis_confirm(99)
    assert play._genesis_confirm == 99
    assert play.handle_key(ord("n")) is None
    assert play._genesis_confirm is None
    play.begin_genesis_confirm(1)
    assert play.handle_key(ord("y")) == "genesis_confirm"
