"""``tw record`` CLI wire (WO-P2-G4-X6, slice 2/2).

The engine (``loops/recorder.py``) is proven end to end -- including the
round trip to a completed replay -- by ``test_loop_recorder.py``. What is
proven HERE is the thing only the wire can get wrong: that the real verb,
dispatched through the real parser, reads a real manifest file, writes to
the real (redirected) store, and returns an exit code that matches what the
recorder actually did.

Same pattern as ``test_cli_loops.py``: ``cli.main([...])`` end to end, store
location redirected via ``store.STATE_DIR`` (the module's own documented
injection seam), nothing mocked.
"""

from __future__ import annotations

import json
from pathlib import Path

from tw2002_aiclient.loops import store
from tw2002_aiclient.loops.loader import load_loop
from tw2002_aiclient.loops.player import OUTCOME_COMPLETED, replay_loop
from tw2002_aiclient.session import cli

ANCHOR_ROWS = [
    "Sector  : 158 in uncharted space.",
    "Command [TL=00:00:00]:[158] (?=Help)? :",
]
PORT_ROWS = [
    "Docking...",
    "",
    "Commerce report for Aegis: 1 Fuel Ore, Organics, Equipment",
    "",
    "<Trade with this port> (Y/N)? ",
]

MANIFEST = {
    "name": "ore-run",
    "anchor": {"screen": ANCHOR_ROWS},
    "steps": [
        {"input": "P", "screen": PORT_ROWS},
        {"input": "1", "screen": ANCHOR_ROWS, "confirm_exact": True},
    ],
}


def _at(monkeypatch, tmp_path: Path) -> None:
    """Point the recorder's default store root at this test's tmp tree --
    the same seam ``test_cli_loops.py`` redirects for the reader."""
    monkeypatch.setattr(store, "STATE_DIR", tmp_path)


def _manifest_file(tmp_path: Path, body=None) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(MANIFEST if body is None else body), encoding="utf-8")
    return path


def _run(capsys, argv):
    rc = cli.main(argv)
    return rc, capsys.readouterr().out


# --------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------


def test_record_verb_is_wired_with_the_manifest_positional_and_draft_flag():
    parser = cli.build_parser()
    args = parser.parse_args(["record", "manifest.json"])

    assert args.func is cli.cmd_record
    assert args.manifest == "manifest.json"
    assert args.draft is False
    assert args.json is False
    # Daemon-free, like `loops`/`menumap --path`: no run-dir flag, because
    # nothing this verb reports depends on which daemon is up.
    assert not hasattr(args, "run_dir")

    opted_in = parser.parse_args(["record", "manifest.json", "--draft", "--json"])
    assert opted_in.draft is True
    assert opted_in.json is True


def test_record_is_advertised_on_help_next_to_loops():
    help_text = cli.build_parser().format_help()
    assert "loops" in help_text
    assert "record" in help_text


def test_the_record_help_strings_do_not_widen_the_ascii_help_crash():
    parser = cli.build_parser()
    sub = next(a for a in parser._actions if getattr(a, "choices", None) is not None)
    entry = next(a for a in sub._choices_actions if a.dest == "record")
    entry.help.encode("ascii")

    for action in sub.choices["record"]._actions:
        (action.help or "").encode("ascii")


def test_record_never_touches_the_daemon(tmp_path, monkeypatch, capsys):
    """Daemon-free by design: proven by making any socket use fatal, not by
    reading the source (same discipline as ``test_loops_never_touches_the_daemon``)."""
    _at(monkeypatch, tmp_path)
    manifest = _manifest_file(tmp_path)

    def explode(*_a, **_kw):
        raise AssertionError("tw record must not touch the daemon")

    monkeypatch.setattr(cli, "send_request", explode)
    monkeypatch.setattr(cli, "daemon_alive", explode)

    rc, _out = _run(capsys, ["record", str(manifest)])
    assert rc == 0


