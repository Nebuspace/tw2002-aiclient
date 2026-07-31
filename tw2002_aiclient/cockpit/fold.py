"""Pure responsive-fold composer for the trainer-cockpit right gutter
(WO-P3-039).

No ``curses`` import here on purpose — this module composes plain strings
only, mirroring ``tw2002_aiclient/cockpit/decisions.py`` / ``goals.py`` /
``focus.py``'s discipline.

Canon (`canon/surfaces/trainer-cockpit.md` "Responsive fold" ~154-170):
below ``LEFT_GUTTER_MIN_COLS`` (138 inner cols, `tw2002_aiclient/cockpit/
layout.py`) "the left-gutter GOALS and FOCUS panels collapse into the idle
DECISIONS pane rather than disappearing — the operator keeps the status and
the ranked suggestions, just relocated." Canon leaves the *exact* stacking
shape inside that idle pane unspecified; this module builds the
operator-ruled concrete shape (canon gap, ruled by the operator 2026-07-24):
below the 138 floor, with a DECISIONS region present, the pane always hosts
stacked labeled sections in a fixed order:

1. the pane's own autopilot-trace lines (unlabeled — the pane's own title,
   drawn by the wire/box layer, already names this section; see the N5-
   style boundary note below),
2. a bare uppercase ``GOALS`` label row, then the GOALS digest,
3. a bare uppercase ``FOCUS`` label row, then the FOCUS ranked lines.

Height-clipping happens naturally at draw time (the curses draw layer clips
from the *bottom* of an overflowing box) — bottom-first order is therefore
load-bearing: FOCUS (last) sheds before GOALS (middle) before the trace
(first), matching the canon-cited priority "the operator keeps the status
[GOALS] and the ranked suggestions [FOCUS]" over the trace itself when
height is scarce. This module does not do any clipping of its own; it only
composes the stack in this fixed order and leaves height-driven truncation
to the draw layer, same division of labor ``goals.py``/``focus.py``/
``decisions.py`` already keep from their own curses host.

**"Still renders" rule.** A section whose composer output happens to equal
that composer's own honest-empty marker (e.g. GOALS with no known fields —
still 9 lines of honest ``?``/``—`` rows) is **not** treated as absent — it
still gets its label row and its (empty-but-honest) content, because that
content **is** status the operator is meant to keep reading (canon: "the
operator keeps the status ... just relocated"). Only the one case where
**all three** sections are simultaneously at their own honest-empty marker
collapses the whole pane down to DECISIONS' own calm-empty state
(``decisions.compose_decisions_lines(None, …)`` — today the four autonomy
HELP one-liners from WO-WIRE-AUTONOMY-HELP-LINES / #285; previously the
canon pair ``["—", "Exploring…"]``) — never a fourteen-line stack of
nothing but honest unknowns. "Empty" is
detected by **comparing a section's real output to that same composer
called on an empty/``None`` status at the same width** — never a
hardcoded string guess — so the check stays correct if a sibling composer's
exact empty-marker text or line count ever changes.

**Hardening (house convention).** Each child composer already documents its
own never-raises contract for any JSON-wire-shaped input, but each also
carves out one explicit exception: a *nested* sub-payload that is itself a
hostile ``dict`` subclass (a raising ``.get()``) is **out of that
composer's own contract** and is "contained at the render layer instead" —
see ``decisions.py``'s ``autopilot_trace`` note and ``focus.py``'s
``focus`` note. This module *is* that render layer for the fold: each child
call is wrapped in its own ``try``/``except`` so one hostile per-section
payload drops **only that section** (no label, no lines) — the fold as a
whole, and its sibling sections, still render. If every section happens to
drop (e.g. a hostile top-level ``status`` itself, shared by all three
children, that is a raising ``dict`` subclass — a hazard every sibling
composer documents as equally out-of-contract at the *top* level), the
resulting stack is empty; this module falls back to the pane's own
honest-empty marker rather than ever returning ``[]`` (never render
literally nothing — same "always something honest" spirit as the sibling
composers' own honest-empty states).

**Width.** ``width`` is coerced once, up front, with the same broadened
``except Exception`` ``hud.py`` uses (not the narrower ``(TypeError,
ValueError)`` ``goals.py``/``focus.py``/``decisions.py`` use elsewhere) —
``int(float("inf"))`` raises ``OverflowError``, and ``json.loads`` accepts a
bare ``Infinity`` literal by default, so a hostile wire width can legitimately
be that exact float. The single coerced value is then passed through
verbatim to every child call and to every empty-marker probe, so a section's
real output and its empty marker are always compared at the *same* width.
``width <= 0`` empties every line to ``""`` (mirroring every sibling
composer's own convention) — including this module's own ``GOALS``/``FOCUS``
label rows.

**Note on ``width <= 0`` and the all-empty check.** GOALS always returns
exactly 9 lines regardless of its input (canon: the panel never vanishes
rows), so at ``width <= 0`` GOALS' real output and its empty marker are
*both* nine ``""`` entries and therefore compare equal even when the real
status carried genuine GOALS data — a **provably harmless** quirk: at
``width <= 0`` every line is already invisible ``""`` regardless of which
branch is taken, so no information a human could read is lost, only the
(also-invisible) line *count* differs between the two branches. This is a
direct, deliberate consequence of "detect empty by comparing to the
composer's own empty output" and is pinned by a test rather than left as a
silent surprise.

D5: no ``ai_pilot``/imperative-mood text anywhere — the only text this
module itself authors is the two bare uppercase section labels below; every
other rendered character is a pass-through of a child composer's own
(already-audited) output, glyphs included (``✓``/``·``/``?``/``⊘``/``★`` are
NO-SWAP rows per ``canon/surfaces/visual-language.md`` and are never
remapped or altered here).
"""

