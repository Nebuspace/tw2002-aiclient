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
    """Accept pin: gate exists; no product path invokes it yet (Option A).

    A future Genesis adapter WO must update this pin deliberately when it
    adds the first production caller — same shape as early armconfirm.
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
    assert callers == [], f"unexpected production callers: {callers}"
