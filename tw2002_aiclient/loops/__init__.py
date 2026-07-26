"""Learned-loop (macro) library — read side.

WO-P2-G3 ships the *list* surface only: a read-only reader over the taught
macro store plus its pure composer. WO-P2-G4-X2 adds the single-loop
*loader* -- read one taught macro by name and validate it for execution.
Arming, replaying, or looping any of these is the App Autopilot Model's job
and is deliberately absent here (``canon/architecture/app-autopilot-model.md``)
-- nothing in this package can send a keystroke.

That last clause is enforced, not merely asserted:
``tests/test_loop_loader.py::test_the_loops_package_still_cannot_send_a_keystroke``
scans every module here for a send-capable symbol AND for any import of
``session`` or a socket -- a package that cannot reach the transport cannot
drive the game through it, whatever it names its variables. Loading is not
playing, and the structure is what keeps the two apart.
"""