from __future__ import annotations

from .decisions import compose_decisions_lines
from .focus import compose_focus_lines
from .goals import compose_goals_lines

# Bare uppercase label rows (mirrors the HUD label-row convention,
# `tw2002_aiclient/cockpit/hud.py`'s `_FIELD_LABELS` — plain text, no
# glyph prefix, no colon). The trace section deliberately has no label of
# its own — the pane's own title ("DECISIONS", drawn by the wire/box
# layer per the WO dispatch) already names it.
GOALS_LABEL = "GOALS"
FOCUS_LABEL = "FOCUS"


def _clip(text: str, *, width: int) -> str:
    if width <= 0:
        return ""
    return text[:width]


def compose_folded_decisions_lines(status: dict | None, *, width: int) -> list[str]:
    """Compose the folded-DECISIONS pane's lines below the 138-col floor.

    Never raises regardless of ``status``'s shape or content — see the
    module docstring's Hardening section for the exact per-section
    containment this adds beyond what each child composer already
    guarantees on its own.

    Reuses ``decisions.compose_decisions_lines`` / ``goals.compose_goals_
    lines`` / ``focus.compose_focus_lines`` verbatim — this module never
    re-implements their field mapping, coercion, or glyph choices; it only
    decides *whether* and *where* each section's already-composed lines
    appear in the combined stack, in the fixed order (1) trace (unlabeled),
    (2) ``GOALS`` label + goals digest, (3) ``FOCUS`` label + focus ranked
    lines. A section whose own output equals that composer's own
    empty-marker output (probed by calling the same composer on ``None`` at
    the same ``width``) still renders in full — see the module docstring's
    "still renders" rule — *unless every section* is simultaneously at its
    own empty marker, in which case the whole pane collapses to
    ``decisions.compose_decisions_lines(None, width=width)`` (DECISIONS'
    calm-empty marker — currently the autonomy HELP one-liners) rather
    than a long stack of nothing but honest unknowns. A section whose own
    composer call raises (an out-of-contract hostile nested payload — see
    Hardening) is dropped from the stack entirely (no label, no lines)
    rather than propagating; if every section drops this way the pane
    still falls back to that same calm-empty marker rather than ever
    returning ``[]``.
    Every line is ``len(line) <= width`` (``width <= 0`` empties every
    line, including the ``GOALS``/``FOCUS`` label rows, to ``""`` —
    mirroring every child composer's own width-clip convention).
    """
    try:
        width = int(width)
    except Exception:
        # Broad except (not just TypeError/ValueError): int(float("inf"))
        # raises OverflowError, and json.loads() accepts a bare Infinity
        # literal by default, so a hostile wire width can legitimately be
        # that exact float -- mirrors hud.py's own now-broadened width
        # coercion (post-Infinity-CRITICAL family standard).
        width = 0

    empty_decisions = compose_decisions_lines(None, width=width)
    empty_goals = compose_goals_lines(None, width=width)
    empty_focus = compose_focus_lines(None, width=width)

    trace_lines: list[str] | None
    try:
        trace_lines = compose_decisions_lines(status, width=width)
    except Exception:
        trace_lines = None

    goals_lines: list[str] | None
    try:
        goals_lines = compose_goals_lines(status, width=width)
    except Exception:
        goals_lines = None

    focus_lines: list[str] | None
    try:
        focus_lines = compose_focus_lines(status, width=width)
    except Exception:
        focus_lines = None

    all_empty = (
        trace_lines is not None
        and trace_lines == empty_decisions
        and goals_lines is not None
        and goals_lines == empty_goals
        and focus_lines is not None
        and focus_lines == empty_focus
    )
    if all_empty:
        return empty_decisions

    lines: list[str] = []
    if trace_lines is not None:
        lines.extend(trace_lines)
    if goals_lines is not None:
        lines.append(_clip(GOALS_LABEL, width=width))
        lines.extend(goals_lines)
    if focus_lines is not None:
        lines.append(_clip(FOCUS_LABEL, width=width))
        lines.extend(focus_lines)

    if not lines:
        # Every section dropped (e.g. a hostile top-level `status` shared
        # by all three children) -- fall back to the honest-empty pane
        # rather than ever rendering nothing at all.
        return empty_decisions

    return lines
