"""Pure control-seat composer (PWO-055, ``workorders/ULTRACODE-WO-INVENTORY.md``
Phase 4 "Product spectate mode (read-only) — PREP").

No ``curses`` import here on purpose — mirrors ``tw2002_aiclient/cockpit/
liveness.py`` / ``strip.py``'s pure-composer discipline: this module renders
plain strings only, curses/attribute handling belongs to the draw layer
(``screens.py``).

Scope (load-bearing, do not re-derive): this is deliberately **not** the N5
mode-line-and-teach-controls WO. ``cockpit/layout.py``'s own ``CONTROL_STRIP``
comment reserves that row's mode badge / A/R/T teach keys / run-record-panic
cluster for N5.

**Scope as it stands today** (the paragraph above described this module at
PWO-055, when it rendered exactly one static "SPECTATE" label with no tone
and no dynamic badge; that has not been true since PWO-056, and the stale
present tense is corrected here rather than left to mislead -- WO-P5-062):
this module renders the SEAT chip as a three-way selection (SPECTATE /
MANUAL / APP) with a tone name per chip, and places one caller-supplied ARM
chip beside it. It still owns no teach affordances, no run/record/panic
cluster, and no color RESOLUTION (tone names only -- curses attrs stay the
draw layer's job). Each addition is recorded in its own dated note below.
Canon grounding for the original static label:

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

**PWO-056 status (this module's half only, as of this WO's lane B dispatch):**
``MANUAL_LABEL``/``attached_label()`` below land the promised "additional
label of its own" -- ``seat_label``'s own signature is untouched, exactly as
forecast. ``compose_control_strip_segments`` gained one new keyword-only
``attached`` parameter (default ``False``, so every existing caller's
behavior is unchanged) rather than a signature rework -- see that function's
own docstring for the priority rule when both are truthy. The DRAW-layer
wiring (``PlayShellScreen`` gaining its own ``attached`` state and passing
it here, alongside the actual Ctrl-A control-switch/keystroke-forward
mechanics -- ``screens.MODE_KEY``, ADR-002) is lane A's ``screens.py``/
``app.py`` territory, not this module's. That wiring has since landed
(PWO-056 attach, PWO-057 detach, Ctrl-A Mode chord), so the badge does
appear on a real screen -- via those modules, not via anything this file
does alone.

**PWO-060 status (App/Human badge, no AI mode -- this dispatch's own
contribution):** ``APP_LABEL``/``app_label()`` add the dual's third and
final chip -- the App holder, canon's ``[ APP ]`` (green/``ok``,
``canon/surfaces/mode-line-and-teach-controls.md`` ~133, ~183-186). App has
no boolean of its own the way Spectate/Human do: it is the terminal
fallback of the selection priority -- "whichever holds the seat when
neither the passive Spectate reading nor the more consequential Human/
attached claim applies" -- because this per-client module still tracks only
the two booleans documented above (``spectating``, ``attached``), never the
daemon-global ``status["mode"]`` field, for the same reason already given:
conflating them would let this cockpit's own indicator claim a fact that
isn't this instance's own. When PWO-060 landed, the only real caller
(``screens.py``) still derived ``attached=not self.spectating``, so the
App branch (reached only when BOTH are falsy) was off-contract/
unreachable in production, and reaching it live was left to the Ctrl-A
App-Human switch (``screens.MODE_KEY``, ADR-002). All of that has since
shipped: ``screens.py`` now passes ``attached=self.attached`` directly
(WO-P5-060), the Ctrl-A switch landed in WO-P5-061-ENTRY, and
WO-ENTRY-APP-CHIP made App-hold the cockpit's ENTRY state
(``spectating=False, attached=False``) -- so the both-falsy input is
no longer hypothetical but the DEFAULT rendering path, hit every time
the cockpit opens. ``compose_control_strip_segments``' label-selection
priority is extended (no signature change) from
``attached_label(attached) or seat_label(spectating)`` to additionally
fall back ``... or app_label()`` -- this is a deliberate, flagged behavior
change for that previously-off-contract both-falsy input (three pre-PWO-060
tests pinned the old "liveness only" reading for it; they're updated in
this dispatch with a comment explaining why, since the old reading was
merely the accidental absence of a third state, not a guaranteed contract).
``compose_control_strip_segments`` (ordered ``(text, tone)`` segments for
the draw layer to per-run-color, ``tone`` one of ``"ok"``/``"warn"``/``None``)
delegates to one private ``_compose_segments`` helper -- the sole public
strip composer (the retired flat-string join helper is gone; join in tests
or the draw path if a string is needed). See ``SendMessage`` to team-lead
(pre-build) for the two contract points this resolution originally
deviated from the literal PWO-060 dispatch text on: (1) selection priority
is attached > spectating > App, matching the shipped strip priority and its
own passing test, not the dispatch's literal "spectating first" wording;
(2) the App branch's reachability required a small additive change to the
composer itself (see above), which the dispatch's literal text did not
call out.

**WO-P5-062 status (autopilot ARM chip -- this dispatch's own
contribution):** the row gains a SECOND chip, placed immediately right of
the seat chip. It answers a different question -- *may the taught
autopilot act* -- from the seat chip's *who holds the keyboard*, and the
two are orthogonal by canon: ``canon/architecture/app-autopilot-model.md``
"Arm-Confirm" describes an armed run that STOPs and hands the keyboard
back on the first unrecognized screen, so armed-but-not-driving is a
routine state the strip must be able to show. Collapsing them into one
chip would make it unrepresentable.

This module does NOT resolve the arm state. It takes a pre-resolved
``(text, tone)`` pair through the new keyword-only ``arm_chip`` parameter
(default ``None``, so every pre-existing caller's row stays byte-identical
-- no signature rework, the same additive shape PWO-056 used for
``attached``), and ``cockpit/arm.py`` owns the extraction from the
daemon's status payload. That division is not incidental: it is what keeps
the commitment this docstring makes above -- that this module never
sources a chip from daemon-global ``status`` -- intact while still letting
the row carry a daemon-global fact. The arm state genuinely IS a
daemon-global fact (unlike ``status["mode"]``, it is not a claim about
which client holds the seat), so reporting it verbatim is honest; reading
it HERE would still be the wrong home for it.

Hardening family (matches ``liveness.py``/``hud.py``): every public function
is never-raises regardless of input shape -- defense-in-depth here, since
today's only real caller (``screens.py``) hands well-formed values on
every parameter: genuine ``bool``s for ``spectating``/``attached``, and a
well-formed ``(text, tone)`` pair or ``None`` for ``arm_chip``. The same
"latent guard" shape ``layout.py``'s own ``LOGS_MIN_H`` clamp and
``tones.py``'s hostile-input branches already document elsewhere in this
codebase.

D5: no ``ai_pilot``/imperative-mood text anywhere -- this module renders a
read-only observation of the seat's own state, never a command.
"""

