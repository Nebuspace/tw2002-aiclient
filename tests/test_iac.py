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
