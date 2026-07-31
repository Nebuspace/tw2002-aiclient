"""The standing teach hint band -- the A/R/T affordance tokens that sit on
the control strip whenever the cockpit is up (WO-P5-066).

# What this is

Canon (`canon/surfaces/mode-line-and-teach-controls.md`) surfaces the three
teach moves in TWO registers, and they are deliberately spelled
differently:

- **The standing hint band** (`:136`, and `visual-language.md §"A calm cockpit reading (App healthy, nothing to see)"`) --
  `^A)ode  A)nalyze  R)ecord  T)rigger  L)chains  P panic`. Calm-state
  chrome, always present, right-aligned on the control strip.
- **The STOP banner's `teach:` line** (`:146`, `:271`) --
  `A)nalyze  R)ecord  T)assign`, promoted onto the banner at a halt so the
  three moves sit where the escalation happened. That register belongs to
  `cockpit.stopbanner.TEACH_LINE` and is NOT this module's business.

Note the `T` token: **`T)rigger` on the standing band, `T)assign` on the
banner.** Canon spells both, and `stopbanner.py`'s own constant comment
calls the distinction out. This module therefore does not import or reuse
`TEACH_LINE` -- reusing it would ship the banner's `T)assign` into the
calm band and quietly violate the "labels per canon" contract while still
passing any check that merely looks for the letters A, R and T.

# Scope -- the triad only

Canon's full band carries six tokens. This module emits **only the A/R/T
triad**: `^A)ode` is the Mode chord (ADR-002 / WO-P5-061-ENTRY) and
`L)chains` / `P panic` are the N5 operate-the-app cluster (WO-071). Those
are other WOs' tokens; a later WO extends the band additively rather than
this one guessing at their placement. `TEACH_TOKENS` is the seam that
makes that extension a list edit rather than a re-parse of a flat string.

# Labels only -- nothing here is wired

`A`/`R`/`T` are **not bound to any key handler on tip**, by design: the
wires are WO-067 (Record), WO-068 (Assign-Trigger) and WO-069 (Analyze).
This band names three moves the human *will* be able to make and stops
there, exactly as `stopbanner.py`'s band-3 does for the halt register.
`tests/test_cockpit_teachband.py` pins that separation mechanically --
the cockpit's `handle_key` must keep returning `None` for `A`, `R` and
`T` -- so a future wire cannot land silently without the pin that owns
its WO going red first.

That "advertises a key that does nothing yet" state is a deliberate,
WO-scoped intermediate, not an oversight: canon's calm band is part of
the surface's teaching function (the human learns the repertoire exists
before needing it), and the alternative -- hiding the affordances until
all three wires land -- would ship three separate surface changes instead
of one.

# Rendering contract

Plain strings and a tone NAME only; attribute resolution belongs to the
draw layer (`screens.py::_control_strip_segment_attr`), the same split
`arm.py` documents. The tone is `TEACH_TONE` -- canon: the hint band is
"right-aligned in **cyan** (`accent_attr`), the chrome accent -- it is
affordance chrome, not data" (`:229-231`), which is why it resolves to
the chrome attr rather than through the `ok`/`warn` badge path that the
seat and ARM chips use. It is chrome, so it is never reverse-video: the
badge treatment is canon's "selected/active" signal (`:179-181`) and this
band is neither.

`unicode_ok` is accepted for API uniformity with every sibling composer
in this package but has no effect: `visual-language.md §"Glyph / status-marker vocabulary"` lists
`KEY)verb` -> `KEY)verb` **(no swap)**, so the tokens are pure ASCII with
no Unicode twin to trade away on an 80-col non-UTF-8 terminal.

Hardening family (matches `arm.py`/`control_seat.py`/`stopbanner.py`):
never raises regardless of any argument's type or content.
"""

from __future__ import annotations

# WO-P5-071. Imported rather than re-spelled: the band and the key handler
# must never disagree about what the panic token says, and a second literal
# here is exactly how that drift starts (the `T)rigger`/`T)assign` split
# below is the same hazard, handled the same way -- by keeping each
# register's spelling in exactly one place).
from .autonomy_keys import HOLD_TOKEN, OFFER_TOKEN
from .chains import CHAINS_TOKEN
from .panic import PANIC_TOKEN
from .reflex_controls import REFLEX_TOKEN
from .rules_library import RULES_TOKEN

# Canon's standing-band spelling of the teach triad
# (`mode-line-and-teach-controls.md §"Mode line, healthy autopilot"`, `visual-language.md §"A calm cockpit reading (App healthy, nothing to see)"`).
#
# `T)rigger` -- NOT the banner's `T)assign`. See this module's docstring;
# the two registers are canon-distinct and `stopbanner.TEACH_LINE` owns
# the other one.
#
# A tuple, not a flat string, so later WOs extend a sequence instead of
# re-parsing prose.
#
# WO-P5-071: `P panic` joins the triad. WO-PLAY-REFLEX-AFFORDANCE /
# WO-PLAY-RULES-LIBRARY: `V)reflex` / `U)rules` before panic. WO-TEACHBAND-
# L-CHAINS: `L)chains` (imported CHAINS_TOKEN) immediately before panic so
# the shipped modal is discoverable. WO-PLAY-HELP-AUTONOMY-KEYS: `H)old?` /
# `O)ffer?` (`?` = confirm-not-auto) sit just before `L)chains`. `E)xplore`
# stays on the autonomy HELP one-liners (and the post-ensure "press E"
# offer) so the calm strip still fits a typical 120-col row. `^A)ode` stays
# out (Mode chord / ADR-002). Panic stays last (canon order).
TEACH_TOKENS: tuple[str, ...] = (
    "A)nalyze",
    "R)ecord",
    "T)rigger",
    REFLEX_TOKEN,
    RULES_TOKEN,
    HOLD_TOKEN,
    OFFER_TOKEN,
    CHAINS_TOKEN,
    PANIC_TOKEN,
)

# Two spaces between tokens -- canon renders the band that way in every
# example it gives (`:136`, `:220`, `visual-language.md §"A calm cockpit reading (App healthy, nothing to see)"`), and it is
# the same gap `arm.ARM_GAP` uses between chips.
TOKEN_GAP = "  "

# The tone NAME (not an attr) the draw layer resolves to canon's cyan
# chrome accent. A distinct name rather than `None`, because `None`
# already means "plain, uncolored" for the liveness cluster and the
# inter-chip separators -- the band must be cyan chrome, and reusing
# `None` would render it uncolored while looking correct in every
# segment-level test.
TEACH_TONE = "chrome"


def compose_teach_band(*, unicode_ok: object = True) -> str:
    """The standing A/R/T hint band as one plain string.

    Returns the joined ``TEACH_TOKENS`` band. `unicode_ok` is accepted and
    ignored (see the module docstring: `KEY)verb` has no Unicode twin).
    Never raises.
    """
    return TOKEN_GAP.join(TEACH_TOKENS)
