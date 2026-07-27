"""The panic control -- halt all automation, immediately (WO-P5-071).

# What this is

Canon's N5 operate-the-app cluster (`canon/surfaces/
mode-line-and-teach-controls.md` "The operate-the-APP control cluster")
names "a **panic** control that halts *all* automation and parks the app in
a non-driving paused state." This module owns that control's affordance and
key binding; `session/autoloop.py` owns what actually stops.

# Panic is NOT confirm-gated, and that is the load-bearing decision

Every *other* affordance in this cluster is confirm-gated. Canon is
emphatic about it -- "no single keystroke ever commits the app to spend
live turns or credits", "a bare Enter must never fire a launch" -- and
calls it "a non-negotiable money-path safety rule born of the
**-75/-78-turn scars**".

Panic is the exception, and the reason is directional. The confirm gate
protects the direction that *spends*: arming a rule, launching a run,
selecting a chain. Panic runs the other way -- it halts. Putting a `y/N`
in front of the one control whose entire value is being instantaneous
would be a safety regression wearing safety clothing: it would add a
keystroke to the emergency path to satisfy a rule written to protect the
commitment path.

This is an easy mistake to make while "being consistent with
`armconfirm.py`", so it is stated here and pinned mechanically in
`tests/test_cockpit_panic.py` -- panic must reach the stop path with no
intervening confirm, and arming must still be gated. Ratified by the hub
2026-07-27.

Note the asymmetry is safe in both directions of *error*: a panic the
operator did not mean costs them a halted run they can re-arm (through the
confirm gate), while a panic they meant and could not fire costs them the
live turns and credits the run keeps spending. The cheap failure is the
one this design chooses.

# What it halts, honestly

`adapters.autoloop_stop()` sends the daemon's `autoloop_stop` verb, which
is **idempotent and never refuses** (`session/protocol.py`
`_dispatch_autoloop_stop`): the player's own arm predicate is what stops
the run, within one send-step, and the run releases its own control-lock
hold as it dies. So panic cannot drop the App's exclusivity out from under
a step still in flight, and pressing it twice is harmless.

It does **not** halt an `explore` run -- that has its own `explore_stop`
verb and its own affordance. "Halts *all* automation" is canon's intent and
is not yet literally true on tip; recorded here rather than quietly
overclaimed in a docstring. A future WO widening panic to every runner
should update this paragraph and the pin that goes with it.

# Pause and relaunch are no longer absent

The paragraph that used to stand here said pause/resume was "descoped to a
follow-on WO that adds runner-side pause first" (hub ruling 2026-07-27,
when `session/autoloop.py` had only `start()`/`stop()` and no capability
to bind a key to). That follow-on landed: `session/autoloop.py` now has a
real `pause()` (WO-AUTOLOOP-PAUSE-RESUME, #101), wired to the daemon's
`autoloop_pause` verb.

The other half is **not** a `resume` -- `resume` would have been a lie:
`replay_loop` takes no start index, so re-arming a paused run always
replays its macro from step 1 and re-issues sends already made. The hub
ruled the verb be named for what it actually does instead --
`autoloop_relaunch` -- disclosing `replays_from_start` and
`sends_already_issued` so a confirm gate can state the truth
(`session/protocol.py::_dispatch_autoloop_relaunch`).

Neither key is bound in THIS module: this module still owns panic alone.
The pause hotkey (ungated, this module's own "halts nothing to spend"
reasoning applies unchanged) and the relaunch confirm gate + label
(money-path, confirm-gated) are `cockpit/autoloop_controls.py`'s job
(WO-AUTOLOOP-RELAUNCH-COCKPIT), wired in `app.py`/`screens.py` alongside
this module's own panic wiring.

Hardening family (matches `arm.py`/`armconfirm.py`/`teachband.py`): never
raises regardless of any argument's type or content.
"""

from __future__ import annotations

# Canon's band spelling, taken from the literal rather than the prose rule.
#
# `mode-line-and-teach-controls.md §"Spacing, alignment & hierarchy — the mode-line reading order"` states "every token uses the uniform
# `KEY)verb` shape", which would make this `P)anic`. But the band literal
# canon actually prints is `^A)ode  A)nalyze  R)ecord  T)rigger  L)chains
# P panic` -- with a SPACE, not a paren -- and it appears three times
# identically across two files (`:136`, `:220`,
# `visual-language.md §"A calm cockpit reading (App healthy, nothing to see)"`). Three consistent cross-file literals is
# stronger evidence of intent than one generalisation that overlooks its
# own last token, so the literal wins here and the conflict is reported to
# the hub rather than silently resolved. Flip this one constant if canon
# rules the other way.
PANIC_TOKEN = "P panic"

# Both cases bind, matching the A/R/T teach keys' posture
# (`screens.py` binds `a`/`A`, `r`/`R`, `t`/`T`).
_PANIC_KEYS = frozenset({ord("p"), ord("P")})

# The intent string the cockpit returns to the app loop. A distinct verb
# rather than reusing an existing one: the app loop must be able to route
# panic to the stop path WITHOUT passing through the arm-confirm gate that
# every other N5 intent goes through (see the module docstring).
PANIC_INTENT = "panic"

# Affordance chrome in the hint band, like the A/R/T tokens beside it --
# `screens.py::_control_strip_segment_attr` resolves this to the cyan chrome
# accent. Deliberately NOT the `danger` tone the arm-confirm line wears:
# `danger` is canon's signal for a prompt that is about to spend something,
# and panic spends nothing. A permanently-red token in the calm band would
# also dilute the one place red means "this commits live turns".
PANIC_TONE = "chrome"


def resolve_panic_key(key: object) -> bool:
    """``True`` when ``key`` is the panic hotkey.

    ``bool`` is rejected even though ``isinstance(True, int)`` holds: a
    ``True`` arriving where a keycode belongs is an upstream type error,
    and ``True == 1`` would silently match ``chr(1)``. Every other
    non-``int`` is likewise ``False`` rather than a guess. Never raises.
    """
    if isinstance(key, bool) or not isinstance(key, int):
        return False
    return key in _PANIC_KEYS
