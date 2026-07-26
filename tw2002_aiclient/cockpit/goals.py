"""Pure GOALS-panel composer for the trainer-cockpit left gutter (PWO-034,
``workorders/WO-P3-034-041-panels-PREP.md`` §PWO-034).

No ``curses`` import here on purpose — this module composes plain strings
only, mirroring ``tw2002_aiclient/cockpit/strip.py``'s discipline.

GOALS is **Layer-1 status only** (`canon/engine/priority-engine.md` "Two-layer
information architecture" / `canon/surfaces/trainer-cockpit.md` GOALS panel
description): each strategic prerequisite gets its own line with a status
glyph. This module never ranks or picks an action — that is FOCUS's job
(PWO-035, `compose_priorities_lines`), a separate panel this module does not
touch.

Canon-authored line set, always rendered in this order regardless of input:
Turns, Credits, StarDock, Map, Formations, Chain, Ship prices, Hold price,
Fighters (`canon/engine/priority-engine.md` "Layer 1 — GOALS"). The panel
never vanishes rows when data is unknown — every row is always present.

Glyphs (`canon/surfaces/visual-language.md` glyph table, ~117-131 — all four
are explicit **NO-SWAP** rows, no ASCII twin, so unlike
``cockpit/strip.py`` this composer takes no ``unicode_ok`` parameter):
``✓`` met/known · ``·`` in progress/partial · ``?`` unknown ·
``⊘`` blocked (unmet prerequisite). The em-dash ``—`` fills the value slot
for a genuinely-unknown detail (same table: "an unknown/empty value ...
throughout HUD/GOALS/PRIORITIES rendering").

Status-dict field mapping (WO-P3-034a). ``status`` is the daemon's ``status``
verb response shape (``tw2002_aiclient/session/protocol.py::dispatch()``).
As of this WO, that response carries ``connected``/``idle_ms``/
``classification``/``host``/``port``/``name``/``autopilot``/
``mode`` only — **none** of the fields below are populated yet
(``state_parser``/world-model are not ported; see the WO-P2-020 Wave-3 CUT
note in ``protocol.py``). Every row therefore renders honestly unknown
against today's real daemon until those land. The key names chosen here
mirror the archive's established convention
(``archive/pre-rebirth-2026-07-23/code/tw2002_aiclient/adapters.py::
goals_snapshot_from_status`` used ``credits``/``turns_left``/
``fighters_aboard`` verbatim) so this composer needs no change the day those
fields are wired back in — it just starts reading real data:

| Row          | key(s) read from ``status``                          |
|--------------|--------------------------------------------------------|
| Turns        | ``turns_left`` (int)                                    |
| Credits      | ``credits`` (int)                                        |
| StarDock     | ``stardock_sectors`` (list) / ``stardock_found`` (bool)  |
| Map          | ``known_sectors`` (int), ``galaxy_size`` (int)           |
| Formations   | ``formations_count`` (int)                               |
| Chain        | ``chain_hops`` (int), ``chain_unit`` (str, default hops) |
| Ship prices  | ``ship_prices_count`` (int) — ``⊘`` if StarDock confirmed |
|              | not found (``stardock_found is False``)                  |
| Hold price   | ``hold_price_label`` (str) — same ``⊘`` gate              |
| Fighters     | ``fighters_aboard`` (int), ``fighter_buy_status`` (str)   |

No field is ever invented: a missing/None key renders ``?``/``—``, never a
guessed value. Malformed values (wrong type, control characters, etc.) are
coerced or ignored, never raised on — same "coerce, don't assume str"
lesson as ``strip.py``'s ``_clean``.
"""

from __future__ import annotations

GLYPH_MET = "✓"
GLYPH_PARTIAL = "·"
GLYPH_UNKNOWN = "?"
GLYPH_BLOCKED = "⊘"

# Canon: the em-dash fills an unknown/empty value slot throughout
# HUD/GOALS/PRIORITIES rendering (visual-language.md glyph table, `—` row).
UNKNOWN_DETAIL = "—"

# Below this GOALS-column width, labels abbreviate rather than let the
# curses draw layer clip them mid-word. Mirrors the archive's
# ``_goals_use_short_labels`` 26-column threshold.
_SHORT_LABEL_WIDTH = 26

# (long label, short label) per row, in canon-authored order.
_LABELS: dict[str, tuple[str, str]] = {
    "turns": ("Turns", "Trn"),
    "credits": ("Credits", "Cr"),
    "stardock": ("StarDock", "Dock"),
    "map": ("Map", "Map"),
    "formations": ("Formations", "Form"),
    "chain": ("Chain", "Chain"),
    "ship_prices": ("Ship prices", "Ships"),
    "hold_price": ("Hold price", "Hold"),
    "fighters": ("Fighters", "Ftr"),
}


def _label(key: str, *, short: bool) -> str:
    long_form, short_form = _LABELS[key]
    return short_form if short else long_form


