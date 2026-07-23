"""TW-28 menu-map inspector — pure summary + clip-safe render lines.

Makes the §23 determinism map visible: counts, you-are-here (★|off-map),
reachable coverage, dead-ends, orphans. No session/sends/execution.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Mapping, Optional, Sequence


def menu_map_summary(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    current_sig: Optional[str] = None,
) -> dict[str, Any]:
    """PURE map stats. ``current_sig`` unknown/None → ``current`` is None (off-map)."""
    by_sig: dict[str, Mapping[str, Any]] = {}
    for node in nodes:
        sig = node.get("signature")
        if sig:
            by_sig[sig] = node

    outgoing: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, int] = defaultdict(int)
    for edge in edges:
        frm = edge.get("from_node")
        to = edge.get("to_node")
        if not frm or not to:
            continue
        outgoing[frm].append(to)
        incoming[to] += 1

    current = None
    if current_sig and current_sig in by_sig:
        node = by_sig[current_sig]
        label = node.get("label") or current_sig
        current = {
            "signature": current_sig,
            "label": label,
            "star": True,
        }

    reachable = 0
    if current is not None:
        visited = {current_sig}
        queue = deque([current_sig])
        while queue:
            node = queue.popleft()
            for nxt in outgoing.get(node, []):
                if nxt in visited:
                    continue
                visited.add(nxt)
                queue.append(nxt)
        reachable = len(visited)

    dead_ends = sorted(
        sig for sig in by_sig if not outgoing.get(sig)
    )
    # Isolated islands only — no-in AND no-out. A map ROOT has no incoming
    # but does have outgoing; flagging it as "orphan" was a false-positive.
    orphans = sorted(
        sig
        for sig in by_sig
        if incoming.get(sig, 0) == 0 and not outgoing.get(sig)
    )

    return {
        "node_count": len(by_sig),
        "edge_count": len(edges),
        "current": current,
        "reachable_from_current": reachable,
        "dead_ends": dead_ends,
        "orphans": orphans,
    }


def format_menu_map_lines(summary: Mapping[str, Any] | None, cols: int = 22) -> list[str]:
    """Clip-safe inspector lines for a ``menu_map_summary`` result."""
    cols = max(8, int(cols))
    if not summary:
        return ["MAP —"[:cols], "here off-map"[:cols]]

    n = int(summary.get("node_count") or 0)
    e = int(summary.get("edge_count") or 0)
    header = f"MAP {n}n·{e}e"

    current = summary.get("current")
    if current is None:
        here = "here off-map"
    else:
        label = str(current.get("label") or current.get("signature") or "?")
        here = f"here ★ {label}"

    reach = int(summary.get("reachable_from_current") or 0)
    dead = len(summary.get("dead_ends") or ())
    orphan = len(summary.get("orphans") or ())
    reach_label = f"{reach}/{n}" if n else str(reach)
    # Prefer dead-ends on the coverage line; orphans at wider cols.
    if cols >= 28:
        cover = f"{reach_label} reachable · {dead} dead-ends · {orphan} orphans"
    else:
        cover = f"{reach_label} reachable · {dead} dead-ends"

    return [header[:cols], here[:cols], cover[:cols]]


def format_menu_map_report(summary: Mapping[str, Any] | None) -> list[str]:
    """Full CLI report: clip-safe header + explicit dead-end/orphan lists."""
    lines = format_menu_map_lines(summary, cols=80)
    if not summary:
        lines.append("dead-ends: (none)")
        lines.append("orphans: (none)")
        return lines
    dead = list(summary.get("dead_ends") or ())
    orphans = list(summary.get("orphans") or ())
    lines.append("dead-ends: " + (", ".join(dead) if dead else "(none)"))
    lines.append("orphans: " + (", ".join(orphans) if orphans else "(none)"))
    return lines


def menu_map_summary_from_store(path, current_sig: Optional[str] = None) -> dict[str, Any]:
    """Thin wrapper: load menu-map from ``game_knowledge``, then summarize."""
    from .game_knowledge import list_menu_edges, list_menu_nodes

    return menu_map_summary(
        list_menu_nodes(path),
        list_menu_edges(path),
        current_sig=current_sig,
    )
