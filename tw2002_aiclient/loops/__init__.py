"""Learned-loop (macro) library — read side, plus the one module that plays.

WO-P2-G3 shipped the *list* surface: a read-only reader over the taught
macro store plus its pure composer. WO-P2-G4-X2 added the single-loop
*loader* -- read one taught macro by name and validate it for execution.
WO-P2-G4-X3 adds ``player.py``, and it changes what this package is: the
player presses keys.

That is a real boundary crossing, so the pin this docstring used to make
("nothing in this package can send a keystroke") is restated rather than
quietly kept. Two different guarantees now live here, and neither is
weaker than what it replaced:

* **The read modules -- ``store``, ``loader``, ``list_view`` -- still
  cannot send at all.** They may not import ``session``, a socket, or any
  transport, so they cannot reach the game however they name their
  variables. Loading is not playing, and the structure is what keeps the
  two apart.
* **``player`` can send, through exactly one call site, on a session its
  CALLER hands it.** It imports no transport and constructs no session; it
  imports two provably pure modules from ``session/`` (``classify`` and
  ``state_parser``) for the closed vocabularies canon requires it to derive
  rather than restate, and it reaches the wire only through an injected
  :class:`~tw2002_aiclient.loops.player.ReplaySession`. Nothing in this
  package can acquire a way to press keys; the player can only be given
  one.

Both clauses are enforced, not asserted.
``tests/test_loop_loader.py::test_the_read_modules_still_cannot_send_a_keystroke``
holds the strict pin (and fails on any NEW module here until someone
decides which pin it belongs under), and
``tests/test_loop_player.py::test_the_player_reaches_the_wire_through_exactly_one_call``
pins the player's single send choke-point, the purity of the two modules it
is allowed to import, and the absence of any default session.

Arming, bounding, or repeating a replay is the App Autopilot Model's job
and is still deliberately absent (``canon/architecture/app-autopilot-model.md``)
-- one invocation of the player is one pass over one taught macro.
"""
