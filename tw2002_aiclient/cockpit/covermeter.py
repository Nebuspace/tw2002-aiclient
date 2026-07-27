"""The coverage meter -- the App-vs-Human live share readout (WO-P5-072).

# What this measures

Canon (`canon/engine/coverage-metrics.md`) defines exactly one live share:

    coverage   = app / (app + human)
    escalation = human / (app + human)      # coverage's complement

`app` counts live keystrokes the taught app played deterministically (a
macro replaying, a guarded rule firing, a loop stepping); `human` counts
keystrokes the operator typed by hand -- every one an escalation.

# There is no AI slice, and that is load-bearing

**`ai` never appears in this denominator and never appears in the rendered
string.** Canon J1: there is no live `ai` sender, so the AI's live share is
*definitionally* zero. Rendering an "AI 0" slice would not be a harmless
extra zero -- it would reassert the AI-pilot framing the reborn vision
removed, by implying a third live driver that merely happens to be idle.
The AI's real contribution is *rule authorship*, measured on a separate
teaching-provenance axis (how many guarded rules it drafted that the human
approved), which is not a share of anything live and does not belong on
this widget.

The archive shipped the inverse of all of this and is the recorded
divergence, not a porting target: `spectate_layout.py:982`'s
`compute_autonomy_ratio()` computes `trainer / (ai + trainer)` -- AI *in*
the live denominator, human *excluded* from it -- and
`format_autonomy_counts()` renders `App N / AI N · Hum N`. Both the formula
and that string are what `trainer-cockpit.md`'s "Code divergence" section
records so that the port does not revive them. This module deliberately
shares no code with either.

# Why the label is `COV` and not the archive's `AUTO`

`coverage-metrics.md` spends its opening paragraph retiring the old
"autonomy ratio," and specifically the framing where "crossing 50%" meant
the trainer "flying itself" -- there is no graduation threshold in the
reborn metric, which is a *description* of a session, not a finish line.
`AUTO %` is the exact label that carried that reading. Canon's surface text
names the widget "the coverage / auto-% meter", so both words are live and
this is a judgement call rather than a canon requirement -- hence a single
module constant, cheap to flip if the hub prefers `AUTO`.

# Honest `?` -- the rule that matters most

`?` is rendered whenever the share is *undefined*, and the two ways it can
be undefined are kept distinct because they are different facts:

- **Counts unavailable** (no ledger, missing/ill-typed inputs) -> `COV ?`
  alone. We do not know how many keystrokes were sent, so we say nothing
  further.
- **Counts available but the window is empty** (`app == human == 0`) ->
  `COV ? · App 0 · Hum 0`. Here we *do* know the counts -- there genuinely
  were no live keystrokes -- but `0 / 0` is undefined, so the share stays
  `?` while the counts are reported honestly.

A zero-keystroke window must never render `COV 0%`. That would state that
the app carried none of the driving, which is a claim about a session that
did not happen.

**On tip this widget renders `COV ?` in the live product, always.** There is
no ledger in the tree (`PWO-025` is PARTIAL -- the lock and `VALID_SENDERS`
are live, but `LedgerWriter` / the attach ledger are still deferred in
`session/daemon.py`), so nothing can supply the counts. That is the
canon-mandated outcome -- "Honest `?` when shares unknown -- never invent"
-- and not a placeholder to be filled with a plausible-looking number. When
the ledger lands, the counts arrive through this module's existing keyword
arguments and nothing here changes.

Note that the legacy-actor mapping canon's "Code divergence" section warns
about (fold legacy `trainer` -> `app`, exclude legacy `ai` from the live
denominator) describes the *archive's* ledger. Tip's send choke point is
already clean -- `session/session.py:67` `VALID_SENDERS = ("app", "human")`
and a legacy sender raises, pinned by `tests/test_actor_attribution.py` --
so this module implements no mapping layer for an enum the live tree cannot
produce.

# Rendering contract

Plain strings only; no `curses` import, matching every sibling composer in
this package. The meter carries tone `None` (plain `A_NORMAL`) -- it is a
*data readout* like the liveness cluster, not a state chip (`ok`/`warn`/
`danger` badge treatment) and not affordance chrome (`teachband.TEACH_TONE`).

Under width pressure the meter is dropped **whole**, never truncated. This
is a stronger rule than the teach band's all-or-nothing drop and it exists
for a different reason: clipping a label yields an unreadable token, but
clipping a *number* yields a readable and wrong one -- `COV 75%` truncated
to `COV 7` reads as seven percent. A silent lie is worse than a missing
gauge, so the meter leaves the row rather than misreport.

Hardening family (matches `arm.py`/`strip.py`/`teachband.py`/
`control_seat.py`): never raises regardless of any argument's type or
content.
"""

from __future__ import annotations

# Canon's recast name for the widget; see the module docstring for why this
# is `COV` rather than the archive's `AUTO`. One constant so the hub can
# flip it in a single edit.
METER_LABEL = "COV"

# The honest-unknown glyph. `trainer-cockpit.md:417` ("Never lie, never
# invent") allows `?`, `—` or `off-map`; WO-P5-072's Accept names `?`
# explicitly, so `?` it is. Unlike `strip.py`'s two different fallbacks
# (identity vs game-letter) there is one kind of unknown here.
UNKNOWN = "?"

