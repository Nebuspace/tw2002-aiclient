"""Pure LOGS-band composer for the trainer-cockpit bottom transcript tail
(WO-P3-041, canon `trainer-cockpit.md` "Bottom band" + "Liveness & motion").

No ``curses`` import here on purpose -- mirrors ``tw2002_aiclient/cockpit/
hud.py`` / ``goals.py`` / ``focus.py`` / ``decisions.py`` / ``liveness.py``'s
pure-composer discipline: this module composes plain strings (plus a small
pure flash-timing decision) only -- curses/attribute handling belongs to
``screens.py``'s draw call, through ``cockpit.draw.draw_lines_attrs``.

LOGS is the cockpit's bottom full-width band, "the running session
transcript tail" (`trainer-cockpit.md` "Bottom band"). Before this WO the
box showed a single line -- ``PlayShellScreen.status_line``, an app.py-owned
ensure-session progress/error string, entirely local to this client
process. This WO adds the daemon's own advancing, pre-redacted transcript
(``status["log_tail"]``) as the box's PRIMARY content; ``status_line``
becomes a fallback only, shown while no real daemon tail exists yet (see
``screens.py``'s own wiring comment for that decision -- this composer
itself knows nothing of ``status_line``, which never reaches this module).

Upstream payload contract (WO-P3-041 dispatch -- landing concurrently with
the session-side sibling WO that produces it; **this composer DEFINES the
contract**, mirroring ``hud.py``/``liveness.py``'s own in-module contract
definitions so the eventual wire bridge needs zero composer rework)::

    status["log_tail"] = [<str>, <str>, ...]   # newest LAST

Every entry is **pre-redacted at insertion, session-side** -- a secret send
never reaches this list as plaintext; a redacted send instead appears as
the marker text ``"<<secret input redacted>>"`` (``tw2002_aiclient.session.
transcript_tail.TranscriptTail.append_redacted()``'s own default wire
format -- see [secrets-and-credentials](/doctrine/secrets-and-credentials.md)).
This
module trusts that upstream guarantee for CONTENT (it never attempts to
detect or scrub secrets itself -- that would be a second, weaker redaction
point, and doctrine puts the ONE guarantee at the insert), but treats every
entry as untrusted DISPLAY text the same way every sibling composer treats
its own free-text fields: no control-character neutralization or
cell-width clipping happens here -- ``cockpit.draw.draw_lines_attrs``'s
``_safe_write``/``_clip_cells`` choke point (already proven against
CJK-heavy and embedded-``\\n`` payloads, ``tests/test_cockpit_frame_pty.py``)
is the one place that hazard is handled, for every panel including this
one.

Fit (canon "Responsive fold" / this WO's dispatch): the tail is
newest-last -- displayed lines keep that same top-to-bottom
oldest-to-newest order, clipped to the available ``height`` by dropping the
OLDEST entries first (``entries[-height:]``), so the visible window always
ends on the newest line. When there is less real content than ``height``,
the returned list is simply shorter (no blank-padding) -- the natural
top-anchored fill of a growing transcript, not a fixed-field panel like
HUD/GOALS. Honest-empty (`trainer-cockpit.md` "Panel states"): no real tail
renders the sticky ``LOGS_EMPTY`` marker, one line, matching every other
panel's "empty panels state their emptiness honestly" convention.
``height <= 0`` returns ``[]`` (nothing fits, not even the honest-empty
line); ``width <= 0`` returns the SAME line count the identical call would
otherwise produce, each emptied to ``""`` (mirroring
``goals.py``/``hud.py``/``liveness.py``'s own width-clip convention).

Hardening family (matches ``hud.py``/``goals.py``/``liveness.py``): never
raises regardless of ``status``'s shape or content. A non-dict ``status``
(including ``None``) or a non-list/tuple ``status["log_tail"]`` both count
as "no real tail" (honest-empty / ``status_line``-fallback territory, per
``newest_tail_entry`` below). Each entry is independently coerced -- a
non-``str`` entry (e.g. an ``int``) is rendered via ``str()``; an entry
whose coercion raises (a hostile object, including a raising ``dict``
subclass's own ``__str__``/``__repr__``) is DROPPED, never rendered as a
placeholder and never crashing the composer, matching ``goals.py``'s
``_safe_sector_token`` per-item containment. ``None`` entries are also
dropped (not coerced to the literal text ``"None"``). Width/height
coercion also catches ``OverflowError`` (``int(float("inf"))``), the same
JSON-``Infinity`` landmine every sibling composer in this package guards.
The top-level ``status``/``status["log_tail"]`` payload itself being a
hostile ``dict``/``list`` subclass (raising ``.get()``/iteration) is out of
contract, matching every sibling composer's own top-level trust boundary --
the daemon's real wire payload is always plain ``json.loads()`` output.

Newest-row flash (canon "Liveness & motion": "the newest LOGS/ticker row
flashes on arrival, ``TICKER_FLASH_DURATION_S = 1.0``" -- **not**
``CREDIT_FLASH_DURATION_S`` (1.5), which the WO-P3-041 dispatch mis-cited
for this row; that constant belongs to the CREDITS delta-chip, a different
cue entirely, per `trainer-cockpit.md`'s own "Liveness & motion" table,
which lists both constants on separate lines). This module has no clock
and no draw-to-draw memory (mirroring every sibling pure composer), so
arrival TRACKING is necessarily ``screens.py``'s own instance state
(content-identity comparison across ``draw()`` calls, using the same
``now_fn`` clock seam WO-P3-038 already wired for the control strip); this
module supplies the two pure primitives that state needs:
``newest_tail_entry`` (the content-identity key to compare draw-to-draw)
and ``flash_active`` (the age-vs-duration decision, Layer-A testable
independent of any real clock or curses).

D5: no ``ai_pilot``/imperative-mood text anywhere -- this module renders a
read-only transcript observation, never a command.
"""

