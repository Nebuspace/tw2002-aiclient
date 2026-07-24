"""Pure DECISIONS-panel composer for the trainer-cockpit right gutter
(PWO-036, ``workorders/WO-P3-034-041-panels-PREP.md`` §PWO-036).

No ``curses`` import here on purpose — this module composes plain strings
only, mirroring ``tw2002_aiclient/cockpit/goals.py`` / ``focus.py``'s
discipline.

DECISIONS is the **autopilot-trace detail** for the current tick
(`canon/surfaces/trainer-cockpit.md` ~80-84: "the trace detail behind the
current tick: the chosen action kind, its rationale, and any gate
reasons"). Where GOALS says *what is known* and FOCUS says *what is worth
doing* (both read-only, ranked-but-not-committed views), DECISIONS says
*what the app is actually reasoning right now* about the SAME candidate set
FOCUS ranks — one line per candidate, marking which one (if any) the
engine's dry-run actually picked this tick. **DECISIONS never sends, and
carries no chosen-and-about-to-fire semantics beyond display** — a "chosen"
candidate here is the engine's dry-run pick for its own bookkeeping, not a
live keystroke; the app's real send path is governed entirely by
[priority-engine](/engine/priority-engine.md) and the human-arming gate in
[mode-line-and-teach-controls](/surfaces/mode-line-and-teach-controls.md),
neither of which this composer touches or reads.

Glyph vocabulary (`canon/surfaces/trainer-cockpit.md` ~388, the ``NO-SWAP``
glyph table): **``★`` chosen action · ``·`` other candidate · ``⊘`` gated**
— this is DECISIONS-only vocabulary; unlike FOCUS (which never renders
``★``, see ``focus.py``'s own docstring), ``★`` is legal and expected here.
Every composed candidate line is **glyph-prefixed** — a structural
guarantee, not a per-line check: no rendered candidate line can begin with
a bare word, imperative or otherwise, because its first character is always
one of ``★``/``·``/``⊘``. The two-line empty state is the one exception and
is composer-authored, present-participle text ("Exploring…"), never an
imperative — see ``IMPERATIVE_DENYLIST`` below.

Status-dict field mapping (WO-P3-036). ``status`` is the daemon's ``status``
verb response shape (``tw2002_aiclient/session/protocol.py::dispatch()``).
As of this WO the live daemon status carries no ``autopilot_trace`` key at
all (the priority engine's dry-run trace bridge into a wire payload is not
built yet — the same "not wired" state ``focus.py`` documents for its own
``status["focus"]`` key), so every real call renders the honest empty panel
until that lands. The key mapping mirrors the archived Phase-1 dry-run
trace shape verbatim (``archive/pre-rebirth-2026-07-23/code/twclient/
spectate_layout.py::PROVISIONAL_AUTOPILOT_TRACE`` / ``format_autopilot_
trace_lines``) so the eventual wire bridge needs zero composer rework:

| key                            | shape                                                             |
|----------------------------------|----------------------------------------------------------------------|
| ``autopilot_trace``              | dict; absent/None/non-dict -> empty panel                            |
| ``autopilot_trace.chosen``       | str kind or ``None`` (no live pick this tick) — the engine's dry-run pick |
| ``autopilot_trace.candidates``   | list of dicts, in the priority engine's own order — this module never re-sorts |
| candidate ``kind``               | str, e.g. ``run_chain``/``upgrade``/``explore`` — same vocabulary as ``focus.py``'s candidates |
| candidate ``ev_cr_per_turn``     | float or None — **note the field name**: the archived trace fixture names this ``ev_cr_per_turn``, distinct from ``focus.py``'s ``ev_per_turn``. These are two independent upstream shapes (FOCUS reads the priority engine's live ``PriorityScore`` ranking; DECISIONS reads the dry-run trace object) and are not guaranteed to share a field name — flagged here so a future wire bridge does not silently assume parity. |
| candidate ``gated``              | bool                                                                  |
| candidate ``gate_reason``        | str or None — shown only when ``gated``                              |
| candidate ``rationale``          | str or None — the trace's own short stated reasoning for this candidate; shown on non-gated lines (canon's "its rationale") |

**Divergence from the archived function.** The archived
``format_autopilot_trace_lines`` treated a non-str ``chosen`` value
(enum/dict/object) as making the *whole trace* malformed and returned the
single-line empty state. This module instead applies the same per-field
coercion discipline ``goals.py``/``focus.py`` use everywhere else:
``chosen`` is coerced with ``_safe_str`` like any other field, and a value
that fails to coerce to a matching string simply never matches any
candidate's ``kind`` (no line gets ``★``) rather than blanking an
otherwise-valid candidate list.

**Coach-tip scope note (WO-P3-036 dispatch).** The dispatch asked to check
whether "the trace-ledger contract carries" a coach-tip text field.
`canon/engine/trace-ledger.md` carries only an optional per-row ``intent``
— a short authored rationale attached to a *historical, already-sent*
ledger row (tier 2, written after the fact by the dispatch path) — which is
not a live per-tick feed this panel could read. The DECISIONS-idle
coach-callout behavior canon actually specifies
(`canon/engine/coaching-engine.md`'s ``infer_coach_triggers`` /
``compose_decisions_coach``) is a **separate, sibling engine** with its own
strategy-card knowledge base, trigger map, and configurable-parameter
substrate — materially larger scope than this pure trace-to-lines
composer. This module deliberately does **not** implement that fallback;
the two-line honest-empty state below is what DECISIONS shows whenever
there is no live trace, exactly as the PREP scoped it. Wiring the
coach-callout fallback in front of that empty state is left to a follow-on
WO against ``coaching-engine.md``.

Helper reuse (WO-P3-036 dispatch note: "reuse goals/focus ``_safe_*``
helpers via package import"). This module imports ``GLYPH_BLOCKED`` /
``UNKNOWN_DETAIL`` / ``_safe_list`` / ``_safe_str`` from ``goals.py`` and
``_format_ev`` / ``_kind_label`` / ``_safe_bool`` / ``_safe_float`` from
``focus.py`` rather than reimplementing any of them — the dispatch's
out-of-bounds note explicitly sanctions importing from both
("goals.py/focus.py beyond importing helpers"). Only ``GLYPH_CHOSEN`` /
``GLYPH_OTHER`` (``★``/``·``, DECISIONS-only) are new here; ``⊘`` is the
same ``GLYPH_BLOCKED`` constant GOALS and FOCUS already share.

This never-raises contract covers any JSON-wire-shaped input — plain
dicts/lists and hostile *values* within them included (non-finite floats,
raising dunders, control characters), matching ``goals.py``/``focus.py``'s
own contract. A hostile top-level ``status``/``autopilot_trace`` payload
that is itself a ``dict`` *subclass* with a raising ``.get()``/
``__contains__`` is out of contract — the daemon's real wire payload is
always a plain ``json.loads()`` dict, never a subclass, and that hazard is
contained at the render layer instead of here (same boundary
``focus.py``/``goals.py`` draw). A hostile *candidate* dict-subclass
(raising ``.get()``) IS in contract — caught per-candidate below, matching
``focus.py``'s own per-candidate try/except.
"""

