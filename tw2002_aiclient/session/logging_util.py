"""Full session transcript logging.

One append-only, human-readable log per daemon session at
`./logs/session-<ts>.log` (project-rooted `logs/` -- see `env.LOG_DIR`).
Structured recent-history (for `tw history`) is kept separately, in-
memory, by the daemon session -- this module only owns the raw RX/TX
transcript.
"""

import os
import time


class TranscriptLogger:
    def __init__(self, log_dir, session_id=None):
        os.makedirs(log_dir, exist_ok=True)
        self.session_id = session_id or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        self.path = os.path.join(log_dir, f"session-{self.session_id}.log")
        # Chmod 600 from creation (mirrors protocol.py::_save_password()) --
        # the transcript can carry a leaked password on a TWGS server that
        # fails to suppress echo on a password prompt, so it gets the same
        # owner-only protection as secrets.json rather than umask-default
        # 0644 world-readable.
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        self._fh = os.fdopen(fd, "a", buffering=1, encoding="utf-8", errors="replace")
        os.chmod(self.path, 0o600)  # re-assert even if the file pre-existed looser

    def log_raw(self, direction: str, data: bytes):
        if not data:
            return
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        text = data.decode("latin-1")
        self._fh.write(f"[{ts}] {direction} ({len(data)} bytes)\n{text}")
        if not text.endswith("\n"):
            self._fh.write("\n")

    def log_redacted(self, direction: str, note: str = "secret input redacted"):
        """Record that a send happened without persisting its content --
        for password entry (`tw do/send --secret`). No byte count is
        logged either, since that would leak input length. This is the
        one redaction sink every password-bearing send routes through
        (see `canon/doctrine/secrets-and-credentials.md`) -- a password
        must never reach `log_raw()`."""
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._fh.write(f"[{ts}] {direction} <<{note}>>\n")

    def log_note(self, note: str):
        """A single operator-visible diagnostic line in the transcript --
        e.g. a swallowed-but-not-silent side-effect failure that must
        never fail the caller's response but also must never vanish with
        zero trace. Not a structured log level -- this project has no
        logging framework; one plain timestamped line follows the exact
        idiom `log_raw`/`log_redacted` already establish for this
        transcript."""
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._fh.write(f"[{ts}] NOTE {note}\n")

    def close(self):
        try:
            self._fh.close()
        except OSError:
            pass