from __future__ import annotations

import math

# Canon "Panel states" honest-empty convention -- "empty panels state their
# emptiness honestly rather than vanishing" -- ported verbatim from the
# pre-WO screens.py module-level ``_LOGS_EMPTY`` this composer now
# supersedes as the canonical home for the marker (``screens.py`` imports
# it from here rather than keeping its own copy).
LOGS_EMPTY = "(none yet)"

# Canon `trainer-cockpit.md` "Liveness & motion" table: "ticker flash |
# newest LOG row bold, TICKER_FLASH_DURATION_S = 1.0". Ported verbatim --
# see the module docstring's correction note on the dispatch's mis-cited
# CREDIT_FLASH_DURATION_S (that constant is 1.5 and belongs to the CREDITS
# delta-chip, an unrelated cue).
TICKER_FLASH_DURATION_S: float = 1.0


def _coerce_width_height(value: object) -> int:
    """Same broadened-except family every sibling composer's own width
    coercion uses: ``int(float("inf"))`` raises ``OverflowError``, not
    ``TypeError``/``ValueError``, and ``json.loads()`` accepts a bare
    ``Infinity`` literal by default, so a hostile wire ``width``/``height``
    can legitimately be that exact float."""
    try:
        return int(value)
    except Exception:
        return 0


def _coerce_entry(value: object) -> str | None:
    """Best-effort per-entry text coercion for one ``log_tail`` item.

    ``None`` is dropped (not rendered as the literal text ``"None"``). A
    real ``str`` is returned verbatim -- no stripping, no re-formatting;
    transcript content is displayed as-is (control-char neutralization is
    the draw layer's job, see the module docstring). Any other value is
    coerced via ``str()``; a hostile object whose ``__str__``/``__repr__``
    itself raises is DROPPED rather than crashing this composer or
    surfacing a placeholder -- the same per-item containment
    ``goals.py``'s ``_safe_sector_token`` uses for one hostile sector
    entry."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:
        return None


def _coerce_tail(raw: object) -> list[str]:
    """A real ``list``/``tuple`` is the only shape trusted as a tail --
    anything else (missing, ``None``, a stray string/dict/int in this
    slot) degrades to an empty tail rather than being iterated
    character-by-character or raising, mirroring ``goals.py``'s
    ``_safe_list``. Each surviving entry has already passed
    ``_coerce_entry``; hostile/unparsable entries are silently absent from
    the result, never replaced with a placeholder -- so the returned list
    length can be shorter than the raw payload's, by design."""
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[str] = []
    for item in raw:
        text = _coerce_entry(item)
        if text is not None:
            out.append(text)
    return out


