"""Pure FOCUS-panel composer for the trainer-cockpit left gutter (PWO-035,
``workorders/WO-P3-034-041-panels-PREP.md`` §PWO-035).

No ``curses`` import here on purpose — this module composes plain strings
only, mirroring ``tw2002_aiclient/cockpit/goals.py``'s discipline.

FOCUS is **Layer-2 ranked suggestions** (`canon/engine/priority-engine.md`
"Layer 2 — FOCUS" / `canon/surfaces/trainer-cockpit.md` ~58-63): the
priority engine's ordered effort candidates for the current tick (Trade
chain / Upgrade / Explore), highest expected-value first, with a gate glyph
``⊘`` and short reason on any candidate the engine has skipped. **FOCUS only
displays the engine's ranking — it never ranks, sorts, or re-orders on its
own, never picks or sends a live action, and carries no "chosen" marker**
(``★`` is DECISIONS/autopilot-trace vocabulary — `canon/surfaces/
trainer-cockpit.md` ~388 — not FOCUS). GOALS says what is known; FOCUS says
what would be worth doing, in the order the engine already computed; the
run-loop's stop-on-unknown and human-arming still gate whether anything
actually fires (`canon/engine/priority-engine.md`).

Status-dict field mapping (WO-P3-035). ``status`` is the daemon's ``status``
verb response shape (``tw2002_aiclient/session/protocol.py::dispatch()``).
FOCUS reads a nested ``status["focus"]`` payload — its own namespace,
separate from GOALS' flat top-level keys, because FOCUS is a *rank-ordered
list* rather than a fixed row set. As of this WO the live daemon status
carries no ``focus`` key at all (the priority engine's boolean-weight
overlay bridge into a wire payload is not built yet — see
``canon/engine/priority-engine.md`` "Boolean-weight overlay ... not built
yet"), so every real call renders the honest empty panel until that lands:

| key                        | shape                                                          |
|-----------------------------|-----------------------------------------------------------------|
| ``focus``                   | dict; absent/None/non-dict → empty panel                        |
| ``focus.candidates``        | list, already in ENGINE rank order — this module never re-sorts |
| candidate ``kind``          | str, e.g. ``run_chain``/``upgrade``/``explore`` — mirrors the archive's ``priority_engine.PriorityScore.kind`` |
| candidate ``ev_per_turn``   | float or None — comparable cr/turn; None when gated/unknown — mirrors ``PriorityScore.ev_per_turn`` |
| candidate ``gated``         | bool — mirrors ``PriorityScore.gated``                          |
| candidate ``gate_reason``   | str or None — shown only when ``gated`` — mirrors ``PriorityScore.gate_reason`` |

Mirroring the engine's own dataclass field names (rather than inventing a
display-shaped payload) keeps this composer a thin display step: it maps
``kind`` to a readable label (`canon/engine/priority-engine.md` "Readable
labels map ``run_chain`` -> 'Trade chain', ``upgrade`` -> 'Upgrade',
``explore`` -> 'Explore'") and renders the gate reason — nothing more. A
non-dict candidate entry is dropped rather than rendered as a fabricated
line; a candidate missing/blank ``kind`` renders with the honest-unknown
filler, never a guessed label.

Glyph choice. GOALS' four-glyph status set (``✓``/``·``/``?``/``⊘``,
`canon/surfaces/visual-language.md` glyph table) is grounded in
``compose_primary_goals_lines`` — canon calls out only ``⊘`` as also used
by "a gated FOCUS/autopilot candidate". FOCUS lines therefore never lead
with ``✓``/``·``/``?`` (that would read as a GOALS status glyph in the
wrong panel); they lead with the candidate's rank number instead, and use
``⊘`` only on a gated row. A missing detail (unknown kind, missing gate
reason) uses the universal em-dash filler ``UNKNOWN_DETAIL`` — imported
from ``goals.py`` — same as GOALS' own "never invent, degrade honestly"
convention, not a status glyph.

Helper reuse (WO-P3-035 dispatch note). This module imports the public
``GLYPH_BLOCKED``/``UNKNOWN_DETAIL`` constants and the private
``_safe_str``/``_safe_list`` coercion helpers directly from ``goals.py``
(a package-internal import — the dispatch's own out-of-bounds note reads
"goals.py beyond importing its helpers", sanctioning exactly this) rather
than extracting a third shared module. Only two of goals.py's helpers apply
here: ``_safe_str`` (a raising ``__str__`` degrades to ``None``, reused
verbatim for both ``kind`` and ``gate_reason``) and ``_safe_list`` (only a
real ``list``/``tuple`` counts as the candidates container). goals.py's
``_safe_int`` does not apply — GOALS' fields are all integer counts, but
FOCUS's ``ev_per_turn`` is a float cr/turn rate, so this module adds its
own ``_safe_float`` (with the same OverflowError-on-``inf`` lesson, plus an
explicit finiteness check so a bare ``Infinity``/``NaN`` payload — which
``json.loads`` accepts by default — never reaches the render as a literal
"inf"/"nan" string). Extracting a shared module for two constants and two
functions felt like premature abstraction for a two-composer codebase; a
direct import is the smaller, more legible diff and keeps goals.py as the
acknowledged owner of the coercion contract both mirror.
"""

from __future__ import annotations

import math

from .goals import GLYPH_BLOCKED, UNKNOWN_DETAIL, _safe_list, _safe_str

# Canon-authored kind -> readable label (`canon/engine/priority-engine.md`
# "Layer 2 — FOCUS": "Readable labels map `run_chain` -> 'Trade chain',
# `upgrade` -> 'Upgrade', `explore` -> 'Explore'").
_KIND_LABELS: dict[str, str] = {
    "run_chain": "Trade chain",
    "upgrade": "Upgrade",
    "explore": "Explore",
}


