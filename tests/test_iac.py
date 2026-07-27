"""IAC stripping + negotiation tests — no network involved."""

from tw2002_aiclient.session.iac import (
    IAC,
    WILL,
    WONT,
    DO,
    DONT,
    SB,
    SE,
    TTYPE,
    NAWS,
    ECHO,
    SGA,
    TTYPE_SEND,
    TelnetHandler,
    _SB_BUF_MAX,
    _STATE_DATA,
    _STATE_SB,
    _STATE_SB_IAC,
)


def test_plain_data_passes_through():
    h = TelnetHandler()
    assert h.feed(b"hello world\r\n") == b"hello world\r\n"
    assert h.pop_pending_output() == b""


def test_escaped_iac_iac_is_literal_0xff():
    h = TelnetHandler()
    clean = h.feed(bytes([ord("a"), IAC, IAC, ord("b")]))
    assert clean == bytes([ord("a"), 0xFF, ord("b")])


def test_do_ttype_replies_will_ttype():
    h = TelnetHandler()
    clean = h.feed(bytes([IAC, DO, TTYPE]))
    assert clean == b""
    assert h.pop_pending_output() == bytes([IAC, WILL, TTYPE])


def test_ttype_subnegotiation_send_replies_with_terminal_type():
    h = TelnetHandler(terminal_type=b"ANSI")
    clean = h.feed(bytes([IAC, SB, TTYPE, TTYPE_SEND, IAC, SE]))
    assert clean == b""
    expected = bytes([IAC, SB, TTYPE, 0]) + b"ANSI" + bytes([IAC, SE])
    assert h.pop_pending_output() == expected


def test_do_naws_replies_will_and_sends_dimensions():
    h = TelnetHandler(width=80, height=25)
    clean = h.feed(bytes([IAC, DO, NAWS]))
    assert clean == b""
    out = h.pop_pending_output()
    assert out.startswith(bytes([IAC, WILL, NAWS]))
    assert out.endswith(bytes([IAC, SB, NAWS, 0, 80, 0, 25, IAC, SE]))


def test_unsupported_do_option_gets_wont():
    h = TelnetHandler()
    h.feed(bytes([IAC, DO, 99]))
    assert h.pop_pending_output() == bytes([IAC, WONT, 99])


def test_do_echo_refused_server_should_echo():
    h = TelnetHandler()
    h.feed(bytes([IAC, DO, ECHO]))
    assert h.pop_pending_output() == bytes([IAC, WONT, ECHO])


def test_will_echo_accepted():
    h = TelnetHandler()
    h.feed(bytes([IAC, WILL, ECHO]))
    assert h.pop_pending_output() == bytes([IAC, DO, ECHO])


def test_will_sga_accepted_data_interleaved():
    h = TelnetHandler()
    clean = h.feed(b"pre" + bytes([IAC, WILL, SGA]) + b"post")
    assert clean == b"prepost"
    assert h.pop_pending_output() == bytes([IAC, DO, SGA])


def test_iac_split_across_two_feed_calls():
    """The state machine must survive an IAC sequence split at a recv() boundary."""
    h = TelnetHandler()
    clean1 = h.feed(b"hello" + bytes([IAC]))
    assert clean1 == b"hello"
    clean2 = h.feed(bytes([DO, TTYPE]) + b"world")
    assert clean2 == b"world"
    assert h.pop_pending_output() == bytes([IAC, WILL, TTYPE])


def test_subnegotiation_split_across_feed_calls():
    h = TelnetHandler(terminal_type=b"ANSI")
    clean1 = h.feed(bytes([IAC, SB, TTYPE]))
    clean2 = h.feed(bytes([TTYPE_SEND, IAC]))
    clean3 = h.feed(bytes([SE]))
    assert clean1 == clean2 == clean3 == b""
    expected = bytes([IAC, SB, TTYPE, 0]) + b"ANSI" + bytes([IAC, SE])
    assert h.pop_pending_output() == expected


def test_dont_replies_wont_and_wont_replies_dont():
    h = TelnetHandler()
    h.feed(bytes([IAC, DONT, 5]))
    assert h.pop_pending_output() == bytes([IAC, WONT, 5])
    h.feed(bytes([IAC, WONT, 5]))
    assert h.pop_pending_output() == bytes([IAC, DONT, 5])


# ---------------------------------------------------------------------------
# I-01: _sb_buf cap — unterminated SB must not wedge the state machine
# ---------------------------------------------------------------------------

def _make_unterminated_sb_flood(extra: int = 16) -> bytes:
    """Open an IAC SB, then send _SB_BUF_MAX + extra non-IAC bytes without SE.

    We explicitly avoid bytes with value 255 (IAC) so that the flood
    does not accidentally leave the handler in _STATE_IAC on the last byte —
    that would make the state-recovery assertions ambiguous.
    """
    # Use bytes 1..254 cycling — no IAC (255), no zero confusion
    data = bytes((i % 254) + 1 for i in range(_SB_BUF_MAX + extra))
    return bytes([IAC, SB]) + data


def test_sb_overflow_buffer_stays_at_or_below_cap():
    """Audit I-01: _sb_buf must never grow past _SB_BUF_MAX."""
    h = TelnetHandler()
    h.feed(_make_unterminated_sb_flood())
    assert len(h._sb_buf) <= _SB_BUF_MAX


def test_sb_overflow_state_returns_to_data():
    """Audit I-01: after overflow the state machine must not remain wedged in SB."""
    h = TelnetHandler()
    h.feed(_make_unterminated_sb_flood())
    assert h._state == _STATE_DATA


def test_sb_overflow_subsequent_bytes_reach_terminal():
    """Audit I-01: after overflow ordinary game bytes must pass through to the caller."""
    h = TelnetHandler()
    h.feed(_make_unterminated_sb_flood())
    clean = h.feed(b"sector 1")
    assert clean == b"sector 1"


def test_sb_overflow_mutation_pin():
    """Mutation pin: proves the cap check is load-bearing.

    Without the _SB_BUF_MAX guard the handler stays in _STATE_SB / _STATE_SB_IAC
    forever and subsequent game bytes never reach the terminal.  This test MUST go
    red if the cap check is removed from iac.py.
    """
    h = TelnetHandler()
    flood = _make_unterminated_sb_flood(extra=_SB_BUF_MAX)  # well past cap
    h.feed(flood)
    # Mutation oracle: state must NOT be wedged in SB — DATA (or IAC mid-seq)
    # are both safe; _STATE_SB / _STATE_SB_IAC mean the cap check is gone.
    assert h._state not in (_STATE_SB, _STATE_SB_IAC), (
        f"State still wedged in {h._state!r} after overflow — cap check is missing"
    )
    # Secondary: bytes after the flood must be delivered
    after = b"trade route data"
    assert h.feed(after) == after
