"""Pure STOP-banner composer for the trainer-cockpit escalation handoff
(WO-P5-064, ``workorders/WO-P5-060-072-mode-teach-PREP.md`` §PWO-064).

No ``curses`` import here on purpose -- mirrors ``tw2002_aiclient/cockpit/
logsband.py`` / ``goals.py`` / ``control_seat.py``'s pure-composer
discipline: this module composes plain strings only; the warn-bold attr
those strings are painted with belongs to ``screens.py``'s draw call.

When the taught autopilot meets a screen it cannot match it **stops** and
hands the keyboard back, "raising a clear escalation signal"
(`canon/architecture/control-and-escalation.md` "Escalate-on-Unknown").
This module composes the human-facing half of that signal: the banner
that says *why* the run halted, who holds the keyboard now, and which
three teach moves are available right there at the halt.

# The reason is a TYPED CODE, never free text

The load-bearing contract (`control-and-escalation.md` "Escalation
reason-code catalog"): "Every App->Human STOP carries a typed reason
code, not a free-text string ... the human-facing STOP banner renders the
code's short label ... Reason is a typed value throughout -- the display
label is a lookup, never the wire form."

``INTERVENTION_REASON_LABELS`` below is that catalog, transcribed
verbatim from the canon table. ``intervention_reason_label()`` is canon's
own **open-by-construction** resolver: an unrecognized code passes
through **as its own text**, and an empty/``None`` code renders ``"?"``
(`control-and-escalation.md`: "so a new STOP cause can ship a new code
before a label exists without breaking any surface -- it simply renders
as the raw code until a label is added"; `mode-line-and-teach-controls.md`:
"the banner never invents a message and never blanks").

That pass-through is the honesty rule, stated positively: this module
**never** guesses an explanation for a code it does not know. Showing the
raw `wormhole_collapse` is honest; inventing "autopilot halted" for it
would be a fabricated claim about why the operator's run stopped, and a
fabricated reason is worse than no reason at all.

# Catalog home (deliberate, flagged)

Canon cites the catalog's as-built home as ``twclient/
intervention_labels.py`` -- "the single source of truth shared by the
trainer/product adapters and the read-only spectate layout". There is no
``twclient`` package in the reborn tree (ADR-001 consolidates everything
under ``tw2002_aiclient``), and the reborn tree has exactly ONE consumer
today: this banner. So the catalog lives here, under its canon-cited
symbol names (``INTERVENTION_REASON_LABELS`` /
``intervention_reason_label``), rather than in a one-consumer module of
its own. **Extraction trigger:** the moment a SECOND surface needs these
codes (the spectate-layout port, or the PWO-065 handoff), lift both
symbols into their own module unchanged -- a pure move, no rename.

# Wire contract (this composer DEFINES it, as ``logsband.py`` did)

::

    status["intervention"] = {
        "needs_attention": <bool>,          # the banner appears only when true
        "reasons": [{"code": <str>}, ...],  # bare <str> entries also accepted
    }
    status["mode"] = "app" | "human" | "spectate"   # daemon-global holder

The ``reasons`` shape (dict-with-``code`` OR bare string) is the archive's
own accepted pair (``archive/pre-rebirth-2026-07-23/code/twclient/
spectate_layout.py::compose_intervention_strip``), kept so the eventual
wire bridge needs zero composer rework.

**Reachability, honestly:** today's daemon never populates
``status["intervention"]`` -- ``session/protocol.py``'s ``status`` verb
carries an explicit "WO-P2-020 Wave-3 CUT vs archive: play/credits*/
turns*/fighters*/**intervention**/world_id still deferred" note. So on a
real daemon this banner does not appear yet, the same way
``goals.py``'s rows render honestly unknown against fields that are not
wired back yet. That is the honest state, not a defect: the banner
renders a halt only when a halt is genuinely reported.

# The three bands

`mode-line-and-teach-controls.md` "The STOP / escalation banner styling"
enumerates the reborn banner as three bands, in this order:

1. ``! STOP — <label(s)>`` -- the reason line, "led by a bare ``!``".
2. ``[ HUMAN — YOU HAVE CONTROL ]`` -- the keyboard-handoff marker.
3. ``teach:  A)nalyze  R)ecord  T)assign`` -- the three teach moves.

(That doc's illustrative mock also splits the reason across a ``! STOP —
<label>`` line and a second ``reason: <label>`` line. This module renders
the reason ONCE, on band 1: the same code twice is duplication, not
information, and the normative three-band enumeration above is what this
follows.)

**Band 2 is a claim, so it is gated on evidence.** The marker asserts
that the keyboard has actually passed to the human. This module therefore
renders it only when the shared ``status`` snapshot itself reports
``mode == "human"`` -- the daemon-global "who holds the one connection"
fact, straight off ``session/protocol.py``'s ``status`` verb (sourced
from ``session.control_lock.mode``). Any other reported holder renders as
that holder (``[ APP ]``/``[ SPECTATE ]``), and a missing/unusable
``mode`` renders ``[ ? ]`` -- canon's own degrade rule for an unknown
mode ("an unrecognized/empty mode renders ``mode.upper()`` or ``"?"``",
`mode-line-and-teach-controls.md` "Panel states"). A banner that always
claimed "YOU HAVE CONTROL" would be stating a handoff that PWO-065, not
this WO, actually performs.

**Deliberate asymmetry with the control-strip chip, documented at the
point of divergence:** ``control_seat.py`` reads this cockpit instance's
own ``spectating``/``attached`` booleans and *deliberately never* reads
``status["mode"]`` -- its chip answers "does THIS client hold the seat".
This band answers a different question -- "did the ESCALATION hand the
keyboard to a human" -- which is a daemon-global fact about the one
shared connection, so the daemon-global field is the correct source here
and the per-client booleans would be the wrong one. The two can honestly
disagree (chip ``APP`` while this band reads ``[ HUMAN — YOU HAVE
CONTROL ]``) whenever some other process holds the human lock; neither is
lying.

**Band 3 is labels only.** The A/R/T wires belong to PWO-066+; nothing
here binds, arms, or fires anything -- the line names the three moves the
human may make and stops there.

# Fit

``height`` folds from the BOTTOM: band 3 drops first, then band 2, so the
``!`` reason line is the last thing standing. This matches both the
archive's as-built single-row strip (``! <label>; <label>``) and canon's
"the escalation is the last thing to fold, never the first". ``height <=
0`` returns ``[]``; ``width <= 0`` returns the same line COUNT with each
line emptied to ``""`` (the convention ``goals.py``/``logsband.py``
already establish, so a caller can rely on the count reflecting real
content presence regardless of width).

Hardening family (matches ``goals.py``/``logsband.py``/``control_seat.py``):
never raises regardless of ``status``'s shape or content, or of
``width``/``height``'s type. A hostile individual reason entry is
contained to its own slot (rendered ``"?"``) rather than voiding the
sibling reasons in the same halt. Control-character neutralization and
cell-accurate clipping are NOT done here -- ``cockpit.draw``'s
``_sanitize_controls``/``_clip_cells`` choke point is the one place that
hazard is handled, for every panel including this one (same trust
boundary ``logsband.py`` documents for transcript text).

D5: no ``ai_pilot``/imperative-mood text anywhere -- this module renders a
read-only observation of a halt the daemon reported, never a command, and
the AI has no seat in it at all (an escalation is App->Human; the AI is
never consulted in the moment).
"""