from __future__ import annotations

from .focus import _format_ev, _kind_label, _safe_bool, _safe_float
from .goals import GLYPH_BLOCKED, UNKNOWN_DETAIL, _safe_list, _safe_str

GLYPH_CHOSEN = "★"
GLYPH_OTHER = "·"

# Small, deliberately-curated set of imperative-mood verbs that would make a
# line read as a live command rather than read-only reasoning (canon
# hazard, `trainer-cockpit.md` PWO-036 hazards: "coaching copy must not
# look like a live driver"). This module's own authored vocabulary (the
# fixed kind labels imported from focus.py, and the two empty-state
# strings below) is checked against it in
# tests/test_cockpit_decisions.py. It is NOT a general sanitizer for
# arbitrary wire-supplied text — an operator-hostile `kind` or `rationale`
# string could still spell an imperative word — same type-safety-only
# boundary goals.py/focus.py already draw for their own free-text fields.
# Every real candidate line is glyph-prefixed regardless of this list (see
# module docstring), which is the load-bearing structural guarantee; this
# denylist is a secondary, narrower check on text this module itself
# chooses to author. "explore"/"trade"/"upgrade" are deliberately absent —
# they collide with the canon-authored FOCUS/DECISIONS kind-label
# vocabulary (`focus.py::_KIND_LABELS`) and are not command-style verbs in
# that noun-phrase context.
IMPERATIVE_DENYLIST = frozenset(
    {
        "attack",
        "buy",
        "sell",
        "do",
        "fire",
        "flee",
        "go",
        "hit",
        "press",
        "retreat",
        "send",
        "type",
        "warp",
    }
)


