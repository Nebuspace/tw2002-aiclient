"""Pure composer for the learned-loop listing (WO-P2-G3).

No filesystem, no session -- formats whatever ``store.read_loop_store``
found. The one rule this module enforces is the one the reader exists to
make enforceable: **the "no loops taught yet" line is emitted only under
``status == "ok"``**, the sole outcome that established the negative. A
store that could not be read renders as unknown (canon's ``?``), never as
empty, and a partial read is labelled INCOMPLETE so its count reads as the
floor it is rather than a total.

Glyphs are canon's (``canon/surfaces/visual-language.md`` glyph table):
``?`` unknown, ``—`` an unknown/empty value "in place of a fabricated ``-``
or a blank", ``!`` the attention mark. All three are listed NO-SWAP, so
there is no ASCII twin to diverge from.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

UNKNOWN = "?"
UNKNOWN_VALUE = "—"
ATTENTION = "!"

_NAME_W = 28
_SOURCE_W = 9
_PROFIT_W = 14


def format_loop_row(loop: Mapping[str, Any]) -> str:
    """One listing row.

    ``name`` is padded but never truncated: it is the identity a human types
    to replay the macro, and a clipped identity is worse than a ragged
    column. Profit renders only when the document carried a real number --
    otherwise canon's em-dash, never a fabricated ``0``.
    """
    tag = "[DRAFT] " if loop.get("draft") else ""
    name = str(loop.get("name") or UNKNOWN)
    # An unrecognized/absent provenance is unknown, not "recorded".
    source = loop.get("source") or UNKNOWN
    steps = loop.get("steps")
    if isinstance(steps, int) and not isinstance(steps, bool):
        steps_text = f"{steps} step" + ("" if steps == 1 else "s")
    else:
        # Defensive only: `store._row` always sets this from `len(...)`, so no
        # store read reaches here. It exists for a hand-built row, and it
        # degrades to unknown rather than to a plausible-looking `0 steps`.
        steps_text = f"{UNKNOWN} steps"

    per_turn = loop.get("profit_per_turn")
    per_action = loop.get("profit_per_action")
    if isinstance(per_turn, (int, float)) and not isinstance(per_turn, bool):
        profit = f"{per_turn:+,.1f}cr/turn"
    elif isinstance(per_action, (int, float)) and not isinstance(per_action, bool):
        profit = f"{per_action:+,.1f}cr/act"
    else:
        profit = UNKNOWN_VALUE

    return (
        f"{tag}{name:<{_NAME_W}} {str(source):<{_SOURCE_W}} "
        f"{profit:>{_PROFIT_W}} {steps_text:>8}"
    )


def _headline(result: Mapping[str, Any]) -> str:
    status = result.get("status")
    listed = len(result.get("loops") or ())
    unread = len(result.get("unreadable") or ())
    if status == "unreadable":
        # No count, not even zero: nothing was established.
        return f"LOOPS {UNKNOWN} — the store could not be read"
    if status == "partial":
        detail = f"{listed} listed"
        if unread:
            detail += f" · {unread} unreadable"
        return f"LOOPS {detail} — INCOMPLETE"
    return f"LOOPS {listed}"


def _trouble_lines(result: Mapping[str, Any]) -> list[str]:
    """One attention line per thing that could not be read, each naming the
    path and the reason -- an operator can only fix a file they can find."""
    lines: list[str] = []
    for root in result.get("roots") or ():
        if root.get("status") != "unreadable":
            continue
        which = "drafts" if root.get("draft") else "store"
        reason = root.get("reason") or "could not be read"
        lines.append(f"{ATTENTION} {which} {root.get('path')}: {reason}")
    unreadable: Sequence[Mapping[str, Any]] = result.get("unreadable") or ()
    if unreadable:
        noun = "file" if len(unreadable) == 1 else "files"
        lines.append(f"{ATTENTION} {len(unreadable)} {noun} in the store could not be read:")
        for entry in unreadable:
            lines.append(f"    {entry.get('path')}: {entry.get('reason') or 'unreadable'}")
    return lines


def _empty_line(result: Mapping[str, Any]) -> str:
    """The honest empty. Reached only from the ``ok`` branch below.

    Distinguishes a store that was never written from one that exists and
    holds nothing -- both are real negatives, but only the first explains
    itself to an operator who expected rows.
    """
    roots = list(result.get("roots") or ())
    blessed = next((r for r in roots if not r.get("draft")), None)
    if blessed is not None and blessed.get("status") == "absent":
        return f"(no loops taught yet — no store at {blessed.get('path')})"
    return "(no loops taught yet — the store is empty)"


def format_loops_report(result: Mapping[str, Any] | None) -> list[str]:
    """Full CLI report lines for a ``read_loop_store`` result.

    Three shapes, one per status, and they never blur:

    * ``unreadable`` -- headline says unknown, then the reasons. **No empty
      line and no count**, because none was earned.
    * ``partial``    -- the real rows, then the reasons, under an INCOMPLETE
      headline so the count reads as a floor.
    * ``ok``         -- the real rows, or the honest empty.
    """
    if not result:
        # Nothing in the live tree passes a falsy result -- but a missing
        # result is the LEAST informed state there is, so it degrades to
        # unknown rather than to the reassuring "no loops".
        return [f"LOOPS {UNKNOWN} — the store could not be read"]

    lines = [_headline(result)]
    loops = list(result.get("loops") or ())
    lines.extend(format_loop_row(loop) for loop in loops)
    lines.extend(_trouble_lines(result))

    if not loops and result.get("status") == "ok":
        lines.append(_empty_line(result))
    return lines