# Separator between the meter's fields. Same `·` the profile strip uses
# (`strip.SEP`) -- deliberately re-declared rather than imported, because a
# future canon change to the profile strip's separator must not silently
# restyle a different widget on a different row.
SEP = " · "

# Field labels. `App` and `Hum` mirror the archive's spelling so the
# operator's eye does not have to relearn two familiar tokens -- the
# divergence being closed is the *math* and the `AI` slice, not these two
# words.
APP_LABEL = "App"
HUMAN_LABEL = "Hum"

# The meter is a data readout, not a chip and not chrome: `screens.py::
# _control_strip_segment_attr` gives `ok`/`warn`/`danger` the reverse-video
# badge treatment and `teachband.TEACH_TONE` the cyan chrome accent, while
# anything else -- including `None` -- stays plain `A_NORMAL`. Liveness, the
# row's other data readout, is plain for the same reason.
METER_TONE = None


def _count(value: object) -> int | None:
    """Coerce one raw count to a non-negative `int`, or `None` for unknown.

    `bool` is rejected even though `isinstance(True, int)` holds: a `True`
    that reached a keystroke-count argument is a type error upstream, and
    silently reading it as the count `1` would render a confident,
    fabricated share. Every other non-`int` (including `float` -- row
    counts are whole) and every negative is likewise `None` rather than a
    guess. Never raises.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def coverage_percentages(*, app: object, human: object) -> tuple[int, int] | None:
    """The `(app_pct, human_pct)` pair, or `None` when the share is undefined.

    `app_pct` is canon's `coverage` (`app / (app + human)`) and `human_pct`
    is its complement, the escalation frequency -- two readings of one
    quantity, so they are computed from the same denominator and returned
    together.

    Returns `None` when either count is unavailable/ill-typed (see
    `_count`) **or** when both are zero: `0 / 0` is undefined, and a
    zero-keystroke window must not render as `0%`.

    The two percentages always sum to exactly 100, **by construction**:
    only `app_pct` is rounded, and the complement is obtained by
    subtracting it from 100. Rounding the two independently is the way to
    lose that, so the returned pair is deliberately derived rather than
    computed twice.

    (Round-half-to-even would in fact keep the sum at 100 even under
    independent rounding -- the two values can only straddle a `.5`
    boundary as `k + 0.5` and `(99 - k) + 0.5`, whose integer parts have
    opposite parity, so exactly one rounds up. That is a genuine second
    line of defence, but it is *not* what this function relies on, and
    saying otherwise would credit the guarantee to the wrong mechanism.
    The regression that actually breaks the sum is independent rounding
    *plus* `int(x + 0.5)`-style rounding together -- `1 app / 7 human`
    then renders `App 13% · Hum 88%` -- and that is the mutation
    `tests/test_cockpit_covermeter.py` was verified against.)

    The rounding rule itself is not pinned: canon specifies no tie-break,
    so `12.5% -> 12` versus `-> 13` is an arbitrary implementation choice,
    and a test asserting either would be pinning a decision canon never
    made.

    Never raises.
    """
    app_n = _count(app)
    human_n = _count(human)
    if app_n is None or human_n is None:
        return None
    total = app_n + human_n
    if total <= 0:
        return None
    app_pct = round(app_n * 100 / total)
    return app_pct, 100 - app_pct


def compose_coverage_meter(
    *,
    app: object = None,
    human: object = None,
    width: object = None,
    unicode_ok: object = True,
) -> str:
    """Compose the one-line coverage meter.

    Shapes, per the module docstring's honest-`?` rule:

    - counts known, window non-empty -> ``COV 75% · App 3 · Hum 1``
    - counts known, window empty     -> ``COV ? · App 0 · Hum 0``
    - counts unavailable             -> ``COV ?``

    `width`, when a positive `int`, is a hard budget: the meter returns
    `""` rather than a truncated string, because a clipped percentage is a
    wrong number rather than an unreadable one (module docstring). A
    `None`/absent/ill-typed `width` means "no budget" and the full string is
    returned.

    `unicode_ok` is accepted for uniformity with every sibling composer and
    is currently unused: the only non-ASCII character here is `·`, which
    `visual-language.md`'s glyph table lists as an explicit NO-SWAP row --
    it renders identically in ASCII mode, exactly as `strip.SEP` documents.

    Never raises, for any argument of any type.
    """
    app_n = _count(app)
    human_n = _count(human)
    pcts = coverage_percentages(app=app, human=human)

    if pcts is None:
        share = UNKNOWN
    else:
        share = f"{pcts[0]}%"

    parts = [f"{METER_LABEL} {share}"]
    # Counts ride along only when we actually have them. When they are
    # unavailable there is nothing honest to print beside the `?`, and
    # `App ? · Hum ?` would add three unknowns where one already said it.
    if app_n is not None and human_n is not None:
        parts.append(f"{APP_LABEL} {app_n}")
        parts.append(f"{HUMAN_LABEL} {human_n}")
    line = SEP.join(parts)

    if isinstance(width, bool) or not isinstance(width, int):
        return line
    if width <= 0 or len(line) > width:
        return ""
    return line
