"""WO-P5-062 Layer-A -- the autopilot ARM indicator's pure composer
(``tw2002_aiclient/cockpit/arm.py``).

Canon: ``canon/architecture/app-autopilot-model.md`` "Arm-Confirm — No Run
Without a Human's Go" (~64-76) -- the arm gate is "a **required, external
input** to the loop, not an internal self-check the loop could grant
itself." That sentence is the whole design of this module: the cockpit
reads the arm state off the daemon's own report and has no way to
originate one. ``canon/surfaces/mode-line-and-teach-controls.md`` (~21-40)
owns the neighbouring actor badge and is explicit that the badge answers
*who holds the keyboard* -- a different question from *may the taught
autopilot act*, which is what this module answers.

Scope split: this file proves the pure state-extraction and label/tone
mapping. The wiring (that the chip reaches a drawn row, that it is
independent of the seat badge, and that nothing in the cockpit can arm as
a side effect) lives in ``tests/test_cockpit_arm_wiring.py``, mirroring the
Layer-A/Layer-B split ``test_cockpit_spectate.py`` /
``test_cockpit_stopbanner_wiring.py`` already use.

Round-trip honesty (WO-P5-062 scope finding): this module completes a
read-only round trip -- the indicator reports what the daemon reports and
claims nothing else. A write path here would be the fabricated-arm claim
the WO exists to prevent, so the absence of a setter is the design.

**Corrected 2026-07-27 (WO-AUDIT-ARM-CLAIM-HONESTY).** This paragraph used
to add that ``protocol.py`` reported ``{"running": False}`` as a HARDCODED
literal and that ``dispatch`` had "no ``arm``/``disarm`` verb at all", so
the runtime "cannot arm". True when written, **false now**:
``session/autoloop.py`` landed a real ``AutoLoopRunner``,
``protocol.py:300`` calls ``autoloop.arm_block(arm)`` off a live
``observe()``, and ``autoloop_start``/``autoloop_stop``/``autoloop_status``
exist. ``ARM ON`` is reachable, so the ``True`` case pinned below is a live
state rather than a defensive one.

Recorded rather than deleted because the stale text framed an expired fact
as a *safety property*; a reader trusting it would treat the ``True``
branch as unreachable. ``tests/test_autoloop.py`` already carries the
corrected reading ("The runtime can arm now") -- this file and
``cockpit/arm.py`` had drifted from it.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.cockpit.arm import (
    ARM_GAP,
    ARM_OFF,
    ARM_OFF_LABEL,
    ARM_ON,
    ARM_ON_LABEL,
    ARM_UNKNOWN,
    ARM_UNKNOWN_LABEL,
    arm_label,
    arm_state,
    arm_tone,
    compose_arm_chip,
)


def _status(running):
    return {"autopilot": {"running": running}}


# ---------------------------------------------------------------------------
# 1. State extraction -- strict identity in BOTH directions.
# ---------------------------------------------------------------------------


def test_literal_true_is_the_only_thing_that_reads_as_armed():
    assert arm_state(_status(True)) == ARM_ON


def test_literal_false_is_the_only_thing_that_reads_as_disarmed():
    assert arm_state(_status(False)) == ARM_OFF


@pytest.mark.parametrize("running", [1, "yes", "true", "on", [1], {"a": 1}, 1.0])
def test_a_truthy_non_bool_is_unknown_not_armed_and_not_disarmed(running):
    """The load-bearing asymmetry, stated once here and relied on
    everywhere else.

    ``1 == True`` in Python, so a ``==`` comparison would silently accept
    ``running: 1`` as armed; ``1 is True`` is ``False``, so the identity
    check this module uses does not. But the interesting half is the OTHER
    direction: a truthy-but-not-``True`` value must NOT fall through to
    ``ARM_OFF`` either, because ``ARM OFF`` is an affirmative safety claim
    ("the taught autopilot is not allowed to act"). Reporting a calm
    ``ARM OFF`` for a payload that might mean armed is the one failure
    mode with real consequences -- an operator reassured by a claim the
    data never supported. Unknown is the honest third answer, and it is
    what every ambiguous shape gets.

    (Note ``1.0`` and ``0.0`` are floats, not bools, so both are unknown
    -- neither is the literal singleton.)"""
    assert arm_state(_status(running)) == ARM_UNKNOWN


@pytest.mark.parametrize("running", [0, "", None, [], {}, 0.0])
def test_a_falsy_non_bool_is_unknown_too_and_never_a_calm_disarmed_claim(running):
    """The mirror of the case above, and the more counter-intuitive one: a
    cleanly-FALSY non-bool is still not proof of disarm. ``running: None``
    most likely means "the daemon did not populate this field," not "the
    autopilot is definitively stood down," and the two must not collapse
    into the same calm reading. Calm is earned by a literal ``False``,
    never inferred from an absence."""
    assert arm_state(_status(running)) == ARM_UNKNOWN


@pytest.mark.parametrize("status", [
    None,
    {},
    {"autopilot": None},
    {"autopilot": {}},
    {"autopilot": "running"},
    {"autopilot": []},
    {"autopilot": True},
    {"connected": True},          # a real status payload, autopilot key absent
    "autopilot",
    42,
    [],
    object(),
])
def test_every_unusable_payload_shape_is_unknown(status):
    assert arm_state(status) == ARM_UNKNOWN


def test_a_hostile_mapping_whose_get_raises_is_unknown_not_a_crash():
    class _Hostile(dict):
        def get(self, *_a, **_k):
            raise RuntimeError("hostile status payload")

    assert arm_state(_Hostile()) == ARM_UNKNOWN


def test_a_hostile_inner_block_whose_get_raises_is_unknown_not_a_crash():
    class _Hostile(dict):
        def get(self, *_a, **_k):
            raise RuntimeError("hostile autopilot block")

    assert arm_state({"autopilot": _Hostile()}) == ARM_UNKNOWN


def test_the_daemons_real_hardcoded_status_shape_reads_as_disarmed():
    """The exact literal ``session/protocol.py:167-168`` emits today, and
    the exact dict ``tests/test_ensure_no_auto_arm.py::
    test_status_json_reports_autopilot_not_running`` already pins as the
    wire contract -- so this test fails the day that contract changes
    shape, rather than the indicator quietly going unknown on a real
    daemon."""
    assert arm_state({"ok": True, "autopilot": {"running": False}}) == ARM_OFF


# ---------------------------------------------------------------------------
# 2. Labels -- three distinguishable readings, no two ever the same text.
# ---------------------------------------------------------------------------


def test_each_state_has_its_own_distinct_label():
    labels = {arm_label(_status(True)), arm_label(_status(False)), arm_label(None)}
    assert labels == {ARM_ON_LABEL, ARM_OFF_LABEL, ARM_UNKNOWN_LABEL}
    assert len(labels) == 3


def test_the_unknown_label_uses_canons_own_unknown_glyph():
    """``canon/surfaces/mode-line-and-teach-controls.md`` glyph vocabulary
    (~341): "``?`` -- an empty/unknown reason code in the banner, or an
    unknown mode in the chip." The arm chip reuses that established marker
    rather than inventing a fourth vocabulary for the same idea."""
    assert ARM_UNKNOWN_LABEL.endswith("?")
    assert "?" not in ARM_ON_LABEL
    assert "?" not in ARM_OFF_LABEL


def test_a_truncated_label_can_never_impersonate_a_different_label():
    """RENAMED and RE-JUSTIFIED (prior name:
    ``test_no_label_is_a_prefix_of_another``, whose docstring claimed this
    property was a safety layer beneath the all-or-nothing placement rule
    -- it is not, and saying so was the more dangerous half of the error).

    What this does NOT protect against, stated first so nobody relies on
    it: all three labels share the prefix ``ARM ``, and ``ARM ON``/``ARM
    OFF`` additionally share ``ARM O``. A truncated chip is therefore
    genuinely ambiguous, and no self-labeling vocabulary can fix that,
    since any such set shares the leading ``ARM``. The ONLY defense
    against truncation is the all-or-nothing placement rule, pinned by
    ``tests/test_cockpit_arm_wiring.py::test_the_arm_chip_is_all_or_
    nothing_never_truncated``.

    What this DOES pin, which is real and narrower: no truncation of any
    label can come out exactly EQUAL to a different valid label. The chip
    can read as incomplete; it can never read as a confident wrong state.
    Asserted directly over every proper truncation rather than via the
    prefix-free property that implies it, so the test states the guarantee
    it actually makes."""
    labels = [ARM_ON_LABEL, ARM_OFF_LABEL, ARM_UNKNOWN_LABEL]
    for label in labels:
        for n in range(1, len(label)):
            assert label[:n] not in labels, (
                f"{label!r} truncated to {label[:n]!r} impersonates a valid label"
            )


def test_every_label_is_plain_ascii_so_no_glyph_twin_is_needed():
    """Unlike ``MANUAL_LABEL``'s embedded em-dash, nothing here needs a
    ``unicode_ok`` ASCII twin -- checked rather than assumed, so a future
    label edit that reaches for a Unicode glyph fails here and gets a
    deliberate glyph-table decision instead of silently degrading on an
    80-col non-UTF-8 terminal."""
    for label in (ARM_ON_LABEL, ARM_OFF_LABEL, ARM_UNKNOWN_LABEL, ARM_GAP):
        assert label.isascii(), f"{label!r} is not plain ASCII"


# ---------------------------------------------------------------------------
# 3. Tone -- calm is earned, never defaulted.
# ---------------------------------------------------------------------------


def test_armed_wears_the_attention_tone():
    assert arm_tone(_status(True)) == "warn"


def test_unknown_wears_the_attention_tone_too():
    """The deliberate divergence from this package's other honest-unknown
    helpers, called out at the point it happens (``arm.py``'s own
    ``arm_tone`` docstring carries the full reasoning).

    ``control_seat._safe_attached`` degrades an unevaluable input AWAY from
    its consequential claim, because there the alarming reading IS the
    claim ("MANUAL — YOU HAVE CONTROL"). Here the polarity is reversed:
    the alarming fact is the ABSENCE of proof that the autopilot is stood
    down. So an unknown arm state degrades TOWARD attention, not away from
    it. Both helpers follow the same underlying rule -- never let an
    unknown render as the reassuring answer -- and land on opposite tones
    only because the reassuring answer is on opposite sides."""
    assert arm_tone(None) == "warn"
    assert arm_tone(_status(1)) == "warn"


def test_only_a_proven_disarm_gets_the_calm_muted_tone():
    assert arm_tone(_status(False)) is None


def test_the_tone_vocabulary_is_exactly_what_the_draw_layer_already_resolves():
    """``screens._control_strip_segment_attr`` resolves ``"ok"``/``"warn"``
    and treats every other value as plain. This module must only ever emit
    a tone from that known set, or the chip would silently lose its badge
    styling."""
    for status in (_status(True), _status(False), None, _status("maybe")):
        assert arm_tone(status) in ("ok", "warn", None)


def test_arm_never_claims_the_ok_tone_reserved_for_the_app_chip():
    """Green/``ok`` is the App seat chip's own colour
    (``control_seat.APP_LABEL``). The arm chip sits directly beside it, so
    it must never wear the same tone -- two green reverse-video chips
    adjacent would read as one badge."""
    for status in (_status(True), _status(False), None, _status(0), _status("x")):
        assert arm_tone(status) != "ok"


# ---------------------------------------------------------------------------
# 4. compose_arm_chip -- the single (text, tone) pair the draw layer takes.
# ---------------------------------------------------------------------------


def test_compose_returns_the_matching_label_and_tone_pair():
    assert compose_arm_chip(_status(True)) == (ARM_ON_LABEL, "warn")
    assert compose_arm_chip(_status(False)) == (ARM_OFF_LABEL, None)
    assert compose_arm_chip(None) == (ARM_UNKNOWN_LABEL, "warn")


def test_compose_always_yields_a_non_empty_label():
    """The chip never blanks. An arm indicator that disappears when the
    daemon payload is unusable would be indistinguishable from one that
    was never built -- the operator could not tell "no information" from
    "no feature." ``ARM ?`` says which."""
    for status in (None, {}, object(), _status(None), _status("?"), 0):
        text, _tone = compose_arm_chip(status)
        assert text


def test_compose_takes_exactly_one_argument_the_daemon_report(monkeypatch):
    """A structural half of Accept #3, cheap and exact: the chip's only
    input is the status payload. There is no second parameter through
    which a caller could assert, override, or suggest an arm state, so no
    amount of cockpit-side state can produce ``ARM ON`` on its own."""
    import inspect

    params = inspect.signature(compose_arm_chip).parameters
    assert len(params) == 1
    only = next(iter(params.values()))
    assert only.kind in (only.POSITIONAL_ONLY, only.POSITIONAL_OR_KEYWORD)
    assert only.default is inspect.Parameter.empty


# ---------------------------------------------------------------------------
# 5. Never-raises -- the family discipline every cockpit composer keeps.
# ---------------------------------------------------------------------------


class _Exploding:
    def __bool__(self):
        raise RuntimeError("boom")

    def __eq__(self, _other):
        raise RuntimeError("boom")

    def __hash__(self):
        raise RuntimeError("boom")


@pytest.mark.parametrize("status", [
    None, {}, [], 0, "", object(), _Exploding(), {"autopilot": _Exploding()},
    {"autopilot": {"running": _Exploding()}},
])
def test_no_public_entry_point_raises_on_any_input_shape(status):
    arm_state(status)
    arm_label(status)
    arm_tone(status)
    compose_arm_chip(status)


def test_an_exploding_running_value_is_unknown_not_armed():
    """The identity checks (``is True`` / ``is False``) call no dunder at
    all, so an object whose ``__eq__``/``__bool__`` raise cannot even reach
    the comparison -- it simply matches neither literal and lands on
    unknown. Executed rather than reasoned about."""
    assert arm_state({"autopilot": {"running": _Exploding()}}) == ARM_UNKNOWN