from __future__ import annotations

# Inter-chip gutter: two blank columns between control-strip segments.
# Reverse-video chips with no gap read as one wider badge.
_ARM_SEPARATOR = "  "
from .teachband import EXPLORE_TOKEN, LOOPS_TOKEN, TEACH_TONE, fit_teach_band

# Canon-cited verbatim (see module docstring) -- deliberately a single
# constant, not a Unicode/ASCII twin pair: plain ASCII text has no glyph
# substitution to make, unlike `liveness.py`'s `→`/heartbeat/spinner glyphs.
SPECTATE_LABEL = "SPECTATE"

# Canon-cited verbatim, cross-checked identical across THREE independent
# sources -- `canon/surfaces/spectate-and-attach.md` "Glyph & status-marker
# vocabulary" (~262), `canon/surfaces/trainer-cockpit.md` "Glyph /
# status-marker vocabulary" (~398), and `canon/surfaces/mode-line-and-
# teach-controls.md` (~188, ~364, its own `_MODE_BADGES` citation) -- the
# Human/attached mode-badge chip text, at tone `warn` (yellow); tone
# resolution is the draw layer's job, same division of labor `SPECTATE_
# LABEL` already keeps from this module. NOT the bracketed `[ HUMAN — YOU
# HAVE CONTROL ]` variant `mode-line-and-teach-controls.md`'s own STOP-
# escalation banner mockup uses (~141) -- that is a DIFFERENT surface (the
# escalation handoff banner, N5's own territory), not this control-strip
# mode-badge chip, which stays unbracketed exactly like `SPECTATE_LABEL`.
#
# Unlike `SPECTATE_LABEL`, this text is NOT plain ASCII -- it embeds the
# em-dash `—`. Still a single constant, not a Unicode/ASCII twin pair,
# because the em-dash is canon's own established NO-SWAP glyph (`canon/
# surfaces/visual-language.md` glyph table: "— (em-dash) | — (no swap)"),
# the same precedent `cockpit/strip.py`'s `MISSING_GAME_LETTER = "—"` and
# `cockpit/goals.py`'s `UNKNOWN_DETAIL = "—"` already rely on elsewhere in
# this package -- `unicode_ok` has no effect on this constant either, for a
# different reason than `SPECTATE_LABEL`'s (ASCII-only vs. deliberately
# un-swapped), but the same zero-effect result.
MANUAL_LABEL = "MANUAL — YOU HAVE CONTROL"