# --------------------------------------------------------------------------
# The headline path -- a real manifest, through the real wire, into a
# document the real loader loads and the real player replays.
# --------------------------------------------------------------------------


def test_a_valid_manifest_writes_a_blessed_loop_that_replays(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)
    manifest = _manifest_file(tmp_path)

    rc, out = _run(capsys, ["record", str(manifest)])

    assert rc == 0
    assert "ore-run" in out
    assert "blessed" in out

    loop = load_loop("ore-run", state_dir=tmp_path)
    assert loop.draft is False
    assert loop.start_anchor == 158
    assert [s.expected_post_class for s in loop.steps] == ["port_trade", "main_command"]

    class _Scripted:
        def __init__(self, screens):
            self.screens = list(screens)
            self.sends = []
            self._i = 0

        def settle(self):
            return True

        def screen(self):
            return self.screens[self._i]

        def is_driver_fenced(self):
            return False

        def should_abort(self):
            return False

        def send_and_confirm(self, keystrokes, wait_prompt):
            self.sends.append((keystrokes, wait_prompt))
            self._i += 1
            return True

    def _pair(rows):
        return "\n".join(rows), rows[-1].strip()

    session = _Scripted([_pair(ANCHOR_ROWS), _pair(PORT_ROWS), _pair(ANCHOR_ROWS)])
    result = replay_loop(loop, session)
    assert result.outcome == OUTCOME_COMPLETED
    assert result.sends_issued == 2


def test_the_draft_flag_writes_under_drafts_and_reports_it(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)
    manifest = _manifest_file(tmp_path)

    rc, out = _run(capsys, ["record", str(manifest), "--draft"])

    assert rc == 0
    assert "draft" in out
    assert (tmp_path / "skills" / "_drafts" / "ore-run.json").exists()
    assert not (tmp_path / "skills" / "ore-run.json").exists()


def test_json_output_reports_the_written_path_and_step_count(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)
    manifest = _manifest_file(tmp_path)

    rc, out = _run(capsys, ["record", str(manifest), "--json"])
    payload = json.loads(out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["name"] == "ore-run"
    assert payload["steps"] == 2
    assert payload["draft"] is False
    assert payload["path"] == str(tmp_path / "skills" / "ore-run.json")


# --------------------------------------------------------------------------
# Refusals -- reported, never a traceback, and nothing is written.
# --------------------------------------------------------------------------


def test_a_manifest_that_is_not_json_is_reported_and_exits_one(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{not json", encoding="utf-8")

    rc, out = _run(capsys, ["record", str(manifest)])

    assert rc == 1
    assert "ERROR" in out
    assert not (tmp_path / "skills").exists()


def test_a_missing_manifest_file_is_reported_and_exits_one(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)

    rc, out = _run(capsys, ["record", str(tmp_path / "nope.json")])

    assert rc == 1
    assert "ERROR" in out


def test_a_manifest_with_no_steps_is_reported_and_exits_one(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)
    manifest = _manifest_file(tmp_path, {**MANIFEST, "steps": []})

    rc, out = _run(capsys, ["record", str(manifest)])

    assert rc == 1
    assert "ERROR" in out
    assert not (tmp_path / "skills").exists()


def test_a_manifest_whose_anchor_sector_is_unreadable_refuses_and_writes_nothing(
    tmp_path, monkeypatch, capsys
):
    """The recorder's own start-anchor refusal (trap 3), reached through
    the wire: a CLASSIC-shape command prompt (no sector bracket at all)
    must not become a document with a fabricated or dropped anchor."""
    _at(monkeypatch, tmp_path)
    bad = {
        **MANIFEST,
        "anchor": {"screen": ["Command [TL=00753:0/0/0/850] (?=Help)? :"]},
    }
    manifest = _manifest_file(tmp_path, bad)

    rc, out = _run(capsys, ["record", str(manifest)])

    assert rc == 1
    assert "ERROR" in out
    assert not (tmp_path / "skills").exists()
