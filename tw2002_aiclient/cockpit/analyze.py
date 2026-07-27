"""A Analyze overlay — WO-P5-069.

``A`` in the Play cockpit opens the teach overlay — an on-demand retrospective
pass that reads the current screen and will return a draft rule for the human
to approve (WO-P5-070 family).  A second ``A`` (or ``Esc``) closes it.

# What this is

Canon (``canon/surfaces/mode-line-and-teach-controls.md`` §A ~56-62):

    A — Analyze.  Invoke the retrospective AI teacher on the current
    screen / escalation moment.  The teacher reads the settled screen,
    parsed state, and surrounding ledger *after the fact* and returns
    a draft guarded rule for the human to approve, edit, or discard.
    On-demand only — the AI never proposes unless the human presses A.
    While a pass is open, the teach-overlay indicator shows on the mode
    line.

This module owns the OPEN/CLOSE state half — the boolean overlay gate
that ``screens.py`` reads to show the ``OVERLAY_LABEL`` badge and that
``app.py`` opens/closes on ``"analyze_open"``/``"analyze_close"`` actions.
The AI teacher content path (producing a draft rule from the settled
screen) is the follow-on work WO-P5-070 scopes.

# What this is NOT

- NOT on the live autopilot fire path.  :class:`AnalyzeSession` is
  inert — it cannot dispatch any keystroke to the game.
- NOT the draft→approve gate.  That is WO-P5-070.
- No live I/O of any kind — this module is pure state; the no-dispatch
  guarantee is structural.  The AI teacher is spectator-only
  (``canon/engine/ai-teacher.md``).
- No ``ensure_auto_arm`` calls of any kind — this module imports
  nothing from the daemon layer and nothing that touches a network
  connection or spawns a process.

# Overlay indicator

:data:`OVERLAY_LABEL` is the string shown on the control strip's
``teach_band`` slot while a pass is open.  The draw layer resolves it
with ``TEACH_TONE`` (cyan/``info``) via
:func:`~tw2002_aiclient.cockpit.control_seat.compose_control_strip_segments`
exactly as it does for the normal ``A)nalyze  R)ecord  T)rigger`` band —
no extra colour wiring is needed.

# Hardening

Never raises on any :class:`AnalyzeSession` public method call,
regardless of argument type — mirrors the family standard ``arm.py`` /
``assign_trigger.py`` / ``teachband.py`` / ``stopbanner.py``.
"""

from __future__ import annotations

__all__ = [
    "AnalyzeSession",
    "OVERLAY_LABEL",
]

# The mode-line overlay badge text — rendered in the control strip's
# ``teach_band`` slot (cyan/info tone) by ``screens.py``'s draw pass
# while ``AnalyzeSession.is_open`` is ``True``.
#
# Deliberately short: the band slot is width-contested and the label
# must fit alongside the liveness cluster at minimal tiers (≥82 inner
# cols, ``canon/surfaces/mode-line-and-teach-controls.md`` "Responsive
# fold").  ``[ ANALYZING ]`` is 13 chars — well within the ~30-col
# budget available after the liveness cluster and chips at 82 cols.
OVERLAY_LABEL = "[ ANALYZING ]"


class AnalyzeSession:
    """Tracks the open/closed state of one Analyze overlay pass.

    On-demand only: never opens without an explicit ``A`` press.

    The AI teacher is spectator-only — it reads the settled screen and
    ledger after the fact but never dispatches keystrokes to the game.
    No live I/O of any kind reaches this module; the no-dispatch
    guarantee is structural.

    Thread safety: not guaranteed — the cockpit runs on a single thread
    (the curses draw/input loop); no locking is added.

    Never raises on any public method call.
    """

    def __init__(self) -> None:
        self._open: bool = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """``True`` while an Analyze overlay pass is open."""
        return self._open

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open an Analyze overlay pass.

        Idempotent: calling while already open is a no-op.  Never
        raises.
        """
        self._open = True

    def close(self) -> None:
        """Close the Analyze overlay pass.

        Idempotent: calling while already closed is a no-op.  Never
        raises.
        """
        self._open = False
