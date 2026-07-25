"""Learned-loop (macro) library — read side.

WO-P2-G3 ships the *list* surface only: a read-only reader over the taught
macro store plus its pure composer. Arming, replaying, or looping any of
these rows is the App Autopilot Model's job and is deliberately absent here
(WO-P2-G4 / ``canon/architecture/app-autopilot-model.md``) -- nothing in this
package can send a keystroke.
"""
