"""WO-P4-053 — ``protocol.build_response()`` color wiring.

Proves: (1) the bare-``rows`` path (settle/subscribe callers -- ``watch.py``'s
seed-subscribe and settle-edge emit both call ``build_response(session)``
with no ``rows``) takes BOTH rows and color from ONE
``session.render_with_color()`` capture, never a separate
``render()`` + ``color_map()`` race; (2) the ``rows=``-supplied path (only
``screen --raw`` today) omits ``color`` entirely rather than pairing the
caller's already-captured rows with a color map read moments later against
whatever the screen has become since.
"""

from __future__ import annotations

from tw2002_aiclient.session import protocol


class _NoSeparateRenderSession:
    """Deliberately has NO ``.render()`` / ``.terminal`` -- if
    ``build_response``'s bare-rows path ever fell back to a two-call
    ``render()`` + ``color_map()`` sequence instead of the single
    ``render_with_color()`` capture, this fixture would raise
    ``AttributeError`` rather than silently succeeding."""

    def __init__(self, rows, color):
        self._rows = rows
        self._color = color
        self.render_with_color_calls = 0
        self.last_sent = None

    def render_with_color(self):
        self.render_with_color_calls += 1
        return list(self._rows), self._color

    def render_text(self, rows=None):
        return "\n".join(rows if rows is not None else self._rows)


_ROWS = ["Command [TL=00:00:00]:[1] (?=Help)? :"]
_COLOR = [[{"start": 0, "end": 7, "fg": "red", "bg": "default", "bold": False}]]


# ---------------------------------------------------------------------------
# Bare-rows path -- color present, one capture
# ---------------------------------------------------------------------------


def test_bare_path_color_present_and_matches_render_with_color_output():
    session = _NoSeparateRenderSession(_ROWS, _COLOR)
    resp = protocol.build_response(session)
    assert resp["screen"] == _ROWS
    assert resp["color"] == _COLOR


def test_bare_path_calls_render_with_color_exactly_once():
    session = _NoSeparateRenderSession(_ROWS, _COLOR)
    protocol.build_response(session)
    assert session.render_with_color_calls == 1


def test_bare_path_rows_and_color_are_the_same_capture():
    # This fixture has no render() to fall back to at all -- a passing
    # assert here is only possible because `screen` and `color` both came
    # out of the ONE render_with_color() tuple, never two separate reads
    # that could observe a shifted bounding box between them.
    rows = ["row0", "row1", "row2"]
    color = [[{"start": 0, "end": 4, "fg": "default", "bg": "default", "bold": False}]] * 3
    session = _NoSeparateRenderSession(rows, color)
    resp = protocol.build_response(session)
    assert resp["screen"] == rows
    assert len(resp["color"]) == len(resp["screen"])


def test_bare_path_empty_screen_still_adds_color_key():
    # An honest empty color map (blank screen) is still an ADDITIVE
    # present key -- distinct from the rows=-supplied path's INTENTIONAL
    # omission below. `color: []` is not the same as no `color` key.
    session = _NoSeparateRenderSession([], [])
    resp = protocol.build_response(session)
    assert "color" in resp
    assert resp["color"] == []


# ---------------------------------------------------------------------------
# rows=-supplied path -- color omitted, render_with_color() never called
# ---------------------------------------------------------------------------


def test_rows_supplied_path_omits_color_key():
    session = _NoSeparateRenderSession(_ROWS, _COLOR)
    resp = protocol.build_response(session, rows=["explicit row"])
    assert "color" not in resp
    assert resp["screen"] == ["explicit row"]


def test_rows_supplied_path_never_calls_render_with_color():
    session = _NoSeparateRenderSession(_ROWS, _COLOR)
    protocol.build_response(session, rows=["explicit row"])
    assert session.render_with_color_calls == 0


def test_rows_supplied_path_with_extra_and_settled_reason_still_omits_color():
    session = _NoSeparateRenderSession(_ROWS, _COLOR)
    resp = protocol.build_response(
        session, rows=["r"], settled_reason="idle", extra={"elapsed": 0.1}
    )
    assert "color" not in resp
    assert resp["settled_reason"] == "idle"
    assert resp["elapsed"] == 0.1


def test_rows_supplied_empty_list_still_omits_color():
    # An explicitly-supplied EMPTY rows list is still "caller supplied
    # rows" -- `rows=[]` must not be confused with the sentinel `None`
    # that means "go capture it yourself".
    session = _NoSeparateRenderSession(_ROWS, _COLOR)
    resp = protocol.build_response(session, rows=[])
    assert "color" not in resp
    assert session.render_with_color_calls == 0


# ---------------------------------------------------------------------------
# Wire-level: real dispatch() verbs that hit each path
# ---------------------------------------------------------------------------


class _FakeConn:
    connected = True


class _DispatchFakeSession:
    """Minimal session for protocol.dispatch()'s screen/send verbs --
    mirrors tests/test_cli_ops_verb_a.py's/test_cli_ops_verb_b.py's own
    FakeSession conventions, kept local so this file doesn't depend on
    another test module's fixtures."""

    def __init__(self, rows):
        self._rows = list(rows)
        self.conn = _FakeConn()
        self.last_sent = None
        self.last_sender = None
        self.host = "127.0.0.1"
        self.port = 23
        self.name = "test"
        self.render_with_color_calls = 0

    def render(self):
        return list(self._rows)

    def render_with_color(self):
        self.render_with_color_calls += 1
        return list(self._rows), []

    def render_raw(self):
        return list(self._rows)

    def render_text(self, rows=None):
        return "\n".join(rows if rows is not None else self._rows)

    def send(self, text, enter=True, secret=False, sender="app"):
        self.last_sent = "<redacted>" if secret else text
        self.last_sender = sender

    def record_history(self, verb, args, prompt, classification, settled_reason):
        # WO-SEND-HISTORY-RING: protocol `send` now files the ring; bare
        # dispatch doubles must accept the call (real Session always has it).
        return


class _FakeServer:
    control_lock = None


def test_wire_send_verb_bare_path_carries_color():
    session = _DispatchFakeSession(_ROWS)
    resp = protocol.dispatch(session, "send", {"input": "x"}, _FakeServer())
    assert resp["ok"] is True
    assert "color" in resp
    assert resp["color"] == []


def test_wire_screen_raw_verb_omits_color_and_skips_render_with_color():
    session = _DispatchFakeSession(_ROWS)
    resp = protocol.dispatch(session, "screen", {"raw": True}, _FakeServer())
    assert resp["ok"] is True
    assert "color" not in resp
    assert session.render_with_color_calls == 0


def test_wire_screen_non_raw_verb_carries_color():
    session = _DispatchFakeSession(_ROWS)
    resp = protocol.dispatch(session, "screen", {}, _FakeServer())
    assert resp["ok"] is True
    assert "color" in resp
    assert session.render_with_color_calls == 1
