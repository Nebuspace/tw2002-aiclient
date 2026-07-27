"""Pure autopilot-ARM-state composer (WO-P5-062, ``workorders/
WO-P5-060-072-mode-teach-PREP.md`` §PWO-062).

No ``curses`` import here on purpose -- mirrors ``liveness.py`` /
``strip.py`` / ``control_seat.py``'s pure-composer discipline: this module
renders plain strings and a tone NAME only; attribute resolution belongs
to the draw layer (``screens.py``).

What this module answers, and what it deliberately does not
=============================================================

The control strip carries two facts that read as one at a glance and are
not the same question:

- **Who holds the keyboard** -- App / Human / (post-detach) Spectate. That
  is ``control_seat.py``'s chip, sourced from THIS client's own two
  booleans (``PlayShellScreen.spectating`` / ``.attached``).
- **Whether the taught autopilot is allowed to act** -- this module's
  chip, sourced from the DAEMON's own reported state.

They are orthogonal, and canon needs them to be: ``canon/architecture/
app-autopilot-model.md`` "Arm-Confirm" (~64-76) describes a run that is
armed by the human and then STOPs and hands the keyboard back the instant
it meets an unrecognized screen -- so "armed" and "currently driving" come
apart routinely and legitimately. An armed behavior whose keyboard has
just been handed to the human is a normal state, not a contradiction, and
the strip must be able to say so. Collapsing the two into one chip would
make that state unrepresentable and would let the operator read "Human has
the keyboard" as "nothing is armed."

Why the state is READ from the daemon and never held here
==========================================================

Canon is explicit that the arm gate is "a **required, external input** to
the loop, not an internal self-check the loop could grant itself"
(``app-autopilot-model.md`` ~74). This module is the presentation-side
expression of that sentence: it takes the daemon's status payload and
maps it to a chip. It has no setter, no cached state, and no second
parameter through which a caller could assert an arm state. The cockpit
therefore has nothing to flip, which is what makes "no silent arm"
structural rather than merely intended -- there is no code path, side
effect, or keystroke that could produce ``ARM ON`` without the daemon
having reported it.

Round-trip status, stated honestly (WO-P5-062 scope finding)
=============================================================

This module is **read-only**: it reports what the daemon reports and
claims nothing further. That is a deliberate outcome, not an unfinished
one -- see "no silent arm" above, which is structural rather than a
discipline someone has to remember.

**Corrected 2026-07-27 (WO-AUDIT-ARM-CLAIM-HONESTY).** This section used
to say that ``session/protocol.py``'s ``status`` verb reported the
autopilot block as a HARDCODED disarmed literal, that ``dispatch``
carried no arm/disarm verb of any kind, and that "there is no ported
run-loop to arm". **All three were true when written and are false now.**
``session/autoloop.py`` landed a real ``AutoLoopRunner``;
``protocol.py:300`` calls ``autoloop.arm_block(arm)`` off a live
``observe()``; and ``autoloop_start`` / ``autoloop_stop`` /
``autoloop_status`` all exist. ``arm_block`` returns
``{"running": bool(snapshot.running)}``, so **``ARM ON`` is reachable
today** and the ``True`` branch below is live, not dead.

The correction is recorded rather than quietly deleted because the stale
text did not merely state an expired fact -- it framed that fact as a
*safety property* ("a runtime that cannot arm"). A reader who trusted it
would conclude ``ARM ON`` is unreachable, which is one step from removing
the ``True`` branch as dead code or from dismissing a genuine ``ARM ON``
as a bug. ``protocol.py`` corrected its own copy of this claim when
``autoloop`` landed; this module and ``screens.py`` did not, and drifted.

The forecast in the old text did hold: this module needed **no code
change** when the run-loop arrived -- it already read the field the new
runtime populates.

Three states, because two would have to lie
============================================

``ARM ON`` and ``ARM OFF`` are both affirmative claims, and a payload that
supports neither must not be forced into one:

- literal ``True``  -> ``ARM ON``
- literal ``False`` -> ``ARM OFF``
- everything else   -> ``ARM ?``

The gate is an ``is`` identity check in BOTH directions, which calls no
dunder method and so cannot be fooled or made to raise by a hostile
object. Identity also matters for a plain arithmetic reason: ``1 ==
True`` in Python, so an equality check would silently accept ``running:
1`` as armed. The ``?`` reuses canon's own established unknown marker
(``mode-line-and-teach-controls.md`` ~341: "``?`` -- an empty/unknown
reason code in the banner, or an unknown mode in the chip") rather than
inventing a fourth vocabulary for the same idea.

D5: no ``ai_pilot``/imperative-mood text anywhere -- this module renders a
read-only observation of the daemon's reported state, never a command.
"""

from __future__ import annotations

# The three readings, as stable identifiers the draw layer and tests can
# name without matching on display text.
ARM_ON = "on"
ARM_OFF = "off"
ARM_UNKNOWN = "unknown"

