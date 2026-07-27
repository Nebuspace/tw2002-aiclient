"""`send_text` refuses a non-`str` at the boundary (found live, 2026-07-27).

Origin: registering a sacrificial profile against `twgs.microblaster.net`
returned `internal_error:AttributeError`. The cause was four frames below the
caller — `None` reached `text.encode("utf-8")` inside the encoder — and the
wire name said only that something, somewhere, was `None`.

Two properties, and the second is the one that makes this worth a test rather
than a comment:

* a non-`str` is refused with a NAMED type, so the daemon's
  `internal_error:{type().__name__}` rendering carries a real diagnosis;
* the refusal never repeats the offending VALUE. This is the same call that
  carries passwords (`secret=True`), and a repr of the argument is exactly
  what the secrets doctrine forbids reaching a log or transcript.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.session.connection import SendTextNotAString, TelnetConnection


class _Sock:
    def __init__(self):
        self.sent = []

    def sendall(self, data):
        self.sent.append(data)


def _conn():
    c = TelnetConnection.__new__(TelnetConnection)
    c._sock = _Sock()
    c._log_tx = lambda *a, **k: None
    return c


def test_a_str_still_sends_unchanged():
    """The guard must not change the working path."""
    c = _conn()
    c.send_text("hello", enter=False)
    assert c._sock.sent == [b"hello"]


def test_enter_still_appends_crlf():
    c = _conn()
    c.send_text("hi", enter=True)
    assert c._sock.sent == [b"hi\r\n"]


def test_none_is_refused_with_a_named_type_not_an_attributeerror():
    """The live failure. `AttributeError` spends the whole diagnostic budget
    saying "something was None"."""
    c = _conn()
    with pytest.raises(SendTextNotAString):
        c.send_text(None)
    assert c._sock.sent == [], "a refused send still put bytes on the wire"


def test_the_refusal_is_not_a_bare_attributeerror():
    c = _conn()
    with pytest.raises(TypeError) as exc:   # SendTextNotAString IS a TypeError
        c.send_text(None)
    assert not isinstance(exc.value, AttributeError)
    assert type(exc.value).__name__ == "SendTextNotAString", (
        "the class name IS the wire diagnosis; keep it precise"
    )


@pytest.mark.parametrize("bogus", [None, 7, 1.5, b"bytes", [], {}, object(), True])
def test_every_non_str_is_refused(bogus):
    c = _conn()
    with pytest.raises(SendTextNotAString):
        c.send_text(bogus)
    assert c._sock.sent == []


def test_the_refusal_names_the_type_but_never_the_value():
    """`secret=True` sends route through here. A password handed in with the
    wrong type must not be echoed into the exception message."""
    c = _conn()
    with pytest.raises(SendTextNotAString) as exc:
        c.send_text(b"hunter2-not-a-str", secret=True)
    msg = str(exc.value)
    assert "bytes" in msg, "the offending TYPE should be named"
    assert "hunter2" not in msg, "the offending VALUE leaked into the message"


def test_a_str_subclass_is_still_accepted():
    """The guard is `isinstance`, not `type() is str` — a `str` subclass is a
    `str` and encodes fine; refusing it would be narrower than the claim."""
    class S(str):
        pass

    c = _conn()
    c.send_text(S("ok"), enter=False)
    assert c._sock.sent == [b"ok"]
