"""Menu localization + nav planning (algorithm half).

Pathfinding lives in ``menu.knowledge.find_menu_path``. This module answers
the player's "where am I?" question: match a live screen to a known
menu-map node (or honestly report off-map), then compose a route.

Signature MUST match the crawler — we import the neutral
``menu.sig.menu_signature`` (same hash the crawler persists). Execution of
the returned key sequence is a separate daemon-side WO.
"""

from __future__ import annotations

from typing import Any, Optional

from .knowledge import find_menu_path, get_menu_node
from .sig import menu_signature


def localize(screen_text: str, path) -> Optional[dict[str, Any]]:
    """Return the known menu-map node for ``screen_text``, or ``None`` if off-map.

    Computes the signature the same way the crawler stored it, then looks
    up ``get_menu_node``. Never guesses a nearby node — ``None`` means
    crawl/escalate, not navigate blind.
    """
    if screen_text is None:
        return None
    sig = menu_signature(screen_text)
    return get_menu_node(path, sig)


def plan_nav(screen_text: str, target_sig: str, path) -> dict[str, Any]:
    """Compose localize → ``find_menu_path`` → keystroke steps (or a typed fail).

    PARKED 2026-07-23 (WO-FA14): FA8 wired ``localize`` into spectate/`tw menumap`;
    this planner + daemon-side keystroke execution remain consumer-less
    (unit-tested). Do not delete — router WO still owns the send half.

    Returns a dict:
      ``ok`` True + ``steps`` (list of ``{key,to_node,kind,desc}``, maybe empty
      if already there) + ``from_sig`` when localized;
      ``ok`` False + ``reason`` in {``off_map``, ``unreachable``} otherwise.
    """
    node = localize(screen_text, path)
    if node is None:
        return {
            "ok": False,
            "reason": "off_map",
            "from_sig": None,
            "steps": None,
        }
    from_sig = node["signature"]
    route = find_menu_path(path, from_sig, target_sig)
    if route is None:
        return {
            "ok": False,
            "reason": "unreachable",
            "from_sig": from_sig,
            "steps": None,
        }
    steps = [
        {
            "key": edge["key"],
            "to_node": edge["to_node"],
            "kind": edge["kind"],
            "desc": edge.get("desc"),
        }
        for edge in route
    ]
    return {
        "ok": True,
        "reason": None,
        "from_sig": from_sig,
        "steps": steps,
    }
