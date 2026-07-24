"""Pure HUD composer for the trainer-cockpit right gutter (PWO-037,
``workorders/WO-P3-034-041-panels-PREP.md`` §PWO-037).

No ``curses`` import here on purpose — this module composes plain strings
only, mirroring ``tw2002_aiclient/cockpit/goals.py`` / ``focus.py`` /
``decisions.py``'s discipline.

The HUD's defining property (`canon/surfaces/trainer-cockpit.md` "The
always-on HUD and its freshness"): it shows the **tracked model**, not the
current screen. TradeWars scatters credits/sector/turns/cargo across
screens and omits them entirely on many, so each cell **persists its
last-known value** and stamps it with an age — ``✦ Ns ago`` / ``✦ now``
(``format_freshness``), dimming once a cell goes stale past
``FRESHNESS_STALE_S`` (canon: 20s). Canon-authored field order, always
rendered regardless of input (`trainer-cockpit.md` mock: "credits/sector/
turns" / "cargo"; this WO's dispatch adds the fifth field, profit, in the
same fixed slot the archive's ``compose_hud_cells`` used):
CREDITS, SECTOR, TURNS, CARGO, PROFIT (``HUD_FIELDS``).

Upstream payload contract (WO-P3-037 dispatch — no wire bridge exists yet;
**this composer DEFINES the contract**, documented verbatim here so the
eventual wire bridge needs zero composer rework)::

    status["hud"] = {
        "credits": {"value": <int|str|None>, "age_s": <float|None>},
        "sector":  {"value": <int|str|None>, "age_s": <float|None>},
        "turns":   {"value": <int|str|None>, "age_s": <float|None>},
        "cargo":   {"value": <int|str|None>, "age_s": <float|None>},
        "profit":  {"value": <int|str|None>, "age_s": <float|None>},
    }

``age_s`` is the observation age in seconds **computed daemon-side** — a
monotonic clock base never crosses the JSON wire, so this module reads a
pre-computed age only. This composer is fully pure: **no clock reads, no
``time`` import for logic** — a fact a caller can rely on for reproducible
snapshot tests.

Per-cell semantics (WO-P3-037 dispatch):

- **Unknown cell** — a missing field, ``value: None``, a malformed slot (not
  a dict), or an absent/None/malformed ``status``/``status["hud"]`` — all
  render the sticky **``-``** value (``UNKNOWN_VALUE``, an ASCII hyphen —
  **not** the em-dash ``UNKNOWN_DETAIL`` GOALS/FOCUS/DECISIONS use; the
  archive's ``_hud_cell``/``_credits_cell``/``_turns_cell`` all use
  ``"value": "-"`` for this state) with **no** freshness stamp and
  ``stale=False``. Canon: "The HUD may cold-start all-``-``"
  (`trainer-cockpit.md` "Cold-join HUD seed") — honest-unknown, not stale;
  this is the state the real daemon produces today (no wire bridge yet).
- **``age_s`` is ``None`` but ``value`` is present** — the value renders with
  no freshness stamp, ``stale=False`` (we know the value, not how old it
  is — different from "unknown").
- **``age_s`` is present** — a stamp is rendered; ``stale`` is
  ``age_s >= FRESHNESS_STALE_S`` (20.0 is stale; 19.999 is not — the
  boundary is inclusive on the stale side, matching the archive's
  ``age >= FRESHNESS_STALE_S``).
- **Non-finite ``age_s`` (JSON-legal bare ``Infinity``/``-Infinity``/``NaN``,
  which ``json.loads`` accepts by default)** — pinned choice: treated
  identically to ``age_s: None`` (value renders, no stamp, ``stale=False``).
  The dispatch flagged "stale=True is acceptable" as an alternative; this
  module instead mirrors the established sibling convention
  (``focus.py``'s ``_safe_float``: a non-finite result screens to
  "unknown" rather than rendering a literal ``inf``/``nan``, and here that
  means "unknown freshness", not "confidently very stale") — pinned here,
  not left ambiguous.
- **Negative ``age_s``** — clamps to ``0.0`` (a slightly-skewed clock should
  never show a negative age; this is a distinct case from non-finite —
  a negative-but-finite value is a real, just-clamped number, not an
  unknown one).
- **Hostile values** — a JSON-legal non-finite ``value`` (a bare float
  ``Infinity``/``NaN``) degrades to the unknown ``-`` cell rather than
  rendering the literal text ``inf``/``nan``. A hostile object in the
  ``value``/``age_s`` slot (one whose ``__int__``/``__float__``/``__str__``
  raises something other than the expected coercion errors) is contained —
  never escapes this composer — matching ``goals.py``/``focus.py``'s
  broadened ``except Exception`` never-raises contract. A ``dict``
  *subclass* used as one field's slot (raising ``.get()``) is contained the
  same way ``focus.py``/``decisions.py`` contain a hostile per-candidate
  dict subclass — the field slot is this module's per-item boundary, the
  same role a FOCUS/DECISIONS candidate plays in those composers. The
  top-level ``status``/``status["hud"]`` payload itself being a hostile
  ``dict`` subclass is out of contract, same boundary ``goals.py`` /
  ``focus.py`` / ``decisions.py`` draw for their own top-level payloads —
  the daemon's real wire payload is always a plain ``json.loads()`` dict.

Value formatting. A real ``int``/``float`` payload is formatted with
thousands separators (credits/turns; sector/cargo stay unformatted,
mirroring the archive's own per-field lambda table; profit is signed) —
see ``_VALUE_FORMATTERS``. A ``str`` payload (or any non-numeric value that
survives coercion) renders **verbatim, trimmed** — never re-parsed or
re-formatted as a number. This avoids guessing whether an upstream string
like a pre-formatted label was meant as text or a number; only a real
``int``/``float`` wire value earns the numeric formatting.

Width: every composed line clips to ``width`` code points (the sibling
``goals.py``/``focus.py``/``decisions.py`` convention; the curses draw
layer is the real cell-width backstop for wide characters).

Glyph law. ``✦``→``*`` under ``unicode_ok=False`` is a **legitimate ASCII
twin** — the freshness mark is explicitly *not* one of the NO-SWAP rows
(`canon/surfaces/trainer-cockpit.md` glyph table: only ``✓``/``·``/``?``/
``⊘``/``★`` are called out NO-SWAP; ``✦`` pairs with ASCII ``*`` the same
way `session/terminal.py`'s ``GLYPHS_ASCII["freshness_mark"]`` already
does for the drawn chrome).

Scope boundary vs. the archive (WO-P3-037 dispatch: "Cold-join seed
(``hud_seed``) may be a sibling WO or fold-in — call out if deferred").
The archive's ``spectate_layout.py`` bundled three concerns this composer
deliberately keeps separate: (1) the **stateful accumulator**
(``update_tracked_stats``/``seed_tracked_from_status``, which threads a
monotonic clock and a persistent ``tracked`` dict through the daemon's
event stream) — out of scope; this module is a **pure per-tick renderer**
of an already-computed ``(value, age_s)`` snapshot, never a clock or event
consumer. (2) The **cold-join ``I``-probe seed** (``hud_seed.py`` in the
archive) that fills sticky cells on join — explicitly flagged in the
dispatch as a sibling WO / fold-in, **not built here**; this module simply
renders whatever the (not-yet-existing) wire bridge hands it, honestly
``-`` until that lands, same as GOALS/FOCUS/DECISIONS render honestly empty
today. (3) **Motion/liveness extras** (credit delta-chip, tween, sparkline,
turns fuel-gauge) the archive's ``compose_hud_cells`` also computed — out
of scope; this WO's API contract is deliberately the simpler
``(value, age_s) -> (text, stale)`` shape, and that polish belongs to the
liveness/motion work (`trainer-cockpit.md` "Liveness & motion"), not this
freshness-focused composer. **Never wires the trace ledger as a live HUD
source** (`trainer-cockpit.md` N4/N8: "the trace ledger is history only");
this module has no ledger import and never will.

D5: no ``ai_pilot``/imperative-mood text anywhere — this module renders
read-only observations (a label and a stamped value), never a command.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from .goals import _safe_str

# The HUD's own sticky-unknown marker — an ASCII hyphen, deliberately
# distinct from GOALS/FOCUS/DECISIONS' em-dash ``UNKNOWN_DETAIL``. The
# archive's ``_hud_cell``/``_credits_cell``/``_turns_cell`` all render
# unknown HUD cells as ``"-"``, and canon's cold-join language ("may
# cold-start all-``-``") names this exact glyph.
UNKNOWN_VALUE = "-"

# A persisted HUD cell dims past this many seconds untouched (canon
# `trainer-cockpit.md` "Panel states — active, stale, empty, alert":
# "dims to A_DIM once its value ages past FRESHNESS_STALE_S (20s)");
# ported verbatim from the archive's ``FRESHNESS_STALE_S``.
FRESHNESS_STALE_S: float = 20.0

# Canon-authored HUD field order (`trainer-cockpit.md` mock: "credits/
# sector/turns" / "cargo"; PROFIT is the archive's own established fifth
# HUD field, `compose_hud_cells`' fixed display order).
HUD_FIELDS: tuple[str, ...] = ("credits", "sector", "turns", "cargo", "profit")

_FIELD_LABELS: dict[str, str] = {
    "credits": "CREDITS",
    "sector": "SECTOR",
    "turns": "TURNS",
    "cargo": "CARGO",
    "profit": "PROFIT",
}

# Per-field numeric formatter. credits/sector/cargo/profit mirror the
# archive's own ``_HUD_FIELD_SPECS`` lambdas verbatim (credits comma'd,
# sector/cargo plain, profit signed+comma'd); turns is this module's own
# addition (the archive special-cased TURNS for its fuel-gauge, out of
# scope here) and is comma'd to match GOALS' own Turns row convention
# (``goals.py``'s ``f"{turns:,}"``) since turn counts run into the
# thousands the same way credits do.
_VALUE_FORMATTERS: dict[str, Callable[[object], str]] = {
    "credits": lambda v: f"{v:,}",
    "sector": lambda v: f"{v}",
    "turns": lambda v: f"{v:,}",
    "cargo": lambda v: f"{v}",
    "profit": lambda v: f"{v:+,}",
}


def format_freshness(age_s: object, *, unicode_ok: bool = True) -> str:
    """``✦ now`` / ``✦ Ns ago`` (ASCII mark ``*`` when ``unicode_ok`` is
    ``False``) — ported verbatim from the archive's threshold: an age under
    one second reads "now", otherwise the truncated whole-second count
    (`trainer-cockpit.md` ~347/392: the freshness stamp is NON-NEGOTIABLE
    per ``TUI-POLISH-PLAN.md``). There is no minutes/hours tier — the
    archive never had one and canon cites only "now"/"Ns ago" — a long
    session's stamp just keeps counting seconds (e.g. "3661s ago").

    Never raises: a non-finite or unparsable ``age_s`` degrades to the
    "now" text (as if age were ``0.0``) rather than crashing. In practice
    ``compose_hud_cells`` never passes this function a non-finite value
    (screened upstream — see the module docstring's non-finite ``age_s``
    policy: that case renders with no stamp at all, a different, composer-
    level choice from this function's own direct-call default) — this
    guard exists because ``format_freshness`` is public API per the WO
    contract and may be called directly with adversarial input.
    """
    mark = "✦" if unicode_ok else "*"
    try:
        seconds = float(age_s)
    except Exception:
        seconds = 0.0
    if not math.isfinite(seconds):
        seconds = 0.0
    seconds = max(0.0, seconds)
    if seconds < 1:
        return f"{mark} now"
    return f"{mark} {int(seconds)}s ago"


def _safe_age(value: object) -> float | None:
    """Best-effort seconds-age coercion. ``None``, unparsable input, or a
    non-finite result (``Infinity``/``-Infinity``/``NaN`` — ``json.loads``
    accepts these by default) all become ``None`` — the module docstring's
    pinned "no freshness stamp" policy for those cases. A negative-but-
    finite age clamps to ``0.0`` (a real, just-skewed number, not an
    unknown one) rather than also collapsing to ``None``. The broad
    ``except Exception`` is the same never-raises backstop
    ``goals.py``/``focus.py`` use for their own coercion helpers — a
    hostile ``__float__`` that raises something unexpected still degrades
    honestly rather than escaping this composer."""
    if value is None:
        return None
    try:
        age = float(value)
    except Exception:
        return None
    if not math.isfinite(age):
        return None
    return max(0.0, age)


def _format_value(field: str, value: object) -> str | None:
    """Best-effort per-field HUD value text, or ``None`` when the slot is
    unknown/unrenderable (caller substitutes the sticky ``UNKNOWN_VALUE``).

    A real ``int``/``float`` (excluding ``bool`` — a JSON boolean is a
    legal-but-nonsensical HUD value and must never silently read as a
    numeric ``1``/``0`` through the comma-formatter) gets this field's
    numeric formatter (see ``_VALUE_FORMATTERS``); a whole-valued float
    (e.g. ``987654.0``) is converted to ``int`` first so it renders as
    ``"987,654"``, not ``"987,654.0"``. A non-finite float (``Infinity``/
    ``NaN``) degrades to ``None`` (unknown) rather than rendering the
    literal text ``inf``/``nan``. Everything else — a ``str`` payload, or
    any hostile/unexpected object — falls through to ``_safe_str``'s own
    never-raises coercion, rendered verbatim rather than re-parsed as a
    number (see module docstring)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return _safe_str(value)
    if isinstance(value, (int, float)):
        try:
            finite = math.isfinite(value)
        except Exception:
            finite = False
        if not finite:
            return None
        numeric = value
        if isinstance(value, float):
            try:
                if value.is_integer():
                    numeric = int(value)
            except Exception:
                pass
        formatter = _VALUE_FORMATTERS.get(field)
        if formatter is not None:
            try:
                return formatter(numeric)
            except Exception:
                pass
        return _safe_str(numeric)
    return _safe_str(value)


def _clip(text: str, *, width: int) -> str:
    if width <= 0:
        return ""
    return text[:width]


def _field_cell(field: str, hud: dict, *, unicode_ok: bool) -> tuple[str, bool]:
    """Compose one field's unclipped value-row text and its ``stale`` flag.

    ``hud.get(field)`` itself is trusted (the top-level ``status["hud"]``
    payload boundary — same trust level ``focus.py``'s
    ``payload.get("candidates")`` extends to its own top-level payload).
    The returned per-field slot is the untrusted, per-item boundary this
    module defends — mirroring ``focus.py``/``decisions.py``'s per-
    candidate ``try``/``except`` around each candidate's own ``.get()``
    calls: a hostile ``dict`` subclass in this slot (raising ``.get()``) is
    contained here, never escapes."""
    field_status = hud.get(field)
    if not isinstance(field_status, dict):
        return UNKNOWN_VALUE, False
    try:
        raw_value = field_status.get("value")
        raw_age = field_status.get("age_s")
    except Exception:
        return UNKNOWN_VALUE, False

    value_text = _format_value(field, raw_value)
    if value_text is None:
        return UNKNOWN_VALUE, False

    age = _safe_age(raw_age)
    if age is None:
        return value_text, False

    stale = age >= FRESHNESS_STALE_S
    freshness = format_freshness(age, unicode_ok=unicode_ok)
    return f"{value_text} {freshness}", stale


def compose_hud_cells(
    status: dict | None, *, width: int, unicode_ok: bool = True
) -> list[tuple[str, bool]]:
    """Compose the HUD panel's fixed 10-line readout — 5 fields
    (``HUD_FIELDS``, canon order CREDITS/SECTOR/TURNS/CARGO/PROFIT) × a
    2-row stride: a label row (e.g. ``"CREDITS"``) then a value row (e.g.
    ``"12,345 ✦ 3s ago"``). Each returned item is ``(text, stale)`` —
    ``stale`` is ``True`` only on a value row whose age has passed
    ``FRESHNESS_STALE_S``; label rows are always ``stale=False`` (a label
    never dims — only the persisted value it stamps does).

    Never raises regardless of ``status``'s shape or content. A non-dict
    ``status`` (including ``None``) or a non-dict/absent ``status["hud"]``
    renders every field as the honest-unknown sticky ``-`` — canon's "the
    HUD may cold-start all-``-``". Every field is independently coerced —
    see the module docstring for the full per-field semantics (unknown
    slot, ``age_s`` absent/non-finite/negative, hostile values, hostile
    per-field ``dict`` subclasses). Every line is ``len(line) <= width``
    (``width <= 0`` — or unparsable, e.g. a non-numeric string — empties
    every line to ``""``, mirroring ``goals.py``/``focus.py``/
    ``decisions.py``'s width-clip convention); the returned list always
    has exactly 10 entries regardless of ``width``.

    This never-raises contract covers any JSON-wire-shaped input — plain
    dicts/lists and hostile *values* within them included, plus a hostile
    per-field ``dict`` subclass (contained the same way FOCUS/DECISIONS
    contain a hostile per-candidate dict subclass). A ``status``/
    ``status["hud"]`` payload that is itself a hostile ``dict`` subclass
    (raising ``.get()``/``__contains__``) is out of contract — the
    daemon's real wire payload is always a plain ``json.loads()`` dict,
    never a subclass, and that hazard is contained at the render layer
    instead of here, matching ``goals.py``/``focus.py``/``decisions.py``'s
    own top-level boundary.
    """
    try:
        width = int(width)
    except (TypeError, ValueError):
        width = 0

    status = status if isinstance(status, dict) else {}
    hud = status.get("hud")
    hud = hud if isinstance(hud, dict) else {}

    lines: list[tuple[str, bool]] = []
    for field in HUD_FIELDS:
        lines.append((_clip(_FIELD_LABELS[field], width=width), False))
        try:
            value_line, stale = _field_cell(field, hud, unicode_ok=unicode_ok)
        except Exception:
            value_line, stale = UNKNOWN_VALUE, False
        lines.append((_clip(value_line, width=width), stale))

    return lines