def _safe_float(value: object) -> float | None:
    """Best-effort float coercion for the ``ev_per_turn`` cr/turn rate.

    Mirrors ``goals.py._safe_int``'s ``OverflowError``-on-``inf`` lesson,
    plus an explicit finiteness check: ``json``'s default ``allow_nan=True``
    means a malformed daemon payload can hand this a real
    ``float('inf')``/``float('nan')`` even after ``float()`` succeeds
    outright (unlike ``int()``, ``float('nan')`` does not raise), so a
    non-finite result is screened out here rather than rendered as a
    literal "inf"/"nan" string. The broad ``except Exception`` (Mack's
    review) is the never-raises *contract* backstop — ``float(value)`` calls
    ``value.__float__()`` for an arbitrary object, and a hostile
    ``__float__`` that raises something other than
    ``TypeError``/``ValueError``/``OverflowError`` (e.g. a bare
    ``RuntimeError``) must still degrade to honest-unknown EV, not escape
    this composer."""
    if value is None:
        return None
    try:
        result = float(value)
    except Exception:
        return None
    if not math.isfinite(result):
        return None
    return result


def _safe_bool(value: object) -> bool:
    """Best-effort bool coercion — a hostile ``__bool__`` that raises
    degrades to ``False`` (not gated) rather than crashing the composer."""
    try:
        return bool(value)
    except Exception:
        return False


def _format_ev(ev: float | None) -> str:
    """Readable signed cr/turn rate, or the honest-unknown filler when
    ``ev`` could not be coerced to a finite float."""
    if ev is None:
        return f"ev {UNKNOWN_DETAIL}"
    return f"{ev:+.1f}cr/t"


def _kind_label(kind_raw: str | None) -> str:
    """Map an engine ``kind`` string to its readable label.

    An unrecognized-but-real kind still renders — humanized (underscores to
    spaces, title-cased) rather than shown raw or guessed away, mirroring
    the archive's ``priority_kind_label`` fallback shape. A missing/blank
    kind degrades to the honest-unknown filler, never a fabricated label.
    """
    if not kind_raw:
        return UNKNOWN_DETAIL
    return _KIND_LABELS.get(kind_raw, kind_raw.replace("_", " ").title())


def _clip(text: str, *, width: int) -> str:
    if width <= 0:
        return ""
    return text[:width]


def compose_focus_lines(status: dict | None, *, width: int) -> list[str]:
    """Compose the FOCUS panel's ranked-suggestion lines.

    Never raises regardless of ``status``'s shape or content. Reads
    ``status["focus"]["candidates"]`` (see module docstring for the exact
    field mapping) and renders one line per valid candidate **in the order
    given** — this function never re-sorts; the priority engine is the sole
    ranker (`canon/engine/priority-engine.md`). An ungated line reads
    ``"<rank> <label> <signed-ev>cr/t"``; a gated line reads
    ``"<rank> ⊘ <label> <reason>"``. A non-dict candidate entry — or a
    dict-shaped one whose field access raises (e.g. a hostile ``.get()``) —
    is dropped silently rather than rendered as a fabricated line;
    survivors renumber with no gap.

    Absent/None/non-dict ``status``, an absent/malformed ``focus`` payload,
    or an empty/malformed ``candidates`` list all render the single-line
    honest-empty state (`canon/surfaces/trainer-cockpit.md` "Panel states":
    "PRIORITIES shows ``—``"), never an invented candidate. Every line is
    ``len(line) <= width`` (``width <= 0`` empties every line to ``""``,
    mirroring ``goals.py``'s width-clip convention).

    This never-raises contract covers any JSON-wire-shaped input — plain
    dicts/lists and hostile *values* within them included, and (per the
    per-candidate try/except above) a hostile-but-real ``dict`` subclass
    used as one *candidate*. A top-level ``status``/``focus`` payload that
    is itself a ``dict`` subclass with a raising ``.get()`` is out of
    contract — the daemon's real wire payload is always a plain
    ``json.loads()`` dict, never a subclass, and that hazard is contained
    at the render layer instead of here.
    """
    try:
        width = int(width)
    except (TypeError, ValueError):
        width = 0

    status = status if isinstance(status, dict) else {}
    payload = status.get("focus")
    payload = payload if isinstance(payload, dict) else {}
    raw_candidates = _safe_list(payload.get("candidates"))
    candidates = [c for c in raw_candidates if isinstance(c, dict)]

    if not candidates:
        return [_clip(UNKNOWN_DETAIL, width=width)]

    lines: list[str] = []
    for cand in candidates:
        try:
            rank = len(lines) + 1
            label = _kind_label(_safe_str(cand.get("kind")))
            if _safe_bool(cand.get("gated")):
                reason = _safe_str(cand.get("gate_reason")) or UNKNOWN_DETAIL
                text = f"{rank} {GLYPH_BLOCKED} {label} {reason}"
            else:
                ev = _safe_float(cand.get("ev_per_turn"))
                text = f"{rank} {label} {_format_ev(ev)}"
        except Exception:
            # A dict-subclass whose own `.get()` (or any other field access
            # here) raises is just another dropped slot — extends the same
            # drop-and-renumber semantics as the `isinstance(c, dict)`
            # filter above; survivors still get sequential ranks with no
            # gap (Mack's review: the isinstance check alone doesn't stop a
            # *real* dict subclass with hostile field access from escaping).
            continue
        lines.append(_clip(text, width=width))

    return lines