def _clip(text: str, *, width: int) -> str:
    if width <= 0:
        return ""
    return text[:width]


def compose_decisions_lines(status: dict | None, *, width: int) -> list[str]:
    """Compose the DECISIONS panel's autopilot-trace lines.

    Never raises regardless of ``status``'s shape or content. Reads
    ``status["autopilot_trace"]`` (see module docstring for the exact field
    mapping) and renders one line per valid candidate **in the trace's own
    order** — this function never re-sorts or re-ranks; DECISIONS is a
    display of the same candidate set FOCUS ranks, from a different lens
    (`canon/surfaces/trainer-cockpit.md`: "GOALS says what is known, FOCUS
    says what is worth doing, DECISIONS says what the app is actually
    reasoning right now").

    A candidate line reads ``"⊘ <label> <gate reason>"`` when gated, else
    ``"★ <label> <ev> <rationale>"`` when its ``kind`` matches the trace's
    ``chosen`` value, else ``"· <label> <ev> <rationale>"``. Gate wins over
    chosen — a candidate the engine flagged ``gated`` was, by definition,
    not actually pickable this tick, even if ``chosen`` happens to name the
    same kind — mirroring the archived ``format_autopilot_trace_lines``'
    glyph precedence.

    A non-dict candidate entry — or a dict-shaped one whose field access
    raises (e.g. a hostile ``.get()``) — is dropped silently rather than
    rendered as a fabricated line; there is no rank number to renumber here
    (unlike FOCUS), so a dropped entry simply leaves one fewer line.

    Absent/None/non-dict ``status``, an absent/malformed ``autopilot_trace``
    payload, or an empty/malformed ``candidates`` list (including one whose
    every entry was dropped as malformed) all render the two-line
    honest-empty state (`canon/surfaces/trainer-cockpit.md` "Panel states":
    ``DECISIONS shows ["—", "Exploring…"]``), never an invented candidate or
    a one-line placeholder.

    Every line is ``len(line) <= width`` (``width <= 0`` empties every line
    to ``""``, mirroring ``goals.py``/``focus.py``'s width-clip convention,
    including both empty-state lines).
    """
    try:
        width = int(width)
    except (TypeError, ValueError):
        width = 0

    status = status if isinstance(status, dict) else {}
    payload = status.get("autopilot_trace")
    payload = payload if isinstance(payload, dict) else {}
    raw_candidates = _safe_list(payload.get("candidates"))
    candidates = [c for c in raw_candidates if isinstance(c, dict)]
    chosen_kind = _safe_str(payload.get("chosen"))

    lines: list[str] = []
    for cand in candidates:
        try:
            kind_raw = _safe_str(cand.get("kind"))
            label = _kind_label(kind_raw)
            gated = _safe_bool(cand.get("gated"))
            if gated:
                reason = _safe_str(cand.get("gate_reason")) or UNKNOWN_DETAIL
                text = f"{GLYPH_BLOCKED} {label} {reason}"
            else:
                glyph = (
                    GLYPH_CHOSEN
                    if chosen_kind is not None and kind_raw == chosen_kind
                    else GLYPH_OTHER
                )
                ev = _format_ev(_safe_float(cand.get("ev_cr_per_turn")))
                rationale = _safe_str(cand.get("rationale")) or UNKNOWN_DETAIL
                text = f"{glyph} {label} {ev} {rationale}"
        except Exception:
            # A dict-subclass whose own `.get()` (or any other field
            # access here) raises is just another dropped slot — no rank
            # to renumber (DECISIONS carries no ranks, unlike FOCUS), the
            # entry simply contributes no line.
            continue
        lines.append(_clip(text, width=width))

    if not lines:
        return [
            _clip(UNKNOWN_DETAIL, width=width),
            _clip("Exploring…", width=width),
        ]

    return lines