from __future__ import annotations

from tw2002_aiclient.session.control_lock import MODE_HUMAN

# Canon `canon/architecture/control-and-escalation.md` "Escalation
# reason-code catalog" -- the enumerated table, transcribed verbatim
# (code -> human label). This IS the catalog; a STOP reason that is not a
# key here is not a known reason, and renders as its own raw text rather
# than borrowing any label below.
INTERVENTION_REASON_LABELS = {
    "autopilot_halted": "autopilot halted",
    "autopilot_no_candidates": "autopilot no candidates",
    "explore_exhausted": "explore exhausted",
    "autopilot_max_ticks_exhausted": "autopilot max ticks exhausted",
    "autopilot_game_select": "autopilot game select",
    "human_attach_blocks_trainer": "human attach blocks trainer",
    "credits_unknown": "credits unknown",
    "credits_stale": "credits stale",
    "credits_unreadable": "credits unreadable",
    "fighters_unknown": "fighters unknown",
    "fighters_stale": "fighters stale",
    # LoopPlayer HALT_REASONS that previously rendered RAW (Max ruling 1A /
    # WO-HALT-BANNER-LABEL-VOCAB 2026-07-26). Unmapped codes still pass through
    # as their own text — never a loud "unlabelled" wrapper.
    "settle_failed": "settle failed",
    "screen_unreadable": "screen unreadable",
    "operator_stop": "operator stop",
    "never_auto_action": "never auto action",
    "unrecognized_screen": "unrecognized screen",
    "start_anchor_missing": "start anchor missing",
    "start_anchor_mismatch": "start anchor mismatch",
    "current_sector_absent": "current sector absent",
    "current_sector_unreadable": "current sector unreadable",
    "confirm_failed": "confirm failed",
    "post_class": "post class",
    "floor_reached": "floor reached",
    # WO-AUTOLOOP-TURN-BUDGET remaining-turns floor (parallel to credits_*).
    "turn_budget_exhausted": "turn budget exhausted",
    "turns_unknown": "turns unknown",
    "turns_stale": "turns stale",
    "turns_unreadable": "turns unreadable",
    "fighters_zero": "fighters zero",
    # WO-STOPBANNER-ROUTE-HAZARD-LABEL / #327–#329: formations Dual-consumer STOP.
    "route_hazard": "route hazard",
}

