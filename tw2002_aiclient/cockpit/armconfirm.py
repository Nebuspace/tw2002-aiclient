"""The confirm-to-arm gate -- the one place a keystroke could commit live
turns, and the one dialog styled to say so (WO-P5-063).

# What canon requires

`canon/surfaces/mode-line-and-teach-controls.md` "The confirm-gate dialog
look":

    Play "Ferren-Sol" x3 LIVE?  y/N     <- danger-tone + reverse-video

> "Arming a live run is the one money-path moment ... The prompt spells out
> *what* runs and *how many cycles*, the `y/N` capitalization signals the
> safe default is No, and **Enter alone must never fire** -- only a
> deliberate `y` commits. This is the -75/-78-turn-scar doctrine made
> visible."

Three separate requirements live in that paragraph and each is pinned
separately in `tests/test_cockpit_armconfirm.py`: the *wording* (what runs,
how many cycles), the *styling* (danger+reverse), and the *key policy*
(only `y`).

# The key policy is default-DENY, and that is structural

`resolve_arm_confirm_key` enumerates the **confirm** set by exact identity
(`y`, `Y`) and returns `CANCEL` for everything else -- unknown keycodes,
`None`, a non-integer, a mouse event, a resize, a key this cockpit has not
heard of yet. The safe outcome is the one that requires no enumeration to
be complete.

That direction matters more than it looks. Written the other way round --
cancel on a known-cancel list, confirm otherwise -- every key nobody
thought about becomes a live arm, and the set of keys nobody thought about
only ever grows. Here a future keycode is inert by construction rather than
by anyone remembering to add it. `Esc`, `Enter`, `N`, `n`, `q` and
`Ctrl-A` are all pinned explicitly anyway, because a policy this important
should fail loudly if the default ever inverts, not silently rely on the
default being right.

**`Enter` is deliberately not special-cased.** It cancels because it is
"not `y`", exactly like every other key. A dedicated `if key in ENTER:
return CANCEL` branch would be a second place to get this right, and the
day someone added Enter-activates-focused-control behaviour to this dialog
(the pattern the control strip already uses, `screens.py` `conn_activate`)
that branch is what they would edit. The absence of the branch is the
guarantee.

# Nothing raises this dialog yet -- deliberately

`arm write-back is still read-only (062 stub); this WO only adds the
confirm gate, not the daemon call` (WO-P5-063 Constraints). The things
canon says *should* raise it -- a Trade-Loop chain launch, a taught-run
launch -- are the N5 operate-the-app cluster (WO-071), unbuilt. So this
module ships a gate that is complete, proven and **not yet triggered by
anything**, the same shape `stopbanner.py` band 3 and `teachband.py` ship
labels whose wires belong to later WOs.

`screens.py` exposes `begin_arm_confirm()` as the single seam a future WO
calls. `tests/test_cockpit_armconfirm.py` pins that **no production call
site invokes it today** -- so the day an arm path appears without its own
WO, that pin goes red before anything can be armed silently (WO-P5-063
Accept #5).

# Rendering contract

Plain strings and a tone NAME only; attribute resolution belongs to the
draw layer, the same split `arm.py` and `teachband.py` document. The tone
is `ARM_CONFIRM_TONE` = `"danger"`, and the draw layer must render it
**bold** and reverse-video.

That weight is load-bearing and easy to get wrong: this tree carries
`danger` in *two* weights. `visual-language.md:58` is the 7-tone table row
(red / **bold**) and lists "the live-play `y/N` confirm" among its own
examples; `visual-language.md:83` is a deliberate per-surface override to
red **non-bold**, for the viewport border's link-down flip only, and
`screens.py` exposes it as `_viewport_danger_attr`. Reaching for that
attribute here -- it is on the class, and it has `danger` in its name --
would render this gate *quieter* than the frame around it while still
satisfying any check that only asks "is it danger-toned?". `:77-78` calls
danger+reverse "the loudest combination the palette owns"; that is what
this gate gets.

Hardening family (matches `arm.py`/`teachband.py`/`stopbanner.py`): never
raises regardless of any argument's type or content.
"""