# PWO-060 (WO-P5-060, "App/Human badge, no AI mode") -- the dual's third
# chip. Canon-cited verbatim, uppercase and unbracketed: `canon/surfaces/
# mode-line-and-teach-controls.md`'s own healthy-autopilot mock (~133)
# renders `[ APP ]`, but -- exactly like `MANUAL_LABEL` above vs. that same
# doc's bracketed STOP-banner mock (~141) -- the bracket there is the DRAWN
# CHIP's reverse-video presentation (the draw layer's job), not this raw
# label constant; this module stays unbracketed like every sibling label
# here. Cross-checked against the archive's own unbracketed badge literals
# (`archive/pre-rebirth-2026-07-23/code/twclient/spectate_layout.py:2717-
# 2722` `_MODE_BADGES` -- `"AUTO-LOOP"`, `"MANUAL — YOU HAVE CONTROL"`,
# `"SPECTATE"` are all bare, unbracketed strings), the same precedent
# `MANUAL_LABEL`/`SPECTATE_LABEL` already follow.
#
# "APP" is a NEW single chip, not a reuse of either as-built literal: canon
# (~183-186) is explicit that the App holder is *currently* two separate
# as-built badges -- `AUTO-LOOP` (tone `ok`/green) and the legacy `AI-PILOT`
# (tone `info`/cyan) -- and mandates the reborn trainer unify them into one
# green chip while the cyan `AI-PILOT` badge retires outright. Per that same
# citation, this constant's color is `ok` (green) -- resolved by the draw
# layer, same division of labor `SPECTATE_LABEL`/`MANUAL_LABEL` already
# keep from this module; this module's own job is only the text. NEVER
# `"AI-PILOT"` or `"AUTO-LOOP"` as a label/value here or anywhere in this
# module -- canon (~184-186) retires both; citing the ban in this comment
# is fine, using either string as a value is not (Accept: zero `AI-PILOT`/
# `ai_pilot` strings in product paths).
#
# Plain ASCII, like `SPECTATE_LABEL` -- no Unicode/ASCII twin to swap,
# `unicode_ok` has no effect on this constant either.
APP_LABEL = "APP"

# WO-PLAY-STRIP-TRAINER-CHROME / DECISION
# RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731 point 1: "One chip with Mode
# key -- merge APP+ARM. No separate APP + ARM ON/OFF chips." `^A)` is the
# SAME Mode-chord notation the (now-retired-from-this-band) standing hint
# line used to show as its own leading token, `^A)ode`
# (`teachband.py`'s pre-trainer module docstring) -- moved onto the seat
# chip itself here rather than invented fresh, so the operator's one
# already-learned Ctrl-A affordance still reads the same chord.
#
# These are ADDITIVE, opt-in labels for the trainer strip only --
# `APP_LABEL`/`MANUAL_LABEL`/`SPECTATE_LABEL` above are UNCHANGED and are
# still exactly what every pre-existing (non-trainer) caller of this
# module sees. The one real production caller (`screens.py`) opts in via
# `compose_control_strip_segments(..., trainer_labels=True)`; every other
# caller's row is untouched (see `_trainer_seat_label` below).
#
# `SPECTATE_LABEL` is DELIBERATELY not given a trainer variant: DECISION's
# own text is explicit ("keep honest SPECTATE ... do not lie APP-ARMED")
# -- a spectating instance holds no seat at all, so claiming an armed
# Mode-key reading for it would be exactly the dishonest claim the
# decision forbids.
TRAINER_MODE_CHORD = "^A)"
TRAINER_APP_ARMED_LABEL = TRAINER_MODE_CHORD + "APP-ARMED"
TRAINER_APP_ARMED_LABEL_NARROW = TRAINER_MODE_CHORD + "APP"
TRAINER_MANUAL_HUMAN_LABEL = TRAINER_MODE_CHORD + "MANUAL-HUMAN"
TRAINER_MANUAL_HUMAN_LABEL_NARROW = TRAINER_MODE_CHORD + "MANUAL"


def _trainer_seat_label(label: str, budget: int) -> str:
    """Remap ``label`` (the pre-existing ``APP_LABEL``/``MANUAL_LABEL``/
    ``SPECTATE_LABEL``/``""`` reading `_resolve_label_and_tone` already
    produced) to the trainer's merged Mode-key+seat wording, choosing the
    narrow form when the full one would not fit in ``budget`` columns.

    All-or-nothing on the ``-ARMED``/``-HUMAN`` suffix, matching every
    other chip's own truncation rule on this row (see
    ``_compose_segments``'s docstring): a mid-word clip like
    ``^A)APP-ARM`` reads as a plausible-but-wrong claim, so the suffix is
    either whole (``TRAINER_..._LABEL``) or dropped to the bare
    Mode+seat form (``TRAINER_..._LABEL_NARROW``), which then falls
    through to this function's caller's own ordinary character
    truncation exactly like every pre-trainer label already does.

    ``label`` values this function does not recognize (``SPECTATE_LABEL``,
    ``""``) pass through unchanged -- see this constant block's own
    honesty note on why SPECTATE never gets an ARMED-flavoured spelling.
    Never raises: any budget value that fails a length comparison (should
    be unreachable -- ``budget`` is always this module's own coerced
    ``int`` by the time it reaches here) degrades to the narrow form,
    the shorter and therefore safer of the two under an unknown budget.
    """
    if label == APP_LABEL:
        full, narrow = TRAINER_APP_ARMED_LABEL, TRAINER_APP_ARMED_LABEL_NARROW
    elif label == MANUAL_LABEL:
        full, narrow = TRAINER_MANUAL_HUMAN_LABEL, TRAINER_MANUAL_HUMAN_LABEL_NARROW
    else:
        return label
    try:
        fits_full = len(full) <= budget
    except Exception:
        fits_full = False
    return full if fits_full else narrow


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


