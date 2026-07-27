"""Menu-map inspector — pure summary + clip-safe render lines.

Makes the determinism map visible: counts, you-are-here (★|off-map),
reachable coverage, dead-ends, orphans. No session/sends/execution.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Mapping, Optional, Sequence


def menu_map_summary(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    current_sig: Optional[str] = None,
    here_unknown: Optional[str] = None,
) -> dict[str, Any]:
    """PURE map stats. ``current_sig`` unknown/None → ``current`` is None (off-map).

    ``here_unknown`` separates the two things a ``current`` of None used to
    mean at once. Canon's contract is that ``localize()`` returning None means
    **off-map** -- "STOP, escalate, never navigate blind"
    (`canon/engine/menu-map-and-introspection.md §"Examples"`). But a caller that
    never got to *ask* localize -- no daemon, an unusable ``screen`` response,
    a blank screen, a raised lookup -- also arrives here with None, and
    rendering that as "off-map" asserts a fact nobody established.

    So: ``here_unknown=None`` means "we looked and you are genuinely off-map";
    a non-empty string is the *reason we could not look*, rendered with canon's
    unknown glyph ``?`` instead of the off-map claim (`?` = unknown,
    `canon/surfaces/visual-language.md §"Glyph / status-marker vocabulary"`; "the system never lies or
    invents", `:289`). Passing it alongside a resolvable ``current_sig`` is
    meaningless and is ignored -- a located ``★`` outranks any reason.
    """
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
        # Only meaningful while `current` is None; cleared when we actually
        # located the player, so no consumer can render "★ here" and "could
        # not look" from the same summary.
        "here_unknown": None if current is not None else (here_unknown or None),
        "reachable_from_current": reachable,
        "dead_ends": dead_ends,
        "orphans": orphans,
    }


def format_menu_map_lines(summary: Mapping[str, Any] | None, cols: int = 22) -> list[str]:
    """Clip-safe inspector lines for a ``menu_map_summary`` result."""
    cols = max(8, int(cols))
    if not summary:
        # Swept alongside the `current is None` branch below, same defect:
        # no summary at all is the LEAST informed state there is, and it was
        # the one asserting the player's position most confidently. Nothing
        # in the live tree passes a falsy summary today (`tw menumap` always
        # builds one), so this is a dormant branch -- but it is dormant, not
        # correct, and leaving the identical claim two lines from its fixed
        # twin is how a defect grows back.
        return ["MAP —"[:cols], "here ? no map"[:cols]]

    n = int(summary.get("node_count") or 0)
    e = int(summary.get("edge_count") or 0)
    header = f"MAP {n}n·{e}e"

    current = summary.get("current")
    if current is None:
        # "off-map" is a CLAIM about where the player is; it is only honest
        # when a lookup actually ran and came back empty. When the summary
        # carries a reason we could not look, say that instead -- `?` is
        # canon's unknown glyph and has no ASCII twin to diverge from.
        # Coerced with str() rather than trusted: this reason reaches here
        # from a caller-supplied field, same discipline as `label` below.
        reason = summary.get("here_unknown")
        here = f"here ? {str(reason)}" if reason else "here off-map"
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
        # The report half of the branch fixed above. `(none)` is a claim about
        # CONTENTS, and with no summary there are no contents to have counted
        # -- the operator could not tell "I looked and there were none" from
        # "I could not look". The house already settled this exact state one
        # module over: `loops.list_view.format_loops_report`'s falsy branch
        # emits its unknown headline and then "**No empty line and no count**,
        # because none was earned" (`loops/list_view.py:119-120`). So the lists
        # are OMITTED rather than rendered empty -- and rather than decorated
        # with a fourth "unknown" phrasing, which would only restate what the
        # `MAP —` header and `here ? no map` above already say.
        return lines
    dead = list(summary.get("dead_ends") or ())
    orphans = list(summary.get("orphans") or ())
    lines.append("dead-ends: " + (", ".join(dead) if dead else "(none)"))
    lines.append("orphans: " + (", ".join(orphans) if orphans else "(none)"))
    return lines


def menu_map_summary_from_store(
    path,
    current_sig: Optional[str] = None,
    here_unknown: Optional[str] = None,
) -> dict[str, Any]:
    """Thin wrapper: load menu-map from knowledge store, then summarize."""
    from .knowledge import list_menu_edges, list_menu_nodes

    return menu_map_summary(
        list_menu_nodes(path),
        list_menu_edges(path),
        current_sig=current_sig,
        here_unknown=here_unknown,
    )
