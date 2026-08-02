"""Pure FORMATIONS-panel composer for the trainer-cockpit left gutter
(WO-LEFT-GUTTER-NEST-FOCUS-FORMATIONS).

No ``curses`` import here on purpose — this module composes plain strings
only, mirroring ``tw2002_aiclient/cockpit/focus.py``'s discipline.

FORMATIONS lists discovered galaxy topologies by name with a short blurb
(`canon/surfaces/trainer-cockpit.md` "Left gutter": "`[FORMATIONS]` --
discovered galaxy topologies by name with a short blurb"). The daemon
``status`` verb may carry a nested ``formations_panel`` payload produced
by ``world_stats.WorldStats`` (dead-end-only items from the mapped warp
graph; see ``tw2002_aiclient/formations.catalog_world`` and
WO-FORMATIONS-CATALOG-PORT). Explore's ``find_formations`` intent routes
via the same catalogue through ``plan_find_formations``. This module is
the render layer only: absent/None/non-dict ``formations_panel``, empty
``items``, or items lacking a usable ``name`` render the single-line
honest-empty state — never a fabricated topology.

Status-dict field mapping. ``status`` is the daemon's ``status`` verb
response shape. FORMATIONS reads a nested ``status["formations_panel"]``
payload -- its own namespace, distinct from GOALS' flat ``formations_count``
field (GOALS answers "how many are known", FORMATIONS answers "which ones,
by name"):

| key                        | shape                                                |
|-----------------------------|-------------------------------------------------------|
| ``formations_panel``        | dict; absent/None/non-dict -> empty panel              |
| ``formations_panel.items``  | list of discovered-topology dicts                       |
| item ``name``                | str -- the topology's catalog name                     |
| item ``blurb``               | str or absent -- a short one-line description          |

A non-dict item entry -- or a dict-shaped one whose field access raises --
is dropped rather than rendered as a fabricated line, same "drop and don't
fabricate" discipline ``focus.py`` uses for a hostile candidate entry. An
item missing a usable ``name`` is dropped too (a formation the operator
cannot identify by name is not useful to list). This module never invents
a formation name, blurb, or count: an empty/malformed ``items`` list -- or
one where every item dropped -- renders the single-line honest-empty state
using canon's own literal (`canon/surfaces/trainer-cockpit.md` "Panel
states": "Empty panels state their emptiness honestly ... FORMATIONS shows
'(none yet — map warps)'"), never a fake count or placeholder topology.
"""

from __future__ import annotations

from .goals import _safe_list, _safe_str

# Canon-cited literal (see module docstring) -- FORMATIONS' own honest-empty
# marker, distinct from FOCUS/PRIORITIES' bare em-dash (``goals.
# UNKNOWN_DETAIL``) because canon names a FORMATIONS-specific string, not
# the generic filler every other panel shares.
EMPTY_FORMATIONS = "(none yet — map warps)"


def _clip(text: str, *, width: int) -> str:
    if width <= 0:
        return ""
    return text[:width]


def compose_formations_panel(status: dict | None, *, width: int) -> list[str]:
    """Compose the FORMATIONS panel's discovered-topology lines.

    Never raises regardless of ``status``'s shape or content. Reads
    ``status["formations_panel"]["items"]`` and renders one line per valid
    item as ``"<name> — <blurb>"`` (bare ``"<name>"`` when no blurb is
    given). Absent/None/non-dict ``status``, an absent/malformed
    ``formations_panel`` payload, an empty/malformed ``items`` list, or one
    whose every item lacked a usable name all render the single-line
    honest-empty state (``EMPTY_FORMATIONS``), never an invented topology.
    Every line is ``len(line) <= width`` (``width <= 0`` empties every line
    to ``""``, mirroring ``goals.py``/``focus.py``'s width-clip convention).
    """
    try:
        width = int(width)
    except (TypeError, ValueError):
        width = 0

    status = status if isinstance(status, dict) else {}
    payload = status.get("formations_panel")
    payload = payload if isinstance(payload, dict) else {}
    raw_items = _safe_list(payload.get("items"))
    items = [item for item in raw_items if isinstance(item, dict)]

    lines: list[str] = []
    for item in items:
        try:
            name = _safe_str(item.get("name"))
            blurb = _safe_str(item.get("blurb"))
        except Exception:
            # A dict-subclass whose own `.get()` raises is a dropped slot --
            # extends focus.py's own hostile-candidate-entry discipline.
            continue
        if name is None:
            continue
        text = f"{name} — {blurb}" if blurb else name
        lines.append(_clip(text, width=width))

    if not lines:
        return [_clip(EMPTY_FORMATIONS, width=width)]

    return lines