from __future__ import annotations

# The two outcomes. Strings rather than a bool so a caller reading
# `resolve_arm_confirm_key(k) == CONFIRM` states the whole condition at the
# call site -- `if resolve(k):` would arm on the truthy value and is exactly
# the misreading this gate cannot afford.
CONFIRM = "confirm"
CANCEL = "cancel"

# The ONLY keys that arm. Canon: "only a deliberate `y` commits."
# Both cases, because the `N` in `y/N` marks the default rather than the
# shift state, and a capitalised `Y` is unambiguously the same intent.
_CONFIRM_KEYS = frozenset({ord("y"), ord("Y")})

# The tone NAME (not an attr). Draw layer resolves it to danger-BOLD +
# reverse -- see the module docstring on why the weight matters.
ARM_CONFIRM_TONE = "danger"

# Canon renders the gate as `<what runs> LIVE?  y/N`. Held as separate
# constants so the pins assert canon's own text rather than a copy of
# whatever this module happened to emit.
LIVE_MARKER = "LIVE?"
CONFIRM_HINT = "y/N"

# Two spaces before the hint, matching canon's rendering and the gap
# `arm.ARM_GAP` / `teachband.TOKEN_GAP` already use.
_HINT_GAP = "  "

# What the gate says when the caller supplies no description. It still
# names the risk rather than degrading to a bare "Confirm?" -- an
# unlabelled money-path prompt is the one thing this surface must never be.
FALLBACK_ACTION = "Arm autopilot"


def _safe_text(value: object) -> str:
    """Coerce a caller-supplied description to a single-line string.

    Newlines are collapsed rather than passed through: this line is drawn
    into one row, and an embedded newline would push the `y/N` hint off
    the rendered line while the string still *contained* it -- a prompt
    that looks answered-by-Enter. Control-character neutralisation and
    cell-accurate clipping stay at ``cockpit.draw``'s single choke point
    (the same trust boundary ``logsband.py`` documents); this only
    guarantees one line.
    """
    if not isinstance(value, str) or not value:
        return ""
    return " ".join(value.split())


def compose_arm_confirm_line(
    action: object = None,
    *,
    cycles: object = None,
    unicode_ok: object = True,
) -> str:
    """Canon's confirm line: ``<what runs> [xN] LIVE?  y/N``.

    ``action`` describes what will run. ``cycles``, when a positive int,
    renders canon's ``x3`` cycle count -- "the prompt spells out *what*
    runs and *how many cycles*". A non-positive or non-integer ``cycles``
    is omitted rather than guessed at: an invented cycle count on a
    money-path prompt is worse than an absent one.

    ``unicode_ok`` is accepted for API uniformity with every sibling
    composer and ignored -- the line is pure ASCII with no Unicode twin.
    Never raises.
    """
    text = _safe_text(action) or FALLBACK_ACTION

    count = None
    if isinstance(cycles, int) and not isinstance(cycles, bool) and cycles > 0:
        count = cycles
    if count is not None:
        text = f"{text} x{count}"

    return f"{text} {LIVE_MARKER}{_HINT_GAP}{CONFIRM_HINT}"


def resolve_arm_confirm_key(key: object) -> str:
    """``CONFIRM`` for `y`/`Y` only; ``CANCEL`` for literally everything else.

    Default-deny by construction -- see the module docstring. `Enter` and
    `Esc` cancel because they are not `y`, not because they are named
    here. Never raises: an unusable ``key`` (``None``, a string, a float,
    an object) cancels, since a key this layer cannot even interpret is
    the last thing that should commit live turns.
    """
    if isinstance(key, bool) or not isinstance(key, int):
        return CANCEL
    return CONFIRM if key in _CONFIRM_KEYS else CANCEL
