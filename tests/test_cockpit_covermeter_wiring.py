"""Coverage meter -> control strip wiring (WO-P5-072).

Separate from `test_cockpit_covermeter.py` (which pins the meter's own math
and honesty) because these pin a different claim: that the composed meter
reaches the row, yields to liveness under pressure, and cannot be passed in
a shape that silently discards it.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.cockpit import covermeter
from tw2002_aiclient.cockpit.control_seat import (
    compose_control_strip_line,
    compose_control_strip_segments,
)

WIDE = 160


def _chip(app=None, human=None):
    """The exact `(text, tone)` shape `screens.py` passes."""
    return (covermeter.compose_coverage_meter(app=app, human=human), covermeter.METER_TONE)


# --------------------------------------------------------------------------
# It reaches the row
# --------------------------------------------------------------------------

def test_meter_appears_on_a_wide_row():
    line = compose_control_strip_line(
        spectating=False, attached=True, liveness_text="LIVE",
        width=WIDE, coverage_meter=_chip(app=3, human=1),
    )
    assert "COV 75%" in line
    assert "App 3" in line and "Hum 1" in line


def test_unknown_meter_still_appears():
    """`COV ?` is the tip reading and must be visible, not suppressed as if
    it were an empty chip -- an absent gauge and a gauge honestly reporting
    `?` are different statements to the operator."""
    line = compose_control_strip_line(
        spectating=False, attached=True, liveness_text="LIVE",
        width=WIDE, coverage_meter=_chip(),
    )
    assert "COV ?" in line


def test_meter_carries_plain_tone_not_a_badge():
    segments = compose_control_strip_segments(
        spectating=False, attached=True, liveness_text="LIVE",
        width=WIDE, coverage_meter=_chip(app=3, human=1),
    )
    meter = [(t, tone) for t, tone in segments if "COV" in t]
    assert meter, "meter segment missing"
    assert meter[0][1] is None, "meter must not take ok/warn/danger badge treatment"


# --------------------------------------------------------------------------
# The shape trap: a bare string is silently discarded
# --------------------------------------------------------------------------

def test_bare_string_meter_is_not_rendered():
    """`control_seat._safe_arm_chip` 2-unpacks its argument, so passing the
    composer's plain string discards it (a 5-char `COV ?` raises on unpack ->
    `("", None)`).

    Pinned deliberately rather than fixed: every chip on this row takes the
    same `(text, tone)` contract, and loosening one to also accept a string
    would make a 2-character string ambiguous between text-and-tone and
    text-alone. The pin exists so the failure is documented and a future
    caller that passes a string sees a test naming the reason, instead of a
    meter that silently never appears.
    """
    line = compose_control_strip_line(
        spectating=False, attached=True, liveness_text="LIVE",
        width=WIDE, coverage_meter="COV 75%",
    )
    assert "COV" not in line


def test_correct_tuple_shape_does_render():
    """The companion half of the pin above -- proves the previous test fails
    for the *shape*, not because the meter is unwired entirely."""
    line = compose_control_strip_line(
        spectating=False, attached=True, liveness_text="LIVE",
        width=WIDE, coverage_meter=("COV 75%", None),
    )
    assert "COV 75%" in line


# --------------------------------------------------------------------------
# Liveness priority -- canon's N5 hazard
# --------------------------------------------------------------------------

def test_liveness_survives_when_the_meter_cannot_fit():
    """Canon (PWO-071 hazard, inherited here): the meter must never claim
    columns the liveness cluster needs. Swept across every width from 1 up to
    comfortably wide -- at every single one, liveness is intact."""
    liveness = "LIVE 12s"
    for width in range(1, 60):
        line = compose_control_strip_line(
            spectating=False, attached=True, liveness_text=liveness,
            width=width, coverage_meter=_chip(app=3, human=1),
        )
        assert len(line) <= width
        if width >= len(liveness):
            assert liveness in line, f"liveness lost at width={width}"


def test_meter_drops_before_liveness_under_pressure():
    """At a width that fits liveness but not both, the meter is what goes."""
    liveness = "LIVE 12s"
    meter_text = covermeter.compose_coverage_meter(app=3, human=1)
    width = len(liveness) + 2
    line = compose_control_strip_line(
        spectating=False, attached=True, liveness_text=liveness,
        width=width, coverage_meter=_chip(app=3, human=1),
    )
    assert liveness in line
    assert meter_text not in line


def test_meter_never_truncated_onto_the_row():
    """A partial `COV 7` must never reach the row at ANY width -- the failure
    mode this whole design exists to prevent."""
    for width in range(1, 120):
        line = compose_control_strip_line(
            spectating=False, attached=True, liveness_text="LIVE",
            width=width, coverage_meter=_chip(app=3, human=1),
        )
        if "COV" in line:
            assert "COV 75%" in line, f"clipped meter on row at width={width}: {line!r}"


# --------------------------------------------------------------------------
# Backward compatibility -- the row is unchanged without the new kwarg
# --------------------------------------------------------------------------

@pytest.mark.parametrize("width", [0, 1, 10, 40, 80, 160])
@pytest.mark.parametrize("spectating,attached", [(True, False), (False, True), (False, False)])
def test_row_is_byte_identical_when_no_meter_is_passed(width, spectating, attached):
    """The new keyword defaults to `None`; every pre-existing caller must get
    exactly the row it got before."""
    kwargs = dict(
        spectating=spectating, attached=attached,
        liveness_text="LIVE 12s", width=width,
    )
    assert compose_control_strip_line(**kwargs) == compose_control_strip_line(
        **kwargs, coverage_meter=None
    )


@pytest.mark.parametrize("width", [0, 1, 40, 160])
def test_line_and_segments_stay_consistent_with_a_meter(width):
    """The two public composers share one code path; the meter must not break
    the "segments concatenate to the line" invariant."""
    kwargs = dict(
        spectating=False, attached=True, liveness_text="LIVE 12s",
        width=width, coverage_meter=_chip(app=3, human=1),
    )
    joined = "".join(text for text, _ in compose_control_strip_segments(**kwargs))
    assert joined == compose_control_strip_line(**kwargs)


# --------------------------------------------------------------------------
# Hardening
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "hostile",
    [object(), 42, [], {}, ("only-one",), ("a", "b", "c"), (None, None), (b"x", None)],
)
def test_hostile_meter_values_degrade_to_absent_without_raising(hostile):
    line = compose_control_strip_line(
        spectating=False, attached=True, liveness_text="LIVE",
        width=WIDE, coverage_meter=hostile,
    )
    assert "LIVE" in line


def test_no_ai_term_reaches_the_row():
    """The WO's grep pin, enforced at the row level as well as the composer:
    an `AI` slice must not appear even if some future chip re-introduces it."""
    for app, human in [(None, None), (0, 0), (3, 1), (1, 7)]:
        line = compose_control_strip_line(
            spectating=False, attached=True, liveness_text="LIVE",
            width=WIDE, coverage_meter=_chip(app=app, human=human),
        )
        assert "AI" not in line
