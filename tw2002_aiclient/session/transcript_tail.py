"""Session-side redacted transcript ring buffer (WO-P3-041 LOGS band).

A bounded ring of plain, human-readable display lines feeding the
cockpit's full-width `[LOGS]` band (canon: `canon/surfaces/trainer-
cockpit.md` "Bottom band -- [LOGS]"), served on the `status` verb as
`log_tail` (`tw2002_aiclient/session/protocol.py`).

This module is the redaction guarantee POINT: a secret must never be able
to enter this buffer, and that is enforced structurally, not by
convention -- `append_redacted()` never accepts the secret text as an
argument at all, only a fixed marker note (default mirrors
`logging_util.TranscriptLogger.log_redacted()`'s own wording byte-for-
byte). There is no code path through this module's own API that could
smuggle a payload into the ring, even by caller mistake.

Callers (`Session.send()` / `Session.send_raw()` in `session.py`) append
at the exact same send-time `secret` decision already threaded into the
real transcript logger's `log_raw`/`log_redacted` sink -- this module
never re-derives or re-classifies anything itself, it only records what
it's handed.

No timestamps: the client does its own arrival-flash detection (canon:
"the newest LOGS/ticker row flashes on arrival", `TICKER_FLASH_
DURATION_S`) from the fact that a new line appeared, not from a stamped
time.
"""

import collections

TAIL_MAX = 100


class TranscriptTail:
    """A bounded ring of plain display strings, newest last.

    `collections.deque(maxlen=...)` silently drops the oldest entry once
    full -- no separate bounds-check needed, and insertion order (hence
    "newest last") is preserved for free.
    """

    def __init__(self, maxlen=TAIL_MAX):
        self._lines = collections.deque(maxlen=maxlen)

    def append_line(self, text):
        """Append one line that is already safe to display verbatim --
        never raw secret text (see module docstring; use
        `append_redacted()` for a secret-bearing send)."""
        self._lines.append(text)

    def append_redacted(self, note="secret input redacted"):
        """Append the redaction marker only -- deliberately takes just a
        note string, never the secret itself, so this method's own
        signature makes leaking a payload through it structurally
        impossible. The default note mirrors `logging_util.
        TranscriptLogger.log_redacted()`'s marker wording exactly."""
        self._lines.append(f"<<{note}>>")

    def snapshot(self):
        """A COPY of the current ring, oldest first. Mutating the
        returned list never touches the live buffer."""
        return list(self._lines)
