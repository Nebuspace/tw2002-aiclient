"""Deterministic-nav executor — armed gate + safe edge kinds."""

from __future__ import annotations

from tw2002_aiclient.menu import knowledge
from tw2002_aiclient.menu.nav import plan_nav
from tw2002_aiclient.menu.nav_exec import run_nav
from tw2002_aiclient.menu.sig import menu_signature

SCREEN_A = "=== Computer ===\n(1) Status\n(2) Ship\n"
SCREEN_B = "=== Ship Status ===\nHolds: 50\n(Q) Quit\n"
SCREEN_C = "=== Cargo ===\nEmpty\n(Q) Quit\n"


class _FakeSession:
    def __init__(self, screens: list[str]) -> None:
        self._screens = list(screens)
        self.sends: list[str] = []
        self.text = screens[0] if screens else ""

    def send(self, payload: str) -> None:
        self.sends.append(payload)
        # Advance to next screen after each send (caller queues expected frames).
        if len(self.sends) < len(self._screens):
            self.text = self._screens[len(self.sends)]

    def rendered_text(self) -> str:
        return self.text


def _seed_ab(path):
    sig_a = menu_signature(SCREEN_A)
    sig_b = menu_signature(SCREEN_B)
    knowledge.upsert_menu_node(path, sig_a, label="Computer")
    knowledge.upsert_menu_node(path, sig_b, label="Ship")
    knowledge.upsert_menu_edge(path, sig_a, "2", sig_b, kind="nav", desc="Ship")
    return sig_a, sig_b


def test_unarmed_never_sends(tmp_path):
    path = tmp_path / "game_knowledge.json"
    _, sig_b = _seed_ab(path)
    plan = plan_nav(SCREEN_A, sig_b, path)
    session = _FakeSession([SCREEN_A, SCREEN_B])
    result = run_nav(
        session,
        plan,
        path,
        should_abort=lambda: False,
        is_armed=lambda: False,
    )
    assert result.ok is False
    assert result.reason == "not_armed"
    assert result.sends_issued == 0
    assert session.sends == []


def test_armed_walks_nav_edge(tmp_path):
    path = tmp_path / "game_knowledge.json"
    _, sig_b = _seed_ab(path)
    plan = plan_nav(SCREEN_A, sig_b, path)
    session = _FakeSession([SCREEN_A, SCREEN_B])
    result = run_nav(
        session,
        plan,
        path,
        should_abort=lambda: False,
        is_armed=lambda: True,
    )
    assert result.ok is True
    assert result.outcome == "completed"
    assert result.sends_issued == 1
    assert session.sends == ["2"]


def test_action_edge_refused_without_send(tmp_path):
    path = tmp_path / "game_knowledge.json"
    sig_a = menu_signature(SCREEN_A)
    sig_c = menu_signature(SCREEN_C)
    knowledge.upsert_menu_node(path, sig_a, label="Computer")
    knowledge.upsert_menu_node(path, sig_c, label="Buy")
    knowledge.upsert_menu_edge(path, sig_a, "B", sig_c, kind="action", desc="Buy")
    # Hand-build a plan that includes an action edge (planner may still return it).
    plan = {
        "ok": True,
        "reason": None,
        "from_sig": sig_a,
        "steps": [{"key": "B", "to_node": sig_c, "kind": "action", "desc": "Buy"}],
    }
    session = _FakeSession([SCREEN_A, SCREEN_C])
    result = run_nav(
        session,
        plan,
        path,
        should_abort=lambda: False,
        is_armed=lambda: True,
    )
    assert result.ok is False
    assert result.reason == "action_edge_requires_rule"
    assert result.sends_issued == 0
    assert session.sends == []


def test_abort_mid_route_halts(tmp_path):
    path = tmp_path / "game_knowledge.json"
    sig_a = menu_signature(SCREEN_A)
    sig_b = menu_signature(SCREEN_B)
    sig_c = menu_signature(SCREEN_C)
    knowledge.upsert_menu_node(path, sig_a, label="A")
    knowledge.upsert_menu_node(path, sig_b, label="B")
    knowledge.upsert_menu_node(path, sig_c, label="C")
    knowledge.upsert_menu_edge(path, sig_a, "2", sig_b, kind="nav")
    knowledge.upsert_menu_edge(path, sig_b, "1", sig_c, kind="nav")
    plan = plan_nav(SCREEN_A, sig_c, path)
    assert plan["ok"] is True
    assert len(plan["steps"]) == 2

    armed = {"v": True}
    abort_after = {"n": 0}

    def should_abort() -> bool:
        return abort_after["n"] >= 1

    def is_armed() -> bool:
        return armed["v"]

    session = _FakeSession([SCREEN_A, SCREEN_B, SCREEN_C])

    class _CountingSession(_FakeSession):
        def send(self, payload: str) -> None:
            super().send(payload)
            abort_after["n"] += 1

    session = _CountingSession([SCREEN_A, SCREEN_B, SCREEN_C])
    result = run_nav(
        session,
        plan,
        path,
        should_abort=should_abort,
        is_armed=is_armed,
    )
    assert result.ok is False
    assert result.reason == "not_armed"
    assert result.sends_issued == 1
    assert session.sends == ["2"]


def test_empty_steps_already_there(tmp_path):
    path = tmp_path / "game_knowledge.json"
    sig_a, _ = _seed_ab(path)
    plan = plan_nav(SCREEN_A, sig_a, path)
    assert plan["ok"] is True
    assert plan["steps"] == []
    session = _FakeSession([SCREEN_A])
    result = run_nav(
        session,
        plan,
        path,
        should_abort=lambda: False,
        is_armed=lambda: True,
    )
    assert result.ok is True
    assert result.sends_issued == 0