# Canon's own empty/unknown marker -- "an empty code renders ``"?"``"
# (`mode-line-and-teach-controls.md` glyph vocabulary: "`?` -- an
# empty/unknown reason code in the banner, or an unknown mode in the
# chip"). Same glyph `goals.py`'s GLYPH_UNKNOWN uses, and a NO-SWAP
# ASCII character either way.
UNKNOWN_REASON = "?"

# Band 1. Canon: the strip is "led by a bare `!`" (the one-glyph
# "attention" mark) and the band is "the `! STOP` reason line". The
# em-dash is canon's own NO-SWAP glyph (`visual-language.md` glyph table),
# the same precedent `control_seat.MANUAL_LABEL` and `goals.UNKNOWN_DETAIL`
# already rely on -- so this module, like `goals.py`, takes no
# `unicode_ok` parameter: it has no glyph with an ASCII twin to swap.
STOP_PREFIX = "! STOP — "

# Multiple simultaneous reasons: the archive's own separator
# (`spectate_layout.compose_intervention_strip` emits `! <label>; <label>`).
REASON_SEPARATOR = "; "

# Band 2. Canon-cited verbatim (`mode-line-and-teach-controls.md`'s
# STOP-banner mock, and its normative three-band enumeration). This is
# DELIBERATELY the bracketed `HUMAN` variant, not `control_seat.
# MANUAL_LABEL` ("MANUAL — YOU HAVE CONTROL") -- that module's own
# constant comment already calls out the split: the unbracketed MANUAL
# text is the control-strip mode-badge chip, this bracketed HUMAN text is
# the escalation banner's handoff marker, a different surface. Two
# constants on purpose, each canon-cited from its own surface.
HANDOFF_MARKER = "[ HUMAN — YOU HAVE CONTROL ]"

# Band 2's honest fallback when the reported holder is unknown -- canon's
# "Panel states / Empty" degrade rule for a mode the surface cannot read.
UNKNOWN_HOLDER_MARKER = "[ ? ]"

# WO-P5-065: the attach affordance, shown on band 2 whenever the human does
# NOT already hold the keyboard.
#
# Canon's band-2 sentence ("Keyboard -> Human ... control has passed to the
# human") describes an outcome this surface cannot produce on its own, and
# saying it anyway would be the one thing the WO forbids -- a "handed to
# Human" claim the lock cannot back. The product reality:
#
#   control_lock.py:159   _SETTABLE_MODES = frozenset({MODE_APP, MODE_SPECTATE})
#   control_lock.py:26    "...cannot enter MODE_HUMAN (attach-scoped only)"
#
# `MODE_HUMAN` is not settable. It is ACQUIRED by a live interactive attach
# holding the socket, and `daemon.py` guards against releasing someone's
# hold out from under them. So a STOP cannot hand the keyboard over; it can
# only say who has it and how to take it.
#
# Hence ruling (b) (hub, 2026-07-27): PROMPT-to-attach. The human initiates.
# Auto-acquiring MODE_HUMAN on a halt -- ruling (c) -- was rejected: it would
# take the daemon's exclusive human lock without the operator pressing
# anything, possibly while nobody is at the keyboard, against both the
# single-connection invariant and the north-star's human-sovereign posture.
#
# The keystroke named here is the EXISTING attach chord (`screens.MODE_KEY`,
# Ctrl-A / ADR-002), not a new binding -- there is one way to attach and this
# band points at it rather than inventing a second. What makes this distinct
# from the voluntary Mode toggle is the CONTEXT, not the mechanism: the calm
# hint band offers `^A)ode` as one option among several, while this line
# appears only at a halt and only when the human does not hold the keyboard.
ATTACH_AFFORDANCE = "press ^A to take the keyboard"

# Band 3. Canon-cited verbatim: the teach triad "move off the band and
# onto the banner's dedicated `teach:` line" as `A)nalyze  R)ecord
# T)assign` (note `T)assign` on the banner, vs the hint band's own
# `T)rigger`). Labels only -- PWO-066+ owns the wires.
TEACH_LINE = "teach:  A)nalyze  R)ecord  T)assign"

