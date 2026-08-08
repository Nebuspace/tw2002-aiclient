"""Pins for mined-skills promote CLI (WO-WIRE-MINED-SKILLS-PROMOTE-CLI)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tw2002_aiclient.loops.loader import load_loop
from tw2002_aiclient.loops.recorder import LoopWriteError, promote_draft
from tw2002_aiclient.loops.store import drafts_dir, loops_dir

DRAFT = {
    "name": "mined-0-demo",
    "created_ts": "2026-08-08T00:00:00Z",
    "source": "mined",
    "start_anchor": 42,
    "steps": [
        {"input": "P", "wait_prompt": None, "expected_post_class": "port_trade"},
        {"input": "", "wait_prompt": None, "expected_post_class": "main_command"},
    ],
}


def _write_draft(tmp_path: Path, doc: dict) -> Path:
    ddir = drafts_dir(tmp_path)
    ddir.mkdir(parents=True, exist_ok=True)
    path = ddir / f"{doc['name']}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_promote_draft_moves_mined_draft_into_blessed_store(tmp_path: Path) -> None:
    src = _write_draft(tmp_path, DRAFT)
    assert src.is_file()
    dest = promote_draft(DRAFT["name"], state_dir=tmp_path)
    assert dest == loops_dir(tmp_path) / f"{DRAFT['name']}.json"
    assert dest.is_file()
    assert not src.exists()
    loop = load_loop(DRAFT["name"], state_dir=tmp_path, include_drafts=False)
    assert loop.draft is False
    assert loop.source == "mined"
    assert loop.start_anchor == 42


def test_promote_draft_is_the_product_call_from_skill_cli() -> None:
    from tw2002_aiclient import skill_cli

    assert skill_cli.cmd_skill_approve.__doc__
    import ast
    from pathlib import Path as P

    src = P(skill_cli.__file__).read_text()
    tree = ast.parse(src)
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and (
            (isinstance(n.func, ast.Name) and n.func.id == "promote_draft")
            or (isinstance(n.func, ast.Attribute) and n.func.attr == "promote_draft")
        )
    ]
    assert calls, "tw skill approve must call promote_draft"


def test_promote_refuses_missing_and_already_blessed(tmp_path: Path) -> None:
    with pytest.raises(LoopWriteError, match="no draft"):
        promote_draft("never-written", state_dir=tmp_path)
    _write_draft(tmp_path, DRAFT)
    promote_draft(DRAFT["name"], state_dir=tmp_path)
    # Re-seed a draft with the same name while blessed exists → refuse.
    _write_draft(tmp_path, DRAFT)
    with pytest.raises(LoopWriteError, match="already in the blessed"):
        promote_draft(DRAFT["name"], state_dir=tmp_path)


def test_session_cli_registers_skill_approve() -> None:
    import ast
    from pathlib import Path as P

    src = P("tw2002_aiclient/session/cli.py").read_text()
    assert "add_skill_parser" in src
    assert ast.parse(src) is not None
