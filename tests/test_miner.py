"""PWO-095 — candidate mining: fixture ledger → inert drafts."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tw2002_aiclient.ledger import REDACTED
from tw2002_aiclient.miner import mine_ledger, mine_patterns, propose_drafts


def _entry(
    *,
    input_text: str,
    settled_class: str,
    sector: int | None,
    d_credits: int,
    d_turns: int | None = -1,
) -> dict:
    reward: dict = {"d_credits": d_credits}
    if d_turns is not None:
        reward["d_turns"] = d_turns
    pre_state: dict = {}
    if sector is not None:
        pre_state["sector"] = sector
    return {
        "input": input_text,
        "settled_class": settled_class,
        "pre_state": pre_state,
        "reward": reward,
        "actor": "human",
    }


def _trade_round(sector: int, qty: str, offer: str, profit: int) -> list[dict]:
    """Two-step buy-shaped window ending on port_trade."""
    return [
        _entry(
            input_text=qty,
            settled_class="port_qty",
            sector=sector,
            d_credits=0,
            d_turns=0,
        ),
        _entry(
            input_text=offer,
            settled_class="port_trade",
            sector=sector,
            d_credits=profit,
            d_turns=-1,
        ),
    ]


@pytest.fixture
def synthetic_ledger() -> list[dict]:
    """Two identical trade shapes with different numerals → one <NUM> group."""
    rows: list[dict] = [
        _entry(
            input_text="p",
            settled_class="main_command",
            sector=42,
            d_credits=0,
            d_turns=0,
        ),
    ]
    rows.extend(_trade_round(42, "10", "146", 200))
    rows.append(
        _entry(
            input_text="p",
            settled_class="main_command",
            sector=42,
            d_credits=0,
            d_turns=0,
        )
    )
    rows.extend(_trade_round(42, "12", "158", 220))
    return rows


def test_mine_patterns_groups_numerics_and_ranks(synthetic_ledger: list[dict]) -> None:
    patterns = mine_patterns(synthetic_ledger, min_support=2)
    assert patterns, "expected at least one recurring profitable pattern"
    top = patterns[0]
    assert top["inputs"] == ["<NUM>", "<NUM>"]
    assert top["support"] >= 2
    assert top["start_anchor"] == 42
    assert top["cr_per_turn"] is not None and top["cr_per_turn"] > 0
    assert top["cr_per_action"] > 0


def test_redacted_window_skipped() -> None:
    entries = [
        _entry(input_text="p", settled_class="main_command", sector=1, d_credits=0),
        _entry(
            input_text=REDACTED,
            settled_class="login",
            sector=1,
            d_credits=0,
            d_turns=0,
        ),
        _entry(input_text="p", settled_class="main_command", sector=1, d_credits=500),
        _entry(input_text="p", settled_class="main_command", sector=1, d_credits=500),
    ]
    # Force a redacted 2-window that would otherwise look profitable if mined.
    patterns = mine_patterns(entries, min_support=1, min_window=2, max_window=2)
    for p in patterns:
        assert REDACTED not in p["inputs"]
        assert all(s.get("input") != REDACTED for s in p["sample_steps"])


def test_propose_drafts_inert_never_blessed(
    synthetic_ledger: list[dict], tmp_path: Path
) -> None:
    drafts_path = tmp_path / "_drafts"
    patterns = mine_patterns(synthetic_ledger, min_support=2)
    proposed = propose_drafts(patterns, top_k=3, drafts_dir_path=drafts_path)
    assert proposed, "expected profitable drafts"
    for item in proposed:
        path = Path(item["path"])
        assert path.parent == drafts_path
        assert "_drafts" in path.parts
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["source"] == "mined"
        assert doc["start_anchor"] == 42
        assert "mined_stats" in doc
        assert doc["mined_stats"]["support"] >= 2
        assert "blessed" not in doc
        assert path.parent.name == "_drafts"


def test_mine_ledger_end_to_end(tmp_path: Path, synthetic_ledger: list[dict]) -> None:
    ledger = tmp_path / "ledger.jsonl"
    drafts = tmp_path / "skills" / "_drafts"
    with ledger.open("w", encoding="utf-8") as fh:
        for row in synthetic_ledger:
            fh.write(json.dumps(row) + "\n")
    result = mine_ledger(
        ledger_path=ledger,
        drafts_dir_path=drafts,
        min_support=2,
        top_k=2,
    )
    assert result["patterns"]
    assert result["drafts"]
    assert list(drafts.glob("*.json"))


def test_cli_dry_run(tmp_path: Path, synthetic_ledger: list[dict]) -> None:
    ledger = tmp_path / "ledger.jsonl"
    drafts = tmp_path / "_drafts"
    drafts.mkdir()
    with ledger.open("w", encoding="utf-8") as fh:
        for row in synthetic_ledger:
            fh.write(json.dumps(row) + "\n")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "tw2002_aiclient.miner",
            "--ledger",
            str(ledger),
            "--drafts",
            str(drafts),
            "--min-support",
            "2",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "drafts=" in proc.stdout
    assert "draft mined-" in proc.stdout
    assert list(drafts.glob("*.json"))


def test_miner_module_has_no_live_connection_imports() -> None:
    """Accept: no live-connection code path in the miner module itself."""
    src = Path(__file__).resolve().parents[1] / "tw2002_aiclient" / "miner.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    banned = {
        "tw2002_aiclient.session.protocol",
        "tw2002_aiclient.session.connection",
        "tw2002_aiclient.session.telnet",
        "socket",
    }
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert banned.isdisjoint(imported), f"banned imports present: {imported & banned}"
    # Also refuse relative session send helpers by name
    text = src.read_text(encoding="utf-8")
    for needle in ("control_lock", "send_raw", "FakeClient", "telnetlib"):
        assert needle not in text
