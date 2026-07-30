"""Blessed rule-library peek — WO-PLAY-RULES-LIBRARY.

Pure: no filesystem, no session, no curses. Formats whatever
``rules.store.read_rule_store`` reported and tracks open/closed + cursor
for scrolling. ``app.py::_run_play`` owns the store read and state
transitions; ``screens.py`` owns drawing.

``U)rules`` is the Play key. Read-only by construction: there is no arm
intent, no promote, no send path. Drafts never appear — the caller must
pass the blessed ``rules`` list only (``include_drafts=False``).

Absent vs empty vs blind
------------------------
``read_rule_store``'s contract: branch on ``status`` before claiming a
count. An empty ``rules`` list is true for an absent store, an empty
store, and a blind (unreadable) store — three different operator
sentences. This module refuses to say "no blessed rules yet" under any
status other than ``ok``.
"""

from __future__ import annotations

from typing import Mapping, Sequence

RULES_OFFER_KEYS: tuple[int, ...] = (ord("u"), ord("U"))
RULES_OFFER_INTENT = "rules_library_open"
RULES_TOKEN = "U)rules"

SELECTED_UNICODE = "▸"
SELECTED_ASCII = ">"
EMPTY_UNICODE = "○ ○"
EMPTY_ASCII = "o o"

TITLE = "Blessed rules"
EMPTY_TEXT = "no blessed rules yet"
ABSENT_TEXT = "rule library absent — nothing written yet"
UNREADABLE_TEXT = "rule store unreadable — cannot list"
PARTIAL_BANNER = "PARTIAL — some rule files unreadable"

UNKNOWN = "?"


def resolve_rules_offer_key(key: object) -> bool:
    """``True`` when ``key`` toggles the rules-library peek. Never raises."""
    if isinstance(key, bool) or not isinstance(key, int):
        return False
    return key in RULES_OFFER_KEYS


def store_status(store_result: object) -> str:
    """Branch field from ``read_rule_store``. Fail-closed to ``unreadable``."""
    if not isinstance(store_result, Mapping):
        return "unreadable"
    status = store_result.get("status")
    if status in ("ok", "partial", "unreadable", "absent"):
        return status
    return "unreadable"


def blessed_rows(store_result: object) -> list[dict]:
    """Display rows from the blessed ``rules`` list only. Never raises.

    Accepts either ``Rule`` objects (attribute access) or plain mappings.
    Drops rows without a usable ``rule_id``. Drafts are not in this list
    by store contract; we do not re-filter on an ``approved`` flag.
    """
    if not isinstance(store_result, Mapping):
        return []
    rules = store_result.get("rules")
    if not isinstance(rules, Sequence) or isinstance(rules, (str, bytes)):
        return []
    out: list[dict] = []
    for rule in rules:
        rid = _field(rule, "rule_id")
        if not isinstance(rid, str) or not rid.strip():
            continue
        out.append(
            {
                "rule_id": rid.strip(),
                "do": _field(rule, "do"),
                "screen_match": _field(rule, "screen_match"),
                "priority": _field(rule, "priority"),
            }
        )
    return out


def _field(rule: object, name: str) -> object:
    if isinstance(rule, Mapping):
        return rule.get(name)
    return getattr(rule, name, None)


class RulesLibrarySession:
    """Open/closed + cursor for the read-only rules peek.

    Same overlay idiom as ``analyze.AnalyzeSession`` / ``ChainsSession``.
    Never auto-opens. No ``selected()`` arm path — peek only.
    """

    def __init__(self) -> None:
        self.is_open: bool = False
        self.rows: list[dict] = []
        self.index: int = 0
        self.status: str = "unreadable"

    def open(self, rows: object = None, status: object = "unreadable") -> None:
        self.rows = (
            [r for r in rows if isinstance(r, Mapping)] if isinstance(rows, list) else []
        )
        self.is_open = True
        self.index = 0
        self.status = (
            status if status in ("ok", "partial", "unreadable", "absent") else "unreadable"
        )

    def close(self) -> None:
        self.is_open = False
        self.index = 0

    def move(self, delta: object) -> None:
        if not self.rows:
            self.index = 0
            return
        if isinstance(delta, bool) or not isinstance(delta, int):
            return
        self.index = max(0, min(len(self.rows) - 1, self.index + delta))


def compose_rule_lines(
    session: object,
    *,
    unicode_ok: bool = True,
    width: int = 40,
) -> list[str]:
    """Popup body lines. Never raises."""
    if not isinstance(session, RulesLibrarySession) and not (
        hasattr(session, "rows") and hasattr(session, "status")
    ):
        return [TITLE, _empty_line("unreadable", unicode_ok=unicode_ok)]

    status = getattr(session, "status", "unreadable")
    rows = getattr(session, "rows", [])
    if not isinstance(rows, list):
        rows = []
    index = getattr(session, "index", 0)
    if not isinstance(index, int):
        index = 0

    lines = [TITLE]
    if status == "partial":
        lines.append(PARTIAL_BANNER)

    if not rows:
        lines.append(_empty_line(status, unicode_ok=unicode_ok))
        return lines

    sel = SELECTED_UNICODE if unicode_ok else SELECTED_ASCII
    pad = " " * len(sel)
    budget = width if isinstance(width, int) and width > 8 else 40
    for i, row in enumerate(rows):
        if not isinstance(row, Mapping):
            continue
        marker = sel if i == index else pad
        body = _format_row(row, budget - len(marker) - 1)
        lines.append(f"{marker} {body}"[:budget])
    return lines


def _empty_line(status: object, *, unicode_ok: bool) -> str:
    glyph = EMPTY_UNICODE if unicode_ok else EMPTY_ASCII
    if status == "ok":
        return f"{glyph}  {EMPTY_TEXT}"
    if status == "absent":
        return f"{glyph}  {ABSENT_TEXT}"
    if status == "partial":
        # Established look, but nothing parseable — not the same as empty ok.
        return f"{glyph}  {UNREADABLE_TEXT}"
    return f"{glyph}  {UNREADABLE_TEXT}"


def _format_row(row: Mapping, budget: int) -> str:
    rid = row.get("rule_id")
    rid = rid.strip() if isinstance(rid, str) and rid.strip() else UNKNOWN
    do = row.get("do")
    do = do.strip() if isinstance(do, str) and do.strip() else UNKNOWN
    screen = row.get("screen_match")
    screen = screen.strip() if isinstance(screen, str) and screen.strip() else UNKNOWN
    prio = row.get("priority")
    if isinstance(prio, bool) or not isinstance(prio, int):
        prio_s = UNKNOWN
    else:
        prio_s = str(prio)
    text = f"{rid}  do={do}  screen={screen}  prio={prio_s}"
    if isinstance(budget, int) and budget > 0 and len(text) > budget:
        return text[: max(0, budget - 1)] + "…"
    return text
