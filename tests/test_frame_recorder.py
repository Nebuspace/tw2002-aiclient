"""WO-BUILD-CLI-VERBS-FRAMES — frame recorder + build_response hook + CLI."""

from tw2002_aiclient.frame_recorder import (
    FrameRecorder,
    diff_frames,
    grep_frames,
    last_nonblank_line,
    read_frames,
)
from tw2002_aiclient.session import protocol


class _FakeSession:
    def __init__(self, screens):
        self._screens = list(screens)
        self._i = 0
        self.rx_count = 0
        self.frame_recorder = None

    def _cur(self):
        return self._screens[min(self._i, len(self._screens) - 1)]

    def render(self):
        return self._cur().split("\n")

    def render_with_color(self):
        return self.render(), []

    def render_raw(self):
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


def test_diff_shows_line_delta():
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


def test_secret_sent_input_never_persisted(tmp_path):
    """Password-shaped prompt → was_secret + redacted prompt; no sent_input."""
    session = _FakeSession(["Password? "])
    rec = FrameRecorder("sec_sess", state_dir=tmp_path)
    session.frame_recorder = rec
    protocol.build_response(session)
    frames = read_frames("sec_sess", state_dir=tmp_path)
    assert "sent_input" not in frames[0]
    assert frames[0]["was_secret"] is True
    assert frames[0]["prompt"] == "<redacted>"
    blob = (tmp_path / "frames" / "sec_sess.jsonl").read_text(encoding="utf-8")
    assert '"sent_input"' not in blob


def test_password_prompt_redacts_from_prompt_text_alone(tmp_path):
    """Prompt-shape alone drives was_secret — no session secret flag."""
    session = _FakeSession(["Enter your password:"])
    rec = FrameRecorder("pw_prompt", state_dir=tmp_path)
    session.frame_recorder = rec
    protocol.build_response(session)
    frames = read_frames("pw_prompt", state_dir=tmp_path)
    assert frames[0]["was_secret"] is True
    assert frames[0]["prompt"] == "<redacted>"
    assert "sent_input" not in frames[0]


def test_non_secret_omits_sent_input(tmp_path):
    """Non-password prompts: was_secret false; keystrokes never mirrored."""
    session = _FakeSession(["Command [TL=40]:"])
    rec = FrameRecorder("plain_sess", state_dir=tmp_path)
    session.frame_recorder = rec
    protocol.build_response(session)
    frames = read_frames("plain_sess", state_dir=tmp_path)
    assert frames[0]["was_secret"] is False
    assert "sent_input" not in frames[0]
    blob = (tmp_path / "frames" / "plain_sess.jsonl").read_text(encoding="utf-8")
    assert '"sent_input"' not in blob


def test_no_recorder_still_ok():
    session = _FakeSession(["Command [TL=40]:"])
    resp = protocol.build_response(session)
    assert resp["ok"] is True
    assert "classification" in resp


def test_frames_cli_tail_and_show(tmp_path, capsys):
    from argparse import Namespace

    from tw2002_aiclient.frames_cli import cmd_frames

    session = _FakeSession(["Option? (A,D,I,R,S,?):?"])
    rec = FrameRecorder("cli_sess", state_dir=tmp_path)
    session.frame_recorder = rec
    protocol.build_response(session)

    rc = cmd_frames(
        Namespace(
            frames_action="tail",
            session="cli_sess",
            n=5,
            json=False,
            state_dir=tmp_path,
        )
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "#1" in out

    rc = cmd_frames(
        Namespace(
            frames_action="show",
            session="cli_sess",
            seq=1,
            json=False,
            state_dir=tmp_path,
        )
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Option?" in out


def test_add_frames_parsers_registers_subcommands():
    import argparse

    from tw2002_aiclient.frames_cli import add_frames_parsers

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="verb")
    add_frames_parsers(sub)
    args = parser.parse_args(["frames", "tail", "-n", "3"])
    assert args.frames_action == "tail"
    assert args.n == 3
    assert callable(args.func)
