"""``tw loops`` CLI wire (WO-P2-G3, slice 2/2).

The engine (``loops/store.py`` + ``loops/list_view.py``) is proven by
``test_loops_store.py``. What is proven HERE is the thing only the wire can
get wrong: that the real verb, dispatched through the real parser, prints
the composer's report over a real on-disk store and **returns an exit code
that matches what the read actually established**.

So every test below drives ``cli.main([...])`` -- the whole dispatch path,
not the function in isolation -- against files this test wrote to disk. The
store location is redirected by pointing ``store.STATE_DIR`` at ``tmp_path``,
which is the module's own documented injection seam; the reader itself is
never mocked, because a mocked reader cannot prove a ``chmod 000`` directory
comes back as ``rc 1``.

The bar, same as the engine's: **a surface must never report an outcome it
did not earn.** For a CLI, the exit code is part of the report -- ``rc 0``
with an empty listing is a machine-readable "there are no loops", and a
store nobody could read never gets to say that.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tw2002_aiclient.loops import store
from tw2002_aiclient.session import cli

RECORDED = {
    "name": "ore-run",
    "created_ts": "2026-07-19T06:08:23Z",
    "source": "recorded",
    "start_anchor": 158,
    "steps": [
        {"input": "P", "wait_prompt": None, "expected_post_class": "port_trade"},
        {"input": "50", "wait_prompt": "offer", "expected_post_class": "port_offer"},
    ],
}

EMPTY_MSG = "no loops taught yet"

needs_unprivileged = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses the permission bits these tests depend on",
)


def _store(tmp_path: Path, docs=None, *, drafts=None) -> Path:
    """Write a real ``<tmp_path>/skills`` tree; return the skills dir."""
    skills = tmp_path / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    for name, body in (docs or {}).items():
        text = body if isinstance(body, str) else json.dumps(body)
        (skills / f"{name}.json").write_text(text, encoding="utf-8")
    if drafts is not None:
        draft_dir = skills / "_drafts"
        draft_dir.mkdir(parents=True, exist_ok=True)
        for name, body in drafts.items():
            text = body if isinstance(body, str) else json.dumps(body)
            (draft_dir / f"{name}.json").write_text(text, encoding="utf-8")
    return skills


def _at(monkeypatch, tmp_path: Path) -> None:
    """Point the reader's default store root at this test's tmp tree."""
    monkeypatch.setattr(store, "STATE_DIR", tmp_path)


def _run(capsys, argv) -> tuple[int, str]:
    rc = cli.main(argv)
    return rc, capsys.readouterr().out


# --------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------


def test_loops_verb_is_wired_with_only_its_canon_flag():
    """``cli-verbs.md:116`` gives ``loops`` exactly one key arg,
    ``--include-drafts``. No ``--run-dir``: the verb is a daemon-free read
    (``cli-verbs.md:36-38``), and a run-dir flag would imply the report can
    depend on which daemon is up, which it cannot."""
    parser = cli.build_parser()
    args = parser.parse_args(["loops"])

    assert args.func is cli.cmd_loops
    assert args.include_drafts is False
    assert args.json is False
    assert not hasattr(args, "run_dir")

    opted_in = parser.parse_args(["loops", "--include-drafts", "--json"])
    assert opted_in.include_drafts is True
    assert opted_in.json is True


def test_loops_is_advertised_on_help_next_to_the_other_read_only_inspectors():
    help_text = cli.build_parser().format_help()
    # `menumap` is the control leg: it pins the render is real, so the
    # presence check below cannot pass on an exploded/empty help.
    assert "menumap" in help_text
    assert "loops" in help_text


def test_the_loops_help_strings_do_not_widen_the_ascii_help_crash():
    """``tw --help`` is printed through the terminal's own codec, so a
    non-ASCII glyph in a help string raises ``UnicodeEncodeError`` on an
    ascii/latin-1 terminal instead of printing help -- the exposure
    ``cmd_attach``'s help comment already records for the em-dashed verbs
    that shipped before it.

    Honest scope: this test does NOT claim ``tw --help`` works on such a
    terminal. Measured on this tip, ``PYTHONIOENCODING=ascii ./tw --help``
    already dies on ``menumap``'s ``★`` well before it reaches ``loops``.
    All this pins is that the newest verb did not add another glyph to that
    pile -- ``tw loops --help`` alone does print under ascii. Fixing the
    pre-existing ones is a separate WO."""
    parser = cli.build_parser()
    sub = next(a for a in parser._actions if getattr(a, "choices", None) is not None)
    entry = next(a for a in sub._choices_actions if a.dest == "loops")
    entry.help.encode("ascii")  # raises if a non-ASCII glyph crept in

    for action in sub.choices["loops"]._actions:
        (action.help or "").encode("ascii")


def test_loops_never_touches_the_daemon(tmp_path, monkeypatch, capsys):
    """`read-only` + daemon-free: canon lists `loops` among the reads that
    "work with the daemon stopped". Proven by making any socket use fatal --
    not by reading the source."""
    _at(monkeypatch, tmp_path)
    _store(tmp_path, {"ore-run": RECORDED})

    def explode(*_a, **_kw):
        raise AssertionError("tw loops must not touch the daemon")

    monkeypatch.setattr(cli, "send_request", explode)
    monkeypatch.setattr(cli, "daemon_alive", explode)

    rc, out = _run(capsys, ["loops"])
    assert rc == 0
    assert "ore-run" in out


# --------------------------------------------------------------------------
# The five store outcomes, each proven by execution against a real store
# --------------------------------------------------------------------------


def test_never_written_store_exits_zero_and_explains_the_zero(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)  # nothing written: state/skills does not exist

    rc, out = _run(capsys, ["loops"])

    assert rc == 0
    assert out.splitlines()[0] == "LOOPS 0"
    assert EMPTY_MSG in out
    assert "no store at" in out
    assert "INCOMPLETE" not in out


def test_empty_store_exits_zero_and_reads_differently_from_a_missing_one(
    tmp_path, monkeypatch, capsys
):
    _at(monkeypatch, tmp_path)
    _store(tmp_path, {})

    rc, out = _run(capsys, ["loops"])

    assert rc == 0
    assert "the store is empty" in out
    assert "no store at" not in out


def test_populated_store_exits_zero_and_lists_exactly_what_is_on_disk(
    tmp_path, monkeypatch, capsys
):
    _at(monkeypatch, tmp_path)
    _store(
        tmp_path,
        {"ore-run": RECORDED, "fuel-hop": {**RECORDED, "name": "fuel-hop"}},
    )

    rc, out = _run(capsys, ["loops"])
    lines = out.splitlines()

    assert rc == 0
    assert lines[0] == "LOOPS 2"
    # Two files on disk, two rows printed -- and nothing else.
    assert len(lines) == 3
    assert "ore-run" in out
    assert "fuel-hop" in out
    assert "2 steps" in out
    assert EMPTY_MSG not in out


def test_partial_read_exits_zero_but_never_prints_a_clean_total(
    tmp_path, monkeypatch, capsys
):
    """rc 0 is earned: one document really was read, and the report says
    INCOMPLETE and names the file it could not read. A caller that only has
    the exit code still gets a truthful "the listing ran"; the fact it is a
    floor is on the surface, where an operator reads it."""
    _at(monkeypatch, tmp_path)
    _store(tmp_path, {"ore-run": RECORDED, "broken": "{not json"})

    rc, out = _run(capsys, ["loops"])

    assert rc == 0
    assert out.splitlines()[0] == "LOOPS 1 listed · 1 unreadable — INCOMPLETE"
    assert "ore-run" in out
    assert "broken.json" in out
    assert "invalid JSON" in out
    assert EMPTY_MSG not in out


@needs_unprivileged
def test_unreadable_store_exits_one_and_reports_no_count_at_all(
    tmp_path, monkeypatch, capsys, request
):
    """THE defect this verb exists to not have. ``tw loops || echo none``
    must not print "none" for a store nobody could read, so an unreadable
    store is the one outcome that leaves via a non-zero exit code."""
    _at(monkeypatch, tmp_path)
    skills = _store(tmp_path, {"ore-run": RECORDED})
    skills.chmod(0o000)
    request.addfinalizer(lambda: skills.chmod(0o700))

    rc, out = _run(capsys, ["loops"])

    assert rc == 1
    assert out.splitlines()[0] == "LOOPS ? — the store could not be read"
    assert "LOOPS 0" not in out
    assert EMPTY_MSG not in out
    assert str(skills) in out


@needs_unprivileged
def test_the_non_zero_exit_comes_from_the_lock_and_not_from_the_harness(
    tmp_path, monkeypatch, capsys, request
):
    """Non-vacuity leg for the test above: the SAME store, same fixture,
    same invocation -- unlocked it exits 0 and lists the macro. So the 1 is
    the unreadable directory being reported, not this harness failing to
    reach a working verb."""
    _at(monkeypatch, tmp_path)
    skills = _store(tmp_path, {"ore-run": RECORDED})
    skills.chmod(0o000)
    request.addfinalizer(lambda: skills.chmod(0o700))

    locked_rc, locked_out = _run(capsys, ["loops"])
    skills.chmod(0o700)
    open_rc, open_out = _run(capsys, ["loops"])

    assert (locked_rc, open_rc) == (1, 0)
    assert "ore-run" not in locked_out
    assert "ore-run" in open_out


# --------------------------------------------------------------------------
# Drafts -- inert, opt-in, unmistakable
# --------------------------------------------------------------------------


def test_drafts_are_absent_without_the_flag_and_tagged_with_it(
    tmp_path, monkeypatch, capsys
):
    """A draft is inert until a human promotes it
    (``canon/engine/candidate-mining.md``), so it may never appear as a
    plain row: off the listing entirely by default, and prefixed ``[DRAFT]``
    when the operator explicitly asks for it."""
    _at(monkeypatch, tmp_path)
    _store(
        tmp_path,
        {"ore-run": RECORDED},
        drafts={"mined-0": {**RECORDED, "name": "mined-0", "source": "mined"}},
    )

    default_rc, default_out = _run(capsys, ["loops"])
    assert default_rc == 0
    assert default_out.splitlines()[0] == "LOOPS 1"
    assert "ore-run" in default_out
    assert "mined-0" not in default_out

    opted_rc, opted_out = _run(capsys, ["loops", "--include-drafts"])
    assert opted_rc == 0
    assert "ore-run" in opted_out
    # Present, and never presentable as an armed macro.
    assert "[DRAFT] mined-0" in opted_out
    draft_line = next(ln for ln in opted_out.splitlines() if "mined-0" in ln)
    blessed_line = next(ln for ln in opted_out.splitlines() if "ore-run" in ln)
    assert draft_line.startswith("[DRAFT] ")
    assert "[DRAFT]" not in blessed_line


@needs_unprivileged
def test_asking_for_drafts_that_cannot_be_read_is_an_incomplete_listing(
    tmp_path, monkeypatch, capsys, request
):
    """The blessed rows are real, so rc stays 0 -- but the operator asked
    for drafts and did not get them, and the report says so rather than
    presenting the blessed rows as the whole answer."""
    _at(monkeypatch, tmp_path)
    skills = _store(tmp_path, {"ore-run": RECORDED}, drafts={})
    (skills / "_drafts").chmod(0o000)
    request.addfinalizer(lambda: (skills / "_drafts").chmod(0o700))

    rc, out = _run(capsys, ["loops", "--include-drafts"])

    assert rc == 0
    assert "INCOMPLETE" in out.splitlines()[0]
    assert "ore-run" in out
    assert str(skills / "_drafts") in out


# --------------------------------------------------------------------------
# --json: the scripted caller's view
# --------------------------------------------------------------------------


def test_json_is_the_reader_result_verbatim(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)
    _store(tmp_path, {"ore-run": RECORDED})

    rc, out = _run(capsys, ["loops", "--json"])
    payload = json.loads(out)

    assert rc == 0
    assert payload == store.read_loop_store(state_dir=tmp_path)
    assert payload["status"] == "ok"
    assert [row["name"] for row in payload["loops"]] == ["ore-run"]
    assert payload["include_drafts"] is False


def test_json_partial_read_carries_its_own_incompleteness(tmp_path, monkeypatch, capsys):
    _at(monkeypatch, tmp_path)
    _store(tmp_path, {"ore-run": RECORDED, "broken": "{not json"})

    rc, out = _run(capsys, ["loops", "--json"])
    payload = json.loads(out)

    assert rc == 0
    assert payload["status"] == "partial"
    assert len(payload["unreadable"]) == 1
    # No synthesized `ok` flag over a partial read: `menumap` prints
    # `"ok": true` because its report either builds or errors out, but here a
    # success flag next to `status: partial` is precisely the outcome the
    # verb did not earn. `status` is the field a caller branches on.
    assert "ok" not in payload


@needs_unprivileged
def test_json_unreadable_store_exits_one_and_flags_itself(
    tmp_path, monkeypatch, capsys, request
):
    """``loops: []`` is structurally unavoidable in JSON -- so the exit code
    and ``status`` are what stop a scripted caller reading that empty list
    as "there are no loops". Both are asserted together, because either one
    alone lets the lie through."""
    _at(monkeypatch, tmp_path)
    skills = _store(tmp_path, {"ore-run": RECORDED})
    skills.chmod(0o000)
    request.addfinalizer(lambda: skills.chmod(0o700))

    rc, out = _run(capsys, ["loops", "--json"])
    payload = json.loads(out)

    assert rc == 1
    assert payload["status"] == "unreadable"
    assert payload["loops"] == []
    assert payload["roots"][0]["reason"]


def test_json_stays_strict_json_when_a_document_carries_nan(tmp_path, monkeypatch, capsys):
    """Python's ``json`` both accepts and emits the bare ``NaN`` token, which
    is NOT valid JSON and breaks every non-Python consumer -- so a store file
    carrying one could otherwise travel straight through ``--json``. The
    reader drops non-finite profit before it can reach the row; asserted
    through the CLI because that is where a real consumer reads it.

    ``parse_constant`` is what makes this non-vacuous: a plain
    ``json.loads`` would happily parse ``NaN`` back and the test would pass
    with the defect present."""
    _at(monkeypatch, tmp_path)
    _store(
        tmp_path,
        {"ore-run": '{"name": "ore-run", "steps": [], "mined_stats": {"cr_per_turn": NaN}}'},
    )

    rc, out = _run(capsys, ["loops", "--json"])

    assert rc == 0
    assert "NaN" not in out
    payload = json.loads(
        out, parse_constant=lambda token: pytest.fail(f"non-JSON constant {token!r} in --json")
    )
    assert "profit_per_turn" not in payload["loops"][0]
