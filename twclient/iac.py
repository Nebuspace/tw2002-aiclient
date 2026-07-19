"""Telnet IAC (Interpret As Command) handling.

Python 3.13+ removed `telnetlib` from the standard library, so this is a
small hand-rolled state machine over raw bytes. It does two jobs:

1. Strip IAC command/subnegotiation sequences out of an inbound byte
   stream, leaving only the data pyte should see.
2. Answer option negotiation (WILL/WONT/DO/DONT) and the TTYPE/NAWS
   subnegotiations a TWGS door expects, queuing the reply bytes for the
   caller to send back on the socket.

The state machine persists across calls to `feed()`, so an IAC sequence
split across two recv() calls is handled correctly.
"""

IAC = 255
DONT = 254
DO = 253
WONT = 252
WILL = 251
SB = 250
SE = 240

# Options we care about.
BINARY = 0
ECHO = 1
SGA = 3
TTYPE = 24
NAWS = 31

TTYPE_IS = 0
TTYPE_SEND = 1

_STATE_DATA = "data"
_STATE_IAC = "iac"
_STATE_CMD_OPTION = "cmd_option"
_STATE_SB = "sb"
_STATE_SB_IAC = "sb_iac"


class TelnetHandler:
    """Feed it raw inbound bytes; get clean data back; pop queued replies."""

    def __init__(self, terminal_type=b"ANSI", width=80, height=25):
        self.terminal_type = terminal_type
        self.width = width
        self.height = height
        self._state = _STATE_DATA
        self._pending_cmd = None
        self._sb_buf = bytearray()
        self._out = bytearray()

    def feed(self, chunk: bytes) -> bytes:
        """Consume raw bytes, return the data portion (IAC sequences removed).

        Negotiation replies triggered by this chunk are queued internally;
        retrieve them with pop_pending_output().
        """
        clean = bytearray()
        for b in chunk:
            if self._state == _STATE_DATA:
                if b == IAC:
                    self._state = _STATE_IAC
                else:
                    clean.append(b)
            elif self._state == _STATE_IAC:
                if b == IAC:
                    # Escaped literal 0xFF in the data stream.
                    clean.append(0xFF)
                    self._state = _STATE_DATA
                elif b in (WILL, WONT, DO, DONT):
                    self._pending_cmd = b
                    self._state = _STATE_CMD_OPTION
                elif b == SB:
                    self._sb_buf = bytearray()
                    self._state = _STATE_SB
                else:
                    # SE with no matching SB, GA, NOP, or anything else
                    # with no trailing option byte — nothing to do.
                    self._state = _STATE_DATA
            elif self._state == _STATE_CMD_OPTION:
                self._negotiate(self._pending_cmd, b)
                self._pending_cmd = None
                self._state = _STATE_DATA
            elif self._state == _STATE_SB:
                if b == IAC:
                    self._state = _STATE_SB_IAC
                else:
                    self._sb_buf.append(b)
            elif self._state == _STATE_SB_IAC:
                if b == SE:
                    self._handle_subnegotiation(bytes(self._sb_buf))
                    self._sb_buf = bytearray()
                    self._state = _STATE_DATA
                elif b == IAC:
                    self._sb_buf.append(0xFF)
                    self._state = _STATE_SB
                else:
                    # Malformed — treat as continuing SB data.
                    self._sb_buf.append(b)
                    self._state = _STATE_SB
        return bytes(clean)

    def pop_pending_output(self) -> bytes:
        """Return and clear any negotiation replies queued by feed()."""
        out = bytes(self._out)
        self._out = bytearray()
        return out

    # -- negotiation -----------------------------------------------------

    def _negotiate(self, cmd, option):
        if cmd == DO:
            if option == TTYPE:
                self._reply(WILL, TTYPE)
            elif option == NAWS:
                self._reply(WILL, NAWS)
                self._send_naws()
            elif option == SGA:
                self._reply(WILL, SGA)
            elif option == BINARY:
                self._reply(WILL, BINARY)
            elif option == ECHO:
                # We don't locally echo — the server (a BBS door) does.
                self._reply(WONT, ECHO)
            else:
                self._reply(WONT, option)
        elif cmd == WILL:
            if option in (ECHO, SGA, BINARY):
                self._reply(DO, option)
            else:
                self._reply(DONT, option)
        elif cmd == DONT:
            self._reply(WONT, option)
        elif cmd == WONT:
            self._reply(DONT, option)

    def _handle_subnegotiation(self, payload: bytes):
        if not payload:
            return
        option = payload[0]
        if option == TTYPE and len(payload) >= 2 and payload[1] == TTYPE_SEND:
            body = bytes([IAC, SB, TTYPE, TTYPE_IS]) + self.terminal_type + bytes([IAC, SE])
            self._out.extend(body)

    def _send_naws(self):
        w_hi, w_lo = divmod(self.width, 256)
        h_hi, h_lo = divmod(self.height, 256)
        body = bytes([IAC, SB, NAWS, w_hi, w_lo, h_hi, h_lo, IAC, SE])
        self._out.extend(body)

    def _reply(self, cmd, option):
        self._out.extend(bytes([IAC, cmd, option]))
