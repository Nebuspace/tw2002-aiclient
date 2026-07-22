"""WO-FRAMES-0 — frame recorder + build_response hook + CLI read path."""

from twclient import protocol
from twclient.frame_recorder import (
    FrameRecorder,
    diff_frames,
    grep_frames,
    last_nonblank_line,
    read_frames,
)


class _FakeSession:
    def __init__(self, screens):
        self._screens = list(screens)
        self._i = 0
        self.last_sent = None
        self.last_sent_secret = False
        self.rx_count = 0
        self.frame_recorder = None

    def _cur(self):
        return self._screens[min(self._i, len(self._screens) - 1)]

    def render(self):
        return self._cur().split("\n")

    def render_with_color(self):
        return self.render(), []

    def render_raw(self):
        # Pad to 25 rows like pyte for greppable full-grid frames.
        rows = self.render()
        while len(rows) < 25:
            rows.append("")
        return rows[:25]

    def render_text(self, rows=None):
        return "\n".join(rows if rows is not None else self.render())

    def cursor_pos(self):
        return {"x": 0, "y": 24}


def test_last_nonblank_prefers_qty_over_blank_pad():
    rows = [
        "Your fighters: 30 vs. theirs: 1",
        "How many fighters do you wish to use (0 to 30) [0]?",
        "",
        "",
    ]
    assert last_nonblank_line(rows).startswith("How many fighters")


def test_recorder_appends_and_grows(tmp_path):
    session = _FakeSession(
        [
            "Option? (A,D,I,R,S,?):?",
            (
                "Your fighters: 30 vs. theirs: 1\n"
                "How many fighters do you wish to use (0 to 30) [0]?"
            ),
        ]
    )
    rec = FrameRecorder("test_sess", state_dir=tmp_path)
    session.frame_recorder = rec

    r1 = protocol.build_response(session)
    assert r1["ok"] is True
    session._i = 1
    session.last_sent = "A"
    r2 = protocol.build_response(session, settled_reason="idle")
    assert r2["ok"] is True

    frames = read_frames("test_sess", state_dir=tmp_path)
    assert len(frames) == 2
    assert frames[0]["seq"] == 1
    assert frames[1]["seq"] == 2
    assert frames[1]["settled_reason"] == "idle"
    assert any("How many fighters" in line for line in frames[1]["screen_raw"])


def test_grep_finds_qty_line(tmp_path):
    session = _FakeSession(
        [
            (
                "Your fighters: 30 vs. theirs: 1\n"
                "How many fighters do you wish to use (0 to 30) [0]?"
            ),
        ]
    )
    rec = FrameRecorder("grep_sess", state_dir=tmp_path)
    session.frame_recorder = rec
    protocol.build_response(session, settled_reason="prompt")

    hits = grep_frames("How many fighters", "grep_sess", state_dir=tmp_path)
    assert len(hits) >= 1
    assert any(
        "How many fighters" in "\n".join(h.get("screen_raw") or []) for h in hits
    )


def test_diff_shows_line_delta(tmp_path):
    a = {
        "seq": 1,
        "screen_raw": ["alpha", "Option? (A,D,I,R,S,?):?"],
    }
    b = {
        "seq": 2,
        "screen_raw": [
            "alpha",
            "How many fighters do you wish to use (0 to 30) [0]?",
        ],
    }
    delta = diff_frames(a, b)
    assert any("Option?" in line for line in delta)
    assert any("How many fighters" in line for line in delta)


def test_secret_sent_input_redacted(tmp_path):
    session = _FakeSession(["Password? "])
    rec = FrameRecorder("sec_sess", state_dir=tmp_path)
    session.frame_recorder = rec
    session.last_sent = "hunter2"
    session.last_sent_secret = True
    protocol.build_response(session)
    frames = read_frames("sec_sess", state_dir=tmp_path)
    assert frames[0]["sent_input"] == "<redacted>"
    assert frames[0]["sent_input_secret"] is True
