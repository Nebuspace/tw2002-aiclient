"""Learned-loop (macro) library — read side, the module that plays, and the
module that writes.

WO-P2-G3 shipped the *list* surface: a read-only reader over the taught
macro store plus its pure composer. WO-P2-G4-X2 added the single-loop
*loader* -- read one taught macro by name and validate it for execution.
WO-P2-G4-X3 added ``player.py``, and it changed what this package is: the
player presses keys. WO-P2-G4-X6 adds ``recorder.py``: the store is no
longer an empty universe, because something can now WRITE a document the
loader loads and the player replays.

That is a real boundary crossing each time, so the pin this docstring used
to make ("nothing in this package can send a keystroke") is restated rather
than quietly kept. Three different guarantees now live here, and none is
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
* **``recorder`` writes files, but still cannot send at all.** It shares
  player's waiver to import ``classify``/``state_parser`` (deriving the
  same closed vocabularies, never restating them), but carries no send
  method, no session, and no wire access of any shape -- it turns an
  already-known (keystrokes, resulting screen) sequence into a stored
  document. A capture is authored by whatever already pressed the keys;
  this module only ever writes down what it is told.

All three clauses are enforced, not asserted.
``tests/test_loop_loader.py::test_the_read_modules_still_cannot_send_a_keystroke``
holds the strict pin (and fails on any NEW module here until someone
decides which pin it belongs under),
``tests/test_loop_player.py::test_the_player_reaches_the_wire_through_exactly_one_call``
pins the player's single send choke-point, the purity of the two modules it
is allowed to import, and the absence of any default session, and
``tests/test_loop_recorder.py::test_the_recorder_still_cannot_send_a_keystroke``
pins the same no-send guarantee for the writer, over the same shared
scanner.

Arming, bounding, or repeating a replay is the App Autopilot Model's job
and is still deliberately absent (``canon/architecture/app-autopilot-model.md``)
-- one invocation of the player is one pass over one taught macro. Wiring a
live human keystroke stream into the recorder (rather than an
already-captured manifest) is deliberately absent too -- see
``recorder.py``'s own docstring, "Capture-only, by construction and by
choice".
"""
