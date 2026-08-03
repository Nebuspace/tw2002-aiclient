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
one of ``★``/``·``/``⊘``. The calm empty state is the one exception: when
there is no live trace, no explore overlay, and no coach card, the pane
shows the four autonomy HELP one-liners (`E`/`H`/`O`/`L`, confirm-not-auto
on H/O — WO-WIRE-AUTONOMY-HELP-LINES) rather than a bare "Exploring…"
pair. Still never an imperative command — see ``IMPERATIVE_DENYLIST``.

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
composer.

**That follow-on has now landed** (``WO-STATUS-CHAIN-SCALARS-COACH``); the
paragraph above described the state before it. The engine itself was
restored by ``WO-COACH-ENGINE-PORT`` (``coach_engine.py`` /
``coach_kb.py``), and this module now consults it **in front of** the
two-line honest-empty state: a live trace still wins outright, and only
when there is no renderable trace does the coach get a turn. Three
properties make that safe to do from a module whose contract is *never
raises*:

* **The KB load is one-shot and defensive.** ``coach_kb.load_coach_kb``
  does file I/O and ``json.loads`` — both raise. It is attempted at most
  once per process, and a failure is cached as "no KB", which degrades to
  the same honest-empty state. A missing or malformed ``strategies.json``
  costs the operator their coaching, never their DECISIONS panel.
* **Card text is never composed here.** Every rendered string comes from
  ``compose_decisions_coach`` over authored ``data/coach/strategies.json``
  content. This module contributes no prose — canon's single-source rule.
* **Fail-closed inputs.** Triggers are inferred only from fields
  ``status`` actually carries. Absent inputs omit their trigger rather
  than guessing one, and no trigger at all falls straight through to the
  empty state.

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

from tw2002_aiclient import chain_status as _chain_status
from tw2002_aiclient import coach_engine as _coach
from tw2002_aiclient import coach_kb as _coach_kb
from tw2002_aiclient.ship_upgrade_decision import (
    compose_upgrade_decision_lines,
    upgrade_decision_from_status,
)

from . import autonomy_keys
from .focus import _format_ev, _kind_label, _safe_bool, _safe_float
from .goals import GLYPH_BLOCKED, UNKNOWN_DETAIL, _safe_list, _safe_str

# One-shot KB load. ``_KB_UNSET`` distinguishes "not attempted yet" from the
# cached result of a *failed* attempt (``None``) -- without it a failure would
# be retried on every draw, turning a missing data file into per-frame file
# I/O on the cockpit's hot path.
_KB_UNSET = object()
_kb_cache: object = _KB_UNSET


def _kb():
    """The strategy KB, or ``None``. Loads at most once; never raises."""
    global _kb_cache
    if _kb_cache is _KB_UNSET:
        try:
            _kb_cache = _coach_kb.load_coach_kb(*_coach_kb.default_kb_paths())
        except Exception:  # noqa: BLE001 -- no coaching is survivable; a dead panel is not
            _kb_cache = None
    return _kb_cache


def _reset_kb_cache_for_tests() -> None:
    """Drop the memoised KB. Tests only -- there is no product caller."""
    global _kb_cache
    _kb_cache = _KB_UNSET


# Halt reason codes that mean the armed loop depleted (canon control /
# escalation + coaching-engine). Anything else on the intervention wire —
# near-miss, unknown, malformed — stays silent for this trigger.
_LOOP_DEPLETION_CODES = frozenset({"floor_reached", "turn_budget_exhausted"})


def _loop_depleting_from_intervention(status: dict) -> bool:
    """``True`` only when ``status["intervention"]["reasons"]`` carries a
    depletion code. Never reads ``prompt``; never invents a halt."""
    intervention = status.get("intervention")
    if not isinstance(intervention, dict):
        return False
    reasons = intervention.get("reasons")
    if not isinstance(reasons, list):
        return False
    for item in reasons:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        if isinstance(code, str) and code in _LOOP_DEPLETION_CODES:
            return True
    return False