def _safe_int(value: object) -> int | None:
    """Best-effort int coercion — ``None``/unparsable input becomes
    ``None`` (unknown) rather than raising.

    ``OverflowError`` is a specifically-documented wire-reachable case:
    Python's ``json`` module accepts bare ``Infinity``/``-Infinity`` by
    default (``allow_nan=True``), so a malformed daemon payload can hand
    this a real ``float('inf')`` — ``int(float('inf'))`` raises
    ``OverflowError``, not ``ValueError``, and a status field backed by
    that value must still degrade to unknown, not crash the composer.
    ``float('nan')`` already raises ``ValueError`` here, not
    ``OverflowError``. The catch is broadened to ``Exception`` (Mack's
    review) as the never-raises *contract* backstop beyond that documented
    case: ``int(value)`` calls ``value.__int__()`` for an arbitrary object,
    and a hostile ``__int__`` that raises something else entirely (e.g. a
    bare ``RuntimeError``) must still degrade to unknown, not escape this
    composer."""
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _safe_str(value: object) -> str | None:
    """Best-effort str coercion — blank/unparsable input becomes ``None``
    (unknown) rather than raising or rendering an empty label."""
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    try:
        text = str(value).strip()
    except Exception:
        return None
    return text or None


def _safe_list(value: object) -> list:
    """Only a real ``list``/``tuple`` counts as a sector list — a stray
    string/dict/int in this slot degrades to empty rather than being
    iterated character-by-character or raising."""
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _safe_sector_token(value: object) -> str:
    """Best-effort display text for one ``stardock_sectors`` entry.

    Every other field goes through ``_safe_str``'s try/except before it
    reaches a composed line; this one-liner join was the exception (a raw
    ``str(s)`` per item) until Mack's review caught it — a sector entry
    whose ``__str__``/``__repr__`` itself raises must degrade to ``?`` for
    that one token, not crash the whole StarDock row."""
    try:
        text = str(value).strip()
    except Exception:
        return "?"
    return text or "?"


def _row(glyph: str, label: str, detail: str, *, width: int) -> str:
    """One GOALS line: ``<glyph> <label> <value-or-state>``, clipped to
    ``width`` code points (cell-width caveat documented in ``strip.py`` —
    wide operator-data can still exceed ``width`` terminal cells; the
    curses draw layer is the real backstop)."""
    if width <= 0:
        return ""
    text = f"{glyph} {label} {detail}".rstrip()
    return text[:width]


