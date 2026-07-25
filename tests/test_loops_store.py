"""Learned-loop store reader + listing composer (WO-P2-G3).

The theme every assertion here defends: **a surface must never report an
outcome it did not earn.** An unreadable store and an empty store are
different facts, a count from a partial read is a floor and not a total,
and no field is defaulted into existence.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tw2002_aiclient.loops.list_view import format_loop_row, format_loops_report
from tw2002_aiclient.loops.store import read_loop_store
from tw2002_aiclient.session import cli

ARCHIVE_SKILLS = (
    Path(__file__).resolve().parents[1]
    / "archive"
    / "pre-rebirth-2026-07-23"
    / "runtime"
    / "state"
    / "skills"
)

# The document canon/engine/macros.md §Schema defines, in the shape the
# archive writer actually emits (verified against the 16 real artifacts).
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


def _write_store(root: Path, docs, *, drafts=None) -> Path:
    """Build ``<root>/skills`` (and ``_drafts``) from name -> doc-or-raw-text."""
    skills = root / "skills"
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


def _lock(request, path: Path) -> None:
    """chmod 000 with a restore finalizer, so tmp_path cleanup still works."""
    path.chmod(0o000)
    request.addfinalizer(lambda: path.chmod(0o700))


needs_unprivileged = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses the permission bits these tests depend on",
)


# --------------------------------------------------------------------------
# The honest empty -- a success, and distinguishable from a failure to look
# --------------------------------------------------------------------------


def test_absent_store_is_an_honest_empty_not_an_error(tmp_path):
    """No store has ever been written: report zero, and say why."""
    result = read_loop_store(state_dir=tmp_path)

    assert result["status"] == "ok"
    assert result["loops"] == []
    assert result["roots"][0]["status"] == "absent"

    report = format_loops_report(result)
    assert report[0] == "LOOPS 0"
    assert any(EMPTY_MSG in line for line in report)
    # The absent store explains itself rather than reading as an error.
    assert any("no store at" in line for line in report)
    assert not any("INCOMPLETE" in line for line in report)


def test_existing_but_empty_store_is_distinct_from_a_never_written_one(tmp_path):
    _write_store(tmp_path, {})
    result = read_loop_store(state_dir=tmp_path)

    assert result["status"] == "ok"
    assert result["roots"][0]["status"] == "ok"

    report = format_loops_report(result)
    assert any("the store is empty" in line for line in report)
    assert not any("no store at" in line for line in report)


# --------------------------------------------------------------------------
# Real rows -- read, never synthesized
# --------------------------------------------------------------------------


def test_real_rows_are_read_from_disk(tmp_path):
    _write_store(tmp_path, {"ore-run": RECORDED})
    result = read_loop_store(state_dir=tmp_path)

    assert result["status"] == "ok"
    assert len(result["loops"]) == 1
    row = result["loops"][0]
    assert row["name"] == "ore-run"
    assert row["source"] == "recorded"
    assert row["created_ts"] == "2026-07-19T06:08:23Z"
    assert row["start_anchor"] == 158
    # The real length of the real list -- 2, not a default and not a count
    # of files.
    assert row["steps"] == 2
    assert row["draft"] is False

    report = format_loops_report(result)
    assert report[0] == "LOOPS 1"
    assert "ore-run" in report[1]
    assert "recorded" in report[1]
    assert "2 steps" in report[1]
    assert not any(EMPTY_MSG in line for line in report)


def test_row_rendering_degrades_to_unknown_never_to_a_plausible_zero():
    """`format_loop_row` is pure, so its degradations are checked directly.
    A row with no usable step count says so rather than showing `0 steps`,
    which an operator would read as a real (and alarming) measurement."""
    solo = format_loop_row({"name": "solo", "source": "recorded", "steps": 1})
    assert solo.endswith("1 step")
    assert "1 steps" not in solo
    assert format_loop_row({"name": "duo", "source": "recorded", "steps": 2}).endswith("2 steps")

    degraded = format_loop_row({})
    assert "? steps" in degraded
    assert "0 steps" not in degraded
    # Name and source both unknown, and neither invented.
    assert degraded.startswith("?")
    assert "recorded" not in degraded


def test_absent_source_is_unknown_never_defaulted_to_recorded(tmp_path):
    """`recorded` means "a human demonstrated this at the keyboard" -- the
    strongest claim the schema makes. It is never inferred from silence."""
    nameless_source = {k: v for k, v in RECORDED.items() if k != "source"}
    _write_store(tmp_path, {"a": nameless_source, "b": {**RECORDED, "name": "b", "source": "invented"}})
    result = read_loop_store(state_dir=tmp_path)

    assert [row["source"] for row in result["loops"]] == [None, None]
    report = format_loops_report(result)
    assert "recorded" not in "\n".join(report)
    # Canon's unknown glyph, on both rows.
    assert report[1].split()[1] == "?"
    assert report[2].split()[1] == "?"


def test_no_profit_metadata_renders_as_unknown_never_a_fabricated_zero(tmp_path):
    """The archive summed ledger rows for a `demo_profit`; an absent ledger
    summed to 0 and rendered `+0cr demo` -- a definite economic claim made
    from no data. Nothing here manufactures a number."""
    _write_store(tmp_path, {"ore-run": RECORDED})
    result = read_loop_store(state_dir=tmp_path)

    row = result["loops"][0]
    assert "profit_per_turn" not in row
    assert "profit_per_action" not in row
    assert "demo_profit" not in row

    line = format_loops_report(result)[1]
    assert "—" in line
    assert "0cr" not in line
    assert "+0" not in line


def test_mined_stats_are_read_when_the_document_carries_them(tmp_path):
    mined = {
        **RECORDED,
        "name": "mined-1",
        "source": "mined",
        "mined_stats": {"cr_per_turn": 230.5, "cr_per_action": 54.375, "support": 8},
    }
    _write_store(tmp_path, {"mined-1": mined})
    result = read_loop_store(state_dir=tmp_path)

    row = result["loops"][0]
    assert row["profit_per_turn"] == 230.5
    assert row["profit_per_action"] == 54.375
    assert row["support"] == 8
    assert "+230.5cr/turn" in format_loops_report(result)[1]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_profit_never_renders_as_a_number(tmp_path, bad):
    """Python's json accepts the bare NaN/Infinity tokens, so a store file
    can carry one and it would format as `nan`/`inf` cr/turn next to a macro
    that spends credits."""
    doc = {**RECORDED, "mined_stats": {"cr_per_turn": bad}}
    _write_store(tmp_path, {"ore-run": doc})
    result = read_loop_store(state_dir=tmp_path)

    row = result["loops"][0]
    assert "profit_per_turn" not in row
    line = format_loops_report(result)[1]
    assert "—" in line
    assert "nan" not in line.lower()
    assert "inf" not in line.lower()


def test_non_finite_profit_survives_a_json_round_trip(tmp_path):
    """The parametrized case above writes NaN via json.dumps; prove the same
    guard holds for a file authored with the literal tokens on disk."""
    raw = json.dumps(RECORDED)[:-1] + ', "mined_stats": {"cr_per_turn": NaN}}'
    _write_store(tmp_path, {"ore-run": raw})
    result = read_loop_store(state_dir=tmp_path)

    assert len(result["loops"]) == 1, "the file must still parse -- NaN is valid to Python's json"
    assert "profit_per_turn" not in result["loops"][0]
    assert "nan" not in format_loops_report(result)[1].lower()


def test_boolean_profit_is_not_a_number(tmp_path):
    """isinstance(True, int) is true in Python, so an unguarded numeric check
    turns `cr_per_turn: true` into a confident `+1.0cr/turn`."""
    doc = {**RECORDED, "mined_stats": {"cr_per_turn": True, "support": False}}
    _write_store(tmp_path, {"ore-run": doc})
    result = read_loop_store(state_dir=tmp_path)

    row = result["loops"][0]
    assert "profit_per_turn" not in row
    assert "support" not in row
    line = format_loops_report(result)[1]
    assert "+1.0" not in line
    assert "—" in line


# --------------------------------------------------------------------------
# The defect class: a failed read must never render as a clean negative
# --------------------------------------------------------------------------


def test_all_files_corrupt_never_reports_an_empty_store(tmp_path):
    """THE defect. The archive did `except SkillError: continue` per file, so
    a store whose every file was corrupt returned `loops: []` and its CLI
    printed "(no learned loops yet ...)" -- a store that could not be read
    rendering byte-for-byte as a store that is genuinely empty."""
    _write_store(tmp_path, {"a": "{not json", "b": "]]]", "c": "{\"trailing\":,}"})
    result = read_loop_store(state_dir=tmp_path)

    assert result["loops"] == []
    assert result["status"] == "partial"
    assert len(result["unreadable"]) == 3

    report = format_loops_report(result)
    joined = "\n".join(report)
    assert EMPTY_MSG not in joined, "an unreadable store must never claim there are no loops"
    assert "INCOMPLETE" in report[0]
    assert "3 unreadable" in report[0]
    # Each unreadable file is named, with a reason -- an operator can only
    # fix a file they can find.
    for stem in ("a.json", "b.json", "c.json"):
        assert stem in joined
    assert "invalid JSON" in joined


def test_partial_read_keeps_real_rows_and_labels_the_count_a_floor(tmp_path):
    _write_store(tmp_path, {"ore-run": RECORDED, "broken": "{not json", "worse": "["})
    result = read_loop_store(state_dir=tmp_path)

    assert result["status"] == "partial"
    # A corrupt sibling never costs us a row that WAS read.
    assert [row["name"] for row in result["loops"]] == ["ore-run"]

    report = format_loops_report(result)
    assert report[0] == "LOOPS 1 listed · 2 unreadable — INCOMPLETE"
    assert any("ore-run" in line for line in report)
    assert EMPTY_MSG not in "\n".join(report)


@needs_unprivileged
def test_unreadable_store_directory_is_not_an_empty_store(tmp_path, request):
    """Path.glob swallows a PermissionError on the directory and returns an
    empty iterator, so a locked store reads as an empty one unless the
    listing is done with something that raises."""
    skills = _write_store(tmp_path, {"ore-run": RECORDED})
    _lock(request, skills)

    result = read_loop_store(state_dir=tmp_path)

    assert result["status"] == "unreadable"
    assert result["loops"] == []
    assert result["roots"][0]["status"] == "unreadable"
    assert result["roots"][0]["reason"]

    report = format_loops_report(result)
    joined = "\n".join(report)
    assert EMPTY_MSG not in joined
    # No count at all -- not even zero was established.
    assert report[0] == "LOOPS ? — the store could not be read"
    assert "LOOPS 0" not in joined
    assert str(skills) in joined


@needs_unprivileged
def test_unreadable_file_does_not_abort_the_whole_listing(tmp_path, request):
    """`load_skill` opened with a bare `open()`, so a PermissionError -- an
    OSError, not the SkillError the archive caught -- escaped the per-file
    handler and took the entire listing down."""
    skills = _write_store(tmp_path, {"ore-run": RECORDED, "locked": RECORDED})
    _lock(request, skills / "locked.json")

    result = read_loop_store(state_dir=tmp_path)

    assert [row["name"] for row in result["loops"]] == ["ore-run"]
    assert result["status"] == "partial"
    assert len(result["unreadable"]) == 1
    assert "locked.json" in result["unreadable"][0]["path"]
    assert result["unreadable"][0]["reason"]


def test_a_file_where_the_store_should_be_is_unreadable_not_absent(tmp_path):
    (tmp_path / "skills").write_text("I am not a directory", encoding="utf-8")
    result = read_loop_store(state_dir=tmp_path)

    assert result["status"] == "unreadable"
    assert result["roots"][0]["reason"] == "not a directory"
    assert EMPTY_MSG not in "\n".join(format_loops_report(result))


@pytest.mark.parametrize(
    "doc, expected_reason",
    [
        ({"steps": []}, "missing a usable 'name'"),
        ({"name": "  ", "steps": []}, "missing a usable 'name'"),
        ({"name": 7, "steps": []}, "missing a usable 'name'"),
        ({"name": "x"}, "missing a usable 'steps' list"),
        ({"name": "x", "steps": 5}, "missing a usable 'steps' list"),
        ({"name": "x", "steps": {"a": 1}}, "missing a usable 'steps' list"),
    ],
)
def test_documents_missing_identity_or_steps_are_unreadable_not_rows(tmp_path, doc, expected_reason):
    """The archive indexed `doc["name"]` and `len(doc.get("steps") or [])`
    unconditionally -- a nameless doc raised KeyError and `steps: 5` raised
    TypeError, either of which crashed the listing. Neither is a row, and
    the filename is not a substitute identity."""
    _write_store(tmp_path, {"suspect": doc})
    result = read_loop_store(state_dir=tmp_path)

    assert result["loops"] == []
    assert result["status"] == "partial"
    assert result["unreadable"][0]["reason"] == expected_reason
    # Never adopted from the file stem.
    assert "suspect" not in [row.get("name") for row in result["loops"]]


def test_non_object_top_level_is_unreadable(tmp_path):
    _write_store(tmp_path, {"listy": "[1, 2, 3]", "stringy": '"hello"'})
    result = read_loop_store(state_dir=tmp_path)

    assert result["loops"] == []
    reasons = sorted(entry["reason"] for entry in result["unreadable"])
    assert reasons == [
        "top-level shape is list, expected an object",
        "top-level shape is str, expected an object",
    ]


# --------------------------------------------------------------------------
# Drafts -- inert, opt-in, never mistakable for a blessed macro
# --------------------------------------------------------------------------


def test_drafts_are_opt_in_and_unmistakably_flagged(tmp_path):
    draft = {**RECORDED, "name": "mined-0", "source": "mined"}
    _write_store(tmp_path, {"ore-run": RECORDED}, drafts={"mined-0": draft})

    without = read_loop_store(state_dir=tmp_path)
    assert [row["name"] for row in without["loops"]] == ["ore-run"]
    assert without["status"] == "ok"

    with_drafts = read_loop_store(state_dir=tmp_path, include_drafts=True)
    assert [row["name"] for row in with_drafts["loops"]] == ["ore-run", "mined-0"]
    assert [row["draft"] for row in with_drafts["loops"]] == [False, True]

    report = format_loops_report(with_drafts)
    assert "[DRAFT] mined-0" in report[2]
    assert "[DRAFT]" not in report[1]


def test_absent_drafts_directory_is_still_an_honest_ok(tmp_path):
    _write_store(tmp_path, {"ore-run": RECORDED})
    result = read_loop_store(state_dir=tmp_path, include_drafts=True)

    assert result["status"] == "ok"
    assert result["roots"][1]["status"] == "absent"
    assert "INCOMPLETE" not in format_loops_report(result)[0]


@needs_unprivileged
def test_unreadable_drafts_do_not_silently_pass_as_a_complete_listing(tmp_path, request):
    """The blessed rows are real, but the operator asked for drafts too and
    did not get them -- the listing is incomplete and says so."""
    skills = _write_store(tmp_path, {"ore-run": RECORDED}, drafts={})
    _lock(request, skills / "_drafts")

    result = read_loop_store(state_dir=tmp_path, include_drafts=True)

    assert result["status"] == "partial"
    assert [row["name"] for row in result["loops"]] == ["ore-run"]

    report = format_loops_report(result)
    assert "INCOMPLETE" in report[0]
    assert any("drafts" in line and str(skills / "_drafts") in line for line in report)


# --------------------------------------------------------------------------
# Schema conformance against the artifacts the real writer produced
# --------------------------------------------------------------------------


@pytest.mark.skipif(not ARCHIVE_SKILLS.is_dir(), reason="archived store not present in this tree")
def test_reads_the_real_archived_artifacts_without_a_single_unreadable():
    """Proof the schema this reader accepts is the one the writer emits --
    16 genuine recorded macros, read as-is with nothing hand-fixed."""
    result = read_loop_store(skills_dir=ARCHIVE_SKILLS, include_drafts=True)

    assert result["unreadable"] == []
    assert result["status"] == "ok"
    blessed = [row for row in result["loops"] if not row["draft"]]
    drafts = [row for row in result["loops"] if row["draft"]]
    assert len(blessed) == 16
    assert drafts, "the archived store carries mined drafts"
    assert all(row["source"] == "recorded" for row in blessed)
    assert all(row["steps"] > 0 for row in blessed)


@pytest.mark.skipif(not ARCHIVE_SKILLS.is_dir(), reason="archived store not present in this tree")
def test_real_mined_draft_reports_the_stat_it_actually_has():
    """`mined-1` really carries `cr_per_turn: None` alongside a genuine
    `cr_per_action: 54.375`. The archive's CLI checked only per-turn and
    fell through to a dash, discarding a real measured number."""
    result = read_loop_store(skills_dir=ARCHIVE_SKILLS, include_drafts=True)
    row = next(r for r in result["loops"] if r["name"].startswith("mined-1"))

    assert "profit_per_turn" not in row
    assert row["profit_per_action"] == 54.375
    assert row["support"] == 8

    line = next(ln for ln in format_loops_report(result) if "mined-1" in ln)
    assert "+54.4cr/act" in line
    assert "—" not in line


# --------------------------------------------------------------------------
# The WO's honesty bar: the verb is advertised once, and only once, it runs
# --------------------------------------------------------------------------


def test_loops_is_on_help_now_that_the_cli_wire_landed():
    """FLIPPED by WO-P2-G3 slice 2/2, as its own docstring instructed.

    Until the wire landed this asserted ``"loop" not in help_text`` --
    WO-P2-OPS-VERB-G-PREP's tripwire on the unwired state ("keep `loops` /
    `autoloop` off `./tw --help` until the matching slice Accepts"), so that
    ``./tw --help`` could never advertise a verb that did not run. It was
    never a claim the verb should not exist, and leaving it pinning a
    condition slice 2 makes false would have been a test certifying a lie in
    the other direction.

    ``autoloop`` (G4) is still unwired and stays off help -- asserted below,
    so the flip does not quietly wave through the verb behind this one.
    Behaviour lives in ``tests/test_cli_loops.py``; this stays the
    advertised-surface pin.
    """
    help_text = cli.build_parser().format_help()

    # Unchanged control leg: pins the help text is real, so neither the
    # presence nor the absence below can pass vacuously on an empty or
    # exploded render.
    assert "menumap" in help_text
    assert "loops" in help_text
    assert cli.build_parser().parse_args(["loops"]).func is cli.cmd_loops
    assert "autoloop" not in help_text