def _safe_attached(value: object) -> bool:
    """Best-effort truthiness for ``attached``. Mirrors ``_safe_spectating``'s
    hardening shape but degrades an **unevaluable** input the OPPOSITE
    direction: ``False``, not ``True``. ``_safe_spectating`` picks the calm
    SPECTATE reading as its honest-unknown default specifically because that
    is the LESS consequential of the two claims this module can render
    (``SPECTATE`` says "nothing to see here"; a wrongly-rendered ``MANUAL —
    YOU HAVE CONTROL`` is an operator-facing claim about who currently holds
    the keyboard). An unevaluable ``attached`` must not invent that claim,
    so it degrades to ``False`` (the label silently drops, same as any other
    falsy input) rather than ``True``. Never raises."""
    try:
        return bool(value)
    except Exception:
        return False


def attached_label(attached: object) -> str:
    """The Human/attached seat's own honest label: ``MANUAL_LABEL`` while
    ``attached`` is (or safely coerces to) truthy, ``""`` otherwise -- the
    same silently-yields-the-row shape ``seat_label`` above uses for
    SPECTATE. Never raises regardless of ``attached``'s type."""
    return MANUAL_LABEL if _safe_attached(attached) else ""


def app_label() -> str:
    """The App seat's own honest label: always ``APP_LABEL`` -- unlike
    ``seat_label``/``attached_label`` this takes no argument, because App
    has no boolean of its own for this module to read. It is the terminal
    fallback of ``_compose_segments``'s selection priority below: "whichever
    holds the seat when neither the passive Spectate reading nor the more
    consequential Human/attached claim applies" (see the module docstring's
    PWO-060 note for why this is deliberately not sourced from the
    daemon-global ``status["mode"]`` field). Never empty, never raises."""
    return APP_LABEL


def _safe_width(value: object) -> int:
    """Best-effort coercion of ``width`` to a non-negative ``int`` column
    count. A cleanly ``int()``-coercible value that lands **positive** is
    returned as the coerced int (a float like ``3.7`` truncates toward zero
    via plain ``int()``, same as ordinary Python). Every other shape --
    zero, negative, or an outright unevaluable input -- degrades to ``0``.

    The ``except Exception`` (not just ``TypeError``/``ValueError``) is
    this module's own instance of the family-standard ``OverflowError``
    widening already documented on ``goals.py``'s ``_safe_int``, ``hud.py``'s
    own width coercion, and ``liveness.py``'s (WO-P3-038): ``int(value)``
    calls ``value.__int__()``, and ``int(float("inf"))`` raises
    ``OverflowError`` rather than ``ValueError`` -- a case JSON's default
    ``allow_nan=True`` makes wire-reachable -- so a plain ``(TypeError,
    ValueError)`` catch would leave a real gap here too.

    Unlike ``_safe_spectating``/``_safe_attached`` above, there is no
    direction to pick between two competing claims here: ``0`` is the
    single claim-least reading for a width -- "this chip has no room to
    render anything" -- so a garbage or raising ``value`` never gets to
    claim more room than it can prove. ``_compose_segments`` below treats
    any ``0`` the same way regardless of which path produced it (an
    outright exception, or a cleanly-coerced non-positive int), returning
    ``[]`` rather than guessing a fallback width. Never raises regardless
    of ``value``'s type."""
    try:
        width = int(value)
    except Exception:
        return 0
    return width if width > 0 else 0