# The full banner's height, in rows -- one per band. `cockpit.layout`
# imports this rather than spelling `3` a second time.
BANNER_H = 3


def _coerce_width_height(value: object) -> int:
    """Same broadened-except family every sibling composer's own width
    coercion uses: ``int(float("inf"))`` raises ``OverflowError``, not
    ``TypeError``/``ValueError``, and ``json.loads()`` accepts a bare
    ``Infinity`` literal by default, so a hostile wire value can
    legitimately be that exact float."""
    try:
        return int(value)
    except Exception:
        return 0


#: Separator in the qualified reason shape `<code>:<detail>`
#: (WO-PLAYER-HALT-NEVER-AUTO-CLASS / #213's explore twin).
#:
#: Declared locally rather than imported from `loops.player`: this module's
#: contract is "plain strings and a tone NAME only", and a cockpit renderer
#: reaching into the loop engine for a constant is the coupling that
#: contract exists to prevent. The cost of the copy is that the two could
#: drift, so `tests/test_cockpit_stopbanner.py` pins them equal -- a copy
#: with a pin, not a copy with a hope.
_QUALIFIER_SEP = ":"


def intervention_reason_label(code: object) -> str:
    """Resolve one typed reason ``code`` to its short human label.

    Canon's open-by-construction contract, unchanged: a code in the
    catalog renders its label; an **unrecognized** code passes through as
    its own text (never a guessed label from a neighbouring entry); an
    empty or ``None`` code renders ``UNKNOWN_REASON`` (``"?"``).

    Lookup is exact and case-sensitive -- ``"AUTOPILOT_HALTED"`` is a
    different code from ``"autopilot_halted"``, and resolving one to the
    other's label would be inventing a mapping canon does not have. No
    stripping either: whitespace is part of whatever the wire actually
    sent, and silently normalizing it would let this function claim a
    match it does not have.

    Never raises: a non-``str`` code is coerced with ``str()``, and a
    hostile object whose ``__str__``/``__repr__`` itself raises degrades
    to ``UNKNOWN_REASON`` -- the same per-item containment
    ``goals.py``'s ``_safe_sector_token`` uses."""
    if code is None:
        return UNKNOWN_REASON
    if isinstance(code, str):
        text = code
    else:
        try:
            text = str(code)
        except Exception:
            return UNKNOWN_REASON
    if not text:
        return UNKNOWN_REASON
    if text in INTERVENTION_REASON_LABELS:
        return INTERVENTION_REASON_LABELS[text]
    # WO-PLAYER-HALT-NEVER-AUTO-CLASS: the qualified shape `<code>:<detail>`
    # (`never_auto_action:money_prompt`). Resolved by its CODE, with the
    # detail carried through verbatim -- no catalog row per class, which
    # would make this table grow every time `classify` gains one.
    #
    # This is NOT the "silently normalizing" the docstring above forbids,
    # and the distinction is worth stating because they look alike. That
    # rule is about mangling a code until it matches something it is not --
    # stripping whitespace, case-folding. This parses a shape the product
    # deliberately emits, and only claims a match when the part before the
    # separator is a code already in the catalog. A qualified code whose
    # base is unknown still falls through to raw passthrough below, so
    # open-by-construction is unchanged and no label is ever guessed from a
    # neighbouring entry.
    base, sep, detail = text.partition(_QUALIFIER_SEP)
    if sep and detail and base in INTERVENTION_REASON_LABELS:
        return f"{INTERVENTION_REASON_LABELS[base]}{_QUALIFIER_SEP} {detail}"
    return text


def needs_attention(status: dict | None) -> bool:
    """``True`` only when the daemon genuinely reports a raised
    escalation -- ``status["intervention"]["needs_attention"]`` truthy.

    Everything else is "no halt to show": a non-dict ``status``
    (including ``None`` -- no provider wired, or a provider that returned
    nothing usable), a missing/non-dict ``intervention`` block, an absent
    or falsy ``needs_attention``, and an **unevaluable** one (a raising
    ``__bool__``) all return ``False``. The unknown-degrades-to-calm
    direction is deliberate and matches ``control_seat._safe_attached``'s
    own reasoning: raising a STOP banner is the consequential claim here
    ("your taught run has halted"), so it is never inferred from a
    reading this module could not actually make.

    Never raises regardless of ``status``'s shape or content."""
    if not isinstance(status, dict):
        return False
    block = status.get("intervention")
    if not isinstance(block, dict):
        return False
    try:
        return bool(block.get("needs_attention"))
    except Exception:
        return False