# Chip text. Plain ASCII throughout -- unlike `control_seat.MANUAL_LABEL`'s
# embedded em-dash there is no Unicode glyph here, so `unicode_ok` has no
# ASCII twin to swap and no effect on this module at all.
#
# TRUNCATION SAFETY -- what actually defends it, stated precisely, because
# an earlier draft of this comment overstated it (corrected on review).
#
# A partially-rendered chip is the one way this surface could actively
# mislead: `ARM O` resolving in the reader's head as a shortened `ARM ON`
# when the truth was `ARM OFF`. **The ONLY defense against that is
# `control_seat._compose_segments`' all-or-nothing placement rule** -- the
# chip renders whole or yields entirely, and never truncates. That rule is
# load-bearing for this chip's honesty and is pinned by a test
# (`tests/test_cockpit_arm_wiring.py::test_the_arm_chip_is_all_or_nothing_
# never_truncated`), not merely documented. Do not relax it believing
# something else catches truncation. Nothing does.
#
# The labels ARE prefix-free, but that property does NOT cover the hazard
# above and must not be read as a second layer under it. All three labels
# share the prefix `ARM `, and `ARM ON`/`ARM OFF` additionally share
# `ARM O`, so a truncation is exactly as ambiguous as described -- and no
# vocabulary can fix that while the chip still names itself, since any
# self-labeling set shares the leading `ARM`. What prefix-freeness buys is
# narrower and real: a truncated label can never come out exactly EQUAL to
# a different valid label, so the chip can misread as "incomplete" but
# never as a confident wrong state. That is worth keeping, and it is all
# it is.
ARM_ON_LABEL = "ARM ON"
ARM_OFF_LABEL = "ARM OFF"
ARM_UNKNOWN_LABEL = "ARM ?"

# Two blank columns between the seat chip and this one. Both are drawn
# reverse-video when they carry a tone, and two adjacent reverse-video
# runs with no gap read as a single wider badge -- the separation is what
# keeps them legible as two independent facts, which is the whole point of
# the pair.
ARM_GAP = "  "

_LABELS = {
    ARM_ON: ARM_ON_LABEL,
    ARM_OFF: ARM_OFF_LABEL,
    ARM_UNKNOWN: ARM_UNKNOWN_LABEL,
}


def arm_state(status: object) -> str:
    """The daemon's reported autopilot arm state as one of ``ARM_ON`` /
    ``ARM_OFF`` / ``ARM_UNKNOWN``, read from ``status["autopilot"]
    ["running"]``.

    Only the literal ``bool`` singletons resolve to a definite answer; any
    other value, a missing or non-mapping ``autopilot`` block, a non-dict
    ``status``, and a hostile payload whose ``get`` raises all resolve to
    ``ARM_UNKNOWN``. Never raises regardless of ``status``'s type.

    The falsy-but-not-``False`` case is the one worth being explicit
    about, since it is where this helper differs from ordinary Python
    truthiness and from ``control_seat``'s own ``bool()``-coercing
    ``_safe_spectating``/``_safe_attached``. ``running: None`` almost
    certainly means "the daemon did not populate this field," not "the
    autopilot is definitively stood down" -- and ``ARM OFF`` is an
    affirmative safety claim an operator will act on. Inferring it from an
    absence would be the surface quietly reassuring someone on evidence it
    never had, so an absence gets ``ARM ?`` instead."""
    try:
        if not isinstance(status, dict):
            return ARM_UNKNOWN
        block = status.get("autopilot")
        if not isinstance(block, dict):
            return ARM_UNKNOWN
        running = block.get("running")
    except Exception:  # noqa: BLE001 -- a hostile payload must not crash the draw pass
        return ARM_UNKNOWN
    if running is True:
        return ARM_ON
    if running is False:
        return ARM_OFF
    return ARM_UNKNOWN


def arm_label(status: object) -> str:
    """The chip's display text for ``status``. Never empty and never
    raises -- the chip always says something, because a chip that vanished
    on an unusable payload would be indistinguishable from a cockpit that
    never had an arm indicator at all, and the operator needs to be able
    to tell "no information" from "no feature"."""
    return _LABELS.get(arm_state(status), ARM_UNKNOWN_LABEL)


def arm_tone(status: object) -> str | None:
    """The chip's semantic tone: ``None`` (muted/plain) for a PROVEN
    disarm, ``"warn"`` for everything else. Never raises.

    This module degrades an unknown in the OPPOSITE direction from its
    sibling helpers, and the divergence is deliberate enough to be worth
    stating where it happens rather than leaving as a surprise.
    ``control_seat._safe_attached`` degrades an unevaluable input AWAY
    from its consequential claim, because there the alarming reading IS
    the claim -- a wrongly-rendered "MANUAL — YOU HAVE CONTROL" tells the
    operator they hold a keyboard they do not. Here the polarity is
    reversed: the alarming fact is the ABSENCE of proof that the autopilot
    is stood down, so an unknown degrades TOWARD attention. Both helpers
    obey the same underlying rule -- never let an unknown render as the
    reassuring answer -- and land on opposite tones only because the
    reassuring answer sits on opposite sides. Calm is earned by a literal
    ``False``, never defaulted into.

    ``"warn"`` (yellow) rather than ``"danger"`` (red) is canon's own
    register for this: ``mode-line-and-teach-controls.md`` reserves the
    danger tone plus reverse-video for the confirm-gate's money-path
    prompt ("the ONLY place the interaction contract combines the loudest
    tone with the selection attr", ~285-289) and red generally for hard
    link-down. An armed autopilot is the attention-with-you register the
    Human chip already wears, not a failure. ``"ok"`` (green) is likewise
    avoided: it is the App seat chip's own tone, and two adjacent green
    reverse-video chips would read as one badge."""
    return None if arm_state(status) == ARM_OFF else "warn"


def compose_arm_chip(status: object) -> tuple[str, str | None]:
    """The ``(text, tone)`` pair the draw layer places on the control
    strip -- the same shape ``control_seat.compose_control_strip_segments``
    already emits for its own chip, so ``screens.py`` resolves both
    through the one existing ``_control_strip_segment_attr`` helper rather
    than growing a second attr path.

    Deliberately ONE parameter, and no default. There is no second input
    through which a caller could assert, override, hint at, or default an
    arm state, so no amount of cockpit-side state can produce ``ARM ON``
    on its own -- the "no silent arm" guarantee reduced to a signature.
    Never raises regardless of ``status``'s type."""
    return arm_label(status), arm_tone(status)