def _is_definitively_false(value: object) -> bool:
    """True only for the literal ``bool`` singleton ``False`` -- an ``is``
    identity check, which calls no dunder method (no ``__eq__``, no
    ``__bool__``), so it cannot be fooled or made to raise by a hostile
    object. This is a DIFFERENT, STRICTER reading than ``_safe_spectating``/
    ``_safe_attached``'s own ``bool()``-coercion truthiness -- that
    convention legitimately treats ``None``/``0``/``""``/``[]``/``{}`` as
    cleanly falsy for ``seat_label``/``attached_label``'s OWN purposes and
    stays unchanged (see each helper's own docstring). This stricter check
    exists only to gate the App fallback in ``_resolve_label_and_tone``
    below: App is an ADDITIONAL AFFIRMATIVE CLAIM ("the deterministic
    autopilot holds the keyboard"), not a passive absence like the
    liveness-only row it can replace, so it must never be inferred from a
    coerced, degraded, or merely-falsy-shaped reading of either flag --
    only from the caller's own state machine unambiguously handing a real
    ``False``. The PWO-060 sibling of ``_safe_attached``'s own "an unknown
    must not invent the consequential 'you have control' claim" principle,
    applied one level up. Never raises."""
    return value is False


def _resolve_label_and_tone(spectating: object, attached: object) -> tuple[str, str | None]:
    """Single source of truth for which chip is showing and its tone --
    ``compose_control_strip_segments`` (via ``_compose_segments`` below)
    is the sole public consumer. Priority:
    ``attached_label(attached) or seat_label(spectating)``,
    falling back to ``app_label()`` only when BOTH are empty AND
    ``_is_definitively_false`` holds for both raw inputs -- Human wins over
    Spectate wins over App, and App additionally requires unambiguous proof
    neither of the other two applies.

    The Human-over-Spectate tie-break is the ALREADY-SHIPPED strip
    priority (PWO-056's own shipped behavior, not a PWO-060 invention),
    not the PWO-060 dispatch's literal "spectating first" wording -- kept
    as-is because reordering it would disagree with this module's own
    passing test (``test_attached_true_wins_over_spectating_true``) on
    the off-contract both-truthy case, and because a
    wrongly-suppressed "YOU HAVE CONTROL" claim is a worse failure than a
    wrongly-suppressed passive SPECTATE one (same reasoning ``attached_
    label``'s own docstring already gives).

    The App gate (team-lead-mandated hardening, added after initial PWO-060
    review): it is NOT enough for ``attached_label(attached) or seat_label(
    spectating)`` to evaluate empty -- that can happen via ``_safe_
    spectating``/``_safe_attached``'s own degrade paths (e.g. ``None``, a
    non-bool falsy-shaped value like ``0``/``""``, or a raising/unevaluable
    ``attached`` degrading to "not attached"), none of which are proof that
    App genuinely holds the seat. Only literal ``spectating is False and
    attached is False`` clears the bar -- see ``_is_definitively_false``'s
    own docstring. Any other combination that empties both labels (e.g.
    ``spectating=None, attached=None``, or ``spectating=False, attached=``
    a raising object) falls through to an empty ``label`` instead, which
    ``_compose_segments`` renders as the liveness-only row -- the same
    "unknown state must not invent a claim" outcome ``_safe_attached``
    already established for MANUAL, now also holding for App.

    Tone vocabulary (draw layer's per-run coloring input, PWO-060):
    ``"ok"`` on the App chip, ``"warn"`` on the MANUAL/Human chip, ``None``
    on the SPECTATE chip (canon: Spectate stays muted/plain, never
    restyled) and on any dropped/empty label. Never raises."""
    label = attached_label(attached) or seat_label(spectating)
    if not label and _is_definitively_false(spectating) and _is_definitively_false(attached):
        label = app_label()
    if label == MANUAL_LABEL:
        return label, "warn"
    if label == APP_LABEL:
        return label, "ok"
    return label, None  # SPECTATE_LABEL (muted/plain) or "" (no claim at all)


def _safe_arm_chip(value: object) -> tuple[str, str | None]:
    """Best-effort coercion of the caller-supplied ``arm_chip`` to a
    ``(text, tone)`` pair, degrading any unusable shape to ``("", None)``
    -- which this module's placement rule below treats exactly like "no
    arm chip was supplied at all", so the row simply carries the seat chip
    and the liveness cluster as it did before WO-P5-062.

    The expected value is ``cockpit.arm.compose_arm_chip``'s own return: a
    2-tuple of a ``str`` text and a ``str``-or-``None`` tone. This module
    never inspects the daemon's status payload to produce it -- see the
    module docstring for why the seat composer stays deliberately blind to
    daemon-global state, a discipline WO-P5-062 keeps by taking the chip
    pre-resolved rather than taking the payload.

    Degrading to "no chip" (rather than to some placeholder text) is the
    claim-least reading, matching ``_safe_width``'s own "never let a
    garbage input claim more room than it can prove" convention: a
    malformed pair is not evidence of any arm state, and the arm module's
    own ``ARM ?`` already covers the case where the daemon's payload is
    unusable but the wiring itself is sound. Never raises regardless of
    ``value``'s type."""
    try:
        text, tone = value  # a 2-element unpack; anything else raises
    except Exception:  # noqa: BLE001 -- an unusable chip must not crash the row
        return "", None
    if not isinstance(text, str) or not text:
        return "", None
    if tone is not None and not isinstance(tone, str):
        return text, None
    return text, tone