def _reason_labels(status: dict) -> list[str]:
    """Every reported reason, resolved to its label, in wire order.

    Accepts both entry shapes the archive's own strip accepted: a dict
    carrying a ``"code"`` key, or a bare code value. A ``reasons`` field
    that is not a list/tuple degrades to no reasons at all rather than
    being iterated character-by-character (``goals._safe_list``'s
    precedent) -- a stray string in that slot is a malformed payload, not
    a single reason.

    Entries are never DROPPED, unlike ``logsband._coerce_tail``'s own
    per-entry handling: an unreadable entry still becomes ``"?"`` here,
    because "a reason was reported that this surface could not read" is
    itself information about the halt, whereas a dropped transcript line
    is merely one missing line of scrollback."""
    block = status.get("intervention")
    if not isinstance(block, dict):
        return []
    raw = block.get("reasons")
    if not isinstance(raw, (list, tuple)):
        return []
    labels = []
    for entry in raw:
        if isinstance(entry, dict):
            labels.append(intervention_reason_label(entry.get("code")))
        else:
            labels.append(intervention_reason_label(entry))
    return labels


def _reason_line(status: dict) -> str:
    """Band 1 -- ``! STOP — <label>[; <label>...]``. A halt with no
    readable reason at all still states the halt, with canon's ``"?"`` in
    the reason slot: the banner "never invents a message and never
    blanks"."""
    labels = _reason_labels(status)
    if not labels:
        return STOP_PREFIX + UNKNOWN_REASON
    return STOP_PREFIX + REASON_SEPARATOR.join(labels)


def _with_attach_affordance(marker: str) -> str:
    """Append the attach prompt to a band-2 marker (WO-P5-065, ruling (b)).

    Applied to every holder reading EXCEPT a confirmed human hold --
    including the unknown fallback. Offering the prompt when the surface
    cannot read the mode is the honest direction: the human may or may not
    hold the keyboard, and telling them how to take it costs nothing (the
    daemon refuses a duplicate attach on its own), whereas withholding it
    would leave an operator staring at `[ ? ]` at a halt with no way
    forward named.

    The affordance is a LABEL. Pressing the key is what attaches, through
    the cockpit's existing `MODE_KEY` path -- nothing here binds, arms, or
    acquires anything, exactly as band 3's teach triad names moves it does
    not perform.
    """
    return f"{marker}  {ATTACH_AFFORDANCE}"


def _holder_line(status: dict) -> str:
    """Band 2 -- the keyboard-handoff marker, claimed only on evidence.

    ``HANDOFF_MARKER`` exactly when the daemon-global ``status["mode"]``
    reports the human holds the one connection. A different reported
    holder renders as that holder (``[ APP ]``); anything unreadable
    renders ``UNKNOWN_HOLDER_MARKER``. See the module docstring for why
    this reads ``status["mode"]`` while ``control_seat.py`` deliberately
    does not."""
    mode = status.get("mode")
    if not isinstance(mode, str):
        return _with_attach_affordance(UNKNOWN_HOLDER_MARKER)
    holder = mode.strip()
    if not holder:
        return _with_attach_affordance(UNKNOWN_HOLDER_MARKER)
    if holder == MODE_HUMAN:
        # The ONLY branch that claims the human has the keyboard, and the
        # only one that omits the affordance -- there is nothing to take.
        return HANDOFF_MARKER
    return _with_attach_affordance(f"[ {holder.upper()} ]")


def compose_stop_banner_lines(
    status: dict | None, *, width: int, height: int = BANNER_H
) -> list[str]:
    """Compose the STOP banner's visible lines, or ``[]`` when no halt is
    reported (see ``needs_attention``).

    Three bands in canon order -- reason, keyboard-handoff marker, teach
    affordances -- folded from the BOTTOM to fit ``height`` so the ``!``
    reason line survives last. ``height <= 0`` returns ``[]``; ``width <=
    0`` returns the same line count with each line emptied to ``""``.

    Never raises regardless of ``status``'s shape or content, or of
    ``width``/``height``'s type (see the module docstring's
    hardening-family paragraph). The top-level ``status`` payload being a
    hostile ``dict`` SUBCLASS (a raising ``.get()``) is out of contract,
    matching every sibling composer's own top-level trust boundary -- the
    daemon's real wire payload is always plain ``json.loads()`` output."""
    width = _coerce_width_height(width)
    height = _coerce_width_height(height)
    if height <= 0:
        return []
    if not needs_attention(status):
        return []

    lines = [_reason_line(status), _holder_line(status), TEACH_LINE]
    lines = lines[:height]
    if width <= 0:
        return ["" for _ in lines]
    return [line[:width] for line in lines]