def _upgrade_decision_lines(status: dict, *, width: int) -> list[str]:
    """PWO-107 Option A: recommend-only UpgradeDecision callouts, or ``[]``.

    Prefer a live TW-30 decision over the generic holds_first strategy card
    when status carries upgrade inputs / a precomputed decision. Never sends.
    """
    try:
        decision = upgrade_decision_from_status(status)
        if decision is None:
            return []
        lines = compose_upgrade_decision_lines(decision, width=max(0, width))
        return [_clip(line, width=width) for line in lines]
    except Exception:  # noqa: BLE001 -- never-raises
        return []


def _coach_lines(status: dict, *, width: int) -> list[str]:
    """Authored coach callouts for ``status``, or ``[]`` when none apply.

    Total: any failure anywhere in the coach path yields ``[]``, which the
    caller renders as the same honest-empty state it would have shown anyway.
    """
    try:
        # PWO-107 Option A: concrete UpgradeDecision wins over generic cards.
        upgrade_lines = _upgrade_decision_lines(status, width=width)
        if upgrade_lines:
            return upgrade_lines
        kb = _kb()
        if kb is None:
            return []
        chain = _chain_status.as_chain_like(
            status.get(_chain_status.HOPS_KEY), status.get(_chain_status.UNIT_KEY)
        )
        # Only fields the `status` verb actually emits are passed. `prompt` is
        # NOT one of them and must not be added: `session/protocol.py::
        # _status_response` omits it deliberately, because on a server that
        # echoes at the password gate that line IS the operator's credential.
        # Three of the trigger map's inputs key off `prompt`, so they simply
        # cannot fire from this consumer -- fail-closed, and the right trade.
        triggers = _coach.infer_coach_triggers(
            classification=_safe_str(status.get("classification")),
            chain=chain,
            fighters_aboard=_safe_int_or_none(status.get("fighters_aboard")),
            # Identity-true only (WO-COACH-HAS-PORT): truthy strings / 1 must
            # not fire the trade card. Absent / False / junk → default False.
            has_port=status.get("has_port") is True,
            # WO-COACH-DEAD-END-COUNT: real non-negative int only; hostile → 0.
            dead_end_count=_safe_nonneg_int(status.get("dead_end_count")) or 0,
            # WO-FORMATIONS-CATALOG-PORT: same pattern — wire the consumer.
            genesis_count=_safe_nonneg_int(status.get("genesis_count")) or 0,
            # WO-COACH-EXPLORE-MODE: fail-closed string only (int/bool must not
            # coerce into a mode); "off"/blank/absent → no card.
            explore_mode=(
                _safe_str(status.get("explore_mode"))
                if isinstance(status.get("explore_mode"), str)
                else None
            ),
            loop_depleting=_loop_depleting_from_intervention(status),
        )
        if not triggers:
            return []
        lines = _coach.compose_decisions_coach(kb, triggers, width=max(0, width))
        if lines == _coach.compose_decisions_placeholder():
            return []
        return [_clip(line, width=width) for line in lines]
    except Exception:  # noqa: BLE001 -- see the never-raises contract above
        return []