def _safe_teach_band(value: object) -> str:
    """Coerce the optional teach band to a plain string.

    Anything that is not a non-empty ``str`` renders as ABSENT rather than
    as a guess -- the same "honest absence of information beats wrong
    information" rule ``_safe_arm_chip`` applies to the chips, and the
    reason this function never falls back to ``teachband.compose_teach_
    band()`` on bad input: a caller that failed to supply the band should
    show no band, not a band this layer invented on its behalf.
    """
    return value if isinstance(value, str) and value else ""


def _infer_teach_toggles(band: str) -> tuple[object, object, object]:
    """Recover P/C/S ON|OFF from a caller-composed calm band string."""
    sep = "·"

    def _on(long_label: str, short_label: str) -> bool:
        for label in (long_label, short_label):
            if f"{label}{sep}OFF" in band:
                return False
            if f"{label}{sep}ON" in band:
                return True
        return True

    return (
        _on("P)ort Trade", "P)ort"),
        _on("C)argo Hold Upgrade", "C)argo"),
        _on("S)hip Upgrade", "S)hip"),
    )


def _fit_teach_into_budget(band: str, budget: int) -> str:
    """Place ``band`` under ``budget``, with progressive calm-band shrink.

    Non-calm hint slots (explore run line, ``[ ANALYZING ]``) stay
    all-or-nothing. Calm repertoire (``E)xplore`` + ``L)ist Loops``) uses
    ``fit_teach_band`` (WO-STRIP-HOTFIX-FIT-TRADE-LOGS).
    """
    if budget <= 0 or not band:
        return ""
    if len(band) <= budget:
        return band
    if EXPLORE_TOKEN not in band or LOOPS_TOKEN not in band:
        return ""
    port_on, cargo_on, ship_on = _infer_teach_toggles(band)
    try:
        return fit_teach_band(
            budget,
            port_trade_on=port_on,
            cargo_upgrade_on=cargo_on,
            ship_upgrade_on=ship_on,
        )
    except Exception:
        return ""


def _safe_status_offer(value: object) -> str:
    """Coerce the optional mid-strip status/offer line to a plain string."""
    return value if isinstance(value, str) and value else ""