def newest_tail_entry(status: dict | None) -> str | None:
    """The coerced text of the newest (last) ``log_tail`` entry, or
    ``None`` when there is no real tail to speak of -- a non-dict
    ``status``, a missing/non-list ``status["log_tail"]``, an empty list,
    or a list whose every entry was hostile/unparsable all collapse to
    this same ``None``.

    This is the pure identity key ``screens.py`` compares draw-to-draw to
    decide whether a NEW line has arrived (content identity, not just a
    length check -- see the module docstring's newest-row-flash section);
    it is also the exact signal ``screens.py`` uses to decide whether the
    box's honest-empty/``status_line`` fallback applies -- this function
    and ``compose_logs_lines``'s own honest-empty branch both key off the
    identical ``_coerce_tail`` check, so the two stay in lockstep by
    construction.

    Never raises regardless of ``status``'s shape or content."""
    status = status if isinstance(status, dict) else {}
    tail = _coerce_tail(status.get("log_tail"))
    return tail[-1] if tail else None


def flash_active(
    arrival_s: object, *, now: object, duration_s: float = TICKER_FLASH_DURATION_S
) -> bool:
    """Pure age-vs-duration decision for the newest-row flash: ``True`` iff
    ``arrival_s`` is a real, finite reading and
    ``0 <= (now - arrival_s) < duration_s``.

    ``arrival_s`` is ``None`` (never observed an arrival -- e.g. no real
    tail yet, or a caller's own fresh instance state) whenever there is
    nothing to flash; this is the CALLER's own state, not read from a
    ``status`` payload, so this function takes it directly rather than a
    dict, unlike every other public function in this module.

    Never raises: unparsable/non-finite ``arrival_s`` or ``now`` (``None``,
    a string, a hostile ``__float__``) degrade to ``False`` (no flash)
    rather than crashing or guessing recency. A ``now`` EARLIER than
    ``arrival_s`` (a clock that moved backward between draws) also
    degrades to ``False`` -- age must be a real non-negative duration to
    count as "just arrived", mirroring every sibling composer's own
    negative-age handling (never renders a fabricated freshness signal
    from an impossible reading). A hostile/non-finite ``duration_s``
    degrades to the module default rather than comparing against garbage."""
    if arrival_s is None:
        return False
    try:
        arrival = float(arrival_s)
        now_val = float(now)
    except Exception:
        return False
    if not (math.isfinite(arrival) and math.isfinite(now_val)):
        return False
    age = now_val - arrival
    if age < 0:
        return False
    try:
        duration = float(duration_s)
    except Exception:
        duration = TICKER_FLASH_DURATION_S
    if not math.isfinite(duration):
        duration = TICKER_FLASH_DURATION_S
    return age < duration


def compose_logs_lines(status: dict | None, *, width: int, height: int) -> list[str]:
    """Compose the LOGS band's visible lines: the daemon's advancing
    ``status["log_tail"]``, newest-last, clipped to ``height`` by dropping
    the OLDEST entries first so the bottom line is always the newest one --
    or the honest-empty ``[LOGS_EMPTY]`` single line when there is no real
    tail (see ``newest_tail_entry``). ``screens.py`` layers its own
    ``status_line`` fallback ON TOP of this honest-empty case (see that
    module's wiring comment); this composer itself knows nothing of
    ``status_line`` -- it is a local app.py concept, not part of the
    daemon wire payload this module reads.

    ``height <= 0`` returns ``[]`` (nothing fits, not even the
    honest-empty line). ``width <= 0`` returns the SAME number of lines
    the identical call would otherwise produce, each emptied to ``""`` --
    mirroring ``goals.py``/``hud.py``/``liveness.py``'s own width-clip
    convention (a caller can always rely on the line COUNT reflecting real
    content presence, independent of whether width happens to be
    non-positive).

    Never raises regardless of ``status``'s shape or content, or
    ``width``/``height``'s type (see the module docstring's
    hardening-family section)."""
    width = _coerce_width_height(width)
    height = _coerce_width_height(height)
    if height <= 0:
        return []

    status = status if isinstance(status, dict) else {}
    entries = _coerce_tail(status.get("log_tail"))

    if not entries:
        lines = [LOGS_EMPTY]
    elif len(entries) > height:
        lines = entries[-height:]
    else:
        lines = list(entries)
    lines = lines[:height]

    if width <= 0:
        return ["" for _ in lines]
    return [line[:width] for line in lines]