def _safe_int_or_none(value: object) -> int | None:
    """``int`` when ``value`` is a real integer, else ``None``.

    ``bool`` is rejected on purpose: ``True == 1``, and a stray boolean in the
    fighters field must not read as "zero fighters aboard" and fire the
    shipyard card.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _safe_nonneg_int(value: object) -> int | None:
    """Non-negative ``int`` when ``value`` is a real integer, else ``None``."""
    n = _safe_int_or_none(value)
    if n is None or n < 0:
        return None
    return n

GLYPH_CHOSEN = "★"
GLYPH_OTHER = "·"

# Small, deliberately-curated set of imperative-mood verbs that would make a
# line read as a live command rather than read-only reasoning (canon
# hazard, `trainer-cockpit.md` PWO-036 hazards: "coaching copy must not
# look like a live driver"). This module's own authored vocabulary (the
# fixed kind labels imported from focus.py, and the calm-empty HELP
# one-liners) is checked against it in tests/test_cockpit_decisions.py.
# It is NOT a general sanitizer for arbitrary wire-supplied text — an
# operator-hostile `kind` or `rationale` string could still spell an
# imperative word — same type-safety-only boundary goals.py/focus.py
# already draw for their own free-text fields. Every real candidate line
# is glyph-prefixed regardless of this list (see module docstring), which
# is the load-bearing structural guarantee; this denylist is a secondary,
# narrower check on text this module itself chooses to author.
# "explore"/"trade"/"upgrade" are deliberately absent — they collide with
# the canon-authored FOCUS/DECISIONS kind-label vocabulary
# (`focus.py::_KIND_LABELS`) and are not command-style verbs in that
# noun-phrase context.
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


def _autonomy_help_empty_lines(*, width: int) -> list[str]:
    """Calm-empty DECISIONS: E · P/C/S · Mode · L/T one-liners
    (WO-WIRE-AUTONOMY-HELP-LINES; vocab WO-AUTONOMY-HELP-VOCAB).

    Never raises. Width-clips like every other DECISIONS line; ``width <= 0``
    yields one empty string per HELP line (same count as the calm empty).
    """
    try:
        help_lines = autonomy_keys.compose_autonomy_help_lines()
    except Exception:  # noqa: BLE001 -- never-raises; fall back to legacy empty
        return [
            _clip(UNKNOWN_DETAIL, width=width),
            _clip("Exploring…", width=width),
        ]
    return [_clip(line, width=width) for line in help_lines]


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
    every entry was dropped as malformed) all yield **no trace lines** —
    never an invented candidate or a one-line placeholder. What renders in
    their place is the coach callout for whatever ``status`` supports
    (``WO-STATUS-CHAIN-SCALARS-COACH``; up to three authored lines), and
    failing that — no KB, no trigger, or ``width <= 0`` — the calm-empty
    autonomy HELP one-liners (WO-WIRE-AUTONOMY-HELP-LINES), clipped to
    ``width`` (four empty strings when ``width <= 0``).

    A live trace always wins: whenever *any* candidate rendered, the coach is
    not consulted at all.

    Every line is ``len(line) <= width`` (``width <= 0`` empties every line
    to ``""``, mirroring ``goals.py``/``focus.py``'s width-clip convention,
    including both empty-state lines).
    """
    try:
        width = int(width)
    except (TypeError, ValueError):
        width = 0

    status = status if isinstance(status, dict) else {}
    # WO-WIRE-EXPLORE-DECISION-LINES: live explore overlay wins over autopilot
    # trace / coach. Injected by Play onto the same status snapshot the draw
    # path already passes here — never a second string table.
    # Key literal matches explore.EXPLORE_DECISION_LINES_KEY (avoid importing
    # explore into this hot composer path).
    overlay = status.get("explore_decision_lines")
    if isinstance(overlay, list) and overlay:
        overlay_lines = [
            _clip(str(item), width=width)
            for item in overlay
            if isinstance(item, str)
        ]
        if overlay_lines:
            return overlay_lines

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
        # Yield-to-live-trace: the coach only speaks when the app has nothing
        # of its own to report this tick. Any failure inside returns [] and
        # falls through to the same empty state.
        #
        # `width > 0` is not defensiveness, it preserves a documented
        # invariant: at width <= 0 every panel here renders as empty strings,
        # and the coach's card count (up to 3) would otherwise change the
        # *number* of empty lines DECISIONS returns.
        coach = _coach_lines(status, width=width) if width > 0 else []
        if coach:
            return coach
        return _autonomy_help_empty_lines(width=width)

    return lines
