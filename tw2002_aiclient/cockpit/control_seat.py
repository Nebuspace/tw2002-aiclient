"""Pure control-seat composer (PWO-055, ``workorders/ULTRACODE-WO-INVENTORY.md``
Phase 4 "Product spectate mode (read-only) — PREP").

No ``curses`` import here on purpose — mirrors ``tw2002_aiclient/cockpit/
liveness.py`` / ``strip.py``'s pure-composer discipline: this module renders
plain strings only, curses/attribute handling belongs to the draw layer
(``screens.py``).

Scope (load-bearing, do not re-derive): this is deliberately **not** the N5
mode-line-and-teach-controls WO. ``cockpit/layout.py``'s own ``CONTROL_STRIP``
comment reserves that row's mode badge / A/R/T teach keys / run-record-panic
cluster for N5 -- this module renders exactly one thing, a static "SPECTATE"
label, with no color state machine, no App/Human dynamic badge, no teach
affordances. Canon grounding for the one thing it does render:

- ``canon/surfaces/visual-language.md`` "Mode-badge colors" (~98-99):
  "**Spectate** (not a dual member; takes no lock) — **muted / plain**.
  Deliberately uncolored -- 'nothing to see here,' idle/parked." The "muted"
  tone (``cockpit.tones.SEMANTIC_COLORS["muted"] == ("default", False)``) is
  achieved here for free rather than by this module resolving any attr
  itself: the control-strip row this composes into already renders its
  entire line in ``curses.A_NORMAL`` (``screens.py``'s existing
  ``draw_lines(..., curses.A_NORMAL, boxed=False)`` call for that row,
  unchanged by this WO) -- default fg, non-bold, exactly "muted". No new
  attr plumbing is needed or added.
- ``canon/surfaces/spectate-and-attach.md`` "Glyph & status-marker
  vocabulary" (~262): cites the mode-badge chip text verbatim as
  ``SPECTATE`` muted/plain -- this module reuses that exact canon-cited
  word rather than inventing a new label or falling back to a bare ``—``,
  because an "honest indicator" should say what state is true, not merely
  that *some* state exists.

Forward-compat contract with PWO-056 (attach from cockpit, "Human badge"):
the caller's own local state is a plain ``bool`` -- ``PlayShellScreen.
spectating`` -- not a three-value mode string. This is a deliberate choice,
not an oversight: the value answers one narrow question, "does THIS cockpit
instance currently hold the human control lock and forward keystrokes,"
which is strictly binary for a single client (spectating XOR attached). It
is intentionally NOT the same vocabulary as the daemon's own wire-reported
``status["mode"]`` (``"app"``/``"human"``/``"spectate"``,
``session/protocol.py``'s ``status`` verb, sourced from ``session.
control_lock.mode``) -- that field is a DAEMON-GLOBAL fact about who
currently holds the one shared connection (which could be App's own
autopilot loop, or a wholly different attach process, neither of which this
cockpit instance ever IS), whereas ``spectating`` describes only this one
client's own relationship to the seat. Conflating the two would let this
cockpit's own indicator wrongly claim to know something it does not (e.g.
rendering an "App" chip for a fact that isn't even this instance's own).
When PWO-056 lands, it flips ``spectating`` to ``False`` on attach and adds
its own "Human"/"attached" rendering alongside this module -- ``seat_label``
below already yields ``""`` (silently drops out of the row) the moment
``spectating`` is falsy, so PWO-056 needs no rework of this module's
signature, only an additional label of its own.

Hardening family (matches ``liveness.py``/``hud.py``): every public function
is never-raises regardless of input shape -- defense-in-depth here, since
today's only real caller (``screens.py``) always hands a genuine ``bool``,
the same "latent guard" shape ``layout.py``'s own ``LOGS_MIN_H`` clamp and
``tones.py``'s hostile-input branches already document elsewhere in this
codebase.

D5: no ``ai_pilot``/imperative-mood text anywhere -- this module renders a
read-only observation of the seat's own state, never a command.
"""

