"""Thin `tw attach` input client — control-lock keystroke forwarder.

No curses / no screen paint (those wait on spectate F2). Opens a lifetime
daemon ``attach`` connection, forwards raw key bytes as JSON ``{"key": ...}``,
releases the lock when the socket closes.

Ported from archive ``interactive_app.AttachInputConn`` (WO-P2-OPS-VERB-F1).
"""

from __future__ import annotations

import json
import socket

DETACH_KEY = 29  # Ctrl-] — release control


class AttachInputConn:
    """Persistent socket dedicated to sending the operator's raw keystrokes
    to the daemon's ``attach`` verb."""

    def __init__(self, sock_path):
        self.sock_path = str(sock_path)
        self._sock = None
        self._file = None
        self.error = None

    def connect(self):
        """Send ``{"verb": "attach"}`` and wait for ack — this is when the
        control-lock is taken (or rejected)."""
        try:
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.connect(self.sock_path)
            self._file = self._sock.makefile("rwb")
            self._file.write((json.dumps({"verb": "attach", "args": {}}) + "\n").encode("utf-8"))
            self._file.flush()
            line = self._file.readline()
        except OSError as e:
            self.error = str(e)
            return False
        if not line:
            self.error = "no_response"
            return False
        try:
            resp = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as e:
            self.error = f"bad_response:{e}"
            return False
        if not resp.get("ok"):
            self.error = resp.get("error", "attach_rejected")
            return False
        return True

    def send_key(self, data: bytes):
        if self._file is None:
            return False
        try:
            self._file.write((json.dumps({"key": data.decode("latin-1")}) + "\n").encode("utf-8"))
            self._file.flush()
            line = self._file.readline()
            if not line:
                return False
            return bool(json.loads(line.decode("utf-8")).get("ok"))
        except (OSError, json.JSONDecodeError):
            return False

    def close(self):
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