def compose_goals_lines(status: dict | None, *, width: int) -> list[str]:
    """Compose the GOALS panel's fixed 9-line status readout.

    Never raises regardless of ``status``'s shape or content — a non-dict
    ``status`` (including ``None``) is treated as empty, and every
    individual field is independently coerced (see module docstring for the
    key mapping). The returned list always has exactly 9 lines, in canon
    order, each ``len(line) <= width``.

    This never-raises contract covers any JSON-wire-shaped input — plain
    dicts/lists and hostile *values* within them included (Mack's review:
    a field whose ``__int__``/``__str__``/etc. raises still degrades
    honestly). A ``status`` that is itself a ``dict`` *subclass* with a
    raising ``.get()``/``__contains__`` is out of contract — the daemon's
    real wire payload is always a plain ``json.loads()`` dict, never a
    subclass, and that hazard is contained at the render layer (the
    curses draw call) instead of here.
    """
    try:
        width = int(width)
    except (TypeError, ValueError):
        width = 0
    status = status if isinstance(status, dict) else {}
    short = width < _SHORT_LABEL_WIDTH

    lines: list[str] = []

    # -- Turns --------------------------------------------------------
    turns = _safe_int(status.get("turns_left"))
    if turns is None:
        lines.append(_row(GLYPH_UNKNOWN, _label("turns", short=short), UNKNOWN_DETAIL, width=width))
    else:
        lines.append(_row(GLYPH_MET, _label("turns", short=short), f"{turns:,}", width=width))

    # -- Credits --------------------------------------------------------
    credits_ = _safe_int(status.get("credits"))
    if credits_ is None:
        lines.append(_row(GLYPH_UNKNOWN, _label("credits", short=short), UNKNOWN_DETAIL, width=width))
    else:
        lines.append(_row(GLYPH_MET, _label("credits", short=short), f"{credits_:,}", width=width))

    # -- StarDock ---------------------------------------------------------
    # ``dock_blocked`` (a confirmed negative search) is the only state that
    # gates Ship prices / Hold price below with ``⊘`` — a merely-unknown
    # StarDock status does not claim those rows are blocked, only unknown.
    sectors = _safe_list(status.get("stardock_sectors"))
    found_flag = status.get("stardock_found")
    dock_blocked = False
    if sectors:
        detail = "@" + ",".join(_safe_sector_token(s) for s in sectors[:3])
        glyph = GLYPH_MET
    elif found_flag is True:
        detail = "found"
        glyph = GLYPH_MET
    elif found_flag is False:
        detail = "not found"
        glyph = GLYPH_PARTIAL
        dock_blocked = True
    else:
        detail = UNKNOWN_DETAIL
        glyph = GLYPH_UNKNOWN
    lines.append(_row(glyph, _label("stardock", short=short), detail, width=width))

    # -- Map (exploration progress) --------------------------------------
    known_sectors = _safe_int(status.get("known_sectors"))
    galaxy_size = _safe_int(status.get("galaxy_size"))
    if known_sectors is None:
        lines.append(_row(GLYPH_UNKNOWN, _label("map", short=short), UNKNOWN_DETAIL, width=width))
    elif galaxy_size and galaxy_size > 0:
        pct = min(100, int(100 * known_sectors / galaxy_size))
        glyph = GLYPH_MET if known_sectors >= galaxy_size else GLYPH_PARTIAL
        detail = f"{known_sectors}/{galaxy_size}" if short else f"{known_sectors}/{galaxy_size} ({pct}%)"
        lines.append(_row(glyph, _label("map", short=short), detail, width=width))
    else:
        # Galaxy size itself is often unknown until fully mapped — a known
        # sector count with no denominator is still real progress, not
        # unknown, so this stays "· N sectors" rather than "?".
        detail = str(known_sectors) if short else f"{known_sectors} sectors"
        lines.append(_row(GLYPH_PARTIAL, _label("map", short=short), detail, width=width))

    # -- Formations ---------------------------------------------------------
    formations = _safe_int(status.get("formations_count"))
    if formations is None:
        lines.append(_row(GLYPH_UNKNOWN, _label("formations", short=short), UNKNOWN_DETAIL, width=width))
    else:
        glyph = GLYPH_PARTIAL if formations else GLYPH_UNKNOWN
        lines.append(_row(glyph, _label("formations", short=short), f"{formations} found", width=width))

    # -- Chain --------------------------------------------------------------
    chain_hops = _safe_int(status.get("chain_hops"))
    chain_unit = _safe_str(status.get("chain_unit")) or "hops"
    if chain_hops is None:
        lines.append(_row(GLYPH_UNKNOWN, _label("chain", short=short), UNKNOWN_DETAIL, width=width))
    elif chain_hops:
        detail = f"{chain_hops} {chain_unit[:1]}" if short else f"{chain_hops} {chain_unit}"
        lines.append(_row(GLYPH_MET, _label("chain", short=short), detail, width=width))
    else:
        lines.append(_row(GLYPH_PARTIAL, _label("chain", short=short), "none yet", width=width))

    # -- Ship prices (gated on a confirmed-not-found StarDock) -----------
    ship_prices = _safe_int(status.get("ship_prices_count"))
    if dock_blocked:
        lines.append(_row(GLYPH_BLOCKED, _label("ship_prices", short=short), UNKNOWN_DETAIL, width=width))
    elif ship_prices is None:
        lines.append(_row(GLYPH_UNKNOWN, _label("ship_prices", short=short), UNKNOWN_DETAIL, width=width))
    elif ship_prices > 0:
        detail = f"{ship_prices} ok" if short else f"{ship_prices} priced"
        lines.append(_row(GLYPH_MET, _label("ship_prices", short=short), detail, width=width))
    else:
        lines.append(_row(GLYPH_PARTIAL, _label("ship_prices", short=short), "price?", width=width))

    # -- Hold price (same gate) ------------------------------------------
    hold_label = _safe_str(status.get("hold_price_label"))
    if dock_blocked:
        lines.append(_row(GLYPH_BLOCKED, _label("hold_price", short=short), UNKNOWN_DETAIL, width=width))
    elif hold_label:
        lines.append(_row(GLYPH_MET, _label("hold_price", short=short), hold_label, width=width))
    elif "hold_price_label" in status:
        # Key present but blank — a quote was attempted and came back
        # empty, distinct from never having asked at all.
        lines.append(_row(GLYPH_PARTIAL, _label("hold_price", short=short), "price?", width=width))
    else:
        lines.append(_row(GLYPH_UNKNOWN, _label("hold_price", short=short), UNKNOWN_DETAIL, width=width))

    # -- Fighters -------------------------------------------------------
    fighters = _safe_int(status.get("fighters_aboard"))
    if fighters is None:
        lines.append(_row(GLYPH_UNKNOWN, _label("fighters", short=short), UNKNOWN_DETAIL, width=width))
    elif fighters > 0:
        lines.append(_row(GLYPH_MET, _label("fighters", short=short), str(fighters), width=width))
    else:
        buy_status = _safe_str(status.get("fighter_buy_status")) or "need some"
        lines.append(_row(GLYPH_PARTIAL, _label("fighters", short=short), f"0 ({buy_status})", width=width))

    return lines