from __future__ import annotations

# Canon-cited verbatim (see module docstring) -- deliberately a single
# constant, not a Unicode/ASCII twin pair: plain ASCII text has no glyph
# substitution to make, unlike `liveness.py`'s `→`/heartbeat/spinner glyphs.
SPECTATE_LABEL = "SPECTATE"


def _safe_spectating(value: object) -> bool:
    """Best-effort truthiness for ``spectating``. A cleanly-evaluated value
    (including cleanly-falsy ``None``/``False``/``0``) coerces via plain
    ``bool()`` and is returned as-is. An **unevaluable** value (a raising
    ``__bool__``/``__len__``) degrades to ``True`` -- the honest-unknown
    default here is the calmer "nothing to see here" spectate reading, not
    the more consequential "attached" claim; mirrors the shared
    unevaluable-degrades-to-the-non-alarming-tone principle
    ``cockpit.tones``'s ``_safe_connected``/``_safe_fraction`` already
    establish for their own hostile inputs. Never raises."""
    try:
        return bool(value)
    except Exception:
        return True


def seat_label(spectating: object) -> str:
    """The control-seat's own honest label: ``SPECTATE_LABEL`` while
    ``spectating`` is (or safely coerces to) truthy, ``""`` otherwise --
    silently yielding the row rather than inventing an "attached" label
    this module does not own (see the module docstring's PWO-056
    forward-compat note). Never raises regardless of ``spectating``'s
    type."""
    return SPECTATE_LABEL if _safe_spectating(spectating) else ""


def _safe_width(value: object) -> int:
    try:
        width = int(value)
    except Exception:
        return 0
    return width if width > 0 else 0


def compose_control_strip_line(
    *, spectating: object, liveness_text: object, width: object, unicode_ok: bool = True
) -> str:
    """Compose the control-strip row's one content line: the seat label
    (``seat_label(spectating)``) left-anchored, the already-composed
    ``liveness_text`` (``cockpit.liveness.compose_liveness_cluster``'s own
    output) right-anchored -- mirroring ``screens.py``'s pre-existing
    ``liveness_text.rjust(cs_w)`` placement, now shared with the seat label
    rather than the row's left half staying blank.

    The two clusters never collide: ``liveness_text`` (the pre-existing,
    operationally-load-bearing "is it frozen?" signal -- see
    ``liveness.py``) always keeps its full space. The seat label only fills
    whatever blank columns remain to its left, truncated to fit, and drops
    entirely (the row degrades to ``liveness_text.rjust(width)`` alone,
    matching this WO's pre-existing behavior) the instant there is not at
    least one free column of separation. This mirrors the same
    "secondary content yields, primary content survives" precedent
    ``layout.py``'s own ``control_strip`` region drops before ``logs``
    under height pressure.

    ``unicode_ok`` is accepted for API uniformity with every sibling
    composer in this package (``liveness.py``, ``strip.py``) but has no
    effect here -- ``SPECTATE_LABEL`` is plain ASCII with no Unicode twin to
    swap (see the module docstring).

    Returns a string of exactly ``width`` characters when ``width > 0``
    (padding/truncation absorbed the same way ``str.rjust``/slicing
    already behaves), or ``""`` when ``width`` is not a usable positive
    ``int`` (including ``OverflowError``-raising inputs like
    ``float("inf")``). Never raises regardless of any argument's type or
    content -- a non-``str`` ``liveness_text`` degrades to ``""`` rather
    than crashing.
    """
    w = _safe_width(width)
    if w <= 0:
        return ""

    text = liveness_text if isinstance(liveness_text, str) else ""
    text = text[-w:]  # defensive: never wider than the row itself
    right = text.rjust(w)

    label = seat_label(spectating)
    gap = w - len(text)
    if not label or gap <= 1:
        return right

    label = label[: gap - 1]  # leave >=1 blank column of separation
    return (label + right[len(label):])[:w]
