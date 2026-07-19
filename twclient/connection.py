"""Raw socket telnet connection with a background reader thread.

One TelnetConnection = one telnet socket. The reader thread recv()s bytes,
runs them through the IAC handler (stripping negotiation, queuing replies),
feeds the clean data into pyte under `self.lock`, and stamps `last_rx` /
`rx_count` for the settle-detection layer. Anything touching the pyte
screen from another thread (the command-socket handler rendering a
response) must take the same lock.
"""

import socket
import threading
import time


class TelnetConnection:
    def __init__(self, host, port, terminal, negotiator, logger=None):
        self.host = host
        self.port = port
        self.terminal = terminal
        self.negotiator = negotiator
        self.logger = logger

        self.lock = threading.Lock()
        self.last_rx = time.monotonic()
        self.rx_count = 0
        self.connected = False

        self._sock = None
        self._reader_thread = None
        self._stop = threading.Event()

    def connect(self, timeout=10):
        self._sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self._sock.settimeout(None)
        self.connected = True
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _reader_loop(self):
        while not self._stop.is_set():
            try:
                data = self._sock.recv(4096)
            except OSError:
                break
            if not data:
                break
            if self.logger:
                self.logger.log_raw("RX", data)
            clean = self.negotiator.feed(data)
            pending = self.negotiator.pop_pending_output()
            with self.lock:
                if clean:
                    self.terminal.feed(clean)
                self.rx_count += len(data)
                self.last_rx = time.monotonic()
            if pending:
                self._send_raw(pending)
        self.connected = False

    def _send_raw(self, data: bytes):
        if not self._sock:
            return
        if self.logger:
            self.logger.log_raw("TX-IAC", data)
        try:
            self._sock.sendall(data)
        except OSError:
            pass

    def send_text(self, text: str, enter: bool = True, secret: bool = False):
        data = text.encode("utf-8", errors="replace")
        if enter:
            data += b"\r\n"
        if self.logger:
            if secret:
                self.logger.log_redacted("TX")
            else:
                self.logger.log_raw("TX", data)
        self._sock.sendall(data)

    def send_bytes(self, data: bytes):
        """Exact pass-through -- no text encoding, no auto-appended CRLF
        (unlike send_text()). Used for raw interactive keystrokes (`tw
        attach`), where the caller has already decided the exact wire
        bytes (e.g. a bare CRLF for Enter, an ANSI cursor escape for an
        arrow key)."""
        if self.logger:
            self.logger.log_raw("TX", data)
        self._sock.sendall(data)

    def close(self):
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
        self.connected = False
