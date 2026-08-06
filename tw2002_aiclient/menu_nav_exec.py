"""Deterministic menu-nav executor — taught/armed send half of ``plan_nav``.

Canon: ``canon/engine/menu-map-and-introspection.md`` — ``nav``/``info`` edges
may walk when **armed**; ``action`` edges refuse (taught-rule gate). Never
sends when ``is_armed()`` is false. Re-checks ``should_abort`` / ``is_armed``
before every keystroke. Off-map after a step → halt (stop-on-unknown).

This module never invents a route — callers pass a ``plan_nav`` result.

Session contract is concrete (no ``getattr`` duck-typing): ``send`` +
``rendered_text`` — missing attributes fail closed via AttributeError.
Lives outside ``menu/`` so the crawl AST chokepoint
(``emit_key_if_safe``) stays the sole send path in that package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol

from tw2002_aiclient.menu.nav import localize

__all__ = [
    "SAFE_EDGE_KINDS",
    "NavRunResult",
    "NavSession",
    "run_nav",
]

SAFE_EDGE_KINDS = frozenset({"nav", "info"})


class NavSession(Protocol):
    """Minimal session surface for armed nav execution."""

    def send(self, payload: str) -> None: ...

    def rendered_text(self) -> str: ...


@dataclass(frozen=True)
class NavRunResult:
    ok: bool
    outcome: str  # completed | halted | refused
    reason: Optional[str]
    sends_issued: int
    steps_done: int


def run_nav(
    session: NavSession,
    plan: dict[str, Any],
    path: object,
    *,
    should_abort: Callable[[], bool],
    is_armed: Callable[[], bool],
) -> NavRunResult:
    """Execute a ``plan_nav`` plan under fail-closed arm / abort gates.

    Unarmed → ``halted`` / ``not_armed`` with **zero** sends (the load-bearing
    antifire pin). An ``action``-kind step → ``refused`` /
    ``action_edge_requires_rule`` without sending that or later steps.
    """
    sends = 0
    done = 0
    if not callable(should_abort) or not callable(is_armed):
        return NavRunResult(False, "refused", "arm_predicates_required", 0, 0)
    if should_abort() or not is_armed():
        return NavRunResult(False, "halted", "not_armed", 0, 0)
    if not isinstance(plan, dict) or plan.get("ok") is not True:
        reason = None
        if isinstance(plan, dict):
            reason = plan.get("reason")
        return NavRunResult(
            False,
            "refused",
            str(reason or "plan_not_ok"),
            0,
            0,
        )
    steps = plan.get("steps")
    if steps is None:
        steps = []
    if not isinstance(steps, list):
        return NavRunResult(False, "refused", "plan_steps_invalid", 0, 0)

    for step in steps:
        if should_abort() or not is_armed():
            return NavRunResult(False, "halted", "not_armed", sends, done)
        if not isinstance(step, dict):
            return NavRunResult(False, "refused", "step_invalid", sends, done)
        kind = step.get("kind")
        key = step.get("key")
        if not isinstance(key, str) or not key:
            return NavRunResult(False, "refused", "step_key_missing", sends, done)
        if kind not in SAFE_EDGE_KINDS:
            return NavRunResult(
                False,
                "refused",
                "action_edge_requires_rule",
                sends,
                done,
            )
        try:
            session.send(key)
            sends += 1
            done += 1
        except AttributeError:
            return NavRunResult(
                False, "halted", "send_failed:AttributeError", sends, done
            )
        except Exception as exc:  # noqa: BLE001
            return NavRunResult(
                False,
                "halted",
                f"send_failed:{type(exc).__name__}",
                sends,
                done,
            )
        # Stop-on-unknown: after each hop, must still localize on-map.
        try:
            text = session.rendered_text()
        except AttributeError:
            return NavRunResult(
                False, "halted", "screen_failed:AttributeError", sends, done
            )
        except Exception as exc:  # noqa: BLE001
            return NavRunResult(
                False,
                "halted",
                f"screen_failed:{type(exc).__name__}",
                sends,
                done,
            )
        if not isinstance(text, str):
            return NavRunResult(False, "halted", "screen_unreadable", sends, done)
        node = localize(text, path)
        if node is None:
            return NavRunResult(False, "halted", "off_map", sends, done)
        expected = step.get("to_node")
        if isinstance(expected, str) and node.get("signature") != expected:
            return NavRunResult(
                False, "halted", "localization_mismatch", sends, done
            )

    if should_abort() or not is_armed():
        return NavRunResult(False, "halted", "not_armed", sends, done)
    return NavRunResult(True, "completed", None, sends, done)