def _compose_segments(
    *,
    spectating: object,
    attached: object,
    liveness_text: object,
    width: object,
    arm_chip: object = None,
    conn_chip: object = None,
    coverage_meter: object = None,
    status_offer: object = None,
    teach_band: object = None,
    trainer_labels: object = False,
) -> list[tuple[str, str | None]]:
    """Shared core: builds the ordered ``(text, tone)`` segments
    ``compose_control_strip_segments`` returns as-is (callers that need a
    flat string join the segment texts).

    Layout, left to right: the seat chip, then (WO-P5-062) the ARM chip
    separated by ``cockpit.arm.ARM_GAP``, then (WO-PLAY-OFFER-VISIBLE-ON-LIVE)
    an optional mid-strip ``status_offer`` (``PlayShellScreen.status_line`` on
    live sessions), then the standing teach/hint band, then the right-justified
    liveness cluster. Either chip may be absent; when both are, the row is the bare
    ``(liveness_only, None)`` segment it has always been. That last case is
    a real, reachable outcome rather than a defensive-only branch: a
    degraded/unknown/non-``bool`` reading of ``spectating``/``attached``
    (e.g. both ``None``) empties both ``attached_label``/``seat_label`` yet
    fails the stricter ``_is_definitively_false`` App-eligibility check
    (see ``_resolve_label_and_tone``), so the row correctly degrades to
    liveness-only rather than inventing any claim.

    PWO-060's XOR structural guarantee is unchanged by the ARM chip: there
    is still never more than one SEAT label segment, so App and MANUAL can
    never co-render regardless of input. The ARM chip is a SECOND
    tone-carrying segment by design, not a violation of that guarantee --
    it answers a different question (may the taught autopilot act) than the
    seat chip (who holds the keyboard), and canon needs both representable
    at once, including the armed-but-not-driving combination the run-loop
    produces every time it STOPs and hands the keyboard back
    (``canon/architecture/app-autopilot-model.md`` "Arm-Confirm").

    Priority under width pressure, in order: the liveness cluster keeps its
    full space (the pre-existing, operationally load-bearing "is it
    frozen?" signal), then the seat chip -- canon: "the mode chip is cell
    #1, hard-left -- *who holds the keyboard* is the highest-priority fact
    on the strip" (``mode-line-and-teach-controls.md`` ~223) -- then the
    ARM chip. The seat chip truncates to fit as it always has; the ARM
    chip is **all-or-nothing** and never truncates. That asymmetry is
    deliberate: a clipped seat label is still unambiguous (``MANUAL — YOU
    HAVE C``), whereas a clipped ``ARM ON`` could read as ``ARM O`` and be
    resolved by the reader as the opposite state. Dropping the chip is an
    honest absence of information; truncating it would be wrong
    information, which on this particular claim is the more expensive
    failure.

    Never raises; returns ``[]`` when ``width`` is not a usable positive
    ``int`` (``"".join([]) == ""``, so a flat join stays empty for the
    same case)."""
    w = _safe_width(width)
    if w <= 0:
        return []

    text = liveness_text if isinstance(liveness_text, str) else ""
    text = text[-w:]  # defensive: never wider than the row itself
    right = text.rjust(w)

    # >=1 blank column of separation from the liveness cluster, so the two
    # halves of the row can never abut.
    budget = w - len(text) - 1
    if budget <= 0:
        return [(right, None)]

    label, tone = _resolve_label_and_tone(spectating, attached)
    # WO-PLAY-STRIP-TRAINER-CHROME: opt-in only (default False leaves
    # every pre-existing caller's row byte-identical) -- see
    # `_trainer_seat_label`'s own docstring for the remap this performs.
    try:
        use_trainer_labels = bool(trainer_labels)
    except Exception:
        use_trainer_labels = False
    if use_trainer_labels:
        label = _trainer_seat_label(label, budget)
    arm_text, arm_tone = _safe_arm_chip(arm_chip)

    left: list[tuple[str, str | None]] = []
    used = 0
    if label:
        label = label[:budget]
        left.append((label, tone))
        used = len(label)
    if arm_text:
        separator = _ARM_SEPARATOR if used else ""
        if used + len(separator) + len(arm_text) <= budget:
            if separator:
                left.append((separator, None))
            left.append((arm_text, arm_tone))
            used += len(separator) + len(arm_text)
    # WO-PLAY-CONN-TOGGLE: CONN chip — placed right of the ARM chip, same
    # all-or-nothing-never-truncate rule: a clipped "CONN" could read as
    # "CON" (unrelated), worse than absent. Reuses `_safe_arm_chip` for
    # input coercion (same `(str, str|None)` tuple contract).
    conn_text, conn_tone = _safe_arm_chip(conn_chip)
    if conn_text:
        separator = _ARM_SEPARATOR if used else ""
        if used + len(separator) + len(conn_text) <= budget:
            if separator:
                left.append((separator, None))
            left.append((conn_text, conn_tone))
            used += len(separator) + len(conn_text)
    # WO-P5-072: the coverage meter — App-vs-Human live share. Placed right
    # of CONN, in the chip run rather than out by the teach band, because it
    # is *data* like ARM/CONN and not affordance chrome; it carries tone
    # `None` (plain) for the same reason liveness does.
    #
    # All-or-nothing like every chip beside it, but for a sharper reason:
    # `covermeter` already refuses to truncate itself (a clipped `COV 75%`
    # reads as `COV 7` — seven percent — a readable wrong number rather than
    # an unreadable token). The width test here is therefore belt-and-braces
    # against the composer's own guard, not the only thing standing between
    # the operator and a misreported share.
    #
    # Deliberately NOT given priority over liveness: `budget` already
    # reserves the liveness cluster's full space above, so the meter can
    # only ever occupy columns liveness does not want. Canon's N5 hazard
    # ("do not steal the liveness slot under pressure") is satisfied
    # structurally here, not by a rule someone has to remember.
    meter_text, meter_tone = _safe_arm_chip(coverage_meter)
    if meter_text:
        separator = _ARM_SEPARATOR if used else ""
        if used + len(separator) + len(meter_text) <= budget:
            if separator:
                left.append((separator, None))
            left.append((meter_text, meter_tone))
            used += len(separator) + len(meter_text)

    band = _safe_teach_band(teach_band)
    gap_total = w - len(text) - used
    status_text = _safe_status_offer(status_offer)
    # Mid-strip status/offer owns the center; the teach band yields to it
    # (canon: affordance chrome, not data). Reserve the band beside a
    # status line ONLY when a fitted band + FULL status still fit —
    # otherwise leave band_reserved=0 so a long calm strip cannot clip
    # "press E" off a live explore offer. Progressive fit
    # (WO-STRIP-HOTFIX-FIT-TRADE-LOGS) may reserve a SHORTER band than the
    # caller-composed full string.
    band_reserved = 0
    if band and gap_total >= 2:
        provisional = _fit_teach_into_budget(band, gap_total - 2)
        if provisional:
            if not status_text:
                band_reserved = len(provisional) + 1
            else:
                sep_len = len(_ARM_SEPARATOR if used else "")
                if gap_total >= sep_len + len(status_text) + 1 + len(provisional) + 1:
                    band_reserved = len(provisional) + 1

    if status_text and gap_total > band_reserved:
        sep = _ARM_SEPARATOR if used else ""
        room = gap_total - band_reserved - len(sep) - 1
        if room > 0:
            if sep:
                left.append((sep, None))
                used += len(sep)
            left.append((status_text[:room], None))
            used += min(len(status_text), room)

    # WO-P5-066: the standing teach band. Canon places the hint band
    # "right-aligned ... it is affordance chrome, not data, so it wears the
    # chrome color and yields the strip's center to the TX channel"
    # (`mode-line-and-teach-controls.md §"Spacing, alignment & hierarchy — the mode-line reading order"`).
    #
    # Canon's own diagram (`:220`) shows the band hugging the row's right
    # edge, because that diagram has no liveness cluster in it. On tip the
    # right edge is already held by liveness -- the operationally
    # load-bearing "is it frozen?" signal this function's docstring pins as
    # keeping its full space ahead of every chip. So the band right-aligns
    # against LIVENESS'S left edge rather than the row's: canon's reading
    # order (chips left, band right, band yields the center) is preserved
    # exactly, and the one element canon's diagram does not model keeps the
    # priority the product already proved it needs. Recorded here rather
    # than silently resolved -- see the WO's Design-decision section.
    if band:
        # Blank columns standing between the chips' end and the liveness
        # cluster's first column.
        gap_total = w - len(text) - used
        # `+ 2` buys one blank column on EACH side: the band may never abut
        # the chips on its left nor the liveness cluster on its right.
        # Under pressure, progressive-fit the calm repertoire into the
        # remaining budget instead of all-or-nothing-dropping the whole
        # band (WO-STRIP-HOTFIX-FIT-TRADE-LOGS). Non-calm hint strings
        # (explore / analyze) still drop whole when they cannot fit.
        place = _fit_teach_into_budget(band, gap_total - 2)
        if place and gap_total >= len(place) + 2:
            lead = gap_total - len(place) - 1
            left.append((" " * lead, None))
            left.append((place, TEACH_TONE))
            used += lead + len(place)

    if not left:
        return [(right, None)]
    return left + [(right[used:], None)]


