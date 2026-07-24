"""Pure GAME-viewport paint composer (WO-P4-052, canon
``canon/surfaces/trainer-cockpit.md`` GAME viewport description).

No ``curses`` import here on purpose -- mirrors every sibling composer's
(``cockpit/goals.py``, ``cockpit/logsband.py``, ``cockpit/hud.py``, ...)
pure-composer discipline: this module turns a ``WatchFeed`` settle-edge
event into plain display strings only. Control-character neutralization and
cell-width-aware clipping are the draw layer's job (``cockpit.draw.
draw_lines``'s ``_safe_write``/``_clip_cells`` choke point) -- this module
does a plain code-point ``[:width]`` slice, same convention
``goals.py``'s ``_row`` and ``logsband.py``'s ``compose_logs_lines`` already
use, and never sanitizes control characters itself.

Upstream payload contract (WO-P4-050's ``WatchFeed``, ``tw2002_aiclient/
watchfeed.py``): ``event`` is a ``protocol.build_response()``-shaped dict --
this composer reads only its ``"screen"`` key, a list of row strings
straight from ``session.render()`` -> ``terminal.render_cropped()``
(trailing blank rows/columns trimmed, LEADING blanks preserved -- so
``cropped(0, 0) == native(0, 0)``, top-left anchored, no offset math needed
here or by the caller).

Trust boundary (matches every sibling composer's own "hostile top-level
payload is out of contract" convention, e.g. ``logsband.py``'s module
docstring): a non-dict ``event`` (including ``None``), a missing/non-list/
non-tuple ``event["screen"]``, or a ``screen`` list containing so much as
ONE non-``str`` row all degrade this composer to an honest EMPTY result
(``[]``) -- never a placeholder, never fake content, never a raise. This is
stricter than ``logsband.py``'s own per-entry coercion (a single hostile
``log_tail`` entry there is dropped, not fatal to the whole tail): a screen
GRID's rows are positionally meaningful relative to each other in a way a
flat transcript's entries are not, so one malformed row invalidates the
whole grid rather than silently reflowing it. A hostile ``dict``/``list``
subclass whose ``.get()``/iteration itself raises is out of contract, same
as every sibling composer -- the daemon's real wire payload is always a
plain ``json.loads()`` object.

Height clipping is TOP-DROP -- a RULED policy, not a per-call choice, and
deliberately the opposite of the archive's ``spectate_layout.py`` (which
dropped from the BOTTOM): when there are more rows than fit, this composer
keeps the LAST ``height`` rows. The bottom row of a live TradeWars screen is
the command prompt -- the row an operator most needs to see under height
pressure -- so overflow sheds from the TOP instead. The drop happens in
exactly this one place (``compose_viewport_lines``'s own slice) so a unit
test can pin it directly.

``width <= 0``/``height <= 0`` both return ``[]`` -- nothing fits, matching
``logsband.py``'s own ``height <= 0`` convention (unlike ``logsband.py``'s
``width <= 0`` branch, which still returns the same line COUNT emptied to
``""``: a screen grid has no honest-empty marker line of its own to
preserve the count of, so collapsing straight to ``[]`` is the simpler,
equally-honest choice here).
"""

from __future__ import annotations


def _coerce_dim(value: object) -> int:
    """Same broadened-except family every sibling composer's own width/
    height coercion uses (see ``logsband.py``'s ``_coerce_width_height``):
    ``int(float("inf"))`` raises ``OverflowError``, not ``TypeError``/
    ``ValueError``, and ``json.loads()`` accepts a bare ``Infinity`` literal
    by default, so a hostile wire ``width``/``height`` can legitimately be
    that exact float."""
    try:
        return int(value)
    except Exception:
        return 0


def _coerce_screen_rows(event: object) -> list[str]:
    """Extract ``event["screen"]`` as a list of ``str`` rows, or ``[]`` for
    anything unusable -- see the module docstring's trust-boundary section
    for why a single non-``str`` row invalidates the WHOLE grid rather than
    being dropped in isolation."""
    if not isinstance(event, dict):
        return []
    raw = event.get("screen")
    if not isinstance(raw, (list, tuple)):
        return []
    rows: list[str] = []
    for row in raw:
        if not isinstance(row, str):
            return []
        rows.append(row)
    return rows


def compose_viewport_lines(event: dict | None, *, width: int, height: int) -> list[str]:
    """Compose the GAME viewport's visible interior lines from the latest
    ``WatchFeed`` settle-edge ``event``.

    Never raises regardless of ``event``'s shape or content, or ``width``/
    ``height``'s type (see the module docstring's hardening-family
    section). Returns ``event["screen"]`` clipped to ``height`` rows
    (TOP-DROP -- keeps the LAST ``height`` rows, see module docstring) and
    each surviving row clipped to ``width`` code points; ``[]`` whenever
    there is nothing usable to show.
    """
    width = _coerce_dim(width)
    height = _coerce_dim(height)
    if height <= 0 or width <= 0:
        return []

    rows = _coerce_screen_rows(event)
    if not rows:
        return []

    # TOP-DROP: keep the LAST `height` rows -- a no-op slice when there are
    # already <= height rows (the "exactly-fitting"/"under height" cases).
    rows = rows[-height:]
    return [row[:width] for row in rows]
