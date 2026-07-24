"""Scripted spectate/watch FakeClient — Layer-B harness helper (WO-P3-HARNESS-REHAB D1 lane 2).

Daemon-free stand-in for a real SpectateClient / watch subscriber. Feeds a
caller-chosen list of watch-event dicts one at a time (with an optional
pause between each), then times out forever. Ported from the archive
inline FakeClient in ``test_spectate_app.py`` / ``test_spectate_autonomy_ledger.py``.

Isolation contract: never opens ``run/twd.sock``, never touches credentials,
never imports product cockpit chrome. Pair with ``tests.pty_helpers`` for
real-curses pty + pyte proofs.

Distinct from ``tests.fake_twgs.FakeTWGS`` (scripted telnet login server).
"""

from __future__ import annotations

import time
from typing import Any


class FakeClient:
    """Minimal watch-event client: ``next_event`` / ``close`` only.

    Parameters
    ----------
    events:
        Sequence of watch-event dicts (or any payloads the under-test
        render loop accepts). Fed in order; exhausted → timeout sleep +
        ``None``.
    gap_s:
        Wall-clock pause before each successful event yield. Lets the
        curses redraw settle between scripted frames (archive default
        was 0.3s for spectate, 0.25s for autonomy-ledger).
    """

    def __init__(self, events: list[Any] | tuple[Any, ...] | None = None, *, gap_s: float = 0.3):
        self._events = list(events or [])
        self._i = 0
        self.gap_s = gap_s

    def next_event(self, timeout: float = 0.1) -> Any | None:
        if self._i < len(self._events):
            if self.gap_s > 0:
                time.sleep(self.gap_s)
            event = self._events[self._i]
            self._i += 1
            return event
        time.sleep(min(timeout, 0.05))
        return None

    def close(self) -> None:
        pass

    @property
    def remaining(self) -> int:
        """Events not yet yielded (handy for assertions outside the loop)."""
        return max(0, len(self._events) - self._i)

    @property
    def exhausted(self) -> bool:
        return self._i >= len(self._events)
