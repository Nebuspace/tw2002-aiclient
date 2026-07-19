"""Full session transcript logging (DESIGN.md §4 `history`, §12).

One append-only, human-readable log per daemon session at
`./logs/session-<ts>.log`. Structured recent-history (for `tw history`) is
kept separately, in-memory, by the daemon session — this module only owns
the raw RX/TX transcript.
"""

import os
import time


class TranscriptLogger:
    def __init__(self, log_dir, session_id=None):
        os.makedirs(log_dir, exist_ok=True)
        self.session_id = session_id or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        self.path = os.path.join(log_dir, f"session-{self.session_id}.log")
        self._fh = open(self.path, "a", buffering=1, encoding="utf-8", errors="replace")

    def log_raw(self, direction: str, data: bytes):
        if not data:
            return
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        text = data.decode("latin-1")
        self._fh.write(f"[{ts}] {direction} ({len(data)} bytes)\n{text}")
        if not text.endswith("\n"):
            self._fh.write("\n")

    def log_redacted(self, direction: str, note: str = "secret input redacted"):
        """Record that a send happened without persisting its content —
        for password entry (`tw do/send --secret`). No byte count is
        logged either, since that would leak input length."""
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._fh.write(f"[{ts}] {direction} <<{note}>>\n")

    def close(self):
        try:
            self._fh.close()
        except OSError:
            pass
