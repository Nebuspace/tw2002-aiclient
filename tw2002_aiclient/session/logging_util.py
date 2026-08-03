"""Full session transcript logging.

One append-only, human-readable log per daemon session at
`./logs/session-<ts>.log` (project-rooted `logs/` -- see `env.LOG_DIR`).
Structured recent-history (for `tw history`) is kept separately, in-
memory, by the daemon session -- this module only owns the raw RX/TX
transcript.

RX writes (PWO-111) reuse the same password-anchor / ``secret=True``
vocabulary as TX and ``ledger.extract_prompt``: either a pending secret
send or a ``password``-shaped chunk routes to ``log_redacted``, never
``log_raw``. Live screen paint remains a separate surface.
"""

import os
import re
import time

# Byte-identical to ``ledger._PASSWORD_PROMPT_RE`` — one vocabulary, two
# sinks. Do not widen this without a fresh hub GO (Propose B scope pin).
_PASSWORD_PROMPT_RE = re.compile(r"password", re.I)


def should_redact_rx(text: str, *, secret_pending: bool) -> bool:
    """TX-vocabulary gate for RX transcript writes (PWO-111).

    ``secret_pending`` mirrors a prior ``secret=True`` operator TX (echo
    window). Password-anchor match is the same ``password`` RE ledger uses
    on prompts. Additive only — never un-redacts.
    """
    return bool(secret_pending) or bool(_PASSWORD_PROMPT_RE.search(text))


class TranscriptLogger:
    def __init__(self, log_dir, session_id=None):
        os.makedirs(log_dir, exist_ok=True)
        self.session_id = session_id or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        self.path = os.path.join(log_dir, f"session-{self.session_id}.log")
        # Chmod 600 from creation (mirrors protocol.py::_save_password()) --
        # defense in depth even after RX redaction: residual live-paint /
        # non-matching frames still get owner-only protection rather than
        # umask-default 0644 world-readable.
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
        """Record that a TX/RX happened without persisting its content --
        for password entry (`tw do/send --secret`) and for RX chunks that
        match the password-anchor / post-secret gate. No byte count is
        logged either, since that would leak input length. This is the
        one redaction sink every password-bearing transcript write routes
        through (see `canon/doctrine/secrets-and-credentials.md`) -- a
        password must never reach `log_raw()`."""
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._fh.write(f"[{ts}] {direction} <<{note}>>\n")

    def close(self):
        try:
            self._fh.close()
        except OSError:
            pass
