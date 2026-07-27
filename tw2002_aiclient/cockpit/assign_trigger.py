"""Assign-Trigger scaffold — WO-P5-068.

``T`` in the Play cockpit binds the current screen to a macro stub: a
draft ``when(screen_match + guards) → do(macro)`` rule that the human
can refine and approve in a later WO (069/070 family).

# What this is

Canon (``canon/surfaces/mode-line-and-teach-controls.md`` §T ~67-70):

    T — Assign-Trigger.  Bind a screen-match + guards to a recorded macro,
    producing a proposed rule (``when(screen_match + guards) → do(macro)``).
    Assigning a trigger drafts the rule; it does not arm it to fire.

This module owns the SCAFFOLD half — the ``when + guards`` schema factory
and an in-memory stub store.  The full rule engine (``do(macro)``
wiring, approval gate, live execution path) is Phase 6 / WO-070 family
and is **deliberately absent** here.

# What this is NOT

- NOT on the live autopilot fire path.  The stub is inert — it cannot
  dispatch any keystroke to the game.
- NOT a replay source.  ``StubStore.get()`` is read-only inspection only.
- NOT the macro recorder — that is WO-067 (``R``).  The ``do`` field is
  ``None`` until a future WO wires the macro.
- No live I/O of any kind — this module is pure schema + data; the
  no-dispatch-path guarantee is structural.

# Schema

``create_stub`` returns::

    {
        "when": {
            "screen": "<classification or empty string>",
            "guards": []
        },
        "do": None
    }

``"screen"`` is the classification name the daemon assigned to the
settled screen when ``T`` was pressed (sourced from ``ensure_session``'s
``result.classification`` on tip — the most recent confirmed class the
product has).  ``"guards"`` is an open list for future condition atoms;
this WO leaves it empty.  ``"do"`` is ``None``: no macro is attached yet.

# Hardening

Never raises, regardless of any argument's type — mirrors the family
standard ``arm.py`` / ``teachband.py`` / ``stopbanner.py`` establish.
"""

from __future__ import annotations


# --------------------------------------------------------------------------
# Schema factory
# --------------------------------------------------------------------------

def create_stub(screen_class: object = None) -> dict:
    """Return a fresh when+guards stub for ``screen_class``.

    ``screen_class`` is the settled screen's classification string (e.g.
    ``"main_command"``).  A ``None`` or non-``str`` value degrades to
    ``""`` — honest absence of information beats a wrong value, same
    posture the whole cockpit family uses for hostile inputs.

    The returned dict is:

        {"when": {"screen": "<class>", "guards": []}, "do": None}

    The ``"guards"`` list is always empty at scaffold time — guard atoms
    are Phase 6 territory.  ``"do"`` is ``None`` — no macro is attached
    until WO-070 wires the approval gate.

    Never raises.
    """
    safe_class = screen_class if isinstance(screen_class, str) else ""
    return {
        "when": {
            "screen": safe_class,
            "guards": [],
        },
        "do": None,
    }


# --------------------------------------------------------------------------
# In-memory stub store
# --------------------------------------------------------------------------

class StubStore:
    """Minimal in-memory holder for the most-recently assigned trigger stub.

    One slot only (scaffold-era): pressing ``T`` replaces the previous
    draft with a fresh one for the current screen.  The full rule engine
    (Phase 6) will graduate this to a keyed store; until then a single
    slot matches the UX ("the trigger I just taught") without inventing
    persistence logic that Phase 6 will replace anyway.

    Thread safety: not guaranteed — the cockpit runs on a single thread
    (the curses draw/input loop); no locking is added.

    Never raises on any public method call.
    """

    def __init__(self) -> None:
        self._stub: dict | None = None

    def set(self, stub: object) -> None:
        """Replace the current stub.

        Accepts only a ``dict`` — any other type is silently dropped
        (honest absence beats a wrong value, same posture ``create_stub``
        uses for its own input).  Never raises.
        """
        if isinstance(stub, dict):
            self._stub = stub

    def get(self) -> dict | None:
        """Return the current stub, or ``None`` if none has been set yet.

        Read-only inspection only — does not clear the slot.  Never
        raises.
        """
        return self._stub

    def clear(self) -> None:
        """Remove the current stub (session teardown / test reset).

        Never raises.
        """
        self._stub = None