def compose_control_strip_segments(
    *,
    spectating: object = True,
    attached: object = False,
    liveness_text: object = "",
    width: object = 0,
    unicode_ok: object = True,
    arm_chip: object = None,
    conn_chip: object = None,
    coverage_meter: object = None,
    status_offer: object = None,
    teach_band: object = None,
    trainer_labels: object = False,
) -> list[tuple[str, str | None]]:
    """PWO-060: the draw layer's per-run-color view of the control-strip
    row -- ordered ``(text, tone)`` segments from the sole public strip
    composer. ``tone`` is one of ``"ok"`` (App chip), ``"warn"``
    (MANUAL/Human chip, and the ARM chip whenever the autopilot is not
    PROVEN disarmed -- WO-P5-062), or ``None`` (SPECTATE chip, a
    proven-disarmed ARM chip, or any non-label segment such as the
    liveness cluster and the inter-chip separator) -- see
    ``_resolve_label_and_tone``'s own docstring for the seat tone
    vocabulary and the App-never-co-renders-with-MANUAL structural
    guarantee, and ``cockpit.arm.arm_tone`` for the ARM chip's own.

    ``arm_chip`` (WO-P5-062) is the optional ``(text, tone)`` pair
    ``cockpit.arm.compose_arm_chip`` produces. It may legitimately
    co-render with ANY seat chip, including a tone-carrying one: the two
    answer different questions, so a result carrying two non-``None``
    tones is correct here and is NOT a widening of the seat chips' own XOR
    (see ``_compose_segments``, which still emits at most one seat label).

    ``unicode_ok`` is accepted for API uniformity with every sibling
    composer in this package but has no effect here -- seat labels are
    plain ASCII / canon NO-SWAP glyphs with no Unicode twin to swap.

    ``trainer_labels`` (WO-PLAY-STRIP-TRAINER-CHROME, default ``False``):
    when truthy, remaps the seat chip to the trainer's merged Mode-key
    reading (``TRAINER_APP_ARMED_LABEL``/``TRAINER_MANUAL_HUMAN_LABEL``,
    narrowing under width pressure) instead of the bare
    ``APP_LABEL``/``MANUAL_LABEL`` -- see `_trainer_seat_label`. Every
    pre-existing caller leaves this at its default and sees no change.

    Returns ``[]`` when ``width`` is not a usable positive ``int``
    (``"".join`` over ``[]`` is ``""``). Never raises regardless of any
    argument's type or content."""
    return _compose_segments(
        spectating=spectating, attached=attached, liveness_text=liveness_text,
        width=width, arm_chip=arm_chip, conn_chip=conn_chip,
        coverage_meter=coverage_meter,
        status_offer=status_offer, teach_band=teach_band,
        trainer_labels=trainer_labels,
    )
